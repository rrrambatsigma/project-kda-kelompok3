import streamlit as st
import pandas as pd
import time
import json
import plotly.express as px
import requests
from datetime import datetime
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes

# --- FUNGSI KRIPTOGRAFI (AES-RSA) ---
@st.cache_resource
def generate_keys():
    key = RSA.generate(2048)
    return key.export_key(), key.public_key().export_key()

private_key_raw, public_key_raw = generate_keys()

def encrypt_data(data_dict, pub_key_str):
    data_bytes = json.dumps(data_dict).encode('utf-8')
    aes_key = get_random_bytes(16)
    cipher_aes = AES.new(aes_key, AES.MODE_GCM)
    ciphertext, tag = cipher_aes.encrypt_and_digest(data_bytes)
    recipient_key = RSA.import_key(pub_key_str)
    cipher_rsa = PKCS1_OAEP.new(recipient_key)
    enc_aes_key = cipher_rsa.encrypt(aes_key)
    return {
        "enc_data": ciphertext.hex(), 
        "enc_key": enc_aes_key.hex(), 
        "nonce": cipher_aes.nonce.hex(), 
        "tag": tag.hex()
    }

def decrypt_data(enc_dict, priv_key_str):
    private_key = RSA.import_key(priv_key_str)
    cipher_rsa = PKCS1_OAEP.new(private_key)
    aes_key = cipher_rsa.decrypt(bytes.fromhex(enc_dict['enc_key']))
    cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=bytes.fromhex(enc_dict['nonce']))
    dec_data = cipher_aes.decrypt_and_verify(bytes.fromhex(enc_dict['enc_data']), bytes.fromhex(enc_dict['tag']))
    return json.loads(dec_data.decode('utf-8'))

# --- FUNGSI PREDIKSI REAL-TIME ---
def predict_label(row_data):
    """
    Prediksi label berdasarkan heuristic sederhana.
    Dalam produksi, gunakan model ML yang sudah di-training.
    """
    voltage = row_data.get('voltage', 220)
    temp = row_data.get('temperature', 30)
    auth_fail = row_data.get('authentication_fail', 0)
    packet_loss = row_data.get('packet_loss', 0)
    
    # Attack indicators
    if auth_fail > 2 or packet_loss > 10:
        return "ATTACK"
    
    # Fault indicators
    if temp > 65 or voltage < 200 or voltage > 240:
        return "FAULT"
    
    # Normal
    return "AMAN"

# --- PENGATURAN HALAMAN ---
st.set_page_config(page_title="Secure Smart Grid Analytics", layout="wide")

st.markdown(f"""
    <div style="text-align: center;">
        <h1>🛡️ Dashboard Keamanan Smart Grid (Real-Time)</h1>
        <p style="color: gray;">Sistem Deteksi Anomali & Enkripsi Data End-to-End</p>
    </div>
    """, unsafe_allow_html=True)

# State untuk menyimpan riwayat data
if 'history' not in st.session_state:
    st.session_state.history = []
if 'is_streaming' not in st.session_state:
    st.session_state.is_streaming = False

# --- SIDEBAR CONTROL ---
with st.sidebar:
    st.header("⚙️ Kontrol Sistem")
    st.info("Dashboard ini menampilkan data IoT real-time dari Smart Grid dengan enkripsi end-to-end.")
    
    # Konfigurasi streaming
    stream_url = st.text_input("🌐 Streaming URL", value="http://localhost:8080/data/latest")
    refresh_rate = st.slider("⏱️ Refresh Rate (detik)", min_value=0.5, max_value=5.0, value=1.0, step=0.5)
    
    col1, col2 = st.columns(2)
    with col1:
        start_btn = st.button("🚀 Mulai", use_container_width=True)
    with col2:
        stop_btn = st.button("🛑 Stop", use_container_width=True)
    
    if st.button("🗑️ Reset Statistik", use_container_width=True):
        st.session_state.history = []
        st.rerun()
    
    # Status koneksi
    st.divider()
    if st.session_state.is_streaming:
        st.success("🟢 Streaming Aktif")
    else:
        st.warning("🔴 Streaming Tidak Aktif")

# Handle button clicks
if start_btn:
    st.session_state.is_streaming = True
if stop_btn:
    st.session_state.is_streaming = False

