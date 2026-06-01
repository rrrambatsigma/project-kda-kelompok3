"""
Smart Grid IoT Security — Real-Time Simulator + SSE Stream  [v2 MULTI-METHOD + NGROK]
======================================================================================
Upgrade dari v1:
  1. Markov Chain     — transisi label NORMAL→ATTACK→FAULT yang realistis
  2. Temporal / AR(1) — nilai sensor bergantung pada state sebelumnya per device
  3. Pola harian      — beban listrik naik-turun sesuai jam (opsional bonus)
  4. 10 row / detik   — burst generate, di-stream via SSE
  5. NGROK INTEGRATION — expose ke internet publik secara otomatis

Label: 0=NORMAL, 1=ATTACK, 2=FAULT

Install dependencies:
  pip install flask flask-cors numpy pyngrok

Jalankan:
  python auto_generate_v2_ngrok.py
  python auto_generate_v2_ngrok.py --port 8080 --rate 10
  python auto_generate_v2_ngrok.py --port 8080 --rate 10 --ngrok-token YOUR_TOKEN
  python auto_generate_v2_ngrok.py --no-ngrok   (matikan ngrok, lokal saja)
"""

import argparse
import csv
import json
import os
import queue
import random
import sys
import threading
import time
from collections import deque
from datetime import datetime

import numpy as np
from flask import Flask, Response, jsonify, request
from flask_cors import CORS

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

DEVICE_IDS = [f"SGD-{i:04d}" for i in range(1, 51)]
CSV_FILE   = "smart_grid_data_v2.csv"
CSV_HEADER = [
    "timestamp", "device_id",
    "voltage", "current", "power", "frequency", "temperature",
    "latency", "packet_loss", "throughput",
    "duplicate_packet", "checksum_valid", "authentication_fail",
    "label", "label_name",
]

# Field yang dikirim ke API / SSE — label TIDAK disertakan
PUBLIC_FIELDS = [
    "timestamp", "device_id",
    "voltage", "current", "power", "frequency", "temperature",
    "latency", "packet_loss", "throughput",
    "duplicate_packet", "checksum_valid", "authentication_fail",
]
LABEL_MAP  = {0: "NORMAL", 1: "ATTACK", 2: "FAULT"}

HISTORY    = deque(maxlen=1000)
TOTAL_ROWS = 0
LOCK       = threading.Lock()
SSE_QUEUES: list[queue.Queue] = []

# Simpan public URL ngrok agar bisa ditampilkan di endpoint /status
NGROK_PUBLIC_URL = None

np.random.seed()

# ══════════════════════════════════════════════════════════════════════════════
# [1] MARKOV CHAIN — Transition Matrix
# ══════════════════════════════════════════════════════════════════════════════
#
# State: 0=NORMAL, 1=ATTACK, 2=FAULT
# Baris = state saat ini, Kolom = state berikutnya
#
#          → NORMAL  ATTACK  FAULT
# NORMAL  [  0.90,   0.07,   0.03 ]   # 90% tetap normal, 7% mulai attack
# ATTACK  [  0.15,   0.75,   0.10 ]   # attack cenderung berlanjut
# FAULT   [  0.20,   0.05,   0.75 ]   # fault juga cenderung berlanjut
#
MARKOV_MATRIX = np.array([
    [0.90, 0.07, 0.03],   # dari NORMAL
    [0.15, 0.75, 0.10],   # dari ATTACK
    [0.20, 0.05, 0.75],   # dari FAULT
])

# State label per device — masing-masing device punya Markov state sendiri
DEVICE_LABEL_STATE: dict[str, int] = {
    d: int(np.random.choice([0, 1, 2], p=[0.70, 0.20, 0.10]))
    for d in DEVICE_IDS
}

def markov_next_label(device_id: str) -> int:
    """Ambil label berikutnya berdasarkan Markov Chain per device."""
    current = DEVICE_LABEL_STATE[device_id]
    probs   = MARKOV_MATRIX[current]
    nxt     = int(np.random.choice([0, 1, 2], p=probs))
    DEVICE_LABEL_STATE[device_id] = nxt
    return nxt


# ══════════════════════════════════════════════════════════════════════════════
# [2] TEMPORAL DEPENDENCY — AR(1) State per Device
# ══════════════════════════════════════════════════════════════════════════════

