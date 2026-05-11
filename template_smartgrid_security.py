import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix

# Import models for Ensemble Learning
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression

# Import Cryptography modules for Hybrid Encryption (AES-GCM & RSA-OAEP)
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def load_data(file_path):
    """Fungsi untuk load dataset Smart Grid"""
    df = pd.read_csv(file_path)
    print(f"Shape of dataset: {df.shape}")
    return df

def preprocess_data(df, target_col):
    """
    Fungsi preprocessing: Mengatasi missing values, encoding klasifikasi, dan Feature Scaling.
    """
    df = df.copy()
    
    # 1. Handling Missing Values
    for col in df.columns:
        if df[col].isnull().sum() > 0:
            if df[col].dtype in ['int64', 'float64']:
                df[col].fillna(df[col].median(), inplace=True)
            else:
                df[col].fillna(df[col].mode()[0], inplace=True)
                
    # 2. Encoding Categorical Variables & Target
    le = LabelEncoder()
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns
    for col in categorical_cols:
        if col != target_col:
            df[col] = le.fit_transform(df[col].astype(str))
            
    if df[target_col].dtype == 'object':
        df[target_col] = le.fit_transform(df[target_col].astype(str))
        
    X = df.drop(columns=[target_col])
    y = df[target_col]
    
    # 3. Feature Scaling
    scaler = StandardScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)
    
    return X_scaled, y, le

def train_ensemble_model(X_train, y_train):
    """Melatih model menggunakan Voting Classifier (Decision Tree, Random Forest, Logistic Regression)."""
    print("Training Ensemble Learning Model...")
    
    dt = DecisionTreeClassifier(random_state=42)
    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    lr = LogisticRegression(max_iter=1000, random_state=42)
    
    ensemble_model = VotingClassifier(
        estimators=[('dt', dt), ('rf', rf), ('lr', lr)],
        voting='soft'
    )
    
    ensemble_model.fit(X_train, y_train)
    return ensemble_model

def evaluate_model(model, X_test, y_test, target_names=None):
    """Evaluasi model Machine Learning."""
    y_pred = model.predict(X_test)
    
    print("\n--- Classification Report ---")
    if target_names:
        print(classification_report(y_test, y_pred, target_names=target_names))
    else:
        print(classification_report(y_test, y_pred))
    
    print("--- Confusion Matrix ---")
    cm = confusion_matrix(y_test, y_pred)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Reds')
    plt.title('Confusion Matrix: Normal vs Attack')
    plt.xlabel('Predicted')
    plt.ylabel('Actual')
    plt.show()
    return y_pred

# =====================================================================
# HYBRID ENCRYPTION MODULE (AES-GCM + RSA-OAEP)
# =====================================================================

def generate_rsa_keys():
    """Generate RSA public and private keys."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key

def encrypt_data_hybrid(data_bytes, public_key):
    """Enkripsi data aktual dengan AES-GCM, lalu kunci AES dienkripsi dengan RSA-OAEP."""
    # 1. Generate AES-GCM Key & Nonce
    aes_key = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)
    
    # 2. Encrypt Data
    encrypted_data = aesgcm.encrypt(nonce, data_bytes, associated_data=None)
    
    # 3. Encrypt AES Key
    encrypted_aes_key = public_key.encrypt(
        aes_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )
    
    return encrypted_data, encrypted_aes_key, nonce

def decrypt_data_hybrid(encrypted_data, encrypted_aes_key, nonce, private_key):
    """Dekripsi kunci AES dengan RSA-OAEP, lalu dekripsi data dengan AES-GCM."""
    # 1. Decrypt AES Key
    aes_key = private_key.decrypt(
        encrypted_aes_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )
    
    # 2. Decrypt Data
    aesgcm = AESGCM(aes_key)
    decrypted_data = aesgcm.decrypt(nonce, encrypted_data, associated_data=None)
    
    return decrypted_data

def main():
    FILE_PATH = 'smart_grid_data.csv' # Ganti dengan dataset Anda
    TARGET_COL = 'label' # Ganti dengan nama kolom label
    
    try:
        # TAHAP 1: MACHINE LEARNING
        print("\n========== 1. MACHINE LEARNING PIPELINE ==========")
        df = load_data(FILE_PATH)
        X, y, le = preprocess_data(df, target_col=TARGET_COL)
        target_names = [str(cls) for cls in le.classes_]
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        
        model = train_ensemble_model(X_train, y_train)
        y_pred = evaluate_model(model, X_test, y_test, target_names=target_names)
        
        # Konversi ke bytes untuk dienkripsi
        results_df = X_test.copy()
        results_df['Actual'] = le.inverse_transform(y_test)
        results_df['Predicted'] = le.inverse_transform(y_pred)
        csv_data_bytes = results_df.to_csv(index=False).encode('utf-8')
        
        # TAHAP 2: HYBRID ENCRYPTION
        print("\n========== 2. HYBRID ENCRYPTION PIPELINE ==========")
        private_key, public_key = generate_rsa_keys()
        
        encrypted_data, encrypted_aes_key, nonce = encrypt_data_hybrid(csv_data_bytes, public_key)
        
        with open('prediction_results_encrypted.bin', 'wb') as f:
            f.write(encrypted_data)
        print("\n[INFO] Data hasil prediksi disimpan sebagai 'prediction_results_encrypted.bin'")
        
        # Simulasi Dekripsi
        print("\n--- Verifikasi Dekripsi ---")
        decrypted_data_bytes = decrypt_data_hybrid(encrypted_data, encrypted_aes_key, nonce, private_key)
        
        if decrypted_data_bytes == csv_data_bytes:
            print("[SUCCESS] Data berhasil didekripsi tanpa kehilangan integritas.")
        else:
            print("[ERROR] Integritas data tidak cocok.")
            
    except FileNotFoundError:
        print(f"File '{FILE_PATH}' tidak ditemukan. Siapkan dataset simulasi Smart Grid terlebih dahulu.")

if __name__ == "__main__":
    main()
