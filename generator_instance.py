import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path


# ============================================================
# CONFIG
# ============================================================

TOTAL_ROWS = 1000
RANDOM_SEED = 42

# Root project berdasarkan lokasi file generator_instance.py
BASE_DIR = Path(__file__).resolve().parent

# Folder penyimpanan data mentah
RAW_DIR = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

np.random.seed(RANDOM_SEED)


# ============================================================
# COLUMN DEFINITIONS
# ============================================================

VOLTAGE_COLUMNS = [
    "timestamp",
    "sensor_id",
    "voltage",
    "current",
    "frequency",
    "power",
    "temperature",
    "load_percentage",
    "status"
]

IOT_COLUMNS = [
    "timestamp",
    "device_id",
    "packet_size",
    "latency",
    "signal_strength",
    "cpu_usage",
    "memory_usage",
    "battery_level",
    "failed_packets",
    "status"
]


# ============================================================
# HELPER FUNCTION
# ============================================================

def generate_timestamp(total_rows: int) -> pd.DatetimeIndex:
    """
    Membuat timestamp dummy sebanyak total_rows.
    """
    start_time = datetime(2022, 1, 1)
    end_time = start_time + timedelta(days=total_rows)

    return pd.date_range(
        start=start_time,
        end=end_time,
        periods=total_rows
    )


# ============================================================
# GENERATE NORMAL DATA FOR VOLTAGE
# ============================================================

def normal_voltage(total_rows: int) -> pd.DataFrame:
    """
    Membuat dummy data voltage kondisi normal.

    status = 0 berarti normal.
    """
    df = pd.DataFrame()

    df["timestamp"] = generate_timestamp(total_rows)
    df["sensor_id"] = "V-01"

    df["voltage"] = np.random.normal(220, 5, total_rows).round(2)
    df["current"] = np.random.normal(10, 1, total_rows).round(2)
    df["frequency"] = np.random.normal(50, 0.1, total_rows).round(2)

    df["power"] = (
        df["voltage"] * df["current"]
    ).round(2)

    df["temperature"] = np.random.normal(30, 5, total_rows).round(2)
    df["load_percentage"] = np.random.uniform(20, 80, total_rows).round(2)
    df["status"] = 0

    return df[VOLTAGE_COLUMNS]


# ============================================================
# GENERATE ANOMALY DATA FOR VOLTAGE
# ============================================================

def anomaly_voltage(total_rows: int) -> pd.DataFrame:
    """
    Membuat dummy data voltage kondisi anomaly/attack.

    status = 1 berarti attack/anomaly.
    """
    df = pd.DataFrame()

    df["timestamp"] = generate_timestamp(total_rows)
    df["sensor_id"] = "V-01"

    df["voltage"] = np.random.normal(400, 30, total_rows).round(2)
    df["current"] = np.random.normal(30, 5, total_rows).round(2)
    df["frequency"] = np.random.normal(60, 3, total_rows).round(2)

    df["power"] = (
        df["voltage"] * df["current"]
    ).round(2)

    df["temperature"] = np.random.normal(80, 10, total_rows).round(2)
    df["load_percentage"] = np.random.uniform(90, 100, total_rows).round(2)
    df["status"] = 1

    return df[VOLTAGE_COLUMNS]


# ============================================================
# GENERATE NORMAL DATA FOR IOT
# ============================================================

def normal_iot_input(total_rows: int) -> pd.DataFrame:
    """
    Membuat dummy data IoT kondisi normal.

    status = 0 berarti normal.
    """
    df = pd.DataFrame()

    df["timestamp"] = generate_timestamp(total_rows)
    df["device_id"] = "IOT-01"

    df["packet_size"] = np.random.normal(512, 50, total_rows).round(2)
    df["latency"] = np.random.normal(10, 2, total_rows).round(2)
    df["signal_strength"] = np.random.normal(-60, 5, total_rows).round(2)

    df["cpu_usage"] = np.random.uniform(10, 40, total_rows).round(2)
    df["memory_usage"] = np.random.uniform(20, 60, total_rows).round(2)
    df["battery_level"] = np.random.uniform(50, 100, total_rows).round(2)
    df["failed_packets"] = np.random.randint(0, 3, total_rows)

    df["status"] = 0

    return df[IOT_COLUMNS]


# ============================================================
# GENERATE ANOMALY DATA FOR IOT
# ============================================================

def anomaly_iot_input(total_rows: int) -> pd.DataFrame:
    """
    Membuat dummy data IoT kondisi anomaly/attack.

    status = 1 berarti attack/anomaly.
    """
    df = pd.DataFrame()

    df["timestamp"] = generate_timestamp(total_rows)
    df["device_id"] = "IOT-01"

    df["packet_size"] = np.random.normal(2000, 300, total_rows).round(2)
    df["latency"] = np.random.normal(500, 50, total_rows).round(2)
    df["signal_strength"] = np.random.normal(-100, 10, total_rows).round(2)

    df["cpu_usage"] = np.random.uniform(90, 100, total_rows).round(2)
    df["memory_usage"] = np.random.uniform(85, 100, total_rows).round(2)
    df["battery_level"] = np.random.uniform(0, 20, total_rows).round(2)
    df["failed_packets"] = np.random.randint(20, 100, total_rows)

    df["status"] = 1

    return df[IOT_COLUMNS]


# ============================================================
# SAVE DATASET
# ============================================================

def save_dataset(df: pd.DataFrame, file_name: str) -> Path:
    """
    Menyimpan dataframe ke folder data/raw.
    """
    output_path = RAW_DIR / file_name
    df.to_csv(output_path, index=False)
    return output_path


# ============================================================
# MAIN PROCESS
# ============================================================

def main() -> None:
    """
    Generate semua dummy dataset dan simpan ke data/raw.
    """
    print("Generating dummy datasets...")
    print(f"Total rows per dataset: {TOTAL_ROWS}")
    print(f"Output folder: {RAW_DIR}")

    voltage_normal_df = normal_voltage(TOTAL_ROWS)
    voltage_anomaly_df = anomaly_voltage(TOTAL_ROWS)

    iot_normal_df = normal_iot_input(TOTAL_ROWS)
    iot_anomaly_df = anomaly_iot_input(TOTAL_ROWS)

    saved_files = {
        "voltage_normal.csv": save_dataset(voltage_normal_df, "voltage_normal.csv"),
        "voltage_anomaly.csv": save_dataset(voltage_anomaly_df, "voltage_anomaly.csv"),
        "iot_normal.csv": save_dataset(iot_normal_df, "iot_normal.csv"),
        "iot_anomaly.csv": save_dataset(iot_anomaly_df, "iot_anomaly.csv"),
    }

    print("\nDataset berhasil dibuat dan disimpan ke data/raw.")
    print("File yang dibuat:")

    for file_name, file_path in saved_files.items():
        print(f"- {file_name}: {file_path}")

    print("\nShape dataset:")
    print("voltage_normal :", voltage_normal_df.shape)
    print("voltage_anomaly:", voltage_anomaly_df.shape)
    print("iot_normal     :", iot_normal_df.shape)
    print("iot_anomaly    :", iot_anomaly_df.shape)

    print("\nPreview voltage_normal:")
    print(voltage_normal_df.head())

    print("\nPreview voltage_anomaly:")
    print(voltage_anomaly_df.head())


if __name__ == "__main__":
    main()