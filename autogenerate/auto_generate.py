"""
Smart Grid IoT Security — Real-Time Simulator + SSE Stream
===========================================================
Generate data sensor smart grid tiap 5 detik.
Data disimpan ke CSV dan bisa diakses via REST API + SSE stream.

Label: 0=NORMAL, 1=ATTACK, 2=FAULT

Jalankan:
  python simulator.py                        # lokal saja
  python simulator.py --port 8080            # custom port
  python simulator.py --interval 3           # generate tiap 3 detik
"""

import argparse
import csv
import json
import os
import queue
import random
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
CSV_FILE   = "smart_grid_data.csv"
CSV_HEADER = [
    "timestamp", "device_id",
    "voltage", "current", "power", "frequency", "temperature",
    "latency", "packet_loss", "throughput",
    "duplicate_packet", "checksum_valid", "authentication_fail",
]
LABEL_MAP  = {0: "NORMAL", 1: "ATTACK", 2: "FAULT"}
CLASS_PROB = [0.415, 0.372, 0.213]   # NORMAL / ATTACK / FAULT

# In-memory store
HISTORY    = deque(maxlen=1000)
TOTAL_ROWS = 0
LOCK       = threading.Lock()

# SSE — satu queue per client yang connect ke /data/realtime
SSE_QUEUES: list[queue.Queue] = []

np.random.seed()

DEVICE_BIAS = {
    d: {
        "v_bias":    float(np.random.uniform(-5, 5)),
        "v_scale":   float(np.random.uniform(0.97, 1.03)),
        "c_bias":    float(np.random.uniform(-0.5, 0.5)),
        "temp_bias": float(np.random.uniform(-3, 3)),
    }
    for d in DEVICE_IDS
}


# ══════════════════════════════════════════════════════════════════════════════
# GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def _bias(device_id, voltage, current, temperature):
    b = DEVICE_BIAS[device_id]
    return (
        voltage     * b["v_scale"] + b["v_bias"],
        current     + b["c_bias"],
        temperature + b["temp_bias"],
    )

def _power(v, c):
    pf = np.random.uniform(0.80, 0.98)
    if np.random.rand() < 0.01:
        return 0.0
    return round(float(v * c * pf * (1 + np.random.normal(0, 0.05))), 4)

def _loglat(mu, sigma):
    return round(float(np.random.lognormal(mu, sigma)), 2)

def _logpkt(mu, sigma, lo=0, hi=100):
    return round(float(np.clip(np.random.lognormal(mu, sigma), lo, hi)), 2)


