"""
dashboard.py — Smart Grid Security Monitoring Dashboard
========================================================
Kelompok 3 - Keamanan Data

ARSITEKTUR:
  SSE Consumer berjalan di background thread terpisah.
  Data masuk ke thread-safe Queue, dibaca saat Streamlit rerun.
  Tidak ada while True di script utama.

Mode:
  LIVE_MODE = False  → pakai data simulasi (tanpa server)
  LIVE_MODE = True   → connect ke SSE server (production)

Jalankan:
  streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import json
import time
import sys
import os
import random
import threading
import queue
from datetime import datetime

# ─────────────────────────────────────────────
# KONFIGURASI
# ─────────────────────────────────────────────

LIVE_MODE        = True
SSE_URL          = "http://localhost:8001/prediction/stream"
REFRESH_INTERVAL = 1.5
MAX_HISTORY      = 100

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "autogenerate"))
from encrypt import build_packet, unpack_packet, setup_keys

LABEL_MAP = {0: "Normal", 1: "Attack", 2: "Fault"}
LABEL_COLOR = {"Normal": "#2E7D32", "Attack": "#C62828", "Fault": "#E65100"}
LABEL_BG    = {"Normal": "#E8F5E9", "Attack": "#FFEBEE", "Fault": "#FFF3E0"}
LABEL_ICON  = {"Normal": "✅",      "Attack": "🚨",      "Fault": "⚠️"}
DEVICES     = [f"SGD-{str(i).zfill(4)}" for i in range(1, 11)]


# ─────────────────────────────────────────────
# SIMULASI DATA
# ─────────────────────────────────────────────

def generate_dummy_raw(label: int) -> dict:
    if label == 0:
        voltage   = round(random.uniform(210, 230), 4)
        current   = round(random.uniform(2.0, 8.0), 4)
        temp      = round(random.uniform(20, 55), 3)
        latency   = round(random.uniform(5, 80), 2)
        pkt_loss  = round(random.uniform(0, 3), 2)
        auth_fail = random.randint(0, 1)
    elif label == 1:
        voltage   = round(random.uniform(210, 230), 4)
        current   = round(random.uniform(2.0, 8.0), 4)
        temp      = round(random.uniform(20, 55), 3)
        latency   = round(random.uniform(100, 500), 2)
        pkt_loss  = round(random.uniform(8, 25), 2)
        auth_fail = random.randint(3, 8)
    else:
        voltage   = round(random.choice([
            random.uniform(150, 195), random.uniform(245, 300)
        ]), 4)
        current   = round(random.uniform(2.0, 8.0), 4)
        temp      = round(random.uniform(66, 90), 3)
        latency   = round(random.uniform(5, 80), 2)
        pkt_loss  = round(random.uniform(0, 3), 2)
        auth_fail = random.randint(0, 1)

    power      = round(voltage * current * random.uniform(0.85, 0.98), 4)
    frequency  = round(random.uniform(49.5, 50.5), 4)
    throughput = round(random.uniform(2, 95), 2)

    return {
        "timestamp":           datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "device_id":           random.choice(DEVICES),
        "voltage":             voltage,
        "current":             current,
        "power":               power,
        "frequency":           frequency,
        "temperature":         temp,
        "latency":             latency,
        "packet_loss":         pkt_loss,
        "throughput":          throughput,
        "duplicate_packet":    random.randint(0, 5),
        "checksum_valid":      random.randint(0, 1),
        "authentication_fail": auth_fail,
        "voting_prediction":   label,
        "label_name":          LABEL_MAP[label],
    }


def get_next_simulated_packet() -> dict:
    label = random.choices([0, 1, 2], weights=[70, 20, 10])[0]
    raw   = generate_dummy_raw(label)
    return unpack_packet(build_packet(raw))


# ─────────────────────────────────────────────
# BACKGROUND WORKERS
# ─────────────────────────────────────────────

def sse_worker(pq: queue.Queue, stop: threading.Event):
    import requests
    last_seq   = -1
    retry_wait = 2

    while not stop.is_set():
        response = None
        try:
            print(f"[SSE] Connecting to {SSE_URL}")
            response = requests.get(
                SSE_URL,
                stream=True,
                timeout=(10, None),
                headers={"Accept": "text/event-stream", "Cache-Control": "no-cache"},
            )
            response.raise_for_status()
            print("[SSE] Connected.")
            retry_wait = 2

            for raw_line in response.iter_lines():
                if stop.is_set():
                    break
                if not raw_line:
                    continue
                line_str = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                if line_str.startswith(":") or not line_str.startswith("data: "):
                    continue
                try:
                    enc = json.loads(line_str[6:])
                except json.JSONDecodeError:
                    continue

                seq = enc.get("_seq", -1)
                if seq != -1 and seq <= last_seq:
                    continue

                try:
                    payload = unpack_packet({
                        "encrypted_payload": enc["encrypted_payload"],
                        "encrypted_aes_key": enc["encrypted_aes_key"],
                        "nonce":             enc["nonce"],
                    })
                    payload["_seq"]       = seq
                    payload["_server_ts"] = enc.get("_server_ts")
                except Exception as e:
                    print(f"[SSE] Decrypt error seq={seq}: {e}")
                    continue

                last_seq = seq
                print(f"[SSE] Packet OK seq={seq} label={payload.get('label_name')}")
                _safe_put(pq, payload)

        except Exception as e:
            print(f"[SSE] Error: {e}")
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            print(f"[SSE] Disconnected. Retry in {retry_wait}s...")

        if not stop.is_set():
            stop.wait(timeout=retry_wait)
            retry_wait = min(retry_wait * 2, 30)


def sim_worker(pq: queue.Queue, stop: threading.Event, interval: float):
    while not stop.is_set():
        try:
            _safe_put(pq, get_next_simulated_packet())
        except Exception as e:
            print(f"[SIM] Error: {e}")
        stop.wait(timeout=interval)


def _safe_put(pq: queue.Queue, item):
    """Masukkan item ke queue; buang item terlama jika penuh."""
    try:
        pq.put_nowait(item)
    except queue.Full:
        try:
            pq.get_nowait()
        except queue.Empty:
            pass
        try:
            pq.put_nowait(item)
        except queue.Full:
            pass


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────

def init_state():
    """Inisialisasi state — tiap key hanya di-set sekali per session."""
    defaults = {
        "history":       [],
        "running":       False,
        "total":         0,
        "counts":        {"Normal": 0, "Attack": 0, "Fault": 0},
        "keys_ready":    False,
        "keys_error":    "",
        "worker_thread": None,
        "stop_event":    None,
        "packet_queue":  None,
        # FIX: simpan speed di session_state agar konsisten antar rerun
        "speed":         REFRESH_INTERVAL,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if not st.session_state.keys_ready:
        try:
            setup_keys()
            st.session_state.keys_ready = True
        except Exception as e:
            st.session_state.keys_ready = False
            st.session_state.keys_error = str(e)


def start_worker():
    """
    Start background worker thread jika belum jalan.
    Idempotent — aman dipanggil berkali-kali.
    Menggunakan speed dari session_state, bukan parameter,
    agar konsisten antar rerun.
    """
    existing = st.session_state.get("worker_thread")
    if existing is not None and existing.is_alive():
        return  # Sudah jalan

    interval   = st.session_state.get("speed", REFRESH_INTERVAL)
    stop_event = threading.Event()
    pkt_queue  = queue.Queue(maxsize=200)

    if LIVE_MODE:
        fn = lambda: sse_worker(pkt_queue, stop_event)
    else:
        fn = lambda: sim_worker(pkt_queue, stop_event, interval)

    thread = threading.Thread(target=fn, daemon=True, name="SmartGridWorker")
    thread.start()

    st.session_state.worker_thread = thread
    st.session_state.stop_event    = stop_event
    st.session_state.packet_queue  = pkt_queue
    print("[MAIN] Worker thread started.")


def stop_worker():
    ev = st.session_state.get("stop_event")
    if ev is not None:
        ev.set()
        print("[MAIN] Stop signal sent.")
    st.session_state.worker_thread = None
    st.session_state.stop_event    = None
    st.session_state.packet_queue  = None


def drain_queue() -> int:
    """
    Baca semua packet dari queue ke history.
    Return jumlah packet baru.
    """
    pq = st.session_state.get("packet_queue")
    if pq is None:
        return 0

    new_count = 0
    while True:
        try:
            payload = pq.get_nowait()
        except queue.Empty:
            break

        label_name = payload.get("label_name")
        if label_name not in LABEL_MAP.values():
            print(f"[DRAIN] Invalid label '{label_name}', skip.")
            continue

        st.session_state.history.append(payload)
        if len(st.session_state.history) > MAX_HISTORY:
            st.session_state.history.pop(0)

        st.session_state.total += 1
        st.session_state.counts[label_name] = (
            st.session_state.counts.get(label_name, 0) + 1
        )
        new_count += 1

    return new_count


# ─────────────────────────────────────────────
# UI COMPONENTS
# ─────────────────────────────────────────────

def render_header():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');
        html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
        .dashboard-header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            border-radius: 16px; padding: 28px 36px; margin-bottom: 24px;
            display: flex; align-items: center; justify-content: space-between;
        }
        .header-title {
            font-family: 'DM Serif Display', serif; font-size: 26px;
            color: #ffffff; margin: 0; letter-spacing: -0.3px;
        }
        .header-subtitle {
            font-family: 'DM Mono', monospace; font-size: 11px;
            color: #7eceff; margin-top: 4px; letter-spacing: 1.5px; text-transform: uppercase;
        }
        .header-badge {
            font-family: 'DM Mono', monospace; font-size: 11px;
            background: rgba(126,206,255,0.15); color: #7eceff;
            border: 1px solid rgba(126,206,255,0.3); border-radius: 20px; padding: 6px 14px;
        }
        .metric-card {
            background: #ffffff; border: 1px solid #e8edf2; border-radius: 12px;
            padding: 20px 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }
        .metric-label {
            font-size: 11px; color: #8a9bb0; font-weight: 600;
            letter-spacing: 1px; text-transform: uppercase; margin-bottom: 6px;
        }
        .metric-value { font-family: 'DM Serif Display', serif; font-size: 32px; color: #1a1a2e; line-height: 1; }
        .metric-sub   { font-size: 12px; color: #8a9bb0; margin-top: 4px; }
        .alert-card   { border-radius: 10px; padding: 14px 18px; margin-bottom: 8px; border-left: 4px solid; font-size: 13px; }
        .section-title {
            font-family: 'DM Serif Display', serif; font-size: 18px; color: #1a1a2e;
            margin: 24px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid #f0f4f8;
        }
        div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; border: 1px solid #e8edf2; }
    </style>
    <div class="dashboard-header">
        <div>
            <div class="header-title">Smart Grid Security Monitor</div>
            <div class="header-subtitle">AES-GCM · RSA-OAEP · Hybrid Encryption · Real-time Detection</div>
        </div>
        <div class="header-badge">Kelompok 3 — Keamanan Data</div>
    </div>
    """, unsafe_allow_html=True)


