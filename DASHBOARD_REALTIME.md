# 🚀 Dashboard Real-Time - Smart Grid Security

## 📋 Deskripsi

Dashboard ini menampilkan **data real-time** dari Smart Grid IoT dengan fitur:
- ✅ **Real-time Streaming**: Data langsung dari streaming server
- ✅ **Enkripsi End-to-End**: AES-GCM + RSA 2048-bit
- ✅ **Deteksi Anomali**: Prediksi AMAN / ATTACK / FAULT
- ✅ **Visualisasi Interaktif**: Grafik pie chart dan line chart
- ✅ **Auto-refresh**: Configurable refresh rate (0.5 - 5 detik)

---

## 🎯 Cara Menjalankan Dashboard Real-Time

### **STEP 1: Install Dependencies**

Buka Command Prompt dan navigasi ke folder project:

```cmd
cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3"
```

Install dependencies yang diperlukan:

```cmd
pip install streamlit pandas plotly pycryptodome requests
```

---

### **STEP 2: Jalankan Streaming Server (Terminal #1)**

**Buka Command Prompt BARU**, navigasi ke folder autogenerate:

```cmd
cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3\autogenerate"
```

Jalankan streaming server:

```cmd
python auto_generate.py --port 8080 --rate 10
```

**Output yang diharapkan:**
```
📡 Local URL : http://localhost:8080
═══════════════════════════════════════════════════════════
  CSV file : D:\...\smart_grid_data_v2.csv
  Rate     : 10 row/detik
═══════════════════════════════════════════════════════════

⚙️  Simulator started — 10 row/detik
```

**⚠️ PENTING: Jangan tutup terminal ini! Biarkan tetap berjalan.**

---

### **STEP 3: Jalankan Dashboard (Terminal #2)**

**Buka Command Prompt BARU**, navigasi ke folder project:

```cmd
cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3"
```

Jalankan dashboard Streamlit:

```cmd
streamlit run dashboard.py
```

**Output:**
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

Browser akan terbuka otomatis menampilkan dashboard.

---

### **STEP 4: Menggunakan Dashboard**

1. **Di Sidebar Kiri:**
   - Pastikan **Streaming URL** sudah benar: `http://localhost:8080/data/latest`
   - Atur **Refresh Rate** sesuai kebutuhan (default: 1 detik)
   - Klik tombol **🚀 Mulai** untuk memulai streaming

2. **Dashboard akan menampilkan:**
   - **Metrik Real-Time**: Total data, Normal, Attack, Fault
   - **Pie Chart**: Distribusi status keamanan
   - **Line Chart**: Tren tegangan (voltage) real-time
   - **Tabel Log**: 10 data terbaru dengan status enkripsi

3. **Kontrol:**
   - **🚀 Mulai**: Mulai streaming data
   - **🛑 Stop**: Hentikan streaming (data tersimpan)
   - **🗑️ Reset Statistik**: Hapus semua data history

---

### **STEP 5: Menghentikan Sistem**