def generate_row(ts=None):
    label     = int(np.random.choice([0, 1, 2], p=CLASS_PROB))
    device_id = random.choice(DEVICE_IDS)
    ts        = ts or datetime.now()

    # ── NORMAL ────────────────────────────────────────────────────────────────
    if label == 0:
        voltage     = np.random.uniform(215, 225)
        current     = np.random.uniform(3, 8)
        frequency   = np.random.uniform(49.8, 50.2)
        temperature = np.random.uniform(25, 40)
        latency     = _loglat(2.8, 0.35)
        packet_loss = _logpkt(-1.0, 0.7, hi=5)
        throughput  = round(np.random.uniform(85, 100), 2)
        dup_packet  = int(np.random.poisson(0.5))
        chk_valid   = int(np.random.rand() > 0.01)
        auth_fail   = int(np.random.choice([0,0,0,0,1]))

    # ── ATTACK ────────────────────────────────────────────────────────────────
    elif label == 1:
        atype = random.choices(
            ["FDI", "Replay", "DoS", "Tampering"],
            weights=[0.28, 0.24, 0.24, 0.24]
        )[0]

        if atype == "FDI":
            voltage     = (np.random.uniform(205, 235) if np.random.rand() < 0.4
                           else np.random.uniform(100, 400))
            current     = np.random.uniform(0.5, 20)
            frequency   = np.random.uniform(46, 55)
            temperature = np.random.uniform(20, 75)
            latency     = _loglat(4.0, 0.7)
            packet_loss = _logpkt(2.5, 0.5)
            throughput  = round(np.random.uniform(15, 75), 2)
            dup_packet  = int(np.random.poisson(2))
            chk_valid   = int(np.random.choice([0,1], p=[0.35, 0.65]))
            auth_fail   = int(np.random.randint(0, 5))

        elif atype == "Replay":
            voltage     = np.random.uniform(215, 225)
            current     = np.random.uniform(3, 8)
            frequency   = np.random.normal(50.0, 0.05)
            temperature = np.random.normal(30.0, 1.0)
            latency     = _loglat(4.5, 0.6)
            packet_loss = _logpkt(2.8, 0.4)
            throughput  = round(np.random.uniform(20, 65), 2)
            dup_packet  = int(np.random.poisson(8))
            chk_valid   = 1
            auth_fail   = int(np.random.randint(1, 8))

        elif atype == "DoS":
            voltage     = np.random.uniform(195, 235)
            current     = np.random.uniform(2, 12)
            frequency   = np.random.uniform(48, 52)
            temperature = np.random.uniform(30, 65)
            latency     = _loglat(5.5, 0.5)
            packet_loss = _logpkt(3.5, 0.4)
            throughput  = round(np.random.uniform(1, 25), 2)
            dup_packet  = int(np.random.poisson(15))
            chk_valid   = int(np.random.choice([0,1]))
            auth_fail   = int(np.random.randint(2, 15))

        else:  # Tampering
            voltage     = (np.random.uniform(120, 150) if np.random.rand() < 0.5
                           else np.random.uniform(350, 400))
            current     = np.random.uniform(0.1, 45)
            frequency   = np.random.uniform(42, 62)
            temperature = np.random.uniform(15, 85)
            latency     = _loglat(4.8, 0.8)
            packet_loss = _logpkt(3.0, 0.6)
            throughput  = round(np.random.uniform(5, 55), 2)
            dup_packet  = int(np.random.poisson(5))
            chk_valid   = int(np.random.choice([0,1], p=[0.55, 0.45]))
            auth_fail   = int(np.random.randint(0, 10))

    # ── FAULT ─────────────────────────────────────────────────────────────────
    else:
        ftype = random.choices(
            ["Drift", "Stuck", "Overheat", "Noisy", "Missing"],
            weights=[0.2, 0.2, 0.2, 0.2, 0.2]
        )[0]

        if ftype == "Drift":
            voltage     = np.clip(np.random.uniform(195, 250), 160, 270)
            current     = np.random.uniform(3, 8)
            frequency   = np.random.normal(50.0, 0.4)
            temperature = np.random.uniform(35, 58)
            latency     = _loglat(3.0, 0.5)
            packet_loss = _logpkt(0.5, 0.7)
            throughput  = round(np.random.uniform(65, 95), 2)
            dup_packet  = int(np.random.poisson(0.8))
            chk_valid   = 1
            auth_fail   = 0

        elif ftype == "Stuck":
            sv          = np.random.uniform(215, 225)
            voltage     = sv if np.random.rand() < 0.88 else np.random.uniform(215, 225)
            current     = np.random.uniform(4, 7)
            frequency   = 50.0
            temperature = np.random.uniform(30, 46)
            latency     = _loglat(2.9, 0.4)
            packet_loss = _logpkt(-0.5, 0.6)
            throughput  = round(np.random.uniform(80, 100), 2)
            dup_packet  = int(np.random.poisson(0.3))
            chk_valid   = 1
            auth_fail   = 0

        elif ftype == "Overheat":
            voltage     = np.random.uniform(210, 232)
            current     = np.random.uniform(5, 13)
            frequency   = np.random.normal(50.0, 0.25)
            temperature = np.random.uniform(68, 100)
            latency     = _loglat(3.2, 0.5)
            packet_loss = _logpkt(1.0, 0.7)
            throughput  = round(np.random.uniform(55, 92), 2)
            dup_packet  = int(np.random.poisson(1.2))
            chk_valid   = int(np.random.rand() > 0.05)
            auth_fail   = int(np.random.choice([0,0,0,1]))

        elif ftype == "Noisy":
            voltage     = np.random.uniform(205, 245)
            current     = np.random.uniform(2, 12)
            frequency   = np.random.uniform(49.0, 51.0)
            temperature = np.random.uniform(28, 62)
            latency     = _loglat(3.5, 0.8)
            packet_loss = _logpkt(1.2, 0.8)
            throughput  = round(np.random.uniform(55, 100), 2)
            dup_packet  = int(np.random.poisson(2))
            chk_valid   = 1
            auth_fail   = int(np.random.choice([0,0,0,0,1]))

        else:  # Missing
            voltage     = np.random.uniform(215, 226)
            current     = np.random.uniform(3.5, 7.5)
            frequency   = np.random.uniform(49.8, 50.2)
            temperature = np.random.uniform(26, 58)
            latency     = _loglat(2.9, 0.5)
            packet_loss = _logpkt(0.5, 0.8)
            throughput  = round(np.random.uniform(70, 100), 2)
            dup_packet  = int(np.random.poisson(0.5))
            chk_valid   = 1
            auth_fail   = 0

    voltage, current, temperature = _bias(device_id, voltage, current, temperature)
    power = _power(voltage, current)

    return {
        "timestamp":           ts.strftime("%Y-%m-%d %H:%M:%S"),
        "device_id":           device_id,
        "voltage":             round(float(voltage),     4),
        "current":             round(float(current),     4),
        "power":               round(float(power),       4),
        "frequency":           round(float(frequency),   4),
        "temperature":         round(float(temperature), 3),
        "latency":             round(float(latency),     2),
        "packet_loss":         round(float(packet_loss), 2),
        "throughput":          round(float(throughput),  2),
        "duplicate_packet":    int(dup_packet),
        "checksum_valid":      int(chk_valid),
        "authentication_fail": int(auth_fail),
    }


