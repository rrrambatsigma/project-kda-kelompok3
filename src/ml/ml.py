import pandas as pd
import numpy as np
import os
import sys
import warnings
import json
import csv
import threading
import time
import requests
from collections import deque
from datetime import datetime
from copy import deepcopy

warnings.filterwarnings('ignore')

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report, accuracy_score, f1_score
)
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
import joblib

# Tambah path ke module encrypt (ada di src/security/)
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "security"
))
from encrypt import build_packet, setup_keys

# ─────────────────────────────────────────────
# PROJECT PATHS (PORTABLE)
# ─────────────────────────────────────────────
# ml.py → ml/ → src/ → project-root/ (3 level naik)
BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
HASIL_DIR = os.path.join(BASE_DIR, "hasil")

OUTPUT_DIR = HASIL_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 0 = Normal, 1 = Attack, 2 = Fault
LABEL_MAP   = {0: "Normal", 1: "Attack", 2: "Fault"}
LABEL_NAMES = ["Normal", "Attack", "Fault"]
N_ITERATIONS = 5

# STREAMING & DRIFT MONITORING CONSTANTS
STREAM_URL = os.environ.get("STREAM_URL", "http://localhost:5055/data/realtime")

# [RAMBAT] Endpoint tujuan kirim encrypted packet ke backend
PREDICTION_POST_URL = "http://localhost:8001/prediction/receive"

STREAM_BUFFER_SIZE = 500
TRAINING_BUFFER_SIZE = 200
DRIFT_LOG_FILE = os.path.join(OUTPUT_DIR, "predictions", "hasil_prediksi_drift.csv")
MODEL_DIR = os.path.join(OUTPUT_DIR, "models")  
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "predictions"), exist_ok=True)

print(f"[PATH] BASE_DIR  : {BASE_DIR}")
print(f"[PATH] DATA_DIR  : {DATA_DIR}")
print(f"[PATH] HASIL_DIR : {HASIL_DIR}")
print(f"[PATH] MODEL_DIR : {MODEL_DIR}")

# Ground truth CSV tidak tersedia di arsitektur streaming
GROUND_TRUTH_CSV = None

# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
def load_data():
    print("\n[1] Load data")
    train_df = pd.read_csv(
        os.path.join(DATA_DIR, "df_train.csv")
    )

    test_df = pd.read_csv(
        os.path.join(DATA_DIR, "df_test_lengkap.csv")
    )

    drop_cols = ['timestamp', 'device_id']

    X_train  = train_df.drop(columns=drop_cols + ['label'], errors='ignore')
    y_train  = train_df['label']

    test_raw = test_df.copy()

    X_test   = test_df.drop(columns=drop_cols + ['label'], errors='ignore')
    y_test   = test_df['label']

    y_train = y_train.reset_index(drop=True)
    y_test  = y_test.reset_index(drop=True)

    print(f"    Train : {X_train.shape[0]} baris | {X_train.shape[1]} fitur")
    print(f"    Test  : {X_test.shape[0]} baris  | {X_test.shape[1]} fitur")
    print(f"    Label : {LABEL_NAMES}")

    print(f"    Distribusi Train:")
    print(y_train.value_counts().sort_index().rename(LABEL_MAP).to_string())
    print(f"    Distribusi Test (Hidden untuk evaluasi):")
    print(y_test.value_counts().sort_index().rename(LABEL_MAP).to_string())

    scaler    = StandardScaler()
    X_train_s = pd.DataFrame(scaler.fit_transform(X_train), columns=X_train.columns)
    X_test_s  = pd.DataFrame(scaler.transform(X_test),      columns=X_test.columns)

    return X_train_s, y_train, X_test_s, y_test, test_raw


# ─────────────────────────────────────────────
# MODEL
# ─────────────────────────────────────────────
def get_models(seed=42):
    return {
        "Decision_Tree"      : DecisionTreeClassifier(random_state=seed, max_depth=10),
        "Random_Forest"      : RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1),
        "Logistic_Regression": LogisticRegression(max_iter=1000, random_state=seed, n_jobs=-1),
    }


