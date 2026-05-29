import pandas as pd
import os
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, accuracy_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression

# ==========================================
# KONSTANTA
# ==========================================
OUTPUT_DIR = "output"
TRAIN_PATH = "path/to/train.csv"
TEST_PATH = "path/to/test.csv"
TARGET_COL = "label"
DROP_COLS = ["timestamp", "device_id"] # Kolom yang tidak dipakai fitur

def load_and_preprocess_data():
    """Memuat dan melakukan preprocessing data."""
    train_df = pd.read_csv(TRAIN_PATH)
    test_df  = pd.read_csv(TEST_PATH)

    # Drop kolom yang tidak diperlukan
    train_df = train_df.drop(columns=DROP_COLS, errors='ignore')
    test_df  = test_df.drop(columns=DROP_COLS, errors='ignore')

    # Pisahkan fitur dan target
    X_train = train_df.drop(columns=[TARGET_COL])
    y_train = train_df[TARGET_COL]
    
    X_test  = test_df.drop(columns=[TARGET_COL])
    y_test  = test_df[TARGET_COL]

    # Standardisasi Data
    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train), columns=X_train.columns)
    X_test_scaled  = pd.DataFrame(scaler.transform(X_test), columns=X_test.columns)

    return X_train_scaled, y_train, X_test_scaled, y_test, test_df

def get_models():
    """Mendefinisikan model-model yang akan dilatih."""
    return {
        "Decision Tree": DecisionTreeClassifier(random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
        "Log Regression": LogisticRegression(max_iter=1000, random_state=42)
    }

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Siapkan Data
    print("[1] Memuat data...")
    X_train, y_train, X_test, y_test, test_raw = load_and_preprocess_data()
    
    models = get_models()
    results_df = test_raw.copy()
    
    # 2. Latih Model & Evaluasi
    print("\n[2] Memulai Training dan Evaluasi Model...")
    for name, model in models.items():
        print(f"\n--- {name} ---")
        
        # Proses Training
        model.fit(X_train, y_train)
        
        # Proses Prediksi
        y_pred = model.predict(X_test)
        results_df[f'{name}_Pred'] = y_pred
        
        # Evaluasi
        acc = accuracy_score(y_test, y_pred)
        print(f"Akurasi: {acc:.4f}")
        print(classification_report(y_test, y_pred))
    
    # 3. Simpan Hasil Prediksi ke CSV
    print("\n[3] Menyimpan Hasil...")
    out_file = os.path.join(OUTPUT_DIR, "predictions.csv")
    results_df.to_csv(out_file, index=False)
    print(f"File prediksi disimpan di: {out_file}")

if __name__ == "__main__":
    main()
