import streamlit as st
import pandas as pd
import time
import json
import plotly.express as px
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

# --- PENGATURAN HALAMAN ---
st.set_page_config(page_title="Secure Smart Grid Analytics", layout="wide")

st.markdown(f"""
    <div style="text-align: center;">
        <h1>🛡️ Dashboard Keamanan Smart Grid</h1>
        <p style="color: gray;">Sistem Deteksi Anomali & Enkripsi Data End-to-End</p>
    </div>
    """, unsafe_allow_html=True)

# State untuk menyimpan riwayat data
if 'history' not in st.session_state:
    st.session_state.history = []

# --- SIDEBAR CONTROL ---
with st.sidebar:
    st.header("⚙️ Kontrol Sistem")
    st.info("Dashboard ini mensimulasikan aliran data IoT dari Smart Grid dan menganalisis keamanan secara real-time.")
    start_btn = st.button("🚀 Jalankan Streaming Data")
    if st.button("🗑️ Reset Statistik"):
        st.session_state.history = []
        st.rerun()

# --- LOGIKA UTAMA ---
if start_btn:
    try:
        # Membaca data hasil voting (Data Test)
        df_raw = pd.read_csv('test_data_with_predictions.csv')
        
        # Placeholder agar tampilan tidak kedap-kedip
        metric_spot = st.empty()
        chart_spot = st.empty()
        table_spot = st.empty()

        for i in range(len(df_raw)):
            row = df_raw.iloc[i]
            
            # Mapping Label
            label_map = {0: "AMAN", 1: "ATTACK", 2: "FAULT"}
            status_label = label_map.get(row['Predicted_Label'], "UNKNOWN")
            
            # 1. Simulasi Pengiriman: Enkripsi di sisi 'Sensor'
            payload = {
                "voltage": float(row['voltage']),
                "latency": float(row['latency']),
                "status": status_label
            }
            encrypted_pkg = encrypt_data(payload, public_key_raw)
            
            # 2. Simulasi Penerimaan: Dekripsi di sisi 'Dashboard'
            decrypted_payload = decrypt_data(encrypted_pkg, private_key_raw)
            
            # Simpan ke memori dashboard
            st.session_state.history.append(decrypted_payload)
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
                    fig_pie = px.pie(
                        hist_df, names='status', title="Distribusi Keamanan",
                        color='status',
                        color_discrete_map={'AMAN':'#2ecc71', 'ATTACK':'#e74c3c', 'FAULT':'#f1c40f'}
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                with col_right:
                    st.subheader("📈 Tren Tegangan Real-Time (Voltage)")
                    st.line_chart(hist_df['voltage'].tail(50)) # Tampilkan 50 data terakhir

            # C. Tabel Detail & Bukti Enkripsi
            with table_spot.container():
                st.subheader("📑 Log Aktivitas Terverifikasi")
                # Menampilkan 5 data terbaru di atas
                display_df = hist_df.tail(5).copy()
                display_df['Integritas'] = "🔐 Terverifikasi (AES-GCM)"
                st.table(display_df)

            time.sleep(0.4) # Kecepatan aliran data

    except FileNotFoundError:
        st.error("File 'test_data_with_predictions.csv' tidak ditemukan! Pastikan file berada di folder yang sama.")
else:
    st.warning("Silakan tekan tombol 'Jalankan Streaming Data' di sidebar untuk memulai.")