AR_ALPHA = 0.65   # semakin besar → perubahan makin lambat / smooth

DEVICE_SENSOR_STATE: dict[str, dict] = {
    d: {
        "voltage":     float(np.random.uniform(218, 222)),
        "current":     float(np.random.uniform(4, 7)),
        "frequency":   50.0,
        "temperature": float(np.random.uniform(28, 35)),
        "latency":     20.0,
        "packet_loss": 0.5,
        "throughput":  95.0,
    }
    for d in DEVICE_IDS
}

def ar_smooth(device_id: str, key: str, target: float) -> float:
    """AR(1) smoothing:  new = α*prev + (1-α)*target"""
    prev = DEVICE_SENSOR_STATE[device_id][key]
    new  = AR_ALPHA * prev + (1 - AR_ALPHA) * target
    DEVICE_SENSOR_STATE[device_id][key] = new
    return new


# ══════════════════════════════════════════════════════════════════════════════
# [3] DEVICE BIAS — Karakteristik unik per device
# ══════════════════════════════════════════════════════════════════════════════

DEVICE_BIAS = {
    d: {
        "v_bias":    float(np.random.uniform(-5, 5)),
        "v_scale":   float(np.random.uniform(0.97, 1.03)),
        "c_bias":    float(np.random.uniform(-0.5, 0.5)),
        "temp_bias": float(np.random.uniform(-3, 3)),
    }
    for d in DEVICE_IDS
}

def apply_device_bias(device_id, voltage, current, temperature):
    b = DEVICE_BIAS[device_id]
    return (
        voltage     * b["v_scale"] + b["v_bias"],
        current     + b["c_bias"],
        temperature + b["temp_bias"],
    )


# ══════════════════════════════════════════════════════════════════════════════
# [4] POLA HARIAN (Diurnal Pattern)
# ══════════════════════════════════════════════════════════════════════════════

def diurnal_load_factor(ts: datetime) -> float:
    """Faktor beban berdasarkan jam (0.0–1.0)."""
    h = ts.hour + ts.minute / 60.0
    morning = 0.8 * np.exp(-0.5 * ((h - 10) / 2.0) ** 2)
    evening = 1.0 * np.exp(-0.5 * ((h - 19) / 1.5) ** 2)
    base    = 0.3
    return float(np.clip(base + morning + evening, 0.3, 1.0))


# ══════════════════════════════════════════════════════════════════════════════
# HELPER DISTRIBUSI
# ══════════════════════════════════════════════════════════════════════════════

def _loglat(mu, sigma):
    return round(float(np.random.lognormal(mu, sigma)), 2)

def _logpkt(mu, sigma, lo=0, hi=100):
    return round(float(np.clip(np.random.lognormal(mu, sigma), lo, hi)), 2)

def _power(v, c):
    pf = np.random.uniform(0.80, 0.98)
    if np.random.rand() < 0.01:
        return 0.0
    return round(float(v * c * pf * (1 + np.random.normal(0, 0.05))), 4)