def render_status_bar(running: bool, mode: str, total: int):
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        dot = "🟢" if running else "⚫"
        st.markdown(
            f"**{dot} Status:** {'LIVE' if running else 'STOPPED'} &nbsp;|&nbsp; "
            f"**Mode:** {'🔴 LIVE SERVER' if mode == 'live' else '🔵 SIMULASI'}"
        )
    with c2:
        st.markdown(f"**Total packet diproses:** `{total}`")
    with c3:
        st.markdown(f"**{'🔒 Enkripsi aktif' if total > 0 else '🔓 Belum ada data'}**")


def render_metric_row(counts: dict, total: int):
    cols = st.columns(4)
    metrics = [
        ("Total Packet", str(total),            "sejak sistem start",                                    "#1a1a2e"),
        ("Normal",       str(counts["Normal"]), f"{counts['Normal'] / max(total,1)*100:.1f}% dari total", LABEL_COLOR["Normal"]),
        ("Attack 🚨",    str(counts["Attack"]), f"{counts['Attack'] / max(total,1)*100:.1f}% dari total", LABEL_COLOR["Attack"]),
        ("Fault ⚠️",     str(counts["Fault"]),  f"{counts['Fault']  / max(total,1)*100:.1f}% dari total", LABEL_COLOR["Fault"]),
    ]
    for col, (label, value, sub, color) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value" style="color:{color}">{value}</div>
                <div class="metric-sub">{sub}</div>
            </div>""", unsafe_allow_html=True)


def render_charts(history: list):
    if len(history) < 2:
        st.info("Menunggu data masuk...")
        return

    df = pd.DataFrame(history)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    col_left, col_right = st.columns([3, 2])
    with col_left:
        st.markdown('<div class="section-title">📈 Grafik Sensor Realtime</div>', unsafe_allow_html=True)
        t1, t2, t3, t4 = st.tabs(["Tegangan", "Arus", "Suhu", "Latency"])
        with t1: st.line_chart(df[["timestamp","voltage"]].set_index("timestamp"),    color="#0f3460", height=200)
        with t2: st.line_chart(df[["timestamp","current"]].set_index("timestamp"),    color="#e94560", height=200)
        with t3: st.line_chart(df[["timestamp","temperature"]].set_index("timestamp"),color="#f5a623", height=200)
        with t4: st.line_chart(df[["timestamp","latency"]].set_index("timestamp"),    color="#7b2d8b", height=200)

    with col_right:
        st.markdown('<div class="section-title">🥧 Distribusi Status</div>', unsafe_allow_html=True)
        counts_now = df["label_name"].value_counts()
        import plotly.express as px
        fig = px.pie(
            pd.DataFrame({"Status": counts_now.index, "Jumlah": counts_now.values}),
            names="Status", values="Jumlah", color="Status",
            color_discrete_map=LABEL_COLOR, hole=0.45,
        )
        fig.update_layout(
            margin=dict(t=10, b=10, l=10, r=10), height=260,
            font=dict(family="DM Sans"),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="section-title">🔔 Alert Terbaru</div>', unsafe_allow_html=True)
        alerts = [r for r in reversed(history) if r["label_name"] != "Normal"][:5]
        if alerts:
            for a in alerts:
                st.markdown(f"""
                <div class="alert-card" style="background:{LABEL_BG[a['label_name']]}; border-color:{LABEL_COLOR[a['label_name']]};">
                    {LABEL_ICON[a['label_name']]} <strong>{a['label_name']}</strong> &nbsp;·&nbsp;
                    <span style="font-family:monospace">{a['device_id']}</span><br>
                    <span style="color:#666;font-size:11px">
                        {a['timestamp']} &nbsp;·&nbsp; V={a['voltage']:.1f}V &nbsp;·&nbsp; T={a['temperature']:.1f}°C
                    </span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown("_Belum ada alert — semua normal_")


