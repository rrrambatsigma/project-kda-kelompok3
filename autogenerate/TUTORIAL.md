# 🚀 Tutorial Lengkap - Sistem Drift Monitoring

## 📋 Deskripsi Sistem

Sistem ini mengimplementasikan prediksi real-time dengan monitoring Model Drift:
- **Base Model**: Model statis yang tidak pernah di-training ulang
- **Adaptive Model**: Model yang terus di-retrain dengan data streaming baru (setiap 200 samples)
- **Voting Classifier**: Hard voting dari Decision Tree, Random Forest, dan Logistic Regression
- **Threading**: 3 thread concurrent untuk stream, prediksi, dan retraining
- **Drift Monitoring**: Komparasi prediksi untuk deteksi drift

---

## 📁 Struktur File

```
project-kda-kelompok3/
├── autogenerate/
│   ├── ML.py                    # Sistem drift monitoring
│   ├── auto_generate.py         # Server streaming data
│   ├── test_drift_system.py     # Test suite
│   └── requirements.txt         # Dependencies
├── data/
│   ├── df_train.csv            # Data training
│   └── df_test_lengkap.csv     # Data testing
└── hasil/                       # Output (dibuat otomatis)
    ├── models/                  # Model tersimpan
    └── hasil_prediksi_drift.csv # Log prediksi real-time
```

---

## 🎯 Cara Menjalankan Sistem

### STEP 1: Install Dependencies

Buka Command Prompt dan navigasi ke folder autogenerate:

```bash
cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3\autogenerate"
```

Install dependencies:

```bash
pip install -r requirements.txt
```

**Output yang diharapkan:**
```
Successfully installed flask-3.0.0 pandas-2.0.0 scikit-learn-1.3.0 ...
```

---

### STEP 2: Training Model (Pertama Kali Saja)

Jalankan training mode untuk melatih model dari data historis:

```bash
python ML.py --mode training
```

**Proses training (2-5 menit):**
```
======================================================================
  MODE: TRAINING - Train models from historical data
======================================================================

[1] Load data
    Train : 10000 baris | 11 fitur
    Test  : 2000 baris  | 11 fitur

[2] Training setiap model (5 iterasi masing-masing)...
    Model: Decision Tree
    Iter 1/5 (seed=42) → CV Acc: 0.9234 ± 0.0123
    ...

[4] Saving trained models...
    ✓ Saved: trained_Decision_Tree.pkl
    ✓ Saved: trained_Random_Forest.pkl
    ✓ Saved: trained_Logistic_Regression.pkl
    ✓ Saved: trained_scaler.pkl
```

**Verifikasi model tersimpan:**
```bash
dir "..\hasil\models"
```

Harus ada 4 file .pkl

---

### STEP 3: Jalankan Streaming Server (Terminal #1)

**Buka Command Prompt BARU** (jangan tutup yang lama!)

Navigasi ke folder autogenerate:
```bash
cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3\autogenerate"
```

Jalankan streaming server:
```bash
python auto_generate.py --port 8080 --rate 10
```

**Output:**
```
📡 Running at http://localhost:8080
============================================================
  Rate     : 10 row/detik
  SSE      : http://localhost:8080/data/realtime
============================================================

⚙️  Simulator started — 10 row/detik
```

**⚠️ PENTING: Jangan tutup terminal ini! Biarkan tetap berjalan.**

---

### STEP 4: Jalankan Drift Monitoring (Terminal #2)

**Buka Command Prompt BARU lagi** (sekarang ada 2 terminal)

Navigasi ke folder autogenerate:
```bash
cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3\autogenerate"
```

Jalankan drift monitoring:
```bash
python ML.py --mode streaming
```

