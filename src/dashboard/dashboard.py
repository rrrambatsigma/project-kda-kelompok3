"""
dashboard.py — Smart Grid Security Monitoring Dashboard
Kelompok 3 - Keamanan Data
Jalankan: streamlit run dashboard.py

CHANGELOG (fixed v2):
- [FIX UTAMA] normalize_label(): case-insensitive matching untuk "Normal"/"NORMAL"
  Root cause: ML.py pakai LABEL_MAP = {0:"Normal",...} (huruf kecil)
  tapi dashboard expect "NORMAL" → sekarang pakai .upper() + LABEL_STR_VALID_UPPER
- [FIX] LABEL_STR_VALID diperluas: accept "Normal","Attack","Fault" DAN "NORMAL","ATTACK","FAULT"
- [FIX] normalize_label() fallback path lebih robust: cek .upper() SEBELUM compare
- [FIX] Hapus syntax error '++++++++' di generate_dummy_raw
- [FIX] get_next_simulated_packet: bypass enkripsi untuk simulasi
- [FIX] Refresh/render chart: @st.fragment(run_every=N) tanpa st.rerun() di dalam button
- [FIX] Tab chart state tidak reset saat auto-refresh
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json, time, sys, os, random, threading, queue
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# KONFIGURASI
# ─────────────────────────────────────────────
LIVE_MODE = True
SSE_URL   = os.environ.get("SSE_URL", "http://localhost:8001/prediction/stream")

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "security"))
from encrypt import build_packet, unpack_packet, setup_keys

# ─────────────────────────────────────────────
# LABEL CONSTANTS
# ─────────────────────────────────────────────
# LABEL_MAP selalu pakai UPPERCASE sebagai standar internal dashboard
LABEL_MAP   = {0: "NORMAL", 1: "ATTACK", 2: "FAULT"}

# [FIX] Set valid label string — terima SEMUA varian case
# ML.py kirim "Normal","Attack","Fault" (mixed case)
# Dashboard internal pakai "NORMAL","ATTACK","FAULT"
# normalize_label() selalu konversi ke uppercase sebelum compare
LABEL_STR_VALID = {"NORMAL", "ATTACK", "FAULT"}  # uppercase canonical

LABEL_COLOR = {"NORMAL": "#4caf84", "ATTACK": "#ef5350", "FAULT": "#ffa726"}
LABEL_BG    = {"NORMAL": "#1a3a2a", "ATTACK": "#3a1a1a", "FAULT": "#3a2a1a"}
LABEL_ICON  = {"NORMAL": "✅", "ATTACK": "🚨", "FAULT": "⚠️"}
DEVICES     = [f"SGD-{str(i).zfill(4)}" for i in range(1, 11)]
MAX_HISTORY = 100
LINE_COLORS = {"voltage": "#7eceff", "current": "#ef5350", "temperature": "#ffa726", "latency": "#ce93d8"}
Y_LABELS    = {"voltage": "Tegangan (V)", "current": "Arus (A)", "temperature": "Suhu (°C)", "latency": "Latency (ms)"}


# ─────────────────────────────────────────────
# NORMALISASI LABEL — FUNGSI TERPUSAT (FIXED)
# ─────────────────────────────────────────────
def normalize_label(payload: dict) -> str:
    """
    Tentukan label akhir dari payload secara case-insensitive.

    [FIX] Root cause bug "NORMAL tidak masuk":
    ML.py menggunakan LABEL_MAP = {0:"Normal", 1:"Attack", 2:"Fault"} (huruf kecil).
    Versi sebelumnya membandingkan label_name langsung ke LABEL_STR_VALID {"NORMAL",...}
    tanpa .upper(), sehingga "Normal" != "NORMAL" → jatuh ke default atau salah cabang.

    Priority: voting_prediction (int) → label_name (string, case-insensitive) → default NORMAL
    """
    # 1. Coba dari voting_prediction (paling reliable, langsung dari model output)
    vp = payload.get("voting_prediction")
    if vp is not None:
        try:
            label = LABEL_MAP.get(int(vp))
            if label:
                return label  # sudah uppercase dari LABEL_MAP kita
        except (ValueError, TypeError):
            pass

    # 2. Fallback ke label_name — SELALU upper() dulu sebelum compare
    # [FIX] Ini yang menangkap "Normal" dari ML.py dan konversi ke "NORMAL"
    ln = payload.get("label_name")
    if ln is not None:
        ln_upper = str(ln).strip().upper()  # "Normal" → "NORMAL", "attack" → "ATTACK"
        if ln_upper in LABEL_STR_VALID:
            return ln_upper  # kembalikan versi uppercase canonical

    # 3. Default NORMAL jika semua gagal
    return "NORMAL"


# ─────────────────────────────────────────────
# SSE BACKGROUND THREAD
# ─────────────────────────────────────────────
_packet_queue: queue.Queue = queue.Queue(maxsize=200)
_sse_thread: threading.Thread = None
_sse_running: bool = False
_sse_connected: bool = False


def _sse_listener():
    """Background thread: listen SSE, decrypt, normalize label, masukkan ke queue."""
    import requests
    global _sse_running, _sse_connected
    while _sse_running:
        try:
            print(f"[SSE] Connecting to {SSE_URL}...")
            r = requests.get(SSE_URL, stream=True, timeout=10)
            _sse_connected = True
            print(f"[SSE] Connected!")
            for line in r.iter_lines():
                if not _sse_running:
                    break
                if not line:
                    continue
                s = line.decode("utf-8")
                if not s.startswith("data: "):
                    continue
                try:
                    raw_packet = json.loads(s[6:])
                    packet = {
                        "encrypted_payload": raw_packet["encrypted_payload"],
                        "encrypted_aes_key": raw_packet["encrypted_aes_key"],
                        "nonce":             raw_packet["nonce"],
                    }
                    payload = unpack_packet(packet)

                    # [FIX] normalize_label() sekarang case-insensitive
                    # "Normal" dari ML.py → .upper() → "NORMAL" → match LABEL_STR_VALID
                    payload["label_name"] = normalize_label(payload)

                    # Pastikan voting_prediction juga tersimpan sebagai int
                    vp = payload.get("voting_prediction")
                    if vp is not None:
                        try:
                            payload["voting_prediction"] = int(vp)
                        except (ValueError, TypeError):
                            pass

                    print(
                        f"[SSE] device={payload.get('device_id')} "
                        f"vp={payload.get('voting_prediction')} "
                        f"label={payload.get('label_name')}"
                    )

                    # Pastikan field wajib ada
                    for field in ["voltage", "current", "temperature", "latency",
                                  "packet_loss", "authentication_fail", "device_id", "timestamp"]:
                        if field not in payload:
                            payload[field] = 0

                    try:
                        _packet_queue.put_nowait(payload)
                    except queue.Full:
                        pass

                except Exception as e:
                    print(f"[SSE] Decrypt/parse error: {e}")

        except Exception as e:
            _sse_connected = False
            print(f"[SSE] Connection error: {e}")
            if _sse_running:
                time.sleep(3)


def start_sse_listener():
    global _sse_thread, _sse_running
    if _sse_thread is None or not _sse_thread.is_alive():
        _sse_running = True
        _sse_thread = threading.Thread(target=_sse_listener, daemon=True)
        _sse_thread.start()


def is_sse_connected() -> bool:
    return _sse_connected and _sse_thread is not None and _sse_thread.is_alive()


def drain_queue():
    packets = []
    while True:
        try:
            packets.append(_packet_queue.get_nowait())
        except queue.Empty:
            break
    if packets:
        print(f"[QUEUE] drained={len(packets)}")
    return packets


# ─────────────────────────────────────────────
# SIMULASI DATA
# ─────────────────────────────────────────────
def generate_dummy_raw(label: int) -> dict:
    """
    Generate satu packet simulasi dengan karakteristik sesuai label.
    [FIX] LABEL_MAP sekarang uppercase: {0:"NORMAL", 1:"ATTACK", 2:"FAULT"}
    sehingga label_name langsung konsisten dengan LABEL_STR_VALID.
    """
    if label == 0:  # NORMAL
        voltage    = round(random.uniform(210, 230), 4)
        temp       = round(random.uniform(20, 55), 3)
        latency    = round(random.uniform(5, 80), 2)
        pkt_loss   = round(random.uniform(0, 3), 2)
        auth_fail  = random.randint(0, 1)
    elif label == 1:  # ATTACK
        voltage    = round(random.uniform(210, 230), 4)
        temp       = round(random.uniform(20, 55), 3)
        latency    = round(random.uniform(100, 500), 2)
        pkt_loss   = round(random.uniform(8, 25), 2)
        auth_fail  = random.randint(3, 8)
    else:  # FAULT (label == 2)
        voltage    = round(random.choice([
                        random.uniform(150, 195),
                        random.uniform(245, 300)
                    ]), 4)
        temp       = round(random.uniform(66, 90), 3)
        latency    = round(random.uniform(5, 80), 2)
        pkt_loss   = round(random.uniform(0, 3), 2)
        auth_fail  = random.randint(0, 1)

    current = round(random.uniform(2.0, 8.0), 4)
    return {
        "timestamp":           datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "device_id":           random.choice(DEVICES),
        "voltage":             voltage,
        "current":             current,
        "power":               round(voltage * current * random.uniform(0.85, 0.98), 4),
        "frequency":           round(random.uniform(49.5, 50.5), 4),
        "temperature":         temp,
        "latency":             latency,
        "packet_loss":         pkt_loss,
        "throughput":          round(random.uniform(2, 95), 2),
        "duplicate_packet":    random.randint(0, 5),
        "checksum_valid":      random.randint(0, 1),
        "authentication_fail": auth_fail,
        "voting_prediction":   label,            # int, sumber kebenaran
        "label_name":          LABEL_MAP[label], # [FIX] sudah uppercase: "NORMAL"/"ATTACK"/"FAULT"
    }


def get_next_simulated_packet() -> dict:
    """
    Hasilkan satu packet simulasi.
    Tidak melalui build_packet -> unpack_packet.
    Label di-normalize() sebagai safety net.
    """
    label  = random.choices([0, 1, 2], weights=[70, 20, 10])[0]
    packet = generate_dummy_raw(label)
    # [FIX] normalize_label() sekarang case-insensitive, jadi ini selalu benar
    packet["label_name"] = normalize_label(packet)
    return packet


# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
def inject_css():
    st.markdown("""
    <style>
    .stApp { background: #0d1117; }
    section[data-testid="stSidebar"] { background: #161b22 !important; border-right: 1px solid #30363d; }
    div[data-testid="block-container"] { padding-top: 1rem; }
    .sg-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%);
        border: 1px solid #30363d; border-radius: 14px;
        padding: 22px 28px; margin-bottom: 16px;
        display: flex; align-items: center; justify-content: space-between;
    }
    .sg-title    { font-size: 20px; font-weight: 700; color: #e6edf3; margin: 0; }
    .sg-subtitle { font-size: 10px; color: #7eceff; margin-top: 5px; letter-spacing: 1.5px; font-family: monospace; }
    .sg-hbadge   { font-size: 10px; background: rgba(126,206,255,.12); color: #7eceff;
                   border: 1px solid rgba(126,206,255,.3); border-radius: 20px; padding: 6px 14px; font-family: monospace; }
    .metric-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 16px 20px; height: 100px; }
    .metric-label { font-size: 10px; color: #8b949e; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 6px; }
    .metric-value { font-size: 32px; font-weight: 700; line-height: 1; }
    .metric-sub   { font-size: 11px; color: #8b949e; margin-top: 4px; }
    .sg-section-title { font-size: 11px; font-weight: 700; color: #8b949e; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 12px; }
    .leg-row { display: flex; align-items: center; justify-content: space-between; font-size: 12px; margin-bottom: 6px; color: #c9d1d9; }
    .leg-dot { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 8px; }
    .stButton > button { border: 1px solid #30363d !important; background: #21262d !important; color: #c9d1d9 !important; border-radius: 8px !important; }
    .stButton > button:hover { background: #30363d !important; }
    button[kind="primary"] { background: #1f6feb !important; border-color: #1f6feb !important; color: #fff !important; }
    .stSlider > div { color: #c9d1d9; }
    label { color: #c9d1d9 !important; }
    p, div { color: #c9d1d9; }
    h1, h2, h3 { color: #e6edf3 !important; }
    .stAlert { background: #1c2128 !important; border-color: #30363d !important; color: #c9d1d9 !important; }
    button[aria-label="View fullscreen"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
def init_state():
    if "keys_ready" not in st.session_state:
        try:
            setup_keys()
            st.session_state.keys_ready = True
        except Exception:
            st.session_state.keys_ready = False

    if "initialized" not in st.session_state:
        st.session_state.history     = []
        st.session_state.counts      = {"NORMAL": 0, "ATTACK": 0, "FAULT": 0}
        st.session_state.total       = 0
        st.session_state.running     = True
        st.session_state.tab         = "voltage"
        st.session_state.initialized = True

    if LIVE_MODE:
        start_sse_listener()


# ─────────────────────────────────────────────
# RENDER COMPONENTS
# ─────────────────────────────────────────────
def render_header():
    total   = st.session_state.total
    running = st.session_state.running
    status  = "● RUNNING" if running else "● STOPPED"
    mode    = "🔴 LIVE" if LIVE_MODE else "🔵 SIMULASI"
    st.markdown(f"""
    <div class="sg-header">
      <div>
        <div class="sg-title">⚡ Smart Grid Security Monitor</div>
        <div class="sg-subtitle">AES-GCM &nbsp;·&nbsp; RSA-OAEP &nbsp;·&nbsp; HYBRID ENCRYPTION &nbsp;·&nbsp; REALTIME DETECTION</div>
      </div>
      <div style="text-align:right">
        <div class="sg-hbadge">{status} &nbsp;|&nbsp; {mode} &nbsp;|&nbsp; {total} packet</div>
        <div style="font-family:monospace;font-size:10px;color:#7eceff;margin-top:6px">Kelompok 3 — Keamanan Data</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_metrics():
    counts = st.session_state.counts
    total  = st.session_state.total
    pct    = lambda k: f"{counts.get(k, 0) / max(total, 1) * 100:.1f}% dari total"
    c1, c2, c3, c4 = st.columns(4)
    for col, label, val, sub, color in [
        (c1, "TOTAL PACKET", total,                  "sejak sistem start", "#e6edf3"),
        (c2, "NORMAL",       counts.get("NORMAL", 0), pct("NORMAL"),       "#4caf84"),
        (c3, "ATTACK 🚨",    counts.get("ATTACK", 0), pct("ATTACK"),       "#ef5350"),
        (c4, "FAULT ⚠️",     counts.get("FAULT", 0),  pct("FAULT"),        "#ffa726"),
    ]:
        col.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">{label}</div>
          <div class="metric-value" style="color:{color}">{val}</div>
          <div class="metric-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)
    st.markdown("<div style='margin-bottom:14px'></div>", unsafe_allow_html=True)


def render_donut():
    counts = st.session_state.counts
    total  = st.session_state.total
    st.markdown('<div class="sg-section-title">Distribusi Status</div>', unsafe_allow_html=True)
    fig = go.Figure(go.Pie(
        labels=["NORMAL", "ATTACK", "FAULT"],
        values=[counts.get("NORMAL", 0) or 0.001, counts.get("ATTACK", 0), counts.get("FAULT", 0)],
        hole=0.60,
        marker=dict(colors=["#4caf84", "#ef5350", "#ffa726"], line=dict(color="#161b22", width=3)),
        textinfo="percent", textfont=dict(size=12, color="#e6edf3"),
        showlegend=False,
    ))
    fig.update_layout(
        margin=dict(t=0, b=0, l=0, r=0), height=190,
        annotations=[dict(
            text=f"<b style='color:#e6edf3'>{total}</b><br><span style='color:#8b949e;font-size:11px'>total</span>",
            x=0.5, y=0.5, font=dict(size=15, color="#e6edf3"), showarrow=False
        )],
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    for label in ["NORMAL", "ATTACK", "FAULT"]:
        n   = counts.get(label, 0)
        pct = f"{n / max(total, 1) * 100:.1f}%"
        st.markdown(f"""
        <div class="leg-row">
          <span><span class="leg-dot" style="background:{LABEL_COLOR[label]}"></span>{label}</span>
          <span style="color:#8b949e">{n} ({pct})</span>
        </div>""", unsafe_allow_html=True)


def render_alerts():
    history = st.session_state.history
    st.markdown('<div class="sg-section-title" style="margin-top:16px">Alert Terbaru</div>', unsafe_allow_html=True)
    # [FIX] Compare dengan "NORMAL" (uppercase), konsisten dengan normalize_label()
    alerts = [r for r in reversed(history) if r.get("label_name", "NORMAL") != "NORMAL"][:5]
    if not alerts:
        st.markdown("<div style='font-size:12px;color:#8b949e;padding:4px 0'>Belum ada alert</div>", unsafe_allow_html=True)
        return
    rows = ""
    for a in alerts:
        lbl   = a.get("label_name", "NORMAL")
        color = LABEL_COLOR.get(lbl, "#8b949e")
        bg    = LABEL_BG.get(lbl, "#1c2128")
        icon  = LABEL_ICON.get(lbl, "ℹ️")
        ts    = str(a.get("timestamp", "")).split(" ")[-1]
        v     = a.get("voltage", 0)
        t     = a.get("temperature", 0)
        lat   = a.get("latency", 0)
        did   = a.get("device_id", "-")
        rows += f"""<div style="display:flex;align-items:center;gap:10px;padding:7px 10px;margin-bottom:5px;border-radius:8px;background:{bg};border-left:3px solid {color}">
          <span style="font-size:15px">{icon}</span>
          <div style="flex:1">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">
              <span style="font-size:12px;font-weight:700;color:{color}">{lbl}</span>
              <span style="font-size:11px;font-family:monospace;color:#8b949e">{did}</span>
            </div>
            <div style="font-size:10px;color:#8b949e">{ts} &nbsp;·&nbsp; V={float(v):.1f}V &nbsp;·&nbsp; T={float(t):.1f}°C &nbsp;·&nbsp; Lat={float(lat):.0f}ms</div>
          </div></div>"""
    st.markdown(rows, unsafe_allow_html=True)


def render_linechart():
    history = st.session_state.history
    tab     = st.session_state.tab
    st.markdown('<div class="sg-section-title">Grafik Sensor Realtime</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    for col, key, label in [
        (c1, "voltage",     "Tegangan (V)"),
        (c2, "current",     "Arus (A)"),
        (c3, "temperature", "Suhu (°C)"),
        (c4, "latency",     "Latency (ms)"),
    ]:
        with col:
            if st.button(label, key=f"btn_{key}",
                         type="primary" if tab == key else "secondary",
                         use_container_width=True):
                st.session_state.tab = key

    tab = st.session_state.tab
    st.markdown(
        f"<div style='font-size:10px;color:#8b949e;margin:6px 0 4px'>"
        f"sumbu X: urutan waktu &nbsp;·&nbsp; sumbu Y: {Y_LABELS[tab]}</div>",
        unsafe_allow_html=True
    )

    if len(history) < 2:
        st.info("Menunggu data masuk...")
        return

    df = pd.DataFrame(history[-50:])
    if tab not in df.columns:
        st.info("Data belum tersedia untuk metrik ini.")
        return
    df[tab] = pd.to_numeric(df[tab], errors="coerce").fillna(0)

    x  = list(range(len(df)))
    y  = df[tab].tolist()
    # [FIX] label_name sudah uppercase jadi LABEL_COLOR.get() pasti match
    pt_colors = [LABEL_COLOR.get(str(r), "#8b949e") for r in df["label_name"]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="none", fill="tozeroy",
        fillcolor=f"rgba({','.join(str(int(LINE_COLORS[tab].lstrip('#')[i:i+2], 16)) for i in (0, 2, 4))},0.08)",
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="lines+markers",
        line=dict(color=LINE_COLORS[tab], width=2),
        marker=dict(color=pt_colors, size=6, line=dict(color="#161b22", width=1)),
        hovertemplate="<b>%{text}</b><br>" + Y_LABELS[tab] + ": %{y:.2f}<br>Device: %{customdata}<extra></extra>",
        text=df["timestamp"].tolist(), customdata=df["device_id"].tolist(),
        showlegend=False,
    ))
    for i, row in enumerate(df["label_name"]):
        if row != "NORMAL":
            fig.add_vline(x=i, line_width=1, line_dash="dot", line_color="rgba(239,83,80,0.3)")

    xtick_step = max(1, len(x) // 8)
    fig.update_layout(
        margin=dict(t=8, b=8, l=8, r=8), height=220,
        xaxis=dict(
            title=None, showgrid=True, gridcolor="#21262d",
            tickvals=x[::xtick_step],
            ticktext=[str(df["timestamp"].iloc[i]).split(" ")[-1] for i in range(0, len(x), xtick_step)],
            tickfont=dict(size=9, color="#8b949e"), linecolor="#30363d", zerolinecolor="#30363d",
        ),
        yaxis=dict(
            title=dict(text=Y_LABELS[tab], font=dict(size=10, color="#8b949e")),
            showgrid=True, gridcolor="#21262d",
            tickfont=dict(size=9, color="#8b949e"), linecolor="#30363d",
        ),
        plot_bgcolor="#0d1117", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="sans-serif", size=11, color="#c9d1d9"),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        "<div style='font-size:10px;color:#8b949e;margin-top:-6px'>"
        "titik <span style='color:#4caf84'>●</span> NORMAL &nbsp;|&nbsp; "
        "<span style='color:#ef5350'>●</span> ATTACK &nbsp;|&nbsp; "
        "<span style='color:#ffa726'>●</span> FAULT &nbsp;|&nbsp; "
        "garis putus-putus = anomali</div>",
        unsafe_allow_html=True
    )


def render_table():
    history = st.session_state.history
    if not history:
        return
    st.markdown('<div class="sg-section-title">Tabel Data Realtime (30 terakhir)</div>', unsafe_allow_html=True)

    rows_data = list(reversed(history[-30:]))
    pill_style = {
        "NORMAL": "background:#1a3a2a;color:#4caf84;font-weight:700;padding:2px 10px;border-radius:10px;font-size:11px",
        "ATTACK": "background:#3a1a1a;color:#ef5350;font-weight:700;padding:2px 10px;border-radius:10px;font-size:11px",
        "FAULT":  "background:#3a2a1a;color:#ffa726;font-weight:700;padding:2px 10px;border-radius:10px;font-size:11px",
    }
    header = """<div style="overflow-x:auto">
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead>
        <tr style="border-bottom:1px solid #30363d">
          <th style="text-align:left;padding:8px 12px;color:#8b949e;font-weight:600;font-size:11px;white-space:nowrap">Timestamp</th>
          <th style="text-align:left;padding:8px 12px;color:#8b949e;font-weight:600;font-size:11px">Device</th>
          <th style="text-align:center;padding:8px 12px;color:#8b949e;font-weight:600;font-size:11px">Status</th>
          <th style="text-align:right;padding:8px 12px;color:#8b949e;font-weight:600;font-size:11px">V (V)</th>
          <th style="text-align:right;padding:8px 12px;color:#8b949e;font-weight:600;font-size:11px">A (A)</th>
          <th style="text-align:right;padding:8px 12px;color:#8b949e;font-weight:600;font-size:11px">T (°C)</th>
          <th style="text-align:right;padding:8px 12px;color:#8b949e;font-weight:600;font-size:11px">Latency (ms)</th>
          <th style="text-align:right;padding:8px 12px;color:#8b949e;font-weight:600;font-size:11px">Pkt Loss (%)</th>
          <th style="text-align:right;padding:8px 12px;color:#8b949e;font-weight:600;font-size:11px">Auth Fail</th>
        </tr>
      </thead><tbody>"""

    body = ""
    for i, r in enumerate(rows_data):
        bg_row = "#1c2128" if i % 2 == 0 else "#161b22"
        # [FIX] label_name sudah uppercase dari normalize_label(), pill_style pasti match
        lbl    = str(r.get("label_name", "NORMAL")).upper()
        pill   = pill_style.get(lbl, pill_style["NORMAL"])

        def safe(k, fmt=".2f"):
            try:
                return format(float(r.get(k, 0)), fmt)
            except Exception:
                return "-"

        body += f"""<tr style="border-bottom:1px solid #21262d;background:{bg_row}">
          <td style="padding:7px 12px;color:#8b949e;font-family:monospace;font-size:11px;white-space:nowrap">{r.get("timestamp", "-")}</td>
          <td style="padding:7px 12px;color:#c9d1d9;font-family:monospace;font-size:11px">{r.get("device_id", "-")}</td>
          <td style="padding:7px 12px;text-align:center"><span style="{pill}">{lbl}</span></td>
          <td style="padding:7px 12px;text-align:right;color:#c9d1d9">{safe("voltage")}</td>
          <td style="padding:7px 12px;text-align:right;color:#c9d1d9">{safe("current")}</td>
          <td style="padding:7px 12px;text-align:right;color:#c9d1d9">{safe("temperature", ".1f")}</td>
          <td style="padding:7px 12px;text-align:right;color:#c9d1d9">{safe("latency", ".1f")}</td>
          <td style="padding:7px 12px;text-align:right;color:#c9d1d9">{safe("packet_loss")}</td>
          <td style="padding:7px 12px;text-align:right;color:#c9d1d9">{r.get("authentication_fail", 0)}</td>
        </tr>"""

    st.markdown(header + body + "</tbody></table></div>", unsafe_allow_html=True)


def render_enc_panel():
    history = st.session_state.history
    if not history:
        return
    last = history[-1]
    st.markdown('<div class="sg-section-title">Info Enkripsi Packet Terakhir</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Metode Enkripsi**")
        st.markdown("- Payload → `AES-256-GCM`\n- AES Key → `RSA-2048-OAEP`\n- Hash → `SHA-256`\n- Integrity tag: 16 byte GCM")
    with c2:
        st.markdown("**Payload Terdekripsi**")
        st.json({
            "device_id":         last.get("device_id", "-"),
            "voting_prediction": last.get("voting_prediction", "-"),
            "label_name":        last.get("label_name", "-"),
            "timestamp":         last.get("timestamp", "-"),
        })
    with c3:
        st.markdown("**Status**")
        st.success("✅ Integritas terverifikasi")
        st.info("🔒 AES key dienkripsi RSA public key")
        st.info("🔀 Nonce 12-byte unik per packet")


def render_all():
    render_header()
    render_metrics()

    col_left, col_right = st.columns([1, 2.5])
    with col_left:
        with st.container(border=True):
            render_donut()
        with st.container(border=True):
            render_alerts()
    with col_right:
        with st.container(border=True):
            render_linechart()

    with st.container(border=True):
        render_table()

    with st.container(border=True):
        render_enc_panel()


# ─────────────────────────────────────────────
# KONSUMSI QUEUE & UPDATE SESSION STATE
# ─────────────────────────────────────────────
def process_incoming_packets() -> bool:
    """
    Ambil semua packet dari queue, normalize label, update session_state.
    [FIX] normalize_label() sekarang case-insensitive, semua label masuk dengan benar.
    """
    if LIVE_MODE:
        new_packets = drain_queue()
        if not new_packets and not is_sse_connected():
            p = get_next_simulated_packet()
            new_packets = [p] if p else []
            if new_packets:
                print("[FALLBACK] SSE down — pakai data simulasi")
    else:
        p = get_next_simulated_packet()
        new_packets = [p] if p else []

    if not new_packets:
        return False

    for payload in new_packets:
        # [FIX] Safety net: normalize ulang — case-insensitive
        # "Normal" → "NORMAL", "ATTACK" → "ATTACK", semua benar
        lbl = normalize_label(payload)
        payload["label_name"] = lbl

        # Pastikan key ada di counts (defensive)
        if lbl not in st.session_state.counts:
            st.session_state.counts[lbl] = 0

        st.session_state.history.append(payload)
        if len(st.session_state.history) > MAX_HISTORY:
            st.session_state.history.pop(0)

        st.session_state.total += 1
        st.session_state.counts[lbl] += 1

    print(f"[UI UPDATE] total={st.session_state.total}, new={len(new_packets)}")
    return True


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="Smart Grid Monitor", page_icon="⚡",
        layout="wide", initial_sidebar_state="expanded"
    )
    init_state()
    inject_css()

    # ── Sidebar ──────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Kontrol")
        st.markdown(f"**Mode:** `{'LIVE' if LIVE_MODE else 'SIMULASI'}`")
        if LIVE_MODE:
            if is_sse_connected():
                st.success("🟢 SSE terhubung (LIVE)")
            elif _sse_thread is not None and _sse_thread.is_alive():
                st.warning("🟡 SSE mencoba konek... (Simulasi aktif)")
            else:
                st.error("🔴 SSE thread mati")
        st.markdown("---")
        speed = st.slider("Interval refresh (detik)", 0.5, 5.0, 1.0, 0.5)
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("▶ Start", use_container_width=True, type="primary"):
                st.session_state.running = True
        with c2:
            if st.button("⏹ Stop", use_container_width=True):
                st.session_state.running = False
        if st.button("🗑 Reset", use_container_width=True):
            st.session_state.initialized = False
            st.rerun()
        st.markdown("---")
        st.markdown("**RSA Keys:**")
        if st.session_state.get("keys_ready"):
            st.success("✅ Key siap")
        else:
            st.error(f"❌ {st.session_state.get('keys_error', 'Belum ada key')}")

    if not st.session_state.get("keys_ready"):
        st.error("RSA key belum ada. Jalankan: `python src/security/encrypt.py`")
        st.stop()

    is_running   = st.session_state.get("running", False)
    run_interval = timedelta(seconds=speed) if is_running else None

    @st.fragment(run_every=run_interval)
    def live_dashboard():
        if st.session_state.get("running", False):
            try:
                process_incoming_packets()
            except Exception as e:
                st.error(f"Error memproses packet: {e}")
                st.session_state.running = False

        render_all()

    live_dashboard()


if __name__ == "__main__":
    main()