"""
Script test untuk debugging training mode
"""
import sys
import os

print("="*60)
print("TEST TRAINING MODE - DEBUGGING")
print("="*60)

# Test 1: Import modules
print("\n[TEST 1] Testing imports...")
try:
    import pandas as pd
    import numpy as np
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    import joblib
    print("✓ All imports successful")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Check data files
print("\n[TEST 2] Checking data files...")
train_path = r"D:\SEMESTER 4\KDA\project-kda-kelompok3\data\df_train.csv"
test_path = r"D:\SEMESTER 4\KDA\project-kda-kelompok3\data\df_test_lengkap.csv"

if os.path.exists(train_path):
    print(f"✓ Train file exists: {train_path}")
else:
    print(f"✗ Train file NOT found: {train_path}")
    sys.exit(1)

if os.path.exists(test_path):
    print(f"✓ Test file exists: {test_path}")
else:
    print(f"✗ Test file NOT found: {test_path}")
    sys.exit(1)

# Test 3: Load data
print("\n[TEST 3] Loading data...")
try:
    train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)
    print(f"✓ Train data loaded: {train_df.shape[0]} rows, {train_df.shape[1]} columns")
    print(f"✓ Test data loaded: {test_df.shape[0]} rows, {test_df.shape[1]} columns")
    print(f"  Train columns: {list(train_df.columns)}")
except Exception as e:
    print(f"✗ Failed to load data: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Check output directory
print("\n[TEST 4] Checking output directory...")
output_dir = r"D:\SEMESTER 4\KDA\project-kda-kelompok3\hasil"
model_dir = os.path.join(output_dir, "models")

if not os.path.exists(output_dir):
    print(f"  Creating output directory: {output_dir}")
    os.makedirs(output_dir, exist_ok=True)
    print(f"✓ Output directory created")
else:
    print(f"✓ Output directory exists: {output_dir}")

if not os.path.exists(model_dir):
    print(f"  Creating model directory: {model_dir}")
    os.makedirs(model_dir, exist_ok=True)
    print(f"✓ Model directory created")
else:
    print(f"✓ Model directory exists: {model_dir}")

# Test 5: Quick training test
print("\n[TEST 5] Quick training test...")
try:
    # Prepare data
    drop_cols = ['timestamp', 'device_id']
    X_train = train_df.drop(columns=drop_cols + ['label'], errors='ignore')
    y_train = train_df['label']
    
    print(f"  X_train shape: {X_train.shape}")
    print(f"  y_train shape: {y_train.shape}")
    print(f"  Label distribution: {dict(y_train.value_counts())}")
    
    # Scale data
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    print(f"✓ Data scaled successfully")
    
    # Train a simple model
    print("  Training Decision Tree (quick test)...")
    model = DecisionTreeClassifier(random_state=42, max_depth=5)
    model.fit(X_train_scaled, y_train)
    print(f"✓ Model trained successfully")
    
    # Save model
    test_model_path = os.path.join(model_dir, "test_model.pkl")
    joblib.dump(model, test_model_path)
    print(f"✓ Model saved: {test_model_path}")
    
    # Load model back
    loaded_model = joblib.load(test_model_path)
    print(f"✓ Model loaded successfully")
    
    # Test prediction
    pred = loaded_model.predict(X_train_scaled[:5])
    print(f"✓ Prediction test: {pred}")
    
except Exception as e:
    print(f"✗ Training test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("ALL TESTS PASSED! ✓")
print("="*60)
print("\nYou can now run: python ML.py --mode training")