**Output:**
```
======================================================================
  MODE: STREAMING - Real-time prediction with drift monitoring
======================================================================

[1] Loading trained models...
    ✓ Loaded: trained_Decision_Tree.pkl
    ✓ Loaded: trained_Random_Forest.pkl
    ✓ Loaded: trained_Logistic_Regression.pkl
    ✓ Loaded: trained_scaler.pkl

[2] Creating adaptive models (copy of base models)...
    ✓ Copied: Decision_Tree
    ✓ Copied: Random_Forest
    ✓ Copied: Logistic_Regression

[3] Initializing drift monitoring system...
    ✓ Created drift log: hasil_prediksi_drift.csv

[4] Starting threads...
    [🌊 STREAM] Connected successfully!
    [🔧 RETRAIN] Retraining monitor started
    [🏷️  LABEL] Simulated label provider started

======================================================================
  🚀 SYSTEM RUNNING
======================================================================

[📊 STATS] Predictions: 50  | Retrains: 0 | Match Rate: 94.00%
[📊 STATS] Predictions: 100 | Retrains: 0 | Match Rate: 92.50%
[📊 STATS] Predictions: 200 | Retrains: 1 | Match Rate: 89.50%

[⚙️ RETRAINING] Starting micro-batch retraining...
    Training data: 200 samples
    Label distribution: {0: 140, 1: 40, 2: 20}
    ✓ Retrained: Decision_Tree
    ✓ Retrained: Random_Forest
    ✓ Retrained: Logistic_Regression
    ✓ Voting Classifier updated
    ✓ Retraining completed (Total retrains: 1)
```

**✅ Sistem berjalan! Biarkan selama 5-10 menit untuk melihat pola drift.**

---

### STEP 5: Monitoring Hasil

#### A. Monitoring Real-time di Terminal

Terminal #2 akan menampilkan statistik setiap 50 prediksi dengan **akurasi real-time dalam format desimal**:

```
[📊 STATS] Predictions: 50 | Retrains: 0
  ├─ Match Rate: 94.00%
  ├─ Base Model Accuracy: 0.9000 (45/50)
  └─ Adaptive Model Accuracy: 0.9200 (46/50)
```

**Setiap 10 prediksi juga akan muncul update singkat:**
```
[📝 LOG] 10 predictions | Base: 0.9200 | Adaptive: 0.9400
[📝 LOG] 20 predictions | Base: 0.9150 | Adaptive: 0.9350
[📝 LOG] 30 predictions | Base: 0.9100 | Adaptive: 0.9300
```

**Interpretasi:**
- **Predictions**: Total prediksi yang sudah dilakukan
- **Retrains**: Jumlah retraining Adaptive Model
- **Match Rate**: Persentase prediksi yang sama antara Base dan Adaptive Model
  - ✅ **> 90%**: Tidak ada drift signifikan
  - ⚠️ **70-90%**: Moderate drift
  - ❌ **< 70%**: Significant drift (perlu investigasi)
- **Base Model Accuracy**: Akurasi Base Model dalam format desimal (0.0000 - 1.0000)
  - Contoh: `0.9200` = 92.00% akurasi
- **Adaptive Model Accuracy**: Akurasi Adaptive Model dalam format desimal
  - Format: `0.XXXX (correct/total)`
  - Contoh: `0.9200 (46/50)` = 46 prediksi benar dari 50 total = 92% akurasi

#### B. Monitoring File CSV

Buka File Explorer dan navigate ke:
```
D:\SEMESTER 4\KDA\project-kda-kelompok3\hasil\
```

Double-click file: **`hasil_prediksi_drift.csv`**

**Isi file CSV:**

| Kolom | Deskripsi |
|-------|-----------|
| `timestamp` | Waktu data masuk |
| `device_id` | ID device IoT |
| `voltage`, `current`, `power`, dll. | Fitur sensor |
| `ground_truth_label` | Label asli (0=Normal, 1=Attack, 2=Fault) |
| `base_prediction` | Prediksi Base Model |
| `adaptive_prediction` | Prediksi Adaptive Model |
| `final_prediction` | Prediksi final (= adaptive_prediction) |
| `base_correct` | 1 jika base prediksi benar, 0 jika salah |
| `adaptive_correct` | 1 jika adaptive prediksi benar, 0 jika salah |
| `base_accuracy` | **Akurasi kumulatif Base Model (format: 0.9564)** |
| `adaptive_accuracy` | **Akurasi kumulatif Adaptive Model (format: 0.9564)** |
| `prediction_match` | 1 = sama, 0 = berbeda (indikasi drift) |
| `total_retrains` | Jumlah retraining yang sudah dilakukan |

