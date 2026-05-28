"""
dashboard.py — Smart Grid Security Monitoring Dashboard
========================================================
Kelompok 3 - Keamanan Data

Mode:
  LIVE_MODE = False  → pakai data simulasi (tanpa server Rambat)
  LIVE_MODE = True   → connect ke SSE server Rambat (production)

Jalankan:
  streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import time
import sys
import os
import random
from datetime import datetime, timedelta
from collections import deque

# ─────────────────────────────────────────────
# KONFIGURASI
# ─────────────────────────────────────────────

# [RAMBAT] Ganti True jika server sudah jalan
LIVE_MODE = False
SSE_URL   = "http://localhost:8080/prediction/stream"

# Import encrypt.py dari folder autogenerate
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "autogenerate"))
from encrypt import build_packet, unpack_packet, setup_keys

LABEL_MAP = {0: "Normal", 1: "Attack", 2: "Fault"}
LABEL_COLOR = {
    "Normal": "#2E7D32",
    "Attack": "#C62828",
    "Fault":  "#E65100",
}
LABEL_BG = {
    "Normal": "#E8F5E9",
    "Attack": "#FFEBEE",
    "Fault":  "#FFF3E0",
}
LABEL_ICON = {
    "Normal": "✅",
    "Attack": "🚨",
    "Fault":  "⚠️",
}

DEVICES = [f"SGD-{str(i).zfill(4)}" for i in range(1, 11)]
MAX_HISTORY = 100


# ─────────────────────────────────────────────
# SIMULASI DATA
# ─────────────────────────────────────────────

def generate_dummy_raw(label: int) -> dict:
    """Generate satu baris data sensor sesuai label."""
    if label == 0:   # Normal
        voltage  = round(random.uniform(210, 230), 4)
        current  = round(random.uniform(2.0, 8.0), 4)
        temp     = round(random.uniform(20, 55), 3)
        latency  = round(random.uniform(5, 80), 2)
        pkt_loss = round(random.uniform(0, 3), 2)
        auth_fail = random.randint(0, 1)
    elif label == 1:  # Attack
        voltage  = round(random.uniform(210, 230), 4)
        current  = round(random.uniform(2.0, 8.0), 4)
        temp     = round(random.uniform(20, 55), 3)
        latency  = round(random.uniform(100, 500), 2)
        pkt_loss = round(random.uniform(8, 25), 2)
        auth_fail = random.randint(3, 8)
    else:             # Fault
        voltage  = round(random.choice([
            random.uniform(150, 195),
            random.uniform(245, 300)
        ]), 4)
        current  = round(random.uniform(2.0, 8.0), 4)
        temp     = round(random.uniform(66, 90), 3)
        latency  = round(random.uniform(5, 80), 2)
        pkt_loss = round(random.uniform(0, 3), 2)
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
    """
    Simulasi alur lengkap: generate → enkripsi → dekripsi → return payload.
    Ini membuktikan enkripsi berjalan di pipeline dashboard.
    """
    # Distribusi: 70% Normal, 20% Attack, 10% Fault
    label = random.choices([0, 1, 2], weights=[70, 20, 10])[0]
    raw   = generate_dummy_raw(label)

    # Enkripsi (seperti yang dilakukan ML.py)
    encrypted_packet = build_packet(raw)

    # Dekripsi (seperti yang dilakukan dashboard saat terima dari server)
    payload = unpack_packet(encrypted_packet)

    return payload


def get_next_live_packet() -> dict | None:
    """Ambil satu packet dari SSE server Rambat (LIVE_MODE=True)."""
    try:
        import requests
        response = requests.get(SSE_URL, stream=True, timeout=3)
        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    encrypted_packet = json.loads(line_str[6:])
                    return unpack_packet(encrypted_packet)
    except Exception:
        return None


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────

def init_state():
    if "history" not in st.session_state:
        st.session_state.history = []
    if "running" not in st.session_state:
        st.session_state.running = False
    if "total" not in st.session_state:
        st.session_state.total = 0
    if "counts" not in st.session_state:
        st.session_state.counts = {"Normal": 0, "Attack": 0, "Fault": 0}
    if "keys_ready" not in st.session_state:
        try:
            setup_keys()
            st.session_state.keys_ready = True
        except Exception as e:
            st.session_state.keys_ready = False
            st.session_state.keys_error = str(e)


# ─────────────────────────────────────────────
# KOMPONEN UI
# ─────────────────────────────────────────────

def render_header():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

        html, body, [class*="css"] {
            font-family: 'DM Sans', sans-serif;
        }
        .dashboard-header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            border-radius: 16px;
            padding: 28px 36px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header-title {
            font-family: 'DM Serif Display', serif;
            font-size: 26px;
            color: #ffffff;
            margin: 0;
            letter-spacing: -0.3px;
        }
        .header-subtitle {
            font-family: 'DM Mono', monospace;
            font-size: 11px;
            color: #7eceff;
            margin-top: 4px;
            letter-spacing: 1.5px;
            text-transform: uppercase;
        }
        .header-badge {
            font-family: 'DM Mono', monospace;
            font-size: 11px;
            background: rgba(126, 206, 255, 0.15);
            color: #7eceff;
            border: 1px solid rgba(126, 206, 255, 0.3);
            border-radius: 20px;
            padding: 6px 14px;
        }
        .metric-card {
            background: #ffffff;
            border: 1px solid #e8edf2;
            border-radius: 12px;
            padding: 20px 24px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }
        .metric-label {
            font-size: 11px;
            color: #8a9bb0;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-bottom: 6px;
        }
        .metric-value {
            font-family: 'DM Serif Display', serif;
            font-size: 32px;
            color: #1a1a2e;
            line-height: 1;
        }
        .metric-sub {
            font-size: 12px;
            color: #8a9bb0;
            margin-top: 4px;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            font-family: 'DM Mono', monospace;
        }
        .alert-card {
            border-radius: 10px;
            padding: 14px 18px;
            margin-bottom: 8px;
            border-left: 4px solid;
            font-size: 13px;
        }
        .section-title {
            font-family: 'DM Serif Display', serif;
            font-size: 18px;
            color: #1a1a2e;
            margin: 24px 0 12px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid #f0f4f8;
        }
        .enc-badge {
            background: #f0f4ff;
            border: 1px solid #c7d2fe;
            border-radius: 8px;
            padding: 10px 14px;
            font-family: 'DM Mono', monospace;
            font-size: 10px;
            color: #4338ca;
            word-break: break-all;
            line-height: 1.6;
        }
        div[data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid #e8edf2;
        }
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
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        dot = "🟢" if running else "⚫"
        st.markdown(f"**{dot} Status:** {'LIVE' if running else 'STOPPED'} &nbsp;|&nbsp; "
                    f"**Mode:** {'🔴 LIVE SERVER' if mode == 'live' else '🔵 SIMULASI'}")
    with col2:
        st.markdown(f"**Total packet diproses:** `{total}`")
    with col3:
        st.markdown(f"**{'🔒 Enkripsi aktif' if total > 0 else '🔓 Belum ada data'}**")


def render_metric_row(counts: dict, total: int):
    cols = st.columns(4)
    metrics = [
        ("Total Packet",  str(total),                    "sejak sistem start",        "#1a1a2e"),
        ("Normal",        str(counts["Normal"]),          f"{counts['Normal']/max(total,1)*100:.1f}% dari total",  LABEL_COLOR["Normal"]),
        ("Attack 🚨",     str(counts["Attack"]),          f"{counts['Attack']/max(total,1)*100:.1f}% dari total",  LABEL_COLOR["Attack"]),
        ("Fault ⚠️",      str(counts["Fault"]),           f"{counts['Fault']/max(total,1)*100:.1f}% dari total",   LABEL_COLOR["Fault"]),
    ]
    for col, (label, value, sub, color) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value" style="color:{color}">{value}</div>
                <div class="metric-sub">{sub}</div>
            </div>
            """, unsafe_allow_html=True)


