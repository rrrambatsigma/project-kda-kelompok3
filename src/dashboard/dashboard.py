"""
Smart Grid Security Dashboard
==============================
Sistem Deteksi Anomali & Enkripsi Data End-to-End
Menggunakan AES-GCM + RSA-OAEP hybrid encryption dengan simulasi streaming realtime.

Jalankan dari root project:
    streamlit run src/dashboard/dashboard.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes

# ─────────────────────────────────────────────
# KONFIGURASI PATH
# ─────────────────────────────────────────────

BASE_DIR: Path = Path(__file__).resolve().parents[2]
DATA_PATH: Path = BASE_DIR / "outputs" / "evaluation_data_with_predictions.csv"

# ─────────────────────────────────────────────
# KONSTANTA
# ─────────────────────────────────────────────

LABEL_MAP: dict[int, str] = {0: "AMAN", 1: "ATTACK", 2: "FAULT"}

STATUS_COLORS: dict[str, str] = {
    "AMAN":   "#2ecc71",
    "ATTACK": "#e74c3c",
    "FAULT":  "#f1c40f",
}

STREAM_DELAY: float = 0.4  # detik antar baris

# ─────────────────────────────────────────────
# KRIPTOGRAFI — AES-GCM + RSA-OAEP
# ─────────────────────────────────────────────

@st.cache_resource
def generate_rsa_keypair() -> tuple[bytes, bytes]:
    """Generate RSA-2048 key pair sekali, di-cache selama sesi."""
    key = RSA.generate(2048)
    return key.export_key(), key.public_key().export_key()


def encrypt_payload(data: dict[str, Any], pub_key_pem: bytes) -> dict[str, str]:
    """
    Enkripsi data dict menggunakan hybrid AES-GCM + RSA-OAEP.
    Mengembalikan dict berisi hex-encoded ciphertext, encrypted AES key, nonce, tag.
    """
    plaintext = json.dumps(data).encode("utf-8")
    aes_key = get_random_bytes(16)

    cipher_aes = AES.new(aes_key, AES.MODE_GCM)
    ciphertext, tag = cipher_aes.encrypt_and_digest(plaintext)

    cipher_rsa = PKCS1_OAEP.new(RSA.import_key(pub_key_pem))
    enc_aes_key = cipher_rsa.encrypt(aes_key)

    return {
        "enc_data": ciphertext.hex(),
        "enc_key":  enc_aes_key.hex(),
        "nonce":    cipher_aes.nonce.hex(),
        "tag":      tag.hex(),
    }


def decrypt_payload(pkg: dict[str, str], priv_key_pem: bytes) -> dict[str, Any]:
    """
    Dekripsi paket terenkripsi menggunakan private key RSA.
    Verifikasi integritas via GCM tag.
    """
    cipher_rsa = PKCS1_OAEP.new(RSA.import_key(priv_key_pem))
    aes_key = cipher_rsa.decrypt(bytes.fromhex(pkg["enc_key"]))

    cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=bytes.fromhex(pkg["nonce"]))
    plaintext = cipher_aes.decrypt_and_verify(
        bytes.fromhex(pkg["enc_data"]),
        bytes.fromhex(pkg["tag"]),
    )
    return json.loads(plaintext.decode("utf-8"))


# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────

def load_dataset(path: Path) -> pd.DataFrame | None:
    """
    Load CSV dari path yang diberikan.
    Return None jika file tidak ditemukan atau kosong.
    Validasi kolom wajib.
    """
    if not path.exists():
        st.error(
            f"❌ File tidak ditemukan:\n`{path}`\n\n"
            "Pastikan pipeline ensemble sudah dijalankan dan file output tersedia."
        )
        return None

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        st.error(f"❌ Gagal membaca CSV: {exc}")
        return None

    if df.empty:
        st.error("❌ File CSV ditemukan tetapi tidak mengandung data (kosong).")
        return None

    required_cols = {"ensemble_prediction", "voltage", "latency"}
    missing = required_cols - set(df.columns)
    if missing:
        st.error(
            f"❌ Kolom wajib tidak ditemukan di CSV: `{missing}`\n\n"
            f"Kolom tersedia: `{list(df.columns)}`"
        )
        return None

    return df


# ─────────────────────────────────────────────
# KOMPONEN UI
# ─────────────────────────────────────────────

def render_page_config() -> None:
    st.set_page_config(
        page_title="Secure Smart Grid Analytics",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def render_header() -> None:
    st.markdown(
        """
        <div style="text-align:center; padding: 1rem 0 0.5rem;">
            <h1 style="font-size:2.2rem; margin-bottom:0.2rem;">
                🛡️ Dashboard Keamanan Smart Grid
            </h1>
            <p style="color:#888; margin-top:0;">
                Sistem Deteksi Anomali &amp; Enkripsi Data End-to-End
                &nbsp;|&nbsp; AES-GCM + RSA-2048
            </p>
        </div>
        <hr style="border-color:#333; margin-bottom:1.5rem;">
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> tuple[bool, bool]:
    """Render sidebar dan return (start_clicked, reset_clicked)."""
    with st.sidebar:
        st.header("⚙️ Kontrol Sistem")
        st.info(
            "Dashboard ini mensimulasikan aliran data IoT dari Smart Grid "
            "dan menganalisis keamanan secara real-time menggunakan "
            "enkripsi hybrid AES-GCM + RSA-OAEP."
        )
        st.markdown("---")
        st.markdown(f"**📂 Data source:**\n\n`{DATA_PATH.relative_to(BASE_DIR)}`")
        st.markdown("---")
        start = st.button("🚀 Jalankan Streaming Data", use_container_width=True)
        reset = st.button("🗑️ Reset Statistik",          use_container_width=True)
        st.markdown("---")
        st.caption(f"Base dir: `{BASE_DIR}`")
    return start, reset