**Contoh data:**
```csv
timestamp,device_id,...,ground_truth_label,base_prediction,adaptive_prediction,base_accuracy,adaptive_accuracy
2024-01-01 12:00:00,SGD-0001,...,0,0,0,0.9200,0.9400
2024-01-01 12:00:01,SGD-0023,...,1,1,1,0.9250,0.9450
2024-01-01 12:00:02,SGD-0045,...,0,2,0,0.9100,0.9500
```

**Analisis:**
- Kolom `base_accuracy` dan `adaptive_accuracy` menunjukkan akurasi kumulatif
- Format: 0.9564 = 95.64% akurasi
- Nilai ini terus diupdate setiap ada prediksi baru
- Bisa langsung digunakan untuk plotting atau analisis statistik

---

### STEP 6: Menghentikan Sistem

#### Terminal #2 (Drift Monitoring):
Tekan `Ctrl + C`

**Output:**
```
[🛑 SHUTDOWN] Stopping all threads...
[✓] All threads stopped

  FINAL STATISTICS:
  ├── Total Predictions: 1523
  ├── Total Retrains: 7
  └── Drift Log: hasil_prediksi_drift.csv
```

#### Terminal #1 (Streaming Server):
Tekan `Ctrl + C`

**Output:**
```
🛑 Stopped.
```

---

## 🧪 Testing Sistem (Opsional)

Untuk memverifikasi sistem bekerja dengan baik, jalankan test suite:

```bash
python test_drift_system.py
```

**Output:**
```
============================================================
  DRIFT MONITORING SYSTEM - TEST SUITE
============================================================

TEST 1: Model Loading
✓ Models loaded successfully

TEST 2: Voting Classifier
✓ Voting classifier created successfully

TEST 3: Drift System Initialization
✓ Drift system initialized successfully

TEST 4: Single Prediction
✓ Prediction successful
  Base Model prediction: 0 (Normal)
  Adaptive Model prediction: 0 (Normal)

TEST 5: Batch Prediction (20 samples)
✓ Processed 20 samples
  Match rate: 18/20 (90.0%)

...

============================================================
  TEST SUITE COMPLETED
============================================================
```

---

## ⚙️ Konfigurasi (Opsional)

Edit file `ML.py` untuk menyesuaikan parameter:

```python
# Baris 18-20
STREAM_URL = "http://localhost:8080/data/realtime"  # URL streaming
STREAM_BUFFER_SIZE = 500                             # Buffer stream
TRAINING_BUFFER_SIZE = 200                           # Ukuran micro-batch
```

**Parameter yang bisa disesuaikan:**
- `TRAINING_BUFFER_SIZE`: Ukuran batch untuk retraining (default: 200)
  - Lebih kecil → retraining lebih sering, lebih responsif
  - Lebih besar → retraining lebih jarang, lebih stabil
- `STREAM_BUFFER_SIZE`: Ukuran buffer stream (default: 500)
- Port streaming server: `--port 8080` (bisa diganti ke 8081, 8082, dll)

---

## 🐛 Troubleshooting

### Error: "Model file not found"

**Penyebab:** Model belum di-training

**Solusi:**
```bash
python ML.py --mode training
```

---

### Error: "Connection refused" saat streaming

**Penyebab:** Streaming server belum berjalan

**Solusi:**
1. Buka terminal baru
2. Jalankan:
```bash
python auto_generate.py --port 8080 --rate 10
```
3. Tunggu sampai muncul "Running at http://localhost:8080"
4. Baru jalankan drift monitoring di terminal lain

---

### Error: "ModuleNotFoundError: No module named 'pandas'"

**Penyebab:** Dependencies belum terinstall

**Solusi:**
```bash
pip install -r requirements.txt
```

---

