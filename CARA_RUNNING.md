

### Opsi 1: Menjalankan Sistem Drift Monitoring (Real-time ML)

### **STEP 1: Install Dependencies**

Buka Command Prompt dan navigasi ke folder autogenerate:

```cmd
cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3\autogenerate"
```

Install dependencies yang diperlukan:

```cmd
pip install pandas numpy scikit-learn joblib flask requests
```

---

### **STEP 2: Training Model (Pertama Kali)**

Jalankan training mode untuk melatih model dari data historis:

```cmd
python ML.py --mode training
```

**Output yang diharapkan:**
- Model akan dilatih menggunakan data dari `data/df_train.csv`
- Model tersimpan di folder `hasil/models/` (4 file .pkl)
- Proses memakan waktu 2-5 menit

---

### **STEP 3: Jalankan Streaming Server (Terminal #1)**

**Buka Command Prompt BARU**, navigasi ke folder autogenerate:

```cmd
cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3\autogenerate"
```

Cek apakah file `auto_generate.py` ada. Jika ada, jalankan:

```cmd
python auto_generate.py --port 8080 --rate 10
```

**⚠️ PENTING: Jangan tutup terminal ini! Biarkan tetap berjalan.**

---

### **STEP 4: Jalankan Drift Monitoring (Terminal #2)**

**Buka Command Prompt BARU lagi**, navigasi ke folder autogenerate:

```cmd
cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3\autogenerate"
```

Jalankan drift monitoring:

```cmd
python ML.py --mode streaming
```

**Output:**
- Sistem akan memproses data real-time
- Statistik muncul setiap 10-50 prediksi
- Hasil tersimpan di `hasil/hasil_prediksi_drift.csv`

---

### **STEP 5: Monitoring Hasil**

Buka file hasil di Excel atau text editor:
```
D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3\hasil\hasil_prediksi_drift.csv
```


### Install Dependencies Dashboard

```cmd
cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3"
pip install streamlit pandas plotly pycryptodome
```

### Jalankan Dashboard

```cmd
streamlit run dashboard.py
```

### verifikasi sistem bekerja dengan baik:

```cmd
cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3\autogenerate"
python test_drift_system.py
```

Atau untuk test training:

```cmd
python test_training.py
```

---