def render_metrics(hist_df: pd.DataFrame) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📥 Total Data Masuk", len(hist_df))
    c2.metric("✅ Normal (AMAN)",     len(hist_df[hist_df["status"] == "AMAN"]))
    c3.metric(
        "⚠️ Serangan (ATTACK)",
        len(hist_df[hist_df["status"] == "ATTACK"]),
        delta_color="inverse",
    )
    c4.metric("🛠️ Gangguan (FAULT)", len(hist_df[hist_df["status"] == "FAULT"]))


def render_charts(hist_df: pd.DataFrame) -> None:
    col_left, col_right = st.columns([1, 2])

    with col_left:
        fig_pie = px.pie(
            hist_df,
            names="status",
            title="Distribusi Status Keamanan",
            color="status",
            color_discrete_map=STATUS_COLORS,
            hole=0.35,
        )
        fig_pie.update_traces(textinfo="percent+label")
        fig_pie.update_layout(
            margin=dict(t=50, b=10, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_right:
        voltage_tail = hist_df["voltage"].tail(50).reset_index(drop=True)

        fig_line = go.Figure()
        fig_line.add_trace(
            go.Scatter(
                y=voltage_tail,
                mode="lines",
                name="Voltage",
                line=dict(color="#3498db", width=2),
                fill="tozeroy",
                fillcolor="rgba(52,152,219,0.1)",
            )
        )
        fig_line.update_layout(
            title="📈 Tren Tegangan Real-Time (50 data terakhir)",
            xaxis_title="Index",
            yaxis_title="Voltage",
            margin=dict(t=50, b=30, l=40, r=20),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_line, use_container_width=True)


def render_log_table(hist_df: pd.DataFrame) -> None:
    st.subheader("📑 Log Aktivitas Terverifikasi (5 Data Terbaru)")
    display_df = hist_df.tail(5).copy()
    display_df.index = range(len(hist_df) - len(display_df) + 1, len(hist_df) + 1)
    display_df["integritas"] = "🔐 Terverifikasi (AES-GCM)"

    # Urutkan kolom yang relevan
    cols_to_show = [c for c in ["voltage", "latency", "status", "integritas"] if c in display_df.columns]
    st.table(display_df[cols_to_show])


# ─────────────────────────────────────────────
# LOGIKA STREAMING
# ─────────────────────────────────────────────

def stream_data(
    df_raw: pd.DataFrame,
    pub_key_pem: bytes,
    priv_key_pem: bytes,
) -> None:
    """
    Iterasi baris df_raw, enkripsi + dekripsi tiap baris,
    lalu update placeholder UI secara realtime.
    """
    metric_spot = st.empty()
    chart_spot  = st.empty()
    table_spot  = st.empty()

    for i in range(len(df_raw)):
        row = df_raw.iloc[i]

        # Ambil label ensemble dan map ke string
        raw_label   = int(row["ensemble_prediction"])
        status_label = LABEL_MAP.get(raw_label, "UNKNOWN")

        # Payload yang akan dienkripsi
        payload: dict[str, Any] = {
            "voltage": float(row["voltage"]),
            "latency": float(row["latency"]),
            "status":  status_label,
        }

        # Simulasi pengiriman sensor → enkripsi
        encrypted_pkg = encrypt_payload(payload, pub_key_pem)

        # Simulasi penerimaan dashboard → dekripsi + verifikasi
        decrypted_payload = decrypt_payload(encrypted_pkg, priv_key_pem)

        # Simpan ke session state history
        st.session_state.history.append(decrypted_payload)
        hist_df = pd.DataFrame(st.session_state.history)

        # ── Update UI ──
        with metric_spot.container():
            render_metrics(hist_df)

        with chart_spot.container():
            render_charts(hist_df)

        with table_spot.container():
            render_log_table(hist_df)

        time.sleep(STREAM_DELAY)

    st.success(f"✅ Streaming selesai. Total {len(df_raw)} baris diproses.")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

def main() -> None:
    render_page_config()
    render_header()

    # Session state init
    if "history" not in st.session_state:
        st.session_state.history = []

    # RSA keys (cached)
    priv_key_pem, pub_key_pem = generate_rsa_keypair()

    start_clicked, reset_clicked = render_sidebar()

    # Reset
    if reset_clicked:
        st.session_state.history = []
        st.rerun()

    # Streaming
    if start_clicked:
        df_raw = load_dataset(DATA_PATH)
        if df_raw is not None:
            stream_data(df_raw, pub_key_pem, priv_key_pem)
    else:
        # Tampilkan snapshot terakhir jika ada history
        if st.session_state.history:
            hist_df = pd.DataFrame(st.session_state.history)
            render_metrics(hist_df)
            render_charts(hist_df)
            render_log_table(hist_df)
        else:
            st.warning(
                "⏳ Tekan **'🚀 Jalankan Streaming Data'** di sidebar untuk memulai simulasi."
            )


if __name__ == "__main__":
    main()