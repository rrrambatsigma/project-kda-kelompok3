# 🔌 Smart Grid IoT Security — Real-Time Simulator

Simulator data IoT Smart Grid yang menghasilkan data sensor secara real-time menggunakan metode **Markov Chain**, **AR(1) Temporal Dependency**, **Diurnal Pattern**, dan **Device Bias**. Data di-stream melalui REST API dan SSE (Server-Sent Events).

---

## 📋 Prasyarat

Pastikan laptop sudah terinstal:

| Kebutuhan | Versi Minimum | Cek Versi |
|-----------|--------------|-----------|
| **Python** | 3.10+ | `python --version` |
| **pip** | terbaru | `pip --version` |

> **Opsional:** [`uv`](https://github.com/astral-sh/uv) sebagai pengganti pip yang lebih cepat.

---

## 🚀 Cara Menjalankan

### Metode 1 — Menggunakan `pip` (Standar)

**Langkah 1: Clone / copy folder `autogenerate` ke laptop**

Pastikan struktur folder seperti ini:
```
autogenerate/
├── auto_generate.py
├── requirements.txt
└── README.md
```

**Langkah 2: Buat virtual environment**

```bash
python -m venv .venv
```

**Langkah 3: Aktifkan virtual environment**

- Windows:
  ```bash
  .venv\Scripts\activate
  ```
- Linux / macOS:
  ```bash
  source .venv/bin/activate
  ```

**Langkah 4: Install dependensi**

```bash
pip install -r requirements.txt
```

**Langkah 5: Jalankan simulator**

```bash
python auto_generate.py
```

---

### Metode 2 — Menggunakan `uv` (Lebih Cepat)

**Langkah 1: Install `uv`** (jika belum)

```bash
pip install uv
```

**Langkah 2: Jalankan langsung (uv otomatis buat venv & install deps)**

```bash
uv run auto_generate.py
```

---

## ⚙️ Opsi Tambahan

Script menerima argumen command-line berikut:

| Argumen | Default | Keterangan |
|---------|---------|------------|
| `--port` | `8080` | Port server Flask |
| `--rate` | `10` | Jumlah baris data per detik |

**Contoh penggunaan:**

```bash
# Jalankan di port 5000 dengan 5 baris/detik
python auto_generate.py --port 5000 --rate 5

# Jalankan di port 8080 dengan 20 baris/detik
python auto_generate.py --port 8080 --rate 20
```

---

## 🌐 Endpoint API

Setelah simulator berjalan, akses endpoint berikut di browser atau tools seperti Postman / curl:

| Endpoint | Keterangan |
|----------|------------|
| `GET /` | Info service & daftar endpoint |
| `GET /status` | Status simulator & distribusi label |
| `GET /data/latest` | Satu baris data terbaru |
| `GET /data/history?limit=50` | N baris terakhir (max 1000) |
| `GET /data/realtime` | **SSE stream real-time ★** |
| `GET /data/download` | Download file CSV |
| `GET /data/stats` | Statistik distribusi label |
| `GET /markov/state` | Debug state Markov tiap device |

**Contoh akses:**

```bash
# Lihat data terbaru
curl http://localhost:8080/data/latest

# Stream data real-time (SSE)
curl -N http://localhost:8080/data/realtime
```

---

## 📊 Format Data

Setiap baris data yang di-generate memiliki field berikut:

| Field | Tipe | Keterangan |
|-------|------|------------|
| `timestamp` | string | Waktu generate (format: `YYYY-MM-DD HH:MM:SS.mmm`) |
| `device_id` | string | ID perangkat (`SGD-0001` s/d `SGD-0050`) |
| `voltage` | float | Tegangan listrik (Volt) |
| `current` | float | Arus listrik (Ampere) |
| `power` | float | Daya (Watt) |
| `frequency` | float | Frekuensi listrik (Hz) |
| `temperature` | float | Suhu perangkat (°C) |
| `latency` | float | Latensi jaringan (ms) |
| `packet_loss` | float | Packet loss (%) |
| `throughput` | float | Throughput jaringan (%) |
| `duplicate_packet` | int | Jumlah paket duplikat |
| `checksum_valid` | int | Validitas checksum (0/1) |
| `authentication_fail` | int | Jumlah kegagalan autentikasi |

> **Catatan:** Field `label` dan `label_name` hanya disimpan di CSV, tidak dikirim ke API (simulasi kondisi nyata).

---

## 📁 Output

Data secara otomatis disimpan ke file CSV:

```
autogenerate/smart_grid_data_v2.csv
```

File akan dibuat otomatis jika belum ada, atau dilanjutkan (append) jika sudah ada.

---

## 🏷️ Label Data

| Label | Kode | Keterangan |
|-------|------|------------|
| NORMAL | 0 | Kondisi operasi normal |
| ATTACK | 1 | Indikasi serangan (FDI, Replay, DoS, Tampering) |
| FAULT | 2 | Kerusakan sensor (Drift, Stuck, Overheat, Noisy, Missing) |

---

## 🛑 Menghentikan Simulator

Tekan `Ctrl + C` di terminal untuk menghentikan simulator.

---

## ❗ Troubleshooting

| Masalah | Solusi |
|---------|--------|
| `ModuleNotFoundError` | Pastikan virtual environment aktif dan `pip install -r requirements.txt` sudah dijalankan |
| `Port already in use` | Ganti port dengan `--port 5000` atau port lain yang kosong |
| `python` tidak dikenali | Coba gunakan `python3` atau pastikan Python sudah ditambahkan ke PATH |
| Tidak bisa akses dari laptop lain | Pastikan firewall mengizinkan port yang digunakan (default: 8080) |