### Error: "FileNotFoundError: df_train.csv"

**Penyebab:** File data tidak ditemukan

**Solusi:**
1. Cek lokasi file data:
```bash
dir "..\data\df_train.csv"
```

2. Jika tidak ada, pastikan file ada di:
```
D:\SEMESTER 4\KDA\project-kda-kelompok3\data\
```

3. Atau edit path di `ML.py` baris 20-21:
```python
train_df = pd.read_csv(r"PATH_ANDA\df_train.csv")
test_df  = pd.read_csv(r"PATH_ANDA\df_test_lengkap.csv")
```

---

### Port 8080 sudah digunakan

**Penyebab:** Ada aplikasi lain yang menggunakan port 8080

**Solusi:** Gunakan port lain
```bash
python auto_generate.py --port 8081 --rate 10
```

Jangan lupa edit `ML.py` baris 18:
```python
STREAM_URL = "http://localhost:8081/data/realtime"
```

---

### Retraining tidak terjadi

**Penyebab:** Training buffer belum penuh (< 200 samples)

**Solusi:**
- Tunggu lebih lama (200 samples ÷ 10 data/detik = 20 detik)
- Atau kurangi `TRAINING_BUFFER_SIZE` di `ML.py` baris 20

---

### Match Rate terlalu rendah (<50%)

**Penyebab:** Kemungkinan ada masalah dengan simulasi label

**Solusi:**
1. Cek distribusi label di output retraining
2. Pastikan heuristic labeling di `simulate_ground_truth_label()` sesuai
3. Dalam produksi, ganti dengan label asli dari operator

---

### Error: "VotingClassifier instance is not fitted yet"

**Penyebab:** VotingClassifier tidak di-fit dengan benar setelah load model

**Solusi:**
Ini sudah diperbaiki di kode. Jika masih terjadi:
1. Stop sistem (Ctrl+C)
2. Jalankan ulang training mode:
```bash
python ML.py --mode training
```
3. Jalankan ulang streaming mode

---

### Error: "'NoneType' object has no attribute 'inverse_transform'"

**Penyebab:** LabelEncoder di VotingClassifier tidak di-setup dengan benar

**Solusi:**
Ini sudah diperbaiki di kode terbaru. Jika masih terjadi:
1. Stop sistem (Ctrl+C di kedua terminal)
2. Pastikan Anda menggunakan kode ML.py yang terbaru
3. Jalankan ulang streaming mode:
```bash
# Terminal #1
python auto_generate.py --port 8080 --rate 10

# Terminal #2
python ML.py --mode streaming
```

---

### Hasil tidak muncul / File CSV kosong

**Penyebab:** Beberapa kemungkinan:
1. Streaming server belum berjalan
2. Koneksi SSE gagal
3. Data tidak sampai ke drift monitoring

**Solusi:**