# ══════════════════════════════════════════════════════════════════════════════
# CORE GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generate_row(ts: datetime | None = None) -> dict:
    ts        = ts or datetime.now()
    device_id = random.choice(DEVICE_IDS)
    label     = markov_next_label(device_id)
    lf        = diurnal_load_factor(ts)

    if label == 0:   # NORMAL
        t_voltage   = np.random.uniform(215, 225) * (0.85 + 0.15 * lf)
        t_current   = np.random.uniform(3, 8)     * (0.6  + 0.4  * lf)
        t_freq      = np.random.uniform(49.8, 50.2)
        t_temp      = np.random.uniform(25, 40)   * (0.8  + 0.2  * lf)
        t_latency   = _loglat(2.8, 0.35)
        t_pktloss   = _logpkt(-1.0, 0.7, hi=5)
        t_thput     = np.random.uniform(85, 100)
        dup_packet  = int(np.random.poisson(0.5))
        chk_valid   = int(np.random.rand() > 0.01)
        auth_fail   = int(np.random.choice([0, 0, 0, 0, 1]))

    elif label == 1:   # ATTACK
        atype = random.choices(
            ["FDI", "Replay", "DoS", "Tampering"],
            weights=[0.28, 0.24, 0.24, 0.24]
        )[0]

        if atype == "FDI":
            t_voltage  = (np.random.uniform(205, 235) if np.random.rand() < 0.4
                          else np.random.uniform(100, 400))
            t_current  = np.random.uniform(0.5, 20)
            t_freq     = np.random.uniform(46, 55)
            t_temp     = np.random.uniform(20, 75)
            t_latency  = _loglat(4.0, 0.7)
            t_pktloss  = _logpkt(2.5, 0.5)
            t_thput    = np.random.uniform(15, 75)
            dup_packet = int(np.random.poisson(2))
            chk_valid  = int(np.random.choice([0, 1], p=[0.35, 0.65]))
            auth_fail  = int(np.random.randint(0, 5))

        elif atype == "Replay":
            t_voltage  = np.random.uniform(215, 225)
            t_current  = np.random.uniform(3, 8)
            t_freq     = np.random.normal(50.0, 0.05)
            t_temp     = np.random.normal(30.0, 1.0)
            t_latency  = _loglat(4.5, 0.6)
            t_pktloss  = _logpkt(2.8, 0.4)
            t_thput    = np.random.uniform(20, 65)
            dup_packet = int(np.random.poisson(8))
            chk_valid  = 1
            auth_fail  = int(np.random.randint(1, 8))

        elif atype == "DoS":
            t_voltage  = np.random.uniform(195, 235)
            t_current  = np.random.uniform(2, 12)
            t_freq     = np.random.uniform(48, 52)
            t_temp     = np.random.uniform(30, 65)
            t_latency  = _loglat(5.5, 0.5)
            t_pktloss  = _logpkt(3.5, 0.4)
            t_thput    = np.random.uniform(1, 25)
            dup_packet = int(np.random.poisson(15))
            chk_valid  = int(np.random.choice([0, 1]))
            auth_fail  = int(np.random.randint(2, 15))

        else:  # Tampering
            t_voltage  = (np.random.uniform(120, 150) if np.random.rand() < 0.5
                          else np.random.uniform(350, 400))
            t_current  = np.random.uniform(0.1, 45)
            t_freq     = np.random.uniform(42, 62)
            t_temp     = np.random.uniform(15, 85)
            t_latency  = _loglat(4.8, 0.8)
            t_pktloss  = _logpkt(3.0, 0.6)
            t_thput    = np.random.uniform(5, 55)
            dup_packet = int(np.random.poisson(5))
            chk_valid  = int(np.random.choice([0, 1], p=[0.55, 0.45]))
            auth_fail  = int(np.random.randint(0, 10))

    else:   # FAULT
        ftype = random.choices(
            ["Drift", "Stuck", "Overheat", "Noisy", "Missing"],
            weights=[0.2, 0.2, 0.2, 0.2, 0.2]
        )[0]

        if ftype == "Drift":
            t_voltage  = np.clip(np.random.uniform(195, 250), 160, 270)
            t_current  = np.random.uniform(3, 8)
            t_freq     = np.random.normal(50.0, 0.4)
            t_temp     = np.random.uniform(35, 58)
            t_latency  = _loglat(3.0, 0.5)
            t_pktloss  = _logpkt(0.5, 0.7)
            t_thput    = np.random.uniform(65, 95)
            dup_packet = int(np.random.poisson(0.8))
            chk_valid  = 1
            auth_fail  = 0

        elif ftype == "Stuck":
            sv         = np.random.uniform(215, 225)
            t_voltage  = sv if np.random.rand() < 0.88 else np.random.uniform(215, 225)
            t_current  = np.random.uniform(4, 7)
            t_freq     = 50.0
            t_temp     = np.random.uniform(30, 46)
            t_latency  = _loglat(2.9, 0.4)
            t_pktloss  = _logpkt(-0.5, 0.6)
            t_thput    = np.random.uniform(80, 100)
            dup_packet = int(np.random.poisson(0.3))
            chk_valid  = 1
            auth_fail  = 0

        elif ftype == "Overheat":
            t_voltage  = np.random.uniform(210, 232)
            t_current  = np.random.uniform(5, 13)
            t_freq     = np.random.normal(50.0, 0.25)
            t_temp     = np.random.uniform(68, 100)
            t_latency  = _loglat(3.2, 0.5)
            t_pktloss  = _logpkt(1.0, 0.7)
            t_thput    = np.random.uniform(55, 92)
            dup_packet = int(np.random.poisson(1.2))
            chk_valid  = int(np.random.rand() > 0.05)
            auth_fail  = int(np.random.choice([0, 0, 0, 1]))

        elif ftype == "Noisy":
            t_voltage  = np.random.uniform(205, 245)
            t_current  = np.random.uniform(2, 12)
            t_freq     = np.random.uniform(49.0, 51.0)
            t_temp     = np.random.uniform(28, 62)
            t_latency  = _loglat(3.5, 0.8)
            t_pktloss  = _logpkt(1.2, 0.8)
            t_thput    = np.random.uniform(55, 100)
            dup_packet = int(np.random.poisson(2))
            chk_valid  = 1
            auth_fail  = int(np.random.choice([0, 0, 0, 0, 1]))

        else:  # Missing
            t_voltage  = np.random.uniform(215, 226)
            t_current  = np.random.uniform(3.5, 7.5)
            t_freq     = np.random.uniform(49.8, 50.2)
            t_temp     = np.random.uniform(26, 58)
            t_latency  = _loglat(2.9, 0.5)
            t_pktloss  = _logpkt(0.5, 0.8)
            t_thput    = np.random.uniform(70, 100)
            dup_packet = int(np.random.poisson(0.5))
            chk_valid  = 1
            auth_fail  = 0

    # ── [2] AR(1) Temporal Smoothing ──────────────────────────────────────────
    voltage     = ar_smooth(device_id, "voltage",     t_voltage)
    current     = ar_smooth(device_id, "current",     t_current)
    frequency   = ar_smooth(device_id, "frequency",   t_freq)
    temperature = ar_smooth(device_id, "temperature", t_temp)
    latency     = ar_smooth(device_id, "latency",     t_latency)
    packet_loss = ar_smooth(device_id, "packet_loss", t_pktloss)
    throughput  = ar_smooth(device_id, "throughput",  t_thput)

    # ── [3] Device Bias ───────────────────────────────────────────────────────
    voltage, current, temperature = apply_device_bias(device_id, voltage, current, temperature)

    # ── Power ─────────────────────────────────────────────────────────────────
    power = _power(voltage, current)

    return {
        "timestamp":           ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "device_id":           device_id,
        "voltage":             round(float(voltage),     4),
        "current":             round(float(current),     4),
        "power":               round(float(power),       4),
        "frequency":           round(float(frequency),   4),
        "temperature":         round(float(temperature), 3),
        "latency":             round(float(latency),     2),
        "packet_loss":         round(max(0.0, float(packet_loss)), 2),
        "throughput":          round(float(np.clip(throughput, 0, 100)), 2),
        "duplicate_packet":    int(dup_packet),
        "checksum_valid":      int(chk_valid),
        "authentication_fail": int(auth_fail),
        "label":               label,
        "label_name":          LABEL_MAP[label],
    }