1. **Dashboard (Terminal #2)**: Tekan `Ctrl + C`
2. **Streaming Server (Terminal #1)**: Tekan `Ctrl + C`

---

## 📊 Fitur Dashboard

### 1. **Real-Time Metrics**
- Total data yang masuk
- Jumlah status Normal (✅)
- Jumlah status Attack (⚠️)
- Jumlah status Fault (🛠️)

### 2. **Visualisasi Interaktif**
- **Pie Chart**: Distribusi status keamanan dengan color coding
  - 🟢 Hijau = AMAN
  - 🔴 Merah = ATTACK
  - 🟡 Kuning = FAULT
- **Line Chart**: Tren tegangan (voltage) untuk deteksi anomali

### 3. **Enkripsi End-to-End**
- **Enkripsi**: AES-256-GCM + RSA-2048
- **Proses**:
  1. Data sensor dienkripsi dengan AES-GCM
  2. AES key dienkripsi dengan RSA public key
  3. Dashboard mendekripsi dengan RSA private key
  4. Data didekripsi dengan AES key
- **Verifikasi**: Setiap data ditandai "🔐 Terverifikasi (AES-GCM)"

### 4. **Deteksi Anomali**
Dashboard menggunakan heuristic untuk prediksi:
- **ATTACK**: `authentication_fail > 2` atau `packet_loss > 10`
- **FAULT**: `temperature > 65` atau `voltage < 200` atau `voltage > 240`
- **AMAN**: Kondisi normal

---

## ⚙️ Konfigurasi

### Mengubah Streaming URL

Jika streaming server berjalan di port lain:

1. Di sidebar dashboard, ubah **Streaming URL**:
   - Port 8081: `http://localhost:8081/data/latest`
   - Remote server: `http://192.168.1.100:8080/data/latest`

### Mengubah Refresh Rate

- **Cepat**: 0.5 detik (2 data/detik)
- **Normal**: 1.0 detik (1 data/detik)
- **Lambat**: 5.0 detik (0.2 data/detik)

### Mengubah Rate Streaming Server

Untuk mengubah kecepatan data dari server:

```cmd
# 5 data per detik
python auto_generate.py --port 8080 --rate 5

# 20 data per detik
python auto_generate.py --port 8080 --rate 20
```

---

## 🔄 Alur Kerja Lengkap

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Install Dependencies                               │
│  pip install streamlit pandas plotly pycryptodome requests  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Jalankan Streaming Server (Terminal #1)           │
│  python auto_generate.py --port 8080 --rate 10              │
│  Status: Biarkan terminal tetap terbuka                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Jalankan Dashboard (Terminal #2)                  │
│  streamlit run dashboard.py                                 │
│  Browser akan terbuka otomatis                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: Gunakan Dashboard                                  │
│  • Klik tombol "🚀 Mulai" di sidebar                        │
│  • Monitor data real-time                                   │
│  • Analisis distribusi keamanan                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 5: Stop Sistem                                        │
│  • Dashboard: Ctrl+C                                        │
│  • Streaming Server: Ctrl+C                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 🐛 Troubleshooting

### Error: "Koneksi Gagal: Tidak dapat terhubung ke streaming server"

**Penyebab:** Streaming server belum berjalan atau port salah

**Solusi:**
1. Pastikan streaming server berjalan di Terminal #1
2. Cek URL di sidebar dashboard: `http://localhost:8080/data/latest`
3. Test manual di browser: buka `http://localhost:8080/status`

---

### Error: "ModuleNotFoundError: No module named 'streamlit'"

**Penyebab:** Dependencies belum terinstall

**Solusi:**
```cmd
pip install streamlit pandas plotly pycryptodome requests
```

---

### Dashboard tidak auto-refresh

**Penyebab:** Streaming tidak aktif atau error koneksi

**Solusi:**
1. Klik tombol "🛑 Stop" lalu "🚀 Mulai" lagi
2. Cek status koneksi di sidebar (harus 🟢 Streaming Aktif)
3. Cek terminal streaming server untuk error

---

### Data tidak muncul / Dashboard kosong

**Penyebab:** Streaming server belum mengirim data

**Solusi:**
1. Tunggu beberapa detik untuk data pertama
2. Cek terminal streaming server, harus ada output:
   ```
   ⚙️  Simulator started — 10 row/detik
   ```
3. Test endpoint manual:
   ```cmd
   curl http://localhost:8080/data/latest
   ```

---

### Port 8501 sudah digunakan

**Penyebab:** Ada aplikasi lain yang menggunakan port 8501

**Solusi:** Gunakan port lain
```cmd
streamlit run dashboard.py --server.port 8502
```

---

## 📈 Perbandingan: Dashboard Lama vs Baru

| Fitur | Dashboard Lama | Dashboard Baru (Real-Time) |
|-------|----------------|----------------------------|
| **Sumber Data** | File CSV statis | Streaming server real-time |
| **Update** | Manual (reload file) | Auto-refresh (0.5-5 detik) |
| **Enkripsi** | ✅ AES-GCM + RSA | ✅ AES-GCM + RSA |
| **Prediksi** | Dari file CSV | Heuristic real-time |
| **Kontrol** | Start/Stop | Start/Stop + Refresh Rate |
| **History** | Semua data file | 1000 data terakhir |
| **Koneksi** | Offline | Online (HTTP) |

---

## 💡 Tips & Best Practices

1. **Refresh Rate Optimal**
   - Untuk monitoring: 1-2 detik
   - Untuk analisis: 3-5 detik
   - Untuk demo: 0.5-1 detik

2. **History Management**
   - Dashboard menyimpan maksimal 1000 data
   - Gunakan "Reset Statistik" untuk clear history
   - Data lengkap tersimpan di `smart_grid_data_v2.csv`

3. **Performance**
   - Refresh rate terlalu cepat (<0.5 detik) bisa membuat browser lag
   - Untuk throughput tinggi, gunakan refresh rate lebih lambat

4. **Production Deployment**
   - Ganti heuristic prediction dengan model ML trained
   - Implementasi authentication untuk dashboard
   - Setup HTTPS untuk enkripsi transport layer
   - Deploy streaming server di cloud (gunakan ngrok atau VPS)

---

## 🚀 Integrasi dengan ML Model

Untuk menggunakan model ML yang sudah di-training (dari `ML.py`):

1. **Load model di dashboard:**
```python
import joblib

# Load trained models
model_dt = joblib.load('hasil/models/trained_Decision_Tree.pkl')
model_rf = joblib.load('hasil/models/trained_Random_Forest.pkl')
model_lr = joblib.load('hasil/models/trained_Logistic_Regression.pkl')
scaler = joblib.load('hasil/models/trained_scaler.pkl')

def predict_with_ml(row_data):
    # Preprocess
    features = ['voltage', 'current', 'power', 'frequency', 'temperature',
               'latency', 'packet_loss', 'throughput', 'duplicate_packet',
               'checksum_valid', 'authentication_fail']
    X = pd.DataFrame([{k: row_data[k] for k in features}])
    X_scaled = scaler.transform(X)
    
    # Predict with voting
    pred_dt = model_dt.predict(X_scaled)[0]
    pred_rf = model_rf.predict(X_scaled)[0]
    pred_lr = model_lr.predict(X_scaled)[0]
    
    # Hard voting
    from collections import Counter
    votes = Counter([pred_dt, pred_rf, pred_lr])
    final_pred = votes.most_common(1)[0][0]
    
    label_map = {0: "AMAN", 1: "ATTACK", 2: "FAULT"}
    return label_map[final_pred]
```

2. **Ganti fungsi `predict_label()` dengan `predict_with_ml()`**

---

## 📞 Catatan Penting

1. **Streaming Server**: Harus berjalan terlebih dahulu sebelum dashboard
2. **Port**: Default 8080 (server) dan 8501 (dashboard)
3. **Browser**: Gunakan Chrome/Firefox untuk performa terbaik
4. **Data**: Label ground truth tersimpan di `smart_grid_data_v2.csv`

---

## 🎯 Quick Reference

### Command Cheat Sheet

```cmd
# Install dependencies
pip install streamlit pandas plotly pycryptodome requests

# Terminal #1: Streaming Server
cd autogenerate
python auto_generate.py --port 8080 --rate 10

# Terminal #2: Dashboard
cd ..
streamlit run dashboard.py

# Test endpoint
curl http://localhost:8080/data/latest
curl http://localhost:8080/status
```

### URL Reference

```
Streaming Server:
  http://localhost:8080/               ← Info & endpoints
  http://localhost:8080/status         ← Status & stats
  http://localhost:8080/data/latest    ← Data terbaru (untuk dashboard)
  http://localhost:8080/data/realtime  ← SSE stream (untuk ML.py)

Dashboard:
  http://localhost:8501                ← Dashboard UI
```

---

**Selamat mencoba! 🚀**

**Dibuat oleh:** Project KDA Kelompok 3  
**Version:** 2.0 (Real-Time)  
**Year:** 2024
