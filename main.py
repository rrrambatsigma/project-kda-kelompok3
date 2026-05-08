from generator_instance import (
    normal_voltage,
    anomaly_voltage,
    normal_iot_input,
    anomaly_iot_input,
)

def main():
    n = 1000  # jumlah baris data

    print("Generating data...")

    normal_voltage(n).to_csv("voltage_normal.csv", index=False)
    print(f"  [OK] voltage_normal.csv ({n} rows)")

    anomaly_voltage(n).to_csv("voltage_anomaly.csv", index=False)
    print(f"  [OK] voltage_anomaly.csv ({n} rows)")

    normal_iot_input(n).to_csv("iot_normal.csv", index=False)
    print(f"  [OK] iot_normal.csv ({n} rows)")

    anomaly_iot_input(n).to_csv("iot_anomaly.csv", index=False)
    print(f"  [OK] iot_anomaly.csv ({n} rows)")

    print("\nSelesai! Semua file CSV berhasil dibuat.")

if __name__ == "__main__":
    main()