# --- LOGIKA STREAMING REAL-TIME ---
if st.session_state.is_streaming:
    # Placeholder agar tampilan tidak kedap-kedip
    metric_spot = st.empty()
    chart_spot = st.empty()
    table_spot = st.empty()
    status_spot = st.empty()
    
    try:
        # Fetch data dari streaming server
        response = requests.get(stream_url, timeout=5)
        
        if response.status_code == 200:
            raw_data = response.json()
            
            # Prediksi label menggunakan heuristic
            status_label = predict_label(raw_data)
            
            # 1. Simulasi Pengiriman: Enkripsi di sisi 'Sensor'
            payload = {
                "timestamp": raw_data.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "device_id": raw_data.get('device_id', 'N/A'),
                "voltage": float(raw_data.get('voltage', 0)),
                "current": float(raw_data.get('current', 0)),
                "temperature": float(raw_data.get('temperature', 0)),
                "latency": float(raw_data.get('latency', 0)),
                "packet_loss": float(raw_data.get('packet_loss', 0)),
                "status": status_label
            }
            encrypted_pkg = encrypt_data(payload, public_key_raw)
            
            # 2. Simulasi Penerimaan: Dekripsi di sisi 'Dashboard'
            decrypted_payload = decrypt_data(encrypted_pkg, private_key_raw)
            
            # Simpan ke memori dashboard
            st.session_state.history.append(decrypted_payload)
            
            # Batasi history maksimal 1000 data
            if len(st.session_state.history) > 1000:
                st.session_state.history = st.session_state.history[-1000:]
            
            hist_df = pd.DataFrame(st.session_state.history)

            # --- VISUALISASI ---
            
            # A. Baris Metrik (Counter)
            with metric_spot.container():
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Data Masuk", len(hist_df))
                c2.metric("Normal ✅", len(hist_df[hist_df['status'] == "AMAN"]))
                c3.metric("Serangan ⚠️", len(hist_df[hist_df['status'] == "ATTACK"]), delta_color="inverse")
                c4.metric("Gangguan Alat 🛠️", len(hist_df[hist_df['status'] == "FAULT"]))

            # B. Grafik (Charts)
            with chart_spot.container():
                col_left, col_right = st.columns([1, 2])
                
                with col_left:
                    if len(hist_df) > 0:
                        fig_pie = px.pie(
                            hist_df, names='status', title="Distribusi Keamanan",
                            color='status',
                            color_discrete_map={'AMAN':'#2ecc71', 'ATTACK':'#e74c3c', 'FAULT':'#f1c40f'}
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)
                
                with col_right:
                    st.subheader("📈 Tren Tegangan Real-Time (Voltage)")
                    if len(hist_df) > 0:
                        st.line_chart(hist_df['voltage'].tail(100))  # Tampilkan 100 data terakhir

            # C. Tabel Detail & Bukti Enkripsi
            with table_spot.container():
                st.subheader("📑 Log Aktivitas Terverifikasi")
                if len(hist_df) > 0:
                    # Menampilkan 10 data terbaru
                    display_df = hist_df.tail(10).copy()
                    display_df['Integritas'] = "🔐 Terverifikasi (AES-GCM)"
                    # Reorder columns
                    cols = ['timestamp', 'device_id', 'voltage', 'current', 'temperature', 'status', 'Integritas']
                    display_df = display_df[[c for c in cols if c in display_df.columns]]
                    st.dataframe(display_df, use_container_width=True)

            # D. Status Update
            with status_spot.container():
                st.success(f"✅ Data terbaru diterima: {decrypted_payload.get('timestamp', 'N/A')} | Device: {decrypted_payload.get('device_id', 'N/A')}")
            
            # Auto-refresh
            time.sleep(refresh_rate)
            st.rerun()
        
        else:
            st.error(f"❌ Error: HTTP {response.status_code} - Tidak dapat terhubung ke streaming server")
            st.info("💡 Pastikan streaming server berjalan di: `python auto_generate.py --port 8080 --rate 10`")
            st.session_state.is_streaming = False
    
    except requests.exceptions.ConnectionError:
        st.error("❌ Koneksi Gagal: Tidak dapat terhubung ke streaming server")
        st.info("💡 Pastikan streaming server berjalan di: `python auto_generate.py --port 8080 --rate 10`")
        st.session_state.is_streaming = False
    
    except requests.exceptions.Timeout:
        st.error("❌ Timeout: Server tidak merespons")
        st.session_state.is_streaming = False
    
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.session_state.is_streaming = False

else:
    # Tampilan ketika streaming tidak aktif
    st.info("ℹ️ Streaming tidak aktif. Tekan tombol '🚀 Mulai' di sidebar untuk memulai.")
    
    # Tampilkan data history jika ada
    if len(st.session_state.history) > 0:
        st.subheader("📊 Data Tersimpan")
        hist_df = pd.DataFrame(st.session_state.history)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Data", len(hist_df))
        col2.metric("Normal ✅", len(hist_df[hist_df['status'] == "AMAN"]))
        col3.metric("Serangan ⚠️", len(hist_df[hist_df['status'] == "ATTACK"]))
        col4.metric("Gangguan 🛠️", len(hist_df[hist_df['status'] == "FAULT"]))
        
        st.dataframe(hist_df.tail(20), use_container_width=True)