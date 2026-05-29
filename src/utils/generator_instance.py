"""
Smart Grid IoT Security Dataset Generator (Realistic Edition)
=============================================================
Versi ini sengaja menghadirkan "ketidaksempurnaan" dunia nyata:

MASALAH YANG DITAMBAHKAN:
  [1]  Label noise          – ~5 % label dibalik secara acak (NORMAL↔ATTACK↔FAULT)
  [2]  Feature overlap      – distribusi antar kelas sengaja tumpang-tindih
  [3]  Temporal correlation – beberapa fitur mengikuti pola harian / noise AR(1)
  [4]  Device heterogeneity – setiap perangkat punya bias & skala berbeda
  [5]  Class imbalance ringan – rasio tidak bulat-bulat 40/40/20
  [6]  Outlier sporadis      – ~2 % data memiliki spike ekstrem di satu fitur
  [7]  NaN tambahan          – NORMAL dan ATTACK kini juga punya nilai hilang
  [8]  Multicollinearity partial – power tidak selalu = V × I × pf
  [9]  Skewed features       – latency & packet_loss berdistribusi log-normal
  [10] Duplicate rows        – ~0.5 % baris duplikat (perangkat kirim ulang)
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# ── Seed ──────────────────────────────────────────────────────────────────────
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

# ── Konfigurasi ───────────────────────────────────────────────────────────────
TOTAL    = 30_000
# [5] Imbalance ringan – bukan 40/40/20 persis
N_NORMAL = int(TOTAL * 0.415)
N_ATTACK = int(TOTAL * 0.372)
N_FAULT  = TOTAL - N_NORMAL - N_ATTACK

DEVICE_IDS = [f"SGD-{i:04d}" for i in range(1, 51)]   # 50 perangkat
START_TIME = datetime(2024, 1, 1, 0, 0, 0)

# ── [4] Bias per-perangkat (sekali, dipakai ulang) ────────────────────────────
DEVICE_BIAS = {
    d: {
        "v_bias":    np.random.uniform(-5, 5),
        "v_scale":   np.random.uniform(0.97, 1.03),
        "c_bias":    np.random.uniform(-0.5, 0.5),
        "temp_bias": np.random.uniform(-3, 3),
        "lat_scale": np.random.uniform(0.8, 1.4),   # beberapa node lebih lambat
    }
    for d in DEVICE_IDS
}


# ══════════════════════════════════════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════════════════════════════════════

def jitter(arr, scale=0.5):
    return arr + np.random.normal(0, scale, len(arr))

def timestamps(n, base=START_TIME, step_sec=5):
    return [base + timedelta(seconds=i * step_sec) for i in range(n)]

def ar1_noise(n, phi=0.8, sigma=1.0):
    """AR(1) noise – memberi korelasi temporal antar baris."""
    out = np.zeros(n)
    out[0] = np.random.normal(0, sigma)
    for i in range(1, n):
        out[i] = phi * out[i-1] + np.random.normal(0, sigma * np.sqrt(1 - phi**2))
    return out

def lognormal_latency(n, mu=2.5, sigma=0.6):
    """[9] Latency berdistribusi log-normal, bukan uniform."""
    return np.random.lognormal(mu, sigma, n)

def lognormal_pktloss(n, mu=0.2, sigma=0.8):
    """[9] Packet loss juga log-normal, diklem ke [0, 100]."""
    return np.clip(np.random.lognormal(mu, sigma, n), 0, 100)

def daily_voltage_pattern(n, amplitude=3.0):
    """[3] Tegangan mengikuti fluktuasi beban harian (sinus ~24 jam)."""
    t = np.arange(n) * 5 / 3600          # waktu dalam jam
    return amplitude * np.sin(2 * np.pi * t / 24 - np.pi / 2)

def apply_device_bias(voltage, current, temp, latency, device_ids, n):
    """[4] Terapkan heterogenitas per-perangkat."""
    for i in range(n):
        b = DEVICE_BIAS[device_ids[i]]
        voltage[i] = voltage[i] * b["v_scale"] + b["v_bias"]
        current[i] = current[i] + b["c_bias"]
        temp[i]    = temp[i]    + b["temp_bias"]
        latency[i] = latency[i] * b["lat_scale"]
    return voltage, current, temp, latency

def inject_outliers(arr, frac=0.02, lo_mult=0.3, hi_mult=3.0):
    """[6] Sisipkan spike ekstrem pada sebagian kecil baris."""
    idx = np.random.choice(len(arr), int(len(arr) * frac), replace=False)
    direction = np.random.choice([-1, 1], len(idx))
    arr[idx] = np.where(
        direction > 0,
        arr[idx] * hi_mult,
        arr[idx] * lo_mult,
    )
    return arr

def inject_nan(arr, frac=0.02):
    """[7] Sisipkan NaN acak."""
    idx = np.random.choice(len(arr), int(len(arr) * frac), replace=False)
    arr = arr.astype(float)
    arr[idx] = np.nan
    return arr

def corrupt_power(voltage, current, n, noise_frac=0.15):
    """[8] power ≠ V×I×pf secara konsisten; ada kalibrasai error & noise."""
    pf     = np.random.uniform(0.80, 0.98, n)
    noise  = np.random.normal(0, noise_frac, n)          # error kalibrasi
    # Kadang meter mati sementara → power=0 meski V,I ada
    dead   = np.random.rand(n) < 0.01
    power  = voltage * current * pf * (1 + noise)
    power[dead] = 0.0
    return power


# ══════════════════════════════════════════════════════════════════════════════
# 1. KONDISI NORMAL
# ══════════════════════════════════════════════════════════════════════════════

def generate_normal(n, device_ids):
    # [3] Tambahkan pola harian + noise AR(1) pada tegangan
    base_v  = 220 + daily_voltage_pattern(n)
    ar_v    = ar1_noise(n, phi=0.85, sigma=0.6)
    voltage = base_v + ar_v + np.random.normal(0, 0.8, n)
    voltage = np.clip(voltage, 200, 240)

    current = np.random.uniform(3, 8, n) + ar1_noise(n, phi=0.5, sigma=0.2)
    current = np.clip(current, 0.5, 15)

    frequency   = np.random.uniform(49.7, 50.3, n)
    temperature = np.random.uniform(25, 40, n) + ar1_noise(n, phi=0.9, sigma=0.5)

    # [9] latency & packet_loss log-normal
    latency     = lognormal_latency(n, mu=2.8, sigma=0.35)   # median ~16ms
    packet_loss = lognormal_pktloss(n, mu=-1.0, sigma=0.7)   # median ~0.4%
    packet_loss = np.clip(packet_loss, 0, 10)

    throughput  = np.random.uniform(85, 100, n) - packet_loss * 0.5
    dup_packet  = np.random.poisson(0.5, n).astype(float)    # Poisson, bukan integer seragam
    chk_valid   = (np.random.rand(n) > 0.01).astype(int)     # [2] 1% checksum gagal di normal
    auth_fail   = np.random.choice([0, 0, 0, 0, 1], n)       # [2] sesekali ada auth fail

    # [4] Bias perangkat
    voltage, current, temperature, latency = apply_device_bias(
        voltage, current, temperature, latency, device_ids, n
    )

    # [8] power kotor
    power = corrupt_power(voltage, current, n)

    # [6] Outlier sporadis di voltage & latency
    voltage = inject_outliers(voltage, frac=0.015)
    latency = inject_outliers(latency, frac=0.015, hi_mult=5.0)

    # [7] NaN di normal juga ada (sensor disconnect)
    temperature = inject_nan(temperature, frac=0.015)
    latency     = inject_nan(latency, frac=0.010)

    return dict(
        voltage=voltage, current=current, power=power,
        frequency=frequency, temperature=temperature,
        latency=latency, packet_loss=packet_loss,
        throughput=throughput, duplicate_packet=dup_packet,
        checksum_valid=chk_valid, authentication_fail=auth_fail,
        label=np.zeros(n, dtype=int)
    )


# ══════════════════════════════════════════════════════════════════════════════
# 2. KONDISI ATTACK
# ══════════════════════════════════════════════════════════════════════════════

def generate_attack(n, device_ids):
    n_fdi    = n // 4
    n_replay = n // 4
    n_dos    = n // 4
    n_tamp   = n - n_fdi - n_replay - n_dos

    rows = []

    # ── False Data Injection ──────────────────────────────────────────
    # [2] Sengaja overlap dengan normal: distribusi bukan 100-400 melulu
    v = np.where(
        np.random.rand(n_fdi) < 0.4,
        np.random.uniform(205, 235, n_fdi),  # overlap ke range normal!
        np.random.uniform(100, 400, n_fdi),
    )
    c = np.random.uniform(0.5, 20, n_fdi)
    lat_fdi = lognormal_latency(n_fdi, mu=4.0, sigma=0.7)   # lebih tinggi, tapi overlap
    rows.append(dict(
        voltage=v, current=c,
        power=corrupt_power(v, c, n_fdi, noise_frac=0.3),
        frequency=np.random.uniform(46, 55, n_fdi),
        temperature=np.random.uniform(20, 75, n_fdi),
        latency=lat_fdi,
        packet_loss=lognormal_pktloss(n_fdi, mu=2.5, sigma=0.5),
        throughput=np.random.uniform(15, 75, n_fdi),
        duplicate_packet=np.random.poisson(2, n_fdi).astype(float),
        checksum_valid=np.random.choice([0, 1], n_fdi, p=[0.35, 0.65]),
        authentication_fail=np.random.randint(0, 5, n_fdi),
    ))

    # ── Replay Attack ─────────────────────────────────────────────────
    # [2] Data yang di-replay mirip normal tapi latency/dup berbeda
    base_v = np.random.uniform(215, 225, 20)
    base_c = np.random.uniform(3, 8, 20)
    idx    = np.random.choice(20, n_replay)
    rows.append(dict(
        voltage=base_v[idx] + np.random.normal(0, 0.2, n_replay),  # sedikit noise, bukan identik
        current=base_c[idx] + np.random.normal(0, 0.05, n_replay),
        power=base_v[idx] * base_c[idx] * np.random.uniform(0.90, 0.98, n_replay),
        frequency=np.random.normal(50.0, 0.05, n_replay),
        temperature=np.random.normal(30.0, 1.0, n_replay),
        latency=lognormal_latency(n_replay, mu=4.5, sigma=0.6),     # lebih lambat
        packet_loss=lognormal_pktloss(n_replay, mu=2.8, sigma=0.4),
        throughput=np.random.uniform(20, 65, n_replay),
        duplicate_packet=np.random.poisson(8, n_replay).astype(float),  # banyak duplikat
        checksum_valid=np.ones(n_replay, dtype=int),
        authentication_fail=np.random.randint(1, 8, n_replay),
    ))

    # ── DoS Attack ────────────────────────────────────────────────────
    rows.append(dict(
        voltage=np.random.uniform(195, 235, n_dos),   # [2] lebih overlap
        current=np.random.uniform(2, 12, n_dos),
        power=corrupt_power(
            np.random.uniform(195, 235, n_dos),
            np.random.uniform(2, 12, n_dos), n_dos, noise_frac=0.4
        ),
        frequency=np.random.uniform(48, 52, n_dos),
        temperature=np.random.uniform(30, 65, n_dos),
        latency=lognormal_latency(n_dos, mu=5.5, sigma=0.5),         # sangat lambat
        packet_loss=lognormal_pktloss(n_dos, mu=3.5, sigma=0.4),
        throughput=np.random.uniform(1, 25, n_dos),
        duplicate_packet=np.random.poisson(15, n_dos).astype(float),
        checksum_valid=np.random.choice([0, 1], n_dos, p=[0.5, 0.5]),
        authentication_fail=np.random.randint(2, 15, n_dos),
    ))

    # ── Data Tampering ────────────────────────────────────────────────
    rows.append(dict(
        voltage=np.where(
            np.random.rand(n_tamp) < 0.5,
            np.random.uniform(120, 160, n_tamp),
            np.random.uniform(340, 390, n_tamp)
        ),
        current=np.random.uniform(0.1, 45, n_tamp),
        power=np.random.uniform(-200, 4500, n_tamp),
        frequency=np.random.uniform(42, 62, n_tamp),
        temperature=np.random.uniform(15, 85, n_tamp),
        latency=lognormal_latency(n_tamp, mu=4.8, sigma=0.8),
        packet_loss=lognormal_pktloss(n_tamp, mu=3.0, sigma=0.6),
        throughput=np.random.uniform(5, 55, n_tamp),
        duplicate_packet=np.random.poisson(5, n_tamp).astype(float),
        checksum_valid=np.random.choice([0, 1], n_tamp, p=[0.55, 0.45]),
        authentication_fail=np.random.randint(0, 10, n_tamp),
    ))

    combined = {k: np.concatenate([r[k] for r in rows]) for k in rows[0]}

    # [4] Device bias
    voltage, current, temperature, latency = apply_device_bias(
        combined["voltage"], combined["current"],
        combined["temperature"], combined["latency"],
        device_ids, n
    )
    combined["voltage"]     = voltage
    combined["current"]     = current
    combined["temperature"] = temperature
    combined["latency"]     = latency

    # [7] NaN di attack juga ada (perangkat dimatikan paksa)
    combined["voltage"]     = inject_nan(combined["voltage"],     frac=0.008)
    combined["throughput"]  = inject_nan(combined["throughput"],  frac=0.012)

    combined["label"] = np.ones(n, dtype=int)
    return combined


# ══════════════════════════════════════════════════════════════════════════════
# 3. KONDISI FAULT
# ══════════════════════════════════════════════════════════════════════════════

def generate_fault(n, device_ids):
    n_drift   = n // 5
    n_stuck   = n // 5
    n_over    = n // 5
    n_noisy   = n // 5
    n_missing = n - n_drift - n_stuck - n_over - n_noisy

    rows = []

    # ── Sensor Drift ──────────────────────────────────────────────────
    t = np.linspace(0, 1, n_drift)
    drift_dir = np.random.choice([-1, 1])
    v_drift   = 220 + drift_dir * t * 25 + ar1_noise(n_drift, phi=0.8, sigma=1.5)
    rows.append(dict(
        voltage=np.clip(v_drift, 160, 270),
        current=jitter(np.random.uniform(3, 8, n_drift), 0.7),
        power=corrupt_power(np.clip(v_drift, 160, 270),
                            np.random.uniform(3, 8, n_drift), n_drift),
        frequency=jitter(np.full(n_drift, 50.0), 0.4),
        temperature=np.random.uniform(35, 58, n_drift),
        latency=lognormal_latency(n_drift, mu=3.0, sigma=0.5),
        packet_loss=lognormal_pktloss(n_drift, mu=0.5, sigma=0.7),
        throughput=np.random.uniform(65, 95, n_drift),
        duplicate_packet=np.random.poisson(0.8, n_drift).astype(float),
        checksum_valid=np.ones(n_drift, dtype=int),
        authentication_fail=np.zeros(n_drift, dtype=int),
    ))

    # ── Stuck Sensor ──────────────────────────────────────────────────
    # [2] Stuck kadang mirip normal: nilai konstan di range normal
    stuck_v = float(np.random.uniform(215, 228))
    stuck_c = float(np.random.uniform(4, 7))
    # Tidak 100% stuck — sesekali ada update kecil (bukan benar-benar beku)
    v_stuck = np.where(np.random.rand(n_stuck) < 0.88,
                       stuck_v,
                       np.random.uniform(215, 228, n_stuck))
    rows.append(dict(
        voltage=v_stuck,
        current=np.full(n_stuck, stuck_c),
        power=corrupt_power(v_stuck, np.full(n_stuck, stuck_c), n_stuck),
        frequency=np.full(n_stuck, 50.0),
        temperature=np.full(n_stuck, float(np.random.uniform(30, 46))),
        latency=lognormal_latency(n_stuck, mu=2.9, sigma=0.4),
        packet_loss=lognormal_pktloss(n_stuck, mu=-0.5, sigma=0.6),
        throughput=np.random.uniform(80, 100, n_stuck),
        duplicate_packet=np.random.poisson(0.3, n_stuck).astype(float),
        checksum_valid=np.ones(n_stuck, dtype=int),
        authentication_fail=np.zeros(n_stuck, dtype=int),
    ))

    # ── Overheating ───────────────────────────────────────────────────
    rows.append(dict(
        voltage=jitter(np.random.uniform(210, 232, n_over), 2.5),
        current=jitter(np.random.uniform(5, 13, n_over), 1.2),
        power=corrupt_power(
            np.random.uniform(210, 232, n_over),
            np.random.uniform(5, 13, n_over), n_over, noise_frac=0.2
        ),
        frequency=jitter(np.full(n_over, 50.0), 0.25),
        temperature=np.random.uniform(68, 100, n_over),
        latency=lognormal_latency(n_over, mu=3.2, sigma=0.5),
        packet_loss=lognormal_pktloss(n_over, mu=1.0, sigma=0.7),
        throughput=np.random.uniform(55, 92, n_over),
        duplicate_packet=np.random.poisson(1.2, n_over).astype(float),
        checksum_valid=(np.random.rand(n_over) > 0.05).astype(int),
        authentication_fail=np.random.choice([0, 0, 0, 1], n_over),
    ))

    # ── Noisy Sensor ──────────────────────────────────────────────────
    # [2] Noise range lebih sempit sehingga overlap dengan normal
    rows.append(dict(
        voltage=np.random.uniform(205, 245, n_noisy),
        current=np.random.uniform(2, 12, n_noisy),
        power=corrupt_power(
            np.random.uniform(205, 245, n_noisy),
            np.random.uniform(2, 12, n_noisy), n_noisy, noise_frac=0.25
        ),
        frequency=np.random.uniform(49.0, 51.0, n_noisy),
        temperature=np.random.uniform(28, 62, n_noisy),
        latency=lognormal_latency(n_noisy, mu=3.5, sigma=0.8),
        packet_loss=lognormal_pktloss(n_noisy, mu=1.2, sigma=0.8),
        throughput=np.random.uniform(55, 100, n_noisy),
        duplicate_packet=np.random.poisson(2, n_noisy).astype(float),
        checksum_valid=np.ones(n_noisy, dtype=int),
        authentication_fail=np.random.choice([0, 0, 0, 0, 1], n_noisy),
    ))

    # ── Missing Values (NaN) ──────────────────────────────────────────
    v_miss    = np.random.uniform(215, 226, n_missing).astype(float)
    c_miss    = np.random.uniform(3.5, 7.5, n_missing).astype(float)
    temp_miss = np.random.uniform(26, 58, n_missing).astype(float)
    freq_miss = np.random.uniform(49.8, 50.2, n_missing).astype(float)

    nan_v     = np.random.rand(n_missing) < 0.15
    nan_c     = np.random.rand(n_missing) < 0.15
    nan_temp  = np.random.rand(n_missing) < 0.20
    nan_freq  = np.random.rand(n_missing) < 0.08   # frekuensi juga bisa hilang

    v_miss[nan_v]       = np.nan
    c_miss[nan_c]       = np.nan
    temp_miss[nan_temp] = np.nan
    freq_miss[nan_freq] = np.nan

    rows.append(dict(
        voltage=v_miss, current=c_miss,
        power=np.where(nan_v | nan_c, np.nan,
                       corrupt_power(v_miss, c_miss, n_missing)),
        frequency=freq_miss,
        temperature=temp_miss,
        latency=lognormal_latency(n_missing, mu=2.9, sigma=0.5),
        packet_loss=lognormal_pktloss(n_missing, mu=0.5, sigma=0.8),
        throughput=np.random.uniform(70, 100, n_missing),
        duplicate_packet=np.random.poisson(0.5, n_missing).astype(float),
        checksum_valid=np.ones(n_missing, dtype=int),
        authentication_fail=np.zeros(n_missing, dtype=int),
    ))

    combined = {k: np.concatenate([r[k] for r in rows]) for k in rows[0]}

    # [4] Device bias
    voltage, current, temperature, latency = apply_device_bias(
        combined["voltage"], combined["current"],
        combined["temperature"], combined["latency"],
        device_ids, n
    )
    combined["voltage"]     = voltage
    combined["current"]     = current
    combined["temperature"] = temperature
    combined["latency"]     = latency

    # [6] Outlier ekstrem sesekali
    combined["temperature"] = inject_outliers(combined["temperature"],
                                              frac=0.02, hi_mult=2.5)

    combined["label"] = np.full(n, 2, dtype=int)
    return combined


# ══════════════════════════════════════════════════════════════════════════════
# ASSEMBLE DATASET
# ══════════════════════════════════════════════════════════════════════════════

print("⚙  Generating NORMAL data  ...")
dev_n  = [random.choice(DEVICE_IDS) for _ in range(N_NORMAL)]
d_normal = generate_normal(N_NORMAL, dev_n)

print("⚙  Generating ATTACK data  ...")
dev_a  = [random.choice(DEVICE_IDS) for _ in range(N_ATTACK)]
d_attack = generate_attack(N_ATTACK, dev_a)

print("⚙  Generating FAULT data   ...")
dev_f  = [random.choice(DEVICE_IDS) for _ in range(N_FAULT)]
d_fault  = generate_fault(N_FAULT, dev_f)

keys = ['voltage','current','power','frequency','temperature',
        'latency','packet_loss','throughput','duplicate_packet',
        'checksum_valid','authentication_fail','label']

data = {k: np.concatenate([d_normal[k], d_attack[k], d_fault[k]]) for k in keys}
data['timestamp'] = timestamps(TOTAL)
data['device_id'] = dev_n + dev_a + dev_f

# ── Shuffle ───────────────────────────────────────────────────────────────────
print("⚙  Shuffling ...")
idx = np.arange(TOTAL)
np.random.shuffle(idx)
for k in data:
    data[k] = np.array(data[k], dtype=object)[idx] if k in ('timestamp','device_id') \
               else np.array(data[k])[idx]

# ── [1] Label noise (~5%) ─────────────────────────────────────────────────────
print("⚙  Injecting label noise ...")
labels     = data['label'].copy()
noise_mask = np.random.rand(TOTAL) < 0.05
for i in np.where(noise_mask)[0]:
    other = [x for x in [0, 1, 2] if x != labels[i]]
    labels[i] = random.choice(other)
data['label'] = labels

# ── [10] Duplicate rows (~0.5%) ───────────────────────────────────────────────
print("⚙  Adding duplicate rows ...")
n_dup = int(TOTAL * 0.005)
dup_idx = np.random.choice(TOTAL, n_dup, replace=False)
for k in data:
    arr = list(data[k])
    arr += [arr[i] for i in dup_idx]
    data[k] = arr

FINAL_LEN = TOTAL + n_dup

# ── DataFrame ─────────────────────────────────────────────────────────────────
cols = ['timestamp','device_id','voltage','current','power','frequency',
        'temperature','latency','packet_loss','throughput',
        'duplicate_packet','checksum_valid','authentication_fail','label']
df = pd.DataFrame(data)[cols]

# Bulatkan: sengaja tidak serapi dulu
num_cols_4dp = ['voltage','current','power','frequency']
num_cols_2dp = ['latency','packet_loss','throughput']
df[num_cols_4dp] = df[num_cols_4dp].round(4)
df[num_cols_2dp] = df[num_cols_2dp].round(2)
df['temperature']     = df['temperature'].round(3)
df['duplicate_packet'] = df['duplicate_packet'].astype("Int64")   # nullable int

# ── Simpan CSV ────────────────────────────────────────────────────────────────
OUTPUT_CSV = 'smart_grid_security_dataset.csv'
df.to_csv(OUTPUT_CSV, index=False)

# ── Laporan ───────────────────────────────────────────────────────────────────
print(f"\n✅ Dataset saved → {OUTPUT_CSV}")
print(f"   Total rows : {len(df):,}  (termasuk {n_dup} duplikat)")
print(f"   Columns    : {list(df.columns)}")

print("\nDistribusi label (setelah noise):")
label_map = {0: 'NORMAL', 1: 'ATTACK', 2: 'FAULT'}
dist = df['label'].map(label_map).value_counts()
for name, count in dist.items():
    print(f"   {name:6s}: {count:,}  ({count/len(df)*100:.2f}%)")

print("\nNaN per kolom:")
nan_counts = df.isnull().sum()
print(nan_counts[nan_counts > 0].to_string())

print("\nStatistik per fitur (latency, packet_loss — harusnya skewed):")
print(df[['latency','packet_loss']].describe().round(2).to_string())

print("\nRentang voltage per kelas (harusnya overlap):")
for lbl, name in label_map.items():
    sub = df[df['label'] == lbl]['voltage'].dropna()
    print(f"   {name:6s}: [{sub.min():.1f}, {sub.max():.1f}]  mean={sub.mean():.1f}")