# ══════════════════════════════════════════════════════════════════════════════
# CSV
# ══════════════════════════════════════════════════════════════════════════════

def to_public(row: dict) -> dict:
    """Hapus label dari row sebelum dikirim ke API / SSE."""
    return {k: row[k] for k in PUBLIC_FIELDS}


def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=CSV_HEADER).writeheader()
        print(f"📄 CSV created: {CSV_FILE}")
    else:
        print(f"📄 Appending to existing: {CSV_FILE}")

def append_csv(rows: list[dict]):
    with open(CSV_FILE, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        for row in rows:
            w.writerow({k: row[k] for k in CSV_HEADER})


# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND SIMULATOR
# ══════════════════════════════════════════════════════════════════════════════

def run_simulator(rate: int):
    global TOTAL_ROWS
    interval = 1.0 / rate
    print(f"⚙️  Simulator started — {rate} row/detik (interval {interval*1000:.0f} ms)")

    while True:
        ts  = datetime.now()
        row = generate_row(ts)
        append_csv([row])

        with LOCK:
            HISTORY.append(row)
            TOTAL_ROWS += 1
            dead = []
            for q in SSE_QUEUES:
                try:
                    q.put_nowait(to_public(row))
                except queue.Full:
                    dead.append(q)
            for q in dead:
                SSE_QUEUES.remove(q)

        time.sleep(interval)


# ══════════════════════════════════════════════════════════════════════════════
# FLASK
# ══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
CORS(app)


@app.route("/")
def index():
    with LOCK:
        n = TOTAL_ROWS
    return jsonify({
        "service":    "Smart Grid IoT Simulator v2 (Multi-Method + Ngrok)",
        "methods":    ["Markov Chain", "AR(1) Temporal Dependency", "Diurnal Pattern", "Device Bias"],
        "total_rows": n,
        "csv_file":   CSV_FILE,
        "public_url": NGROK_PUBLIC_URL or "ngrok not active",
        "endpoints": {
            "GET /data/latest":   "Row terbaru",
            "GET /data/history":  "N row terakhir (?limit=50)",
            "GET /data/realtime": "SSE stream real-time ★",
            "GET /data/download": "Download CSV",
            "GET /data/stats":    "Statistik distribusi label",
            "GET /status":        "Status simulator",
            "GET /markov/state":  "Lihat Markov state semua device",
        }
    })


@app.route("/status")
def status():
    with LOCK:
        n    = TOTAL_ROWS
        hist = list(HISTORY)
    dist = {LABEL_MAP[i]: 0 for i in range(3)}
    for r in hist:
        dist[LABEL_MAP[r["label"]]] += 1
    csv_size = os.path.getsize(CSV_FILE) if os.path.exists(CSV_FILE) else 0
    return jsonify({
        "status":              "running",
        "total_rows":          n,
        "csv_file":            CSV_FILE,
        "csv_size_kb":         round(csv_size / 1024, 2),
        "sse_clients":         len(SSE_QUEUES),
        "label_dist_last1000": dist,
        "public_url":          NGROK_PUBLIC_URL or "ngrok not active",
    })


@app.route("/data/latest")
def latest():
    with LOCK:
        row = dict(HISTORY[-1]) if HISTORY else {}
    if not row:
        return jsonify({"error": "No data yet"}), 503
    return jsonify(to_public(row))


@app.route("/data/history")
def history():
    limit = min(int(request.args.get("limit", 100)), 1000)
    with LOCK:
        rows = list(HISTORY)[-limit:]
    return jsonify({"count": len(rows), "rows": [to_public(r) for r in rows]})


@app.route("/data/stats")
def stats():
    with LOCK:
        rows = list(HISTORY)
    if not rows:
        return jsonify({"error": "No data yet"}), 503
    total = len(rows)
    dist  = {LABEL_MAP[i]: 0 for i in range(3)}
    for r in rows:
        dist[LABEL_MAP[r["label"]]] += 1
    return jsonify({
        "total_in_memory": total,
        "distribution": {
            k: {"count": v, "pct": round(v / total * 100, 1)}
            for k, v in dist.items()
        },
    })


@app.route("/data/download")
def download():
    if not os.path.exists(CSV_FILE):
        return jsonify({"error": "CSV not found"}), 404
    with open(CSV_FILE, "r") as f:
        content = f.read()
    return Response(
        content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={CSV_FILE}"}
    )


@app.route("/markov/state")
def markov_state():
    return jsonify({
        d: LABEL_MAP[s] for d, s in DEVICE_LABEL_STATE.items()
    })


# ── SSE STREAM ────────────────────────────────────────────────────────────────
@app.route("/data/realtime")
def realtime():
    """
    Server-Sent Events.
    Akses:
      curl   : curl -N http://localhost:8080/data/realtime
      JS     : const es = new EventSource('.../data/realtime')
               es.onmessage = e => console.log(JSON.parse(e.data))
    """
    def stream(client_q: queue.Queue):
        try:
            while True:
                try:
                    new_row = client_q.get(timeout=30)
                    yield f"data: {json.dumps(new_row)}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            with LOCK:
                if client_q in SSE_QUEUES:
                    SSE_QUEUES.remove(client_q)

    client_q: queue.Queue = queue.Queue(maxsize=200)
    with LOCK:
        SSE_QUEUES.append(client_q)

    return Response(
        stream(client_q),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        }
    )