# ══════════════════════════════════════════════════════════════════════════════
# CSV
# ══════════════════════════════════════════════════════════════════════════════

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=CSV_HEADER).writeheader()
        print(f"📄 CSV created: {CSV_FILE}")
    else:
        print(f"📄 Appending to existing: {CSV_FILE}")

def append_csv(row: dict):
    with open(CSV_FILE, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=CSV_HEADER).writerow(
            {k: row[k] for k in CSV_HEADER}
        )


# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND SIMULATOR THREAD
# ══════════════════════════════════════════════════════════════════════════════

def run_simulator(interval: int):
    global TOTAL_ROWS
    print(f"⚙️  Simulator started — generating 1 row every {interval}s")
    while True:
        row = generate_row()
        append_csv(row)

        with LOCK:
            HISTORY.append(row)
            TOTAL_ROWS += 1
            # Broadcast ke semua SSE client yang sedang connect
            dead = []
            for q in SSE_QUEUES:
                try:
                    q.put_nowait(row)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                SSE_QUEUES.remove(q)

        print(f"  [{row['timestamp']}] {row['device_id']} | "
              f"V={row['voltage']:.2f}V  T={row['temperature']:.1f}°C  "
              )
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
        "service":    "Smart Grid IoT Simulator",
        "total_rows": n,
        "csv_file":   CSV_FILE,
        "endpoints": {
            "GET /data/latest":   "Row terbaru",
            "GET /data/history":  "N row terakhir (?limit=50)",
            "GET /data/realtime": "SSE stream — semua data real-time",
            "GET /data/download": "Download CSV",
            "GET /data/stats":    "Statistik distribusi label",
            "GET /status":        "Status simulator",
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
    })


@app.route("/data/latest")
def latest():
    with LOCK:
        row = dict(HISTORY[-1]) if HISTORY else {}
    if not row:
        return jsonify({"error": "No data yet"}), 503
    return jsonify(row)


@app.route("/data/history")
def history():
    limit = min(int(request.args.get("limit", 100)), 1000)
    with LOCK:
        rows = list(HISTORY)[-limit:]
    return jsonify({"count": len(rows), "rows": rows})


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


# ── SSE STREAM ────────────────────────────────────────────────────────────────
@app.route("/data/realtime")
def realtime():
    """
    Server-Sent Events — hanya kirim ROW BARU saja tiap kali data di-generate.

    Setiap event berisi 1 object JSON (bukan array):
      data: {"timestamp": "...", "device_id": "...", "voltage": ..., "label": 0, ...}

    Bisa diakses dari:
      - curl   : curl -N http://localhost:8080/data/realtime
      - browser: buka URL langsung
      - JS     : const es = new EventSource('.../data/realtime')
                 es.onmessage = e => console.log(JSON.parse(e.data))
    """
    def stream(client_q: queue.Queue):
        try:
            while True:
                try:
                    new_row = client_q.get(timeout=30)
                    # Kirim hanya 1 row baru — bukan seluruh array
                    yield f"data: {json.dumps(new_row)}\n\n"
                except queue.Empty:
                    # Keep-alive ping agar koneksi tidak putus
                    yield ": ping\n\n"
        finally:
            with LOCK:
                if client_q in SSE_QUEUES:
                    SSE_QUEUES.remove(client_q)

    # Daftarkan queue baru untuk client ini
    client_q: queue.Queue = queue.Queue(maxsize=100)
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
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Grid Simulator")
    parser.add_argument("--port",     type=int, default=8080)
    parser.add_argument("--interval", type=int, default=5,
                        help="Interval generate data dalam detik (default: 5)")
    args = parser.parse_args()

    init_csv()

    t = threading.Thread(target=run_simulator, args=(args.interval,), daemon=True)
    t.start()

    print(f"\n📡 Running at http://localhost:{args.port}")
    print(f"   Expose ke internet: jalankan ngrok di terminal lain")
    print(f"   → ngrok http {args.port}\n")
    print("═" * 60)
    print(f"  CSV file : {os.path.abspath(CSV_FILE)}")
    print(f"  Interval : {args.interval} detik per row")
    print("═" * 60)
    print(f"""
Endpoints:
  http://localhost:{args.port}/               ← info
  http://localhost:{args.port}/status         ← status & stats
  http://localhost:{args.port}/data/latest    ← row terbaru
  http://localhost:{args.port}/data/history   ← 100 row terakhir
  http://localhost:{args.port}/data/realtime  ← SSE stream real-time ★
  http://localhost:{args.port}/data/download  ← download CSV

Tekan Ctrl+C untuk berhenti.
""")

    try:
        app.run(host="0.0.0.0", port=args.port, debug=False,
                threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n🛑 Stopped.")