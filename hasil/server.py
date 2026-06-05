"""
server.py — KDA Kelompok 3 Secure Prediction Server
=====================================================
Menerima encrypted packet dari ML.py via POST,
meneruskan ke dashboard.py via SSE.

Jalankan:
  uvicorn server:app --host 0.0.0.0 --port 8001
  (jangan pakai --reload di production)
"""

import asyncio
import itertools
import json
import logging
from collections import deque
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("kda-server")

# ─────────────────────────────────────────────
# STATE GLOBAL
# ─────────────────────────────────────────────

# Buffer packet terenkripsi — maxlen mencegah unbounded memory growth
PACKET_BUFFER: deque = deque(maxlen=500)

# FIX Bug #3: itertools.count() adalah thread-safe counter
# Tidak perlu lock — next() pada count() adalah atomic di CPython
_seq_counter = itertools.count(start=1)

# FIX Bug #2: asyncio.Condition menggantikan asyncio.Event tunggal
# notify_all() memastikan SEMUA SSE client wake up saat ada packet baru,
# bukan hanya satu client yang kebetulan pertama acquire
_new_packet_condition: asyncio.Condition | None = None

# FIX Bug #1: Tracking berbasis seq, bukan index list
# Menyimpan seq tertinggi yang sudah ada di buffer saat ini
_highest_seq_in_buffer: int = 0

# Flag shutdown — di-set saat server menerima sinyal berhenti
# SSE generator mengecek flag ini agar bisa exit dengan bersih
_server_shutting_down: bool = False

# ─────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────

