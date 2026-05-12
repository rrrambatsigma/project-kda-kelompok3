"""
Smart Grid IoT Security Dataset Generator
=========================================
Menghasilkan 10.000 data dummy untuk simulasi keamanan smart grid
dengan kondisi: NORMAL (0), ATTACK (1), FAULT (2)
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
TOTAL      = 10_000
N_NORMAL   = int(TOTAL * 0.60)            # 6000
N_ATTACK   = int(TOTAL * 0.25)            # 2500
N_FAULT    = TOTAL - N_NORMAL - N_ATTACK  # 1500

DEVICE_IDS = [f"SGD-{i:04d}" for i in range(1, 51)]   # 50 perangkat
START_TIME = datetime(2024, 1, 1, 0, 0, 0)


# ══════════════════════════════════════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════════════════════════════════════

def jitter(arr, scale=0.5):
    return arr + np.random.normal(0, scale, len(arr))

def timestamps(n, base=START_TIME, step_sec=5):
    return [base + timedelta(seconds=i * step_sec) for i in range(n)]


# ══════════════════════════════════════════════════════════════════════════════
# 1. KONDISI NORMAL
# ══════════════════════════════════════════════════════════════════════════════

def generate_normal(n):
    voltage     = np.random.uniform(215, 225, n)
    current     = np.random.uniform(3, 8, n)
    frequency   = np.random.uniform(49.8, 50.2, n)
    temperature = np.random.uniform(25, 40, n)
    latency     = np.random.uniform(5, 30, n)
    packet_loss = np.random.uniform(0, 2, n)
    throughput  = np.random.uniform(90, 100, n)
    dup_packet  = np.random.randint(0, 3, n).astype(float)
    chk_valid   = np.ones(n, dtype=int)
    auth_fail   = np.zeros(n, dtype=int)

    # Smooth dengan rolling mean kecil
    voltage = pd.Series(jitter(voltage, 0.3)).rolling(3, min_periods=1).mean().values
    current = pd.Series(jitter(current, 0.1)).rolling(3, min_periods=1).mean().values
    power   = voltage * current * 0.95

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

def generate_attack(n):
    n_fdi    = n // 4
    n_replay = n // 4
    n_dos    = n // 4
    n_tamp   = n - n_fdi - n_replay - n_dos

    rows = []

    # False Data Injection
    v = np.random.uniform(100, 400, n_fdi)
    c = np.random.uniform(0.1, 30, n_fdi)
    rows.append(dict(
        voltage=v, current=c,
        power=v * c * np.random.uniform(0.4, 1.5, n_fdi),
        frequency=np.random.uniform(45, 56, n_fdi),
        temperature=np.random.uniform(20, 80, n_fdi),
        latency=np.random.uniform(50, 300, n_fdi),
        packet_loss=np.random.uniform(5, 40, n_fdi),
        throughput=np.random.uniform(10, 70, n_fdi),
        duplicate_packet=np.random.randint(0, 10, n_fdi).astype(float),
        checksum_valid=np.random.choice([0, 1], n_fdi, p=[0.4, 0.6]),
        authentication_fail=np.random.randint(0, 5, n_fdi),
    ))

    # Replay Attack
    base_v = np.random.uniform(215, 225, 20)
    base_c = np.random.uniform(3, 8, 20)
    idx    = np.random.choice(20, n_replay)
    rows.append(dict(
        voltage=base_v[idx], current=base_c[idx],
        power=base_v[idx] * base_c[idx] * 0.95,
        frequency=np.full(n_replay, 50.0),
        temperature=np.full(n_replay, 30.0),
        latency=np.random.uniform(100, 500, n_replay),
        packet_loss=np.random.uniform(10, 50, n_replay),
        throughput=np.random.uniform(20, 60, n_replay),
        duplicate_packet=np.random.randint(5, 30, n_replay).astype(float),
        checksum_valid=np.ones(n_replay, dtype=int),
        authentication_fail=np.random.randint(1, 8, n_replay),
    ))

    # DoS Attack
    rows.append(dict(
        voltage=np.random.uniform(200, 230, n_dos),
        current=np.random.uniform(2, 10, n_dos),
        power=np.random.uniform(400, 2300, n_dos),
        frequency=np.random.uniform(48, 52, n_dos),
        temperature=np.random.uniform(30, 60, n_dos),
        latency=np.random.uniform(300, 1000, n_dos),
        packet_loss=np.random.uniform(40, 80, n_dos),
        throughput=np.random.uniform(1, 20, n_dos),
        duplicate_packet=np.random.randint(10, 50, n_dos).astype(float),
        checksum_valid=np.random.choice([0, 1], n_dos, p=[0.5, 0.5]),
        authentication_fail=np.random.randint(2, 15, n_dos),
    ))

    # Data Tampering
    rows.append(dict(
        voltage=np.where(
            np.random.rand(n_tamp) < 0.5,
            np.random.uniform(100, 150, n_tamp),
            np.random.uniform(350, 400, n_tamp)
        ),
        current=np.random.uniform(0.01, 50, n_tamp),
        power=np.random.uniform(-500, 5000, n_tamp),
        frequency=np.random.uniform(40, 65, n_tamp),
        temperature=np.random.uniform(10, 90, n_tamp),
        latency=np.random.uniform(100, 800, n_tamp),
        packet_loss=np.random.uniform(20, 70, n_tamp),
        throughput=np.random.uniform(5, 50, n_tamp),
        duplicate_packet=np.random.randint(2, 20, n_tamp).astype(float),
        checksum_valid=np.random.choice([0, 1], n_tamp, p=[0.6, 0.4]),
        authentication_fail=np.random.randint(0, 10, n_tamp),
    ))

    combined = {k: np.concatenate([r[k] for r in rows]) for k in rows[0]}
    combined['label'] = np.ones(n, dtype=int)
    return combined


# ══════════════════════════════════════════════════════════════════════════════
# 3. KONDISI FAULT
# ══════════════════════════════════════════════════════════════════════════════

def generate_fault(n):
    n_drift   = n // 5
    n_stuck   = n // 5
    n_over    = n // 5
    n_noisy   = n // 5
    n_missing = n - n_drift - n_stuck - n_over - n_noisy

    rows = []

    # Sensor Drift
    t = np.linspace(0, 1, n_drift)
    drift_dir = np.random.choice([-1, 1])
    v_drift = 220 + drift_dir * t * 30 + np.random.normal(0, 1, n_drift)
    rows.append(dict(
        voltage=np.clip(v_drift, 160, 260),
        current=jitter(np.random.uniform(3, 8, n_drift), 0.5),
        power=np.clip(v_drift, 160, 260) * np.random.uniform(3, 8, n_drift) * 0.95,
        frequency=jitter(np.full(n_drift, 50.0), 0.3),
        temperature=np.random.uniform(35, 55, n_drift),
        latency=np.random.uniform(10, 60, n_drift),
        packet_loss=np.random.uniform(0, 5, n_drift),
        throughput=np.random.uniform(70, 95, n_drift),
        duplicate_packet=np.random.randint(0, 3, n_drift).astype(float),
        checksum_valid=np.ones(n_drift, dtype=int),
        authentication_fail=np.zeros(n_drift, dtype=int),
    ))

    # Stuck Sensor
    stuck_v = float(np.random.uniform(215, 225))
    stuck_c = float(np.random.uniform(3, 8))
    rows.append(dict(
        voltage=np.full(n_stuck, stuck_v),
        current=np.full(n_stuck, stuck_c),
        power=np.full(n_stuck, stuck_v * stuck_c * 0.95),
        frequency=np.full(n_stuck, 50.0),
        temperature=np.full(n_stuck, float(np.random.uniform(30, 45))),
        latency=np.random.uniform(5, 35, n_stuck),
        packet_loss=np.random.uniform(0, 3, n_stuck),
        throughput=np.random.uniform(80, 100, n_stuck),
        duplicate_packet=np.random.randint(0, 2, n_stuck).astype(float),
        checksum_valid=np.ones(n_stuck, dtype=int),
        authentication_fail=np.zeros(n_stuck, dtype=int),
    ))

    # Overheating
    rows.append(dict(
        voltage=jitter(np.random.uniform(210, 230, n_over), 2),
        current=jitter(np.random.uniform(5, 12, n_over), 1),
        power=np.random.uniform(1000, 2500, n_over),
        frequency=jitter(np.full(n_over, 50.0), 0.2),
        temperature=np.random.uniform(70, 100, n_over),
        latency=np.random.uniform(20, 80, n_over),
        packet_loss=np.random.uniform(1, 10, n_over),
        throughput=np.random.uniform(60, 90, n_over),
        duplicate_packet=np.random.randint(0, 5, n_over).astype(float),
        checksum_valid=np.ones(n_over, dtype=int),
        authentication_fail=np.random.randint(0, 2, n_over),
    ))

    # Noisy Sensor
    rows.append(dict(
        voltage=np.random.uniform(190, 250, n_noisy),
        current=np.random.uniform(1, 15, n_noisy),
        power=np.random.uniform(200, 3500, n_noisy),
        frequency=np.random.uniform(48, 52, n_noisy),
        temperature=np.random.uniform(25, 65, n_noisy),
        latency=np.random.uniform(5, 100, n_noisy),
        packet_loss=np.random.uniform(0, 15, n_noisy),
        throughput=np.random.uniform(50, 100, n_noisy),
        duplicate_packet=np.random.randint(0, 8, n_noisy).astype(float),
        checksum_valid=np.ones(n_noisy, dtype=int),
        authentication_fail=np.random.randint(0, 2, n_noisy),
    ))

    # Missing Values (NaN)
    v_miss    = np.random.uniform(215, 225, n_missing).astype(float)
    c_miss    = np.random.uniform(3, 8, n_missing).astype(float)
    temp_miss = np.random.uniform(25, 60, n_missing).astype(float)

    nan_v    = np.random.rand(n_missing) < 0.15
    nan_c    = np.random.rand(n_missing) < 0.15
    nan_temp = np.random.rand(n_missing) < 0.20

    v_miss[nan_v]       = np.nan
    c_miss[nan_c]       = np.nan
    temp_miss[nan_temp] = np.nan

    rows.append(dict(
        voltage=v_miss, current=c_miss,
        power=np.where(nan_v | nan_c, np.nan, v_miss * c_miss * 0.95),
        frequency=jitter(np.full(n_missing, 50.0), 0.1),
        temperature=temp_miss,
        latency=np.random.uniform(5, 40, n_missing),
        packet_loss=np.random.uniform(0, 8, n_missing),
        throughput=np.random.uniform(70, 100, n_missing),
        duplicate_packet=np.random.randint(0, 3, n_missing).astype(float),
        checksum_valid=np.ones(n_missing, dtype=int),
        authentication_fail=np.zeros(n_missing, dtype=int),
    ))

    combined = {k: np.concatenate([r[k] for r in rows]) for k in rows[0]}
    combined['label'] = np.full(n, 2, dtype=int)
    return combined


# ══════════════════════════════════════════════════════════════════════════════
# ASSEMBLE DATASET
# ══════════════════════════════════════════════════════════════════════════════

print("⚙  Generating NORMAL data  ...")
d_normal = generate_normal(N_NORMAL)

print("⚙  Generating ATTACK data  ...")
d_attack = generate_attack(N_ATTACK)

print("⚙  Generating FAULT data   ...")
d_fault  = generate_fault(N_FAULT)

keys = ['voltage','current','power','frequency','temperature',
        'latency','packet_loss','throughput','duplicate_packet',
        'checksum_valid','authentication_fail','label']

data = {k: np.concatenate([d_normal[k], d_attack[k], d_fault[k]]) for k in keys}
data['timestamp'] = timestamps(TOTAL)
data['device_id'] = [random.choice(DEVICE_IDS) for _ in range(TOTAL)]

# Shuffle
idx = np.arange(TOTAL)
np.random.shuffle(idx)
for k in data:
    data[k] = np.array(data[k])[idx] if k != 'timestamp' else [data[k][i] for i in idx]

# DataFrame
cols = ['timestamp','device_id','voltage','current','power','frequency',
        'temperature','latency','packet_loss','throughput',
        'duplicate_packet','checksum_valid','authentication_fail','label']
df = pd.DataFrame(data)[cols]

num_cols = ['voltage','current','power','frequency','temperature',
            'latency','packet_loss','throughput']
df[num_cols] = df[num_cols].round(4)
df['duplicate_packet'] = df['duplicate_packet'].round(0)

# Simpan CSV
OUTPUT_CSV = 'smart_grid_security_dataset.csv'
df.to_csv(OUTPUT_CSV, index=False)

print(f"\n✅ Dataset saved → {OUTPUT_CSV}")
print(f"   Total rows : {len(df):,}")
print(f"   Columns    : {list(df.columns)}")
print("\nDistribusi label:")
label_map = {0: 'NORMAL', 1: 'ATTACK', 2: 'FAULT'}
dist = df['label'].map(label_map).value_counts()
for name, count in dist.items():
    print(f"   {name:6s}: {count:,}  ({count/len(df)*100:.1f}%)")
print("\nNaN per kolom:")
nan_counts = df.isnull().sum()
print(nan_counts[nan_counts > 0].to_string())