def render_charts(history: list):
    if len(history) < 2:
        st.info("Menunggu data masuk...")
        return

    df = pd.DataFrame(history)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown('<div class="section-title">📈 Grafik Sensor Realtime</div>', unsafe_allow_html=True)

        tab1, tab2, tab3, tab4 = st.tabs(["Tegangan", "Arus", "Suhu", "Latency"])

        with tab1:
            chart_df = df[["timestamp", "voltage"]].set_index("timestamp")
            st.line_chart(chart_df, color="#0f3460", height=200)

        with tab2:
            chart_df = df[["timestamp", "current"]].set_index("timestamp")
            st.line_chart(chart_df, color="#e94560", height=200)

        with tab3:
            chart_df = df[["timestamp", "temperature"]].set_index("timestamp")
            st.line_chart(chart_df, color="#f5a623", height=200)

        with tab4:
            chart_df = df[["timestamp", "latency"]].set_index("timestamp")
            st.line_chart(chart_df, color="#7b2d8b", height=200)

    with col_right:
        st.markdown('<div class="section-title">🥧 Distribusi Status</div>', unsafe_allow_html=True)

        counts_now = df["label_name"].value_counts()
        pie_data   = pd.DataFrame({
            "Status": counts_now.index,
            "Jumlah": counts_now.values
        })

        import plotly.express as px
        fig = px.pie(
            pie_data,
            names="Status",
            values="Jumlah",
            color="Status",
            color_discrete_map=LABEL_COLOR,
            hole=0.45,
        )
        fig.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            height=260,
            font=dict(family="DM Sans"),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
            showlegend=True,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

        # Alert terbaru
        st.markdown('<div class="section-title">🔔 Alert Terbaru</div>', unsafe_allow_html=True)
        alerts = [r for r in reversed(history) if r["label_name"] != "Normal"][:5]
        if alerts:
            for a in alerts:
                color  = LABEL_COLOR[a["label_name"]]
                bg     = LABEL_BG[a["label_name"]]
                icon   = LABEL_ICON[a["label_name"]]
                st.markdown(f"""
                <div class="alert-card" style="background:{bg}; border-color:{color};">
                    {icon} <strong>{a['label_name']}</strong> &nbsp;·&nbsp;
                    <span style="font-family:monospace">{a['device_id']}</span><br>
                    <span style="color:#666;font-size:11px">{a['timestamp']} &nbsp;·&nbsp;
                    V={a['voltage']:.1f}V &nbsp;·&nbsp; T={a['temperature']:.1f}°C</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("_Belum ada alert — semua normal_")


def render_table(history: list):
    if not history:
        return

    st.markdown('<div class="section-title">📋 Tabel Data Realtime</div>', unsafe_allow_html=True)

    df = pd.DataFrame(history[-30:]).iloc[::-1].reset_index(drop=True)

    display_cols = [
        "timestamp", "device_id", "label_name",
        "voltage", "current", "temperature",
        "latency", "packet_loss", "authentication_fail"
    ]
    display_cols = [c for c in display_cols if c in df.columns]
    df_show = df[display_cols].copy()
    df_show.columns = [
        "Timestamp", "Device", "Status",
        "Voltage (V)", "Current (A)", "Temp (°C)",
        "Latency (ms)", "Packet Loss (%)", "Auth Fail"
    ][:len(display_cols)]

    def color_status(val):
        c = LABEL_COLOR.get(val, "#000")
        b = LABEL_BG.get(val, "#fff")
        return f"background-color: {b}; color: {c}; font-weight: 600"

    styled = df_show.style.applymap(color_status, subset=["Status"])
    st.dataframe(styled, use_container_width=True, height=300)


def render_encryption_info(history: list):
    if not history:
        return

    last = history[-1]
    st.markdown('<div class="section-title">🔐 Info Enkripsi Packet Terakhir</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Metode Enkripsi**")
        st.markdown("""
        - Payload → **AES-256-GCM**
        - AES Key → **RSA-2048-OAEP**
        - Hash → **SHA-256**
        - Integrity tag: **16 byte GCM tag**
        """)
    with col2:
        st.markdown("**Payload Terdekripsi**")
        st.json({
            "device_id":        last["device_id"],
            "voting_prediction": last["voting_prediction"],
            "label_name":        last["label_name"],
            "timestamp":         last["timestamp"],
        })
    with col3:
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

    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Kontrol")
        mode = "live" if LIVE_MODE else "simulasi"
        st.markdown(f"**Mode:** `{mode.upper()}`")

        if not LIVE_MODE:
            st.info("Mode simulasi aktif.\nGanti `LIVE_MODE = True` di dashboard.py untuk connect ke server Rambat.")

        st.markdown("---")
        speed = st.slider("Kecepatan simulasi (detik)", 0.3, 3.0, 1.0, 0.1)
        st.markdown("---")

        col_start, col_stop = st.columns(2)
        with col_start:
            if st.button("▶ Start", use_container_width=True, type="primary"):
                st.session_state.running = True
        with col_stop:
            if st.button("⏹ Stop", use_container_width=True):
                st.session_state.running = False

        if st.button("🗑 Reset", use_container_width=True):
            st.session_state.history = []
            st.session_state.total   = 0
            st.session_state.counts  = {"Normal": 0, "Attack": 0, "Fault": 0}
            st.rerun()

        st.markdown("---")
        st.markdown("**RSA Keys:**")
        if st.session_state.get("keys_ready"):
            st.success("✅ Siap")
        else:
            st.error("❌ Belum ada key")

    # Cek key
    if not st.session_state.get("keys_ready"):
        st.error(f"RSA key belum tersedia. Jalankan `python encrypt.py` di folder `autogenerate/` terlebih dahulu.")
        return

    # Placeholder untuk update realtime
    status_placeholder = st.empty()
    metric_placeholder  = st.empty()
    chart_placeholder   = st.empty()
    table_placeholder   = st.empty()
    enc_placeholder     = st.empty()

    def refresh_ui():
        history = st.session_state.history
        total   = st.session_state.total
        counts  = st.session_state.counts

        with status_placeholder.container():
            render_status_bar(st.session_state.running, mode, total)

        with metric_placeholder.container():
            render_metric_row(counts, total)

        with chart_placeholder.container():
            render_charts(history)

        with table_placeholder.container():
            render_table(history)

        with enc_placeholder.container():
            render_encryption_info(history)

    # Tampilkan state awal
    refresh_ui()

    # Loop realtime
    while st.session_state.running:
        try:
            if LIVE_MODE:
                payload = get_next_live_packet()
            else:
                payload = get_next_simulated_packet()

            if payload:
                label_name = payload.get("label_name", "Normal")

                # Simpan ke history
                st.session_state.history.append(payload)
                if len(st.session_state.history) > MAX_HISTORY:
                    st.session_state.history.pop(0)

                # Update statistik
                st.session_state.total += 1
                st.session_state.counts[label_name] = \
                    st.session_state.counts.get(label_name, 0) + 1

                refresh_ui()

            time.sleep(speed)

        except Exception as e:
            st.error(f"Error: {e}")
            st.session_state.running = False
            break


if __name__ == "__main__":
    main()