def render_table(history: list):
    if not history:
        return
    st.markdown('<div class="section-title">📋 Tabel Data Realtime</div>', unsafe_allow_html=True)
    df = pd.DataFrame(history[-30:]).iloc[::-1].reset_index(drop=True)
    cols = ["timestamp","device_id","label_name","voltage","current",
            "temperature","latency","packet_loss","authentication_fail"]
    cols = [c for c in cols if c in df.columns]
    rename = {
        "timestamp":"Timestamp","device_id":"Device","label_name":"Status",
        "voltage":"Voltage (V)","current":"Current (A)","temperature":"Temp (°C)",
        "latency":"Latency (ms)","packet_loss":"Packet Loss (%)","authentication_fail":"Auth Fail",
    }
    st.dataframe(df[cols].rename(columns={c:rename[c] for c in cols if c in rename}),
                 use_container_width=True, height=300)


def render_encryption_info(history: list):
    if not history:
        return
    last = history[-1]
    st.markdown('<div class="section-title">🔐 Info Enkripsi Packet Terakhir</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Metode Enkripsi**")
        st.markdown("- Payload → **AES-256-GCM**\n- AES Key → **RSA-2048-OAEP**\n- Hash → **SHA-256**\n- Integrity tag: **16 byte GCM tag**")
    with c2:
        st.markdown("**Payload Terdekripsi**")
        st.json({
            "device_id":         last.get("device_id"),
            "voting_prediction": last.get("voting_prediction"),
            "label_name":        last.get("label_name"),
            "timestamp":         last.get("timestamp"),
        })
    with c3:
        st.markdown("**Status Keamanan**")
        st.success("✅ Integritas terverifikasi")
        st.info("🔒 AES key dienkripsi RSA")
        st.info("🔀 Nonce unik tiap packet")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Smart Grid Monitor",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    init_state()
    render_header()

    # ── Sidebar ──────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Kontrol")
        mode = "live" if LIVE_MODE else "simulasi"
        st.markdown(f"**Mode:** `{mode.upper()}`")

        if not LIVE_MODE:
            st.info("Mode simulasi aktif.\nGanti `LIVE_MODE = True` untuk connect ke server.")

        st.markdown("---")

        # FIX: slider update session_state["speed"] — tidak pakai nilai return langsung
        # sebagai parameter ke start_worker(), karena worker sudah jalan saat slider digeser
        new_speed = st.slider(
            "Interval refresh (detik)",
            0.5, 5.0,
            st.session_state.speed,   # nilai awal dari session_state
            0.5,
        )
        if new_speed != st.session_state.speed:
            st.session_state.speed = new_speed  # simpan ke state, berlaku di rerun berikutnya

        st.markdown("---")

        col_start, col_stop = st.columns(2)
        with col_start:
            if st.button("▶ Start", use_container_width=True, type="primary"):
                if not st.session_state.running:
                    st.session_state.running = True
                    start_worker()   # ambil speed dari session_state["speed"]
                    # TIDAK st.rerun() di sini — biarkan script selesai render dulu
        with col_stop:
            if st.button("⏹ Stop", use_container_width=True):
                if st.session_state.running:
                    st.session_state.running = False
                    stop_worker()

        if st.button("🗑 Reset", use_container_width=True):
            stop_worker()
            st.session_state.history = []
            st.session_state.total   = 0
            st.session_state.counts  = {"Normal": 0, "Attack": 0, "Fault": 0}
            st.session_state.running = False

        st.markdown("---")
        st.markdown("**RSA Keys:**")
        if st.session_state.get("keys_ready"):
            st.success("✅ Siap")
        else:
            st.error(f"❌ {st.session_state.get('keys_error', 'Belum ada key')}")

        if st.checkbox("Debug info"):
            thread = st.session_state.get("worker_thread")
            q      = st.session_state.get("packet_queue")
            st.markdown(f"""
            - Thread alive: `{thread.is_alive() if thread else False}`
            - Queue size: `{q.qsize() if q else 0}`
            - History len: `{len(st.session_state.history)}`
            - Speed: `{st.session_state.speed}s`
            """)

    # ── Guard: RSA keys ──────────────────────────────────────────────────
    if not st.session_state.get("keys_ready"):
        st.error(
            f"RSA key belum tersedia: {st.session_state.get('keys_error', '')}. "
            "Jalankan `python encrypt.py` di folder `autogenerate/` terlebih dahulu."
        )
        return

    # ── FIX UTAMA: Drain queue → render UI → schedule rerun ──────────────
    #
    # URUTAN YANG BENAR:
    #   1. Pastikan worker jalan
    #   2. Drain semua packet dari queue ke session_state
    #   3. RENDER UI dengan data terbaru  ← ini yang hilang sebelumnya!
    #   4. Setelah render selesai, schedule rerun via st.rerun()
    #      menggunakan st.fragment atau time.sleep kecil
    #
    # st.rerun() menghentikan eksekusi SAAT ITU JUGA.
    # Jika dipanggil sebelum render_*, semua fungsi render tidak pernah jalan.
    # ─────────────────────────────────────────────────────────────────────

    if st.session_state.running:
        # Pastikan worker masih hidup (guard setelah hot-reload Streamlit)
        start_worker()
        # Drain semua packet baru dari queue ke session_state SEKARANG
        drain_queue()
        # Setelah drain, LANGSUNG render UI di bawah (tidak st.rerun() dulu)
        # Auto-refresh dijadwalkan SETELAH semua render selesai (paling bawah)

    # ── Render UI dengan data terkini dari session_state ─────────────────
    history = st.session_state.history
    total   = st.session_state.total
    counts  = st.session_state.counts

    render_status_bar(st.session_state.running, mode, total)
    render_metric_row(counts, total)
    render_charts(history)
    render_table(history)
    render_encryption_info(history)

    # ── Auto-refresh: SETELAH semua render selesai ────────────────────────
    # Ini adalah satu-satunya tempat st.rerun() boleh dipanggil.
    # time.sleep() di sini aman karena semua render sudah selesai —
    # user melihat UI yang terupdate, lalu setelah sleep script rerun lagi.
    if st.session_state.running:
        time.sleep(st.session_state.speed)
        st.rerun()


if __name__ == "__main__":
    main()