**A. Cek Streaming Server (Terminal #1):**
```bash
# Pastikan muncul output seperti ini:
📡 Running at http://localhost:8080
⚙️  Simulator started — 10 row/detik
```

**B. Cek Drift Monitoring (Terminal #2):**
```bash
# Harus muncul output seperti ini:
[✓ STREAM] Connected successfully!
[📡 STREAM] Waiting for data...
[📥 STREAM] Received data #1: device=SGD-0001
[📝 LOG] Processed 10 predictions...
[📝 LOG] Processed 20 predictions...
```

**C. Jika tidak ada output "Received data":**
1. Stop drift monitoring (Ctrl+C)
2. Cek streaming server masih berjalan
3. Test manual dengan browser: buka `http://localhost:8080/status`
4. Jalankan ulang drift monitoring

**D. Cek file CSV:**
```bash
dir "..\hasil\hasil_prediksi_drift.csv"
```
Jika file ada tapi kosong, berarti ada error saat processing. Lihat error di terminal.

---

## 📊 Alur Kerja Lengkap

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Install Dependencies                               │
│  pip install -r requirements.txt                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Training Model (Pertama Kali)                     │
│  python ML.py --mode training                               │
│  Output: Model tersimpan di hasil/models/                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Jalankan Streaming Server (Terminal #1)           │
│  python auto_generate.py --port 8080 --rate 10              │
│  Status: Biarkan terminal tetap terbuka                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: Jalankan Drift Monitoring (Terminal #2)           │
│  python ML.py --mode streaming                              │
│  Status: Sistem berjalan, monitoring real-time              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 5: Monitoring & Analisis                             │
│  • Lihat terminal untuk statistik real-time                │
│  • Buka hasil_prediksi_drift.csv untuk analisis detail     │
│  • Match Rate menunjukkan tingkat drift                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 6: Stop Sistem                                        │
│  • Terminal #2: Ctrl+C (Drift Monitoring)                  │
│  • Terminal #1: Ctrl+C (Streaming Server)                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Fitur Sistem

✅ **Dual Model System**: Base Model (static) vs Adaptive Model (retrained)  
✅ **Real-time Streaming**: Konsumsi data via SSE (10 data/detik)  
✅ **Voting Classifier**: Hard voting dari Decision Tree, Random Forest, Logistic Regression  
✅ **Micro-batch Retraining**: Adaptive Model di-retrain setiap 200 samples  
✅ **Threading**: 3 thread concurrent (stream, retrain, labeling)  
✅ **Thread-safe**: Lock mechanism untuk mencegah race condition  
✅ **CSV Logging**: Semua prediksi tercatat untuk analisis  
✅ **Drift Detection**: Match rate monitoring untuk deteksi drift  

---

## 📈 Tech Stack

| Kategori | Technology |
|----------|------------|
| **Language** | Python 3.8+ |
| **ML Framework** | Scikit-learn |
| **Concurrency** | Threading |
| **Data Structure** | Collections.deque |
| **Serialization** | Joblib |
| **HTTP Client** | Requests (SSE) |
| **Data Processing** | Pandas, NumPy |
| **Streaming Server** | Flask SSE |

---

## 💡 Tips & Best Practices

1. **First Time Setup**
   - Jalankan training mode terlebih dahulu
   - Pastikan data training ada di folder `data/`

2. **Running System**
   - Butuh 2 terminal: streaming server + drift monitoring
   - Biarkan berjalan minimal 5-10 menit untuk melihat pola drift

3. **Monitoring**
   - Cek terminal untuk statistik real-time
   - Buka CSV untuk analisis detail
   - Match Rate < 70% = significant drift

4. **Production Deployment**
   - Ganti `simulate_ground_truth_label()` dengan label asli
   - Setup logging ke database
   - Implementasi alerting untuk drift detection
   - Backup model secara berkala

---

## 📞 Catatan Penting

1. **Label Ground Truth**: Saat ini menggunakan simulasi heuristic. Dalam produksi, ganti dengan label asli dari operator atau sistem monitoring.

2. **Retraining Strategy**: Micro-batch retraining setiap 200 samples. Sesuaikan `TRAINING_BUFFER_SIZE` berdasarkan kebutuhan dan karakteristik data.

3. **Performance**: Sistem dapat handle 10 data/detik. Untuk throughput lebih tinggi, pertimbangkan batch processing atau async I/O.

4. **Model Persistence**: Model disimpan di `hasil/models/`. Backup secara berkala untuk production.

---

## 🚀 Quick Reference

### Command Cheat Sheet

```bash
# Install dependencies
pip install -r requirements.txt

# Training mode
python ML.py --mode training

# Streaming server (Terminal #1)
python auto_generate.py --port 8080 --rate 10

# Drift monitoring (Terminal #2)
python ML.py --mode streaming

# Testing
python test_drift_system.py
```

### File Locations

```
Output:
  hasil/hasil_prediksi_drift.csv    ← Main output
  hasil/models/*.pkl                ← Trained models

Data:
  data/df_train.csv                 ← Training data
  data/df_test_lengkap.csv          ← Test data
```

---

**Selamat mencoba! 🚀**

**Dibuat oleh:** Project KDA Kelompok 3  
**Version:** 2.0  
**Year:** 2024