# ══════════════════════════════════════════════════════════════════════════════
# [5] NGROK INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

def start_ngrok(port: int, auth_token: str | None = None) -> str | None:
    """
    Mulai tunnel ngrok dan kembalikan public URL.
    Mengembalikan None jika pyngrok tidak terinstall atau gagal.
    """
    global NGROK_PUBLIC_URL

    try:
        from pyngrok import ngrok, conf
    except ImportError:
        print("⚠️  pyngrok tidak terinstall. Jalankan: pip install pyngrok")
        print("   Server tetap berjalan secara lokal.")
        return None

    try:
        # Set auth token jika diberikan via argumen
        # Jika tidak, pyngrok akan memakai token dari ~/.ngrok2/ngrok.yml
        if auth_token:
            ngrok.set_auth_token(auth_token)

        # Buka tunnel HTTP
        tunnel = ngrok.connect(port, "http")
        public_url = tunnel.public_url

        # Ganti http → https jika perlu
        if public_url.startswith("http://"):
            public_url = public_url.replace("http://", "https://", 1)

        NGROK_PUBLIC_URL = public_url

        print("\n" + "═" * 60)
        print(f"  🌐 NGROK PUBLIC URL : {public_url}")
        print("═" * 60)
        print(f"""
Public Endpoints (bisa diakses dari internet):
  {public_url}/               ← info & metode
  {public_url}/status         ← status & stats
  {public_url}/data/latest    ← row terbaru
  {public_url}/data/history   ← 100 row terakhir
  {public_url}/data/realtime  ← SSE stream ★
  {public_url}/data/download  ← download CSV
  {public_url}/markov/state   ← debug Markov state
        """)

        return public_url

    except Exception as e:
        print(f"⚠️  Gagal memulai ngrok: {e}")
        print("   Server tetap berjalan secara lokal.")
        return None