# ─────────────────────────────────────────────
# TRAIN & PREDICT
# ─────────────────────────────────────────────
def train_and_predict_all(X_train, y_train, X_test, y_test, n_iterations=5):
    print(f"\n[2] Training setiap model ({n_iterations} iterasi masing-masing)...")
    print(f"    Model : Decision Tree | Random Forest | Logistic Regression\n")

    results   = {}
    pred_dict = {}

    for model_name in get_models().keys():
        print(f"  {'─'*50}")
        print(f"  Model: {model_name.replace('_', ' ')}")
        print(f"  {'─'*50}")

        all_proba    = []
        iter_records = []

        for i in range(n_iterations):
            seed  = 42 + i * 7
            model = get_models(seed=seed)[model_name]
            model.fit(X_train, y_train)

            proba = model.predict_proba(X_test)
            all_proba.append(proba)

            cv_scores = cross_val_score(
                get_models(seed=seed)[model_name],
                X_train, y_train, cv=5, scoring='accuracy', n_jobs=-1
            )
            iter_records.append({
                'Model'      : model_name.replace('_', ' '),
                'Iterasi'    : i + 1,
                'Seed'       : seed,
                'CV_Acc_Mean': round(cv_scores.mean(), 4),
                'CV_Acc_Std' : round(cv_scores.std(),  4),
            })
            print(f"    Iter {i+1}/{n_iterations} (seed={seed}) → CV Acc: "
                  f"{cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

        avg_proba  = np.mean(all_proba, axis=0)
        final_pred = np.argmax(avg_proba, axis=1)

        final_model = get_models(seed=42)[model_name]
        final_model.fit(X_train, y_train)
        y_pred_train = final_model.predict(X_train)
        train_acc    = accuracy_score(y_train, y_pred_train)

        test_acc = accuracy_score(y_test, final_pred)
        test_f1  = f1_score(y_test, final_pred, average='weighted')

        print(f"\n    Train Accuracy : {train_acc:.4f}")
        print(f"    Test Accuracy  : {test_acc:.4f}  |  Test F1 (weighted): {test_f1:.4f}")

        print(f"\n    Classification Report (Test Set):")
        report_names = [LABEL_MAP[i] for i in sorted(LABEL_MAP.keys())]
        for line in classification_report(
            y_test, final_pred,
            target_names=report_names,
            labels=sorted(LABEL_MAP.keys())
        ).splitlines():
            print(f"      {line}")

        results[model_name] = {
            'train_acc'   : train_acc,
            'test_acc'    : test_acc,
            'test_f1'     : test_f1,
            'cv_mean_last': iter_records[-1]['CV_Acc_Mean'],
            'iter_records': iter_records,
        }
        pred_dict[model_name] = {
            'pred'     : final_pred,
            'avg_proba': avg_proba,
        }

    return results, pred_dict


# ─────────────────────────────────────────────
# BUILD OUTPUT
# ─────────────────────────────────────────────
def build_output_csv(test_raw, pred_dict):
    df = test_raw.copy().reset_index(drop=True)

    short = {
        "Decision_Tree"      : "DT",
        "Random_Forest"      : "RF",
        "Logistic_Regression": "LR",
    }

    for model_name, data in pred_dict.items():
        pfx  = short[model_name]
        pred = data['pred']
        df[f'{pfx}_prediction'] = pred

    return df


# ─────────────────────────────────────────────
# SAVE & LOAD MODELS
# ─────────────────────────────────────────────
def save_models(models_dict, scaler, prefix="trained"):
    for model_name, model in models_dict.items():
        path = os.path.join(MODEL_DIR, f"{prefix}_{model_name}.pkl")
        joblib.dump(model, path)
        print(f"    ✓ Saved: {path}")

    scaler_path = os.path.join(MODEL_DIR, f"{prefix}_scaler.pkl")
    joblib.dump(scaler, scaler_path)
    print(f"    ✓ Saved: {scaler_path}")


def load_models(prefix="trained"):
    models_dict = {}
    for model_name in get_models().keys():
        path = os.path.join(MODEL_DIR, f"{prefix}_{model_name}.pkl")
        if os.path.exists(path):
            models_dict[model_name] = joblib.load(path)
            print(f"    ✓ Loaded: {path}")
        else:
            raise FileNotFoundError(f"Model file not found: {path}")

    scaler_path = os.path.join(MODEL_DIR, f"{prefix}_scaler.pkl")
    if os.path.exists(scaler_path):
        scaler = joblib.load(scaler_path)
        print(f"    ✓ Loaded: {scaler_path}")
    else:
        raise FileNotFoundError(f"Scaler file not found: {scaler_path}")

    return models_dict, scaler


# ─────────────────────────────────────────────
# VOTING CLASSIFIER
# ─────────────────────────────────────────────
def create_voting_classifier(models_dict):
    from sklearn.preprocessing import LabelEncoder

    estimators = [(name, model) for name, model in models_dict.items()]
    voting_clf = VotingClassifier(estimators=estimators, voting='hard')

    voting_clf.estimators_ = [model for name, model in models_dict.items()]
    voting_clf.named_estimators_ = models_dict
    voting_clf.classes_ = models_dict[list(models_dict.keys())[0]].classes_

    le = LabelEncoder()
    le.fit(voting_clf.classes_)
    voting_clf.le_ = le

    return voting_clf


def predict_with_voting(voting_clf, X):
    return voting_clf.predict(X)


# ─────────────────────────────────────────────
# DRIFT MONITORING SYSTEM
# ─────────────────────────────────────────────
class DriftMonitoringSystem:

    def __init__(self, base_models, adaptive_models, scaler):
        self.base_models  = base_models
        self.base_voting  = create_voting_classifier(base_models)

        self.adaptive_models = adaptive_models
        self.adaptive_voting = create_voting_classifier(adaptive_models)

        self.scaler = scaler

        self.stream_buffer   = deque(maxlen=STREAM_BUFFER_SIZE)
        self.training_buffer = deque(maxlen=TRAINING_BUFFER_SIZE * 2)

        self.model_lock  = threading.Lock()
        self.buffer_lock = threading.Lock()

        self.total_predictions = 0
        self.total_retrains    = 0

        self.base_correct     = 0
        self.adaptive_correct = 0
        self.predictions_with_label = 0

        self.ground_truth_cache = {}
        self.ground_truth_lock  = threading.Lock()

        self._init_drift_log()

        print("\n[✓] DriftMonitoringSystem initialized")
        print(f"    Base Models: {list(base_models.keys())}")
        print(f"    Adaptive Models: {list(adaptive_models.keys())}")
        print(f"    Stream Buffer Size: {STREAM_BUFFER_SIZE}")
        print(f"    Training Buffer Size: {TRAINING_BUFFER_SIZE}")

    def get_ground_truth_label(self, timestamp, device_id):
        # Ground truth tidak tersedia di mode streaming
        if GROUND_TRUTH_CSV is None:
            return None

        key = f"{timestamp}_{device_id}"

        with self.ground_truth_lock:
            if key in self.ground_truth_cache:
                return self.ground_truth_cache[key]

            try:
                if os.path.exists(GROUND_TRUTH_CSV):
                    df = pd.read_csv(GROUND_TRUTH_CSV, usecols=['timestamp', 'device_id', 'label'])
                    match = df[(df['timestamp'] == timestamp) & (df['device_id'] == device_id)]

                    if not match.empty:
                        label = int(match.iloc[0]['label'])
                        self.ground_truth_cache[key] = label
                        return label
            except Exception as e:
                print(f"[⚠️  WARNING] Failed to read ground truth: {e}")

            return None

    def _init_drift_log(self):
        if not os.path.exists(DRIFT_LOG_FILE):
            with open(DRIFT_LOG_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'device_id', 'voltage', 'current', 'power',
                    'frequency', 'temperature', 'latency', 'packet_loss',
                    'throughput', 'duplicate_packet', 'checksum_valid',
                    'authentication_fail', 'ground_truth_label', 'base_prediction',
                    'adaptive_prediction', 'final_prediction', 'base_correct',
                    'adaptive_correct', 'base_accuracy', 'adaptive_accuracy',
                    'prediction_match', 'total_retrains'
                ])
            print(f"    ✓ Created drift log: {DRIFT_LOG_FILE}")

    def preprocess_data(self, raw_data):
        features = ['voltage', 'current', 'power', 'frequency', 'temperature',
                    'latency', 'packet_loss', 'throughput', 'duplicate_packet',
                    'checksum_valid', 'authentication_fail']

        X = pd.DataFrame([{k: raw_data[k] for k in features}])
        X_scaled = pd.DataFrame(
            self.scaler.transform(X),
            columns=X.columns
        )
        return X_scaled

    def predict_both_models(self, X_scaled):
        with self.model_lock:
            base_pred     = self.base_voting.predict(X_scaled)[0]
            adaptive_pred = self.adaptive_voting.predict(X_scaled)[0]

        return base_pred, adaptive_pred

    def log_prediction(self, raw_data, base_pred, adaptive_pred, ground_truth=None):
        match      = 1 if base_pred == adaptive_pred else 0
        final_pred = adaptive_pred

        base_correct     = 1 if (ground_truth is not None and base_pred == ground_truth) else None
        adaptive_correct = 1 if (ground_truth is not None and adaptive_pred == ground_truth) else None

        if ground_truth is not None:
            self.predictions_with_label += 1
            if base_pred == ground_truth:
                self.base_correct += 1
            if adaptive_pred == ground_truth:
                self.adaptive_correct += 1

        base_accuracy     = round(self.base_correct / self.predictions_with_label, 4) if self.predictions_with_label > 0 else 0.0000
        adaptive_accuracy = round(self.adaptive_correct / self.predictions_with_label, 4) if self.predictions_with_label > 0 else 0.0000

        row = [
            raw_data['timestamp'],
            raw_data['device_id'],
            raw_data['voltage'],
            raw_data['current'],
            raw_data['power'],
            raw_data['frequency'],
            raw_data['temperature'],
            raw_data['latency'],
            raw_data['packet_loss'],
            raw_data['throughput'],
            raw_data['duplicate_packet'],
            raw_data['checksum_valid'],
            raw_data['authentication_fail'],
            ground_truth if ground_truth is not None else '',
            base_pred,
            adaptive_pred,
            final_pred,
            base_correct if base_correct is not None else '',
            adaptive_correct if adaptive_correct is not None else '',
            base_accuracy,
            adaptive_accuracy,
            match,
            self.total_retrains
        ]

        with open(DRIFT_LOG_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def add_to_training_buffer(self, X_scaled, label):
        with self.buffer_lock:
            self.training_buffer.append((X_scaled, label))

    def should_retrain(self):
        with self.buffer_lock:
            return len(self.training_buffer) >= TRAINING_BUFFER_SIZE

    def retrain_adaptive_model(self):
        print(f"\n[⚙️ RETRAINING] Starting micro-batch retraining...")

        with self.buffer_lock:
            training_data = list(self.training_buffer)
            self.training_buffer.clear()

        if len(training_data) == 0:
            print("    ⚠️  No data in training buffer, skipping retrain")
            return

        X_list  = [item[0] for item in training_data]
        y_list  = [item[1] for item in training_data]
        X_train = pd.concat(X_list, ignore_index=True)
        y_train = pd.Series(y_list)

        print(f"    Training data: {len(X_train)} samples")
        print(f"    Label distribution: {dict(y_train.value_counts())}")

        with self.model_lock:
            for model_name, model in self.adaptive_models.items():
                try:
                    model.fit(X_train, y_train)
                    print(f"    ✓ Retrained: {model_name}")
                except Exception as e:
                    print(f"    ✗ Failed to retrain {model_name}: {e}")

            from sklearn.preprocessing import LabelEncoder
            estimators = [(name, model) for name, model in self.adaptive_models.items()]
            self.adaptive_voting = VotingClassifier(estimators=estimators, voting='hard')
            self.adaptive_voting.estimators_ = [model for name, model in self.adaptive_models.items()]
            self.adaptive_voting.named_estimators_ = self.adaptive_models
            self.adaptive_voting.classes_ = self.adaptive_models[list(self.adaptive_models.keys())[0]].classes_

            le = LabelEncoder()
            le.fit(self.adaptive_voting.classes_)
            self.adaptive_voting.le_ = le

            print(f"    ✓ Voting Classifier updated")

        self.total_retrains += 1
        print(f"    ✓ Retraining completed (Total retrains: {self.total_retrains})")

    # ─────────────────────────────────────────────
    # [VIO] FUNGSI ENKRIPSI & KIRIM
    # ─────────────────────────────────────────────
    def _build_and_send_packet(self, raw_data, adaptive_pred):
        """
        Bungkus hasil prediksi ke payload, enkripsi dengan AES-GCM + RSA-OAEP,
        lalu kirim sebagai encrypted packet ke backend Rambat.

        Dipanggil dari process_stream_data() setiap ada prediksi baru.
        """
        try:
            # Susun payload lengkap: semua field sensor + hasil voting
            payload = {
                "timestamp":           raw_data["timestamp"],
                "device_id":           raw_data["device_id"],
                "voltage":             raw_data["voltage"],
                "current":             raw_data["current"],
                "power":               raw_data["power"],
                "frequency":           raw_data["frequency"],
                "temperature":         raw_data["temperature"],
                "latency":             raw_data["latency"],
                "packet_loss":         raw_data["packet_loss"],
                "throughput":          raw_data["throughput"],
                "duplicate_packet":    raw_data["duplicate_packet"],
                "checksum_valid":      raw_data["checksum_valid"],
                "authentication_fail": raw_data["authentication_fail"],
                "voting_prediction":   int(adaptive_pred),
                "label_name":          LABEL_MAP[int(adaptive_pred)],
            }

            # Enkripsi payload → encrypted_packet (dict dengan 3 key: base64)
            encrypted_packet = build_packet(payload)

            # [RAMBAT] Kirim encrypted_packet ke endpoint POST server Rambat
            # Rambat perlu membuat endpoint: POST /prediction/receive
            # yang menerima JSON body berisi encrypted_packet ini
            try:
                response = requests.post(
                    PREDICTION_POST_URL,
                    json=encrypted_packet,
                    timeout=5
                )
                if response.status_code == 200:
                    pass  # sukses, tidak perlu print tiap data
                else:
                    print(f"[⚠️  ENCRYPT] POST gagal: HTTP {response.status_code}")
            except requests.exceptions.ConnectionError:
                # Server Rambat belum jalan — simpan di buffer saja, tidak crash
                pass
            except requests.exceptions.Timeout:
                print(f"[⚠️  ENCRYPT] POST timeout, data tetap di buffer")

            # Kembalikan encrypted_packet agar bisa disimpan di stream_buffer
            return encrypted_packet

        except Exception as e:
            print(f"[✗ ENCRYPT] Gagal enkripsi: {e}")
            import traceback
            traceback.print_exc()
            return None

    def process_stream_data(self, raw_data):
        """
        Proses satu data streaming:
        1. Preprocessing
        2. Prediksi dengan kedua model
        3. Log hasil
        4. [VIO] Enkripsi + kirim ke backend Rambat
        5. Simpan ke stream buffer (berisi encrypted_packet)
        """
        try:
            # Preprocessing
            X_scaled = self.preprocess_data(raw_data)

            # Prediksi
            base_pred, adaptive_pred = self.predict_both_models(X_scaled)

            # Ground truth (untuk evaluasi offline)
            ground_truth = self.get_ground_truth_label(
                raw_data['timestamp'],
                raw_data['device_id']
            )

            # Log prediksi ke CSV
            self.log_prediction(raw_data, base_pred, adaptive_pred, ground_truth)

            # Update statistik
            self.total_predictions += 1

            # ── [VIO] Enkripsi & kirim ──────────────────────────
            encrypted_packet = self._build_and_send_packet(raw_data, adaptive_pred)
            # ────────────────────────────────────────────────────

            # Simpan ke stream buffer
            # encrypted_packet ikut disimpan agar Rambat bisa ambil dari sini
            # jika tidak mau pakai POST endpoint
            with self.buffer_lock:
                self.stream_buffer.append({
                    'data':             raw_data,
                    'base_pred':        base_pred,
                    'adaptive_pred':    adaptive_pred,
                    'ground_truth':     ground_truth,
                    'encrypted_packet': encrypted_packet,   # [VIO] tambahan
                    'timestamp':        datetime.now()
                })

            # Print progress setiap 50 prediksi
            if self.total_predictions % 50 == 0:
                match_rate = self._calculate_recent_match_rate()
                base_acc     = self.base_correct / self.predictions_with_label if self.predictions_with_label > 0 else 0
                adaptive_acc = self.adaptive_correct / self.predictions_with_label if self.predictions_with_label > 0 else 0

                print(f"\n[📊 STATS] Predictions: {self.total_predictions} | Retrains: {self.total_retrains}")
                print(f"  ├─ Match Rate: {match_rate:.2%}")
                if self.predictions_with_label > 0:
                    print(f"  ├─ Base Model Accuracy: {base_acc:.4f} ({self.base_correct}/{self.predictions_with_label})")
                    print(f"  └─ Adaptive Model Accuracy: {adaptive_acc:.4f} ({self.adaptive_correct}/{self.predictions_with_label})")
                else:
                    print(f"  └─ Accuracy: N/A (ground truth not available yet)")

            elif self.total_predictions % 10 == 0:
                if self.predictions_with_label > 0:
                    base_acc     = self.base_correct / self.predictions_with_label
                    adaptive_acc = self.adaptive_correct / self.predictions_with_label
                    print(f"[📝 LOG] {self.total_predictions} predictions | Base: {base_acc:.4f} | Adaptive: {adaptive_acc:.4f}")
                else:
                    print(f"[📝 LOG] {self.total_predictions} predictions | Accuracy: N/A")

            return base_pred, adaptive_pred

        except Exception as e:
            print(f"[✗ ERROR] Failed to process data: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def _calculate_recent_match_rate(self):
        with self.buffer_lock:
            recent = list(self.stream_buffer)[-100:]

        if len(recent) == 0:
            return 0.0

        matches = sum(1 for item in recent
                      if item['base_pred'] == item['adaptive_pred'])
        return matches / len(recent)


# ─────────────────────────────────────────────
# STREAMING THREADS
# ─────────────────────────────────────────────
def stream_consumer_thread(drift_system, stop_event):
    print(f"\n[🌊 STREAM] Connecting to {STREAM_URL}...")

    retry_count = 0
    max_retries = 5

    while not stop_event.is_set() and retry_count < max_retries:
        try:
            response = requests.get(STREAM_URL, stream=True, timeout=60)

            if response.status_code != 200:
                print(f"[✗ STREAM] HTTP {response.status_code}, retrying...")
                retry_count += 1
                time.sleep(2)
                continue

            print(f"[✓ STREAM] Connected successfully!")
            print(f"[📡 STREAM] Waiting for data...")
            retry_count = 0

            data_count = 0
            for line in response.iter_lines():
                if stop_event.is_set():
                    break

                if line:
                    line_str = line.decode('utf-8')

                    if line_str.startswith('data: '):
                        try:
                            json_str = line_str[6:]
                            data     = json.loads(json_str)

                            data_count += 1
                            if data_count <= 5:
                                print(f"[📥 STREAM] Received data #{data_count}: device={data.get('device_id', 'N/A')}")

                            drift_system.process_stream_data(data)

                        except json.JSONDecodeError as e:
                            print(f"[✗ STREAM] JSON decode error: {e}")
                        except Exception as e:
                            print(f"[✗ STREAM] Processing error: {e}")
                            import traceback
                            traceback.print_exc()

        except requests.exceptions.RequestException as e:
            print(f"[✗ STREAM] Connection error: {e}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"[🔄 STREAM] Retrying in 5 seconds... ({retry_count}/{max_retries})")
                time.sleep(5)
        except Exception as e:
            print(f"[✗ STREAM] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            break

    if retry_count >= max_retries:
        print(f"[✗ STREAM] Max retries reached, stopping stream consumer")

    print("[🛑 STREAM] Stream consumer thread stopped")


def retraining_thread(drift_system, stop_event):
    print("\n[🔧 RETRAIN] Retraining monitor started")

    while not stop_event.is_set():
        try:
            if drift_system.should_retrain():
                drift_system.retrain_adaptive_model()
            time.sleep(5)
        except Exception as e:
            print(f"[✗ RETRAIN] Error in retraining thread: {e}")
            time.sleep(5)

    print("[🛑 RETRAIN] Retraining thread stopped")


def simulated_label_provider_thread(drift_system, stop_event):
    print("\n[🏷️  LABEL] Label provider started")
    print("    (Using actual labels from streaming data)")

    while not stop_event.is_set():
        try:
            time.sleep(2)

            raw_data = None
            ground_truth = None

            with drift_system.buffer_lock:
                if len(drift_system.stream_buffer) > 0:
                    recent_data  = drift_system.stream_buffer[-1]
                    raw_data     = recent_data['data']
                    ground_truth = recent_data['ground_truth']

            # Guard: hanya tambahkan ke training buffer jika
            # raw_data ada DAN ground_truth bukan None
            if raw_data is not None and ground_truth is not None:
                X_scaled = drift_system.preprocess_data(raw_data)
                drift_system.add_to_training_buffer(X_scaled, ground_truth)

        except Exception as e:
            print(f"[✗ LABEL] Error in label provider: {e}")
            time.sleep(2)

    print("[🛑 LABEL] Label provider thread stopped")


def simulate_ground_truth_label(raw_data):
    voltage     = raw_data['voltage']
    temp        = raw_data['temperature']
    auth_fail   = raw_data['authentication_fail']
    packet_loss = raw_data['packet_loss']

    if auth_fail > 2 or packet_loss > 10:
        return 1
    if temp > 65 or voltage < 200 or voltage > 240:
        return 2
    return 0


# ─────────────────────────────────────────────
# MAIN - TRAINING MODE
# ─────────────────────────────────────────────
def main_training():
    print("\n" + "="*70)
    print("  MODE: TRAINING - Train models from historical data")
    print("="*70)

    X_train, y_train, X_test, y_test, test_raw = load_data()

    results, pred_dict = train_and_predict_all(
        X_train, y_train, X_test, y_test, n_iterations=N_ITERATIONS
    )

    print("\n[3] Menyusun output CSV...")
    pred_df = build_output_csv(test_raw, pred_dict)

    summary_rows = []
    for model_name, res in results.items():
        summary_rows.append({
            'Model'         : model_name.replace('_', ' '),
            'CV_Acc_Mean'   : f"{res['cv_mean_last']:.4f}",
            'Train_Accuracy': f"{res['train_acc']:.4f}",
            'Test_Accuracy' : f"{res['test_acc']:.4f}",
            'Test_F1'       : f"{res['test_f1']:.4f}",
        })
    summary_df = pd.DataFrame(summary_rows)

    all_iter = []
    for res in results.values():
        all_iter.extend(res['iter_records'])
    iter_df = pd.DataFrame(all_iter)

    out_pred = os.path.join(OUTPUT_DIR, "predictions", "test_predictions.csv")
    out_summ = os.path.join(OUTPUT_DIR, "metrics", "model_summary.csv")
    out_iter = os.path.join(OUTPUT_DIR, "metrics", "iteration_metrics.csv")

    os.makedirs(os.path.join(OUTPUT_DIR, "predictions"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "metrics"), exist_ok=True)

    pred_df.to_csv(out_pred, index=False)
    summary_df.to_csv(out_summ, index=False)
    iter_df.to_csv(out_iter, index=False)

    print("\n  RINGKASAN PERFORMA MODEL (PADA TEST SET)")
    print("="*65)
    print(summary_df.to_string(index=False))

    print("\n  DISTRIBUSI PREDIKSI TEST")
    print("="*60)
    for model_name, data in pred_dict.items():
        dist = pd.Series(data['pred']).map(LABEL_MAP).value_counts()
        print(f"  {model_name.replace('_',' '):<22}: {dict(dist)}")

    print("\n  PREVIEW test_predictions.csv (5 baris pertama)")
    print("="*60)
    cols_preview = ['timestamp', 'device_id', 'label', 'DT_prediction', 'RF_prediction', 'LR_prediction']
    cols_preview = [c for c in cols_preview if c in pred_df.columns]
    print(pred_df[cols_preview].head(5).to_string(index=False))

    print("\n[4] Saving trained models...")
    X_train_full, y_train_full, _, _, _ = load_data()
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_full)

    final_models = {}
    for model_name in get_models().keys():
        model = get_models(seed=42)[model_name]
        model.fit(X_train_scaled, y_train_full)
        final_models[model_name] = model

    save_models(final_models, scaler, prefix="trained")

    print("\n  OUTPUT FILES:")
    print("="*60)
    print(f"  ├── test_predictions.csv  → df_test + kolom DT/RF/LR_prediction")
    print(f"  ├── model_summary.csv     → Akurasi & F1 tiap model pada Test Set")
    print(f"  ├── iteration_metrics.csv → CV accuracy per iterasi per model")
    print(f"  └── models/               → Trained models (pkl files)")


# ─────────────────────────────────────────────
# MAIN - STREAMING MODE
# ─────────────────────────────────────────────
def main_streaming():
    print("\n" + "="*70)
    print("  MODE: STREAMING - Real-time prediction with drift monitoring")
    print("="*70)

    # [VIO] Setup RSA keys — generate sekali jika belum ada
    print("\n[0] Setup encryption keys...")
    setup_keys()

    print("\n[1] Loading trained models...")
    try:
        base_models, scaler = load_models(prefix="trained")
    except FileNotFoundError as e:
        print(f"\n[✗ ERROR] {e}")
        print("\n  Please run training mode first:")
        print("  python ML.py --mode training")
        return

    print("\n[2] Creating adaptive models (copy of base models)...")
    adaptive_models = {}
    for model_name, model in base_models.items():
        adaptive_models[model_name] = deepcopy(model)
        print(f"    ✓ Copied: {model_name}")

    print("\n[3] Initializing drift monitoring system...")
    drift_system = DriftMonitoringSystem(base_models, adaptive_models, scaler)

    stop_event = threading.Event()

    print("\n[4] Starting threads...")

    stream_thread = threading.Thread(
        target=stream_consumer_thread,
        args=(drift_system, stop_event),
        daemon=True
    )
    stream_thread.start()

    retrain_thread = threading.Thread(
        target=retraining_thread,
        args=(drift_system, stop_event),
        daemon=True
    )
    retrain_thread.start()

    label_thread = threading.Thread(
        target=simulated_label_provider_thread,
        args=(drift_system, stop_event),
        daemon=True
    )
    label_thread.start()

    print("\n" + "="*70)
    print("  🚀 SYSTEM RUNNING")
    print("="*70)
    print(f"  Stream URL  : {STREAM_URL}")
    print(f"  Predict POST: {PREDICTION_POST_URL}")
    print(f"  Drift Log   : {DRIFT_LOG_FILE}")
    print(f"  Micro-batch : {TRAINING_BUFFER_SIZE} samples")
    print("\n  Press Ctrl+C to stop...")
    print("="*70 + "\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[🛑 SHUTDOWN] Stopping all threads...")
        stop_event.set()

        stream_thread.join(timeout=5)
        retrain_thread.join(timeout=5)
        label_thread.join(timeout=5)

        print("\n[✓] All threads stopped")

        base_acc     = drift_system.base_correct / drift_system.predictions_with_label if drift_system.predictions_with_label > 0 else 0
        adaptive_acc = drift_system.adaptive_correct / drift_system.predictions_with_label if drift_system.predictions_with_label > 0 else 0

        print(f"\n  FINAL STATISTICS:")
        print(f"  ├── Total Predictions: {drift_system.total_predictions}")
        print(f"  ├── Total Retrains: {drift_system.total_retrains}")
        print(f"  ├── Base Model Accuracy: {base_acc:.4f} ({drift_system.base_correct}/{drift_system.predictions_with_label})")
        print(f"  ├── Adaptive Model Accuracy: {adaptive_acc:.4f} ({drift_system.adaptive_correct}/{drift_system.predictions_with_label})")
        print(f"  └── Drift Log: {DRIFT_LOG_FILE}")

        if base_acc > 0:
            improvement     = adaptive_acc - base_acc
            improvement_pct = (improvement / base_acc * 100) if base_acc > 0 else 0
            print(f"\n  📈 Adaptive Model Improvement:")
            print(f"     Absolute: {improvement:+.4f}")
            print(f"     Relative: {improvement_pct:+.2f}%")
            if improvement > 0:
                print(f"     ✅ Adaptive model performs BETTER (retraining helps!)")
            elif improvement < 0:
                print(f"     ⚠️  Adaptive model performs WORSE (may need more data)")
            else:
                print(f"     ➖ Both models perform equally")


# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────
def main():
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--mode":
        mode = sys.argv[2] if len(sys.argv) > 2 else "training"
    else:
        mode = "streaming"

    if mode == "training":
        main_training()
    elif mode == "streaming":
        main_streaming()
    else:
        print(f"[✗ ERROR] Unknown mode: {mode}")
        print("\nUsage:")
        print("  python ML.py --mode training   # Train models from historical data")
        print("  python ML.py --mode streaming  # Real-time prediction with drift monitoring")


if __name__ == "__main__":
    main()