app = FastAPI(
    title="KDA Kelompok 3 — Secure Prediction Server",
    description=(
        "Backend server untuk menerima encrypted prediction packet dari ML.py "
        "dan meneruskannya secara realtime ke dashboard.py melalui SSE."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# LIFECYCLE EVENT
# ─────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    """
    Inisialisasi asyncio primitives di sini, bukan di global scope.
    asyncio.Condition() harus dibuat di dalam event loop yang aktif.
    Membuat di global scope (saat import) bisa pakai event loop yang salah.
    """
    global _new_packet_condition, _server_shutting_down
    _new_packet_condition  = asyncio.Condition()
    _server_shutting_down  = False
    logger.info("Server started. Condition variable initialized.")


@app.on_event("shutdown")
async def on_shutdown():
    """
    Saat server shutdown (Ctrl+C / SIGTERM):
    Set flag shutdown lalu notify_all() agar semua SSE generator
    yang sedang Condition.wait() langsung wake up dan exit bersih.
    Tanpa ini → warning: Task was destroyed but it is pending!
    """
    global _server_shutting_down
    _server_shutting_down = True
    logger.info("Server shutting down — notifying all SSE clients.")
    if _new_packet_condition is not None:
        async with _new_packet_condition:
            _new_packet_condition.notify_all()


# ─────────────────────────────────────────────
# VALIDASI
# ─────────────────────────────────────────────

REQUIRED_FIELDS = {"encrypted_payload", "encrypted_aes_key", "nonce"}


class SecurePacket(BaseModel):
    encrypted_payload: str
    encrypted_aes_key: str
    nonce: str


def validate_packet(data: dict) -> None:
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Field wajib tidak ditemukan: {sorted(missing)}",
        )
    empty = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if empty:
        raise HTTPException(
            status_code=400,
            detail=f"Field berikut tidak boleh kosong: {sorted(empty)}",
        )


# ─────────────────────────────────────────────
# ENDPOINT: RECEIVE
# ─────────────────────────────────────────────

@app.post("/prediction/receive", status_code=200)
async def receive_prediction(packet: SecurePacket) -> JSONResponse:
    global _highest_seq_in_buffer

    data = packet.model_dump()
    validate_packet(data)

    # FIX Bug #3: next() pada itertools.count() adalah atomic di CPython
    seq = next(_seq_counter)

    enriched = {
        **data,
        "_server_ts": datetime.utcnow().isoformat() + "Z",
        "_seq": seq,
    }

    PACKET_BUFFER.append(enriched)
    _highest_seq_in_buffer = seq

    logger.info(
        "Packet diterima seq=%s | buffer=%s",
        enriched["_seq"],
        len(PACKET_BUFFER),
    )

    # FIX Bug #2: notify_all() membangunkan SEMUA SSE client sekaligus
    if _new_packet_condition is not None:
        async with _new_packet_condition:
            _new_packet_condition.notify_all()

    return JSONResponse(
        content={
            "status": "ok",
            "message": "Packet diterima dan disimpan ke buffer.",
            "seq": seq,
            "buffer_size": len(PACKET_BUFFER),
        }
    )


# ─────────────────────────────────────────────
# SSE GENERATOR
# ─────────────────────────────────────────────

async def sse_packet_generator(request: Request) -> AsyncGenerator[str, None]:
    """
    Generator SSE per-client.

    FIX Bug #1: tracking berbasis _seq (sequence number), bukan index list.
    Dengan deque(maxlen=500), saat buffer penuh packet lama dibuang dari kiri.
    Index list akan bergeser, tapi _seq adalah nilai absolut yang tidak berubah.

    Cara kerja:
      - last_sent_seq = seq tertinggi yang sudah dikirim ke client ini
      - Setiap iterasi, ambil semua packet dari buffer yang seq-nya > last_sent_seq
      - Kirim, update last_sent_seq
    """
    # Kirim heartbeat awal agar koneksi SSE langsung confirmed di sisi client
    yield ": heartbeat\n\n"

    # Client baru hanya terima packet yang datang SETELAH connect
    # (bukan replay seluruh buffer historis)
    last_sent_seq: int = _highest_seq_in_buffer

    logger.info("SSE client terhubung. Mulai dari seq > %s", last_sent_seq)

    while True:
        # Cek disconnect sebelum melakukan apapun
        if await request.is_disconnected():
            logger.info("SSE client disconnect (seq=%s).", last_sent_seq)
            break

        # FIX Bug #1: filter berdasarkan _seq, bukan index
        # list(PACKET_BUFFER) adalah snapshot atomik dari deque
        current_snapshot = list(PACKET_BUFFER)
        new_packets = [p for p in current_snapshot if p.get("_seq", 0) > last_sent_seq]

        if new_packets:
            # Urutkan berdasarkan seq untuk menjaga urutan
            new_packets.sort(key=lambda p: p.get("_seq", 0))
            for pkt in new_packets:
                payload = json.dumps(pkt, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                logger.debug("SSE kirim packet seq=%s", pkt.get("_seq"))
            last_sent_seq = new_packets[-1].get("_seq", last_sent_seq)
        else:
            # Tidak ada packet baru → tunggu notifikasi dari receive_prediction.
            # CancelledError ditangkap eksplisit agar task exit bersih saat
            # server shutdown — menghilangkan warning:
            # "Task was destroyed but it is pending!"
            try:
                async with _new_packet_condition:
                    try:
                        await asyncio.wait_for(
                            _new_packet_condition.wait(),
                            timeout=15.0,
                        )
                    except asyncio.TimeoutError:
                        # Timeout normal → kirim ping, lanjut loop
                        yield ": ping\n\n"
                        continue

                # Wake up karena notify_all() — cek apakah karena shutdown
                if _server_shutting_down:
                    logger.info("SSE generator: shutdown detected, exiting cleanly.")
                    break

            except asyncio.CancelledError:
                # Server shutdown membatalkan task ini — normal, exit bersih
                logger.info("SSE generator cancelled (server shutdown).")
                break
            except Exception as e:
                logger.error("SSE generator error: %s", e)
                break


# ─────────────────────────────────────────────
# ENDPOINT: STREAM
# ─────────────────────────────────────────────

@app.get("/prediction/stream")
async def prediction_stream(request: Request) -> StreamingResponse:
    logger.info("SSE subscriber baru terhubung dari %s", request.client)
    return StreamingResponse(
        sse_packet_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


# ─────────────────────────────────────────────
# ENDPOINT: UTILITY
# ─────────────────────────────────────────────

@app.get("/health")
async def health_check() -> JSONResponse:
    return JSONResponse({
        "status":      "ok",
        "buffer_size": len(PACKET_BUFFER),
        "highest_seq": _highest_seq_in_buffer,
    })


@app.get("/buffer/peek")
async def peek_buffer(n: int = 5) -> JSONResponse:
    """Lihat n packet terakhir di buffer (tanpa mendekripsi). Untuk testing."""
    packets = list(PACKET_BUFFER)[-n:]
    return JSONResponse({"count": len(packets), "packets": packets})


@app.delete("/buffer/clear")
async def clear_buffer() -> JSONResponse:
    """Kosongkan buffer. Untuk testing/reset."""
    global _highest_seq_in_buffer
    PACKET_BUFFER.clear()
    _highest_seq_in_buffer = 0
    logger.warning("Buffer dikosongkan secara manual.")
    return JSONResponse({"status": "ok", "message": "Buffer dikosongkan."})


# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    # FIX Bug #5: reload=False di production
    # Gunakan: uvicorn server:app --host 0.0.0.0 --port 8001
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8001,
        reload=False,   # True hanya untuk development
        log_level="info",
    )