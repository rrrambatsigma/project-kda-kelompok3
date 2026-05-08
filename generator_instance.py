import pandas as pd
import numpy as np
from datetime import datetime, timedelta

voltage_columns = [
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

iot_columns = [
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

voltage_anomaly = pd.DataFrame(columns=voltage_columns)
iot_anomaly = pd.DataFrame(columns=iot_columns)
voltage_normal = pd.DataFrame(columns=voltage_columns)
iot_normal = pd.DataFrame(columns=iot_columns)


# =======================================
#   GENERATE NORMAL DATA FOR VOLTAGE
# =======================================
x = int(100)

def normal_voltage(x: int):

    voltage_normal = pd.DataFrame()

    start_time = datetime(2022, 1, 1)
    end_time = start_time + timedelta(days=x)

    voltage_normal['timestamp'] = pd.date_range(
        start=start_time,
        end=end_time,
        periods=x
    )

    voltage_normal['sensor_id'] = 'V-01'
    voltage_normal['voltage'] = np.random.normal(220, 5, x).round(2)
    voltage_normal['current'] = np.random.normal(10, 1, x).round(2)
    voltage_normal['frequency'] = np.random.normal(50, 0.1, x).round(2)
    voltage_normal['power'] = (
        voltage_normal['voltage']
        * voltage_normal['current']
    ).round(2)

    voltage_normal['temperature'] = np.random.normal(30, 5, x).round(2)
    voltage_normal['load_percentage'] = np.random.uniform(20, 80, x).round(2)
    voltage_normal['status'] = 0

    return voltage_normal


# =======================================
#   GENERATE ANOMALY DATA FOR VOLTAGE
# =======================================
def anomaly_voltage(x: int):
    global voltage_anomaly

    voltage_anomaly = pd.DataFrame()

    start_time = datetime(2022, 1, 1)
    end_time = start_time + timedelta(days=x)

    voltage_anomaly['timestamp'] = pd.date_range(
        start=start_time,
        end=end_time,
        periods=x
    )

    voltage_anomaly['sensor_id'] = 'V-01'
    voltage_anomaly['voltage'] = np.random.normal(400, 30, x).round(2)
    voltage_anomaly['current'] = np.random.normal(30, 5, x).round(2)
    voltage_anomaly['frequency'] = np.random.normal(60, 3, x).round(2)
    voltage_anomaly['power'] = (
        voltage_anomaly['voltage']
        * voltage_anomaly['current']
    ).round(2)

    voltage_anomaly['temperature'] = np.random.normal(80, 10, x).round(2)
    voltage_anomaly['load_percentage'] = np.random.uniform(90, 100, x).round(2)
    voltage_anomaly['status'] = 1

    return voltage_anomaly
   

   
# =======================================
#   GENERATE NORMAL DATA FOR IOT
# =======================================

def normal_iot_input(x: int):

    iot_df = pd.DataFrame()

    start_time = datetime(2022, 1, 1)
    end_time = start_time + timedelta(days=x)

    iot_df['timestamp'] = pd.date_range(
        start=start_time,
        end=end_time,
        periods=x
    )

    iot_df['device_id'] = 'V-01'

    iot_df['packet_size'] = np.random.normal(
        512,
        50,
        x
    ).round(2)

    iot_df['latency'] = np.random.normal(
        10,
        2,
        x
    ).round(2)

    iot_df['signal_strength'] = np.random.normal(
        -60,
        5,
        x
    ).round(2)

    iot_df['memory_usage'] = np.random.uniform(
        20,
        60,
        x
    ).round(2)

    iot_df['battery_level'] = np.random.uniform(
        50,
        100,
        x
    ).round(2)

    iot_df['cpu_usage'] = np.random.uniform(
        10,
        40,
        x
    ).round(2)

    iot_df['failed_packets'] = np.random.randint(
        0,
        3,
        x
    )

    iot_df['status'] = 0

    return iot_df


# =======================================
#   GENERATE ANOMLALY DATA FOR IOT
# =======================================
def anomaly_iot_input(x: int):
    global iot_anomaly

    iot_anomaly = pd.DataFrame()

    start_time = datetime(2022, 1, 1)
    end_time = start_time + timedelta(days=x)

    iot_anomaly['timestamp'] = pd.date_range(
        start=start_time,
        end=end_time,
        periods=x
    )

    iot_anomaly['device_id'] = 'V-01'
    iot_anomaly['packet_size'] = np.random.normal(
        2000,
        300,
        x
    ).round(2)

    iot_anomaly['latency'] = np.random.normal(
        500,
        50,
        x
    ).round(2)

    iot_anomaly['signal_strength'] = np.random.normal(
        -100,
        10,
        x
    ).round(2)

    iot_anomaly['memory_usage'] = np.random.uniform(
        85,
        100,
        x
    ).round(2)

    iot_anomaly['battery_level'] = np.random.uniform(
        0,
        20,
        x
    ).round(2)

    iot_anomaly['cpu_usage'] = np.random.uniform(
        90,
        100,
        x
    ).round(2)

    iot_anomaly['failed_packets'] = np.random.randint(
        20,
        100,
        x
    )

    iot_anomaly['status'] = 1

    return iot_anomaly

print(normal_voltage(x))