def stop_ngrok():
    """Hentikan semua tunnel ngrok dengan aman."""
    try:
        from pyngrok import ngrok
        ngrok.kill()
        print("🔌 Ngrok tunnel ditutup.")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Grid Simulator v2 + Ngrok")
    parser.add_argument("--port",        type=int,  default=8080,
                        help="Port lokal Flask (default: 8080)")
    parser.add_argument("--rate",        type=int,  default=10,
                        help="Jumlah row per detik (default: 10)")
    parser.add_argument("--ngrok-token", type=str,  default=None,
                        help="Ngrok auth token (opsional jika sudah login ngrok)")
    parser.add_argument("--no-ngrok",    action="store_true",
                        help="Matikan ngrok, jalankan lokal saja")
    args = parser.parse_args()

    # ── Inisialisasi CSV ───────────────────────────────────────────────────────
    init_csv()

    # ── Mulai background simulator ─────────────────────────────────────────────
    t = threading.Thread(target=run_simulator, args=(args.rate,), daemon=True)
    t.start()

    # ── Info lokal ─────────────────────────────────────────────────────────────
    print(f"\n📡 Local URL : http://localhost:{args.port}")
    print("═" * 60)
    print(f"  CSV file : {os.path.abspath(CSV_FILE)}")
    print(f"  Rate     : {args.rate} row/detik")
    print(f"  Methods  : Markov Chain + AR(1) Temporal + Diurnal + Device Bias + Ngrok")
    print("═" * 60)
    print(f"""
Local Endpoints:
  http://localhost:{args.port}/               ← info & metode
  http://localhost:{args.port}/status         ← status & stats
  http://localhost:{args.port}/data/latest    ← row terbaru
  http://localhost:{args.port}/data/history   ← 100 row terakhir
  http://localhost:{args.port}/data/realtime  ← SSE stream ★
  http://localhost:{args.port}/data/download  ← download CSV
  http://localhost:{args.port}/markov/state   ← debug Markov state

Tekan Ctrl+C untuk berhenti.
""")

    # ── Mulai ngrok (kecuali --no-ngrok) ──────────────────────────────────────
    if not args.no_ngrok:
        start_ngrok(args.port, auth_token=args.ngrok_token)
    else:
        print("ℹ️  Ngrok dinonaktifkan (--no-ngrok). Berjalan lokal saja.\n")

    # ── Jalankan Flask ─────────────────────────────────────────────────────────
    try:
        app.run(
            host="0.0.0.0",
            port=args.port,
            debug=False,
            threaded=True,
            use_reloader=False,
        )
    except KeyboardInterrupt:
        print("\n🛑 Berhenti...")
    finally:
        stop_ngrok()
        print("✅ Server ditutup.")