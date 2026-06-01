"""
Test script untuk Drift Monitoring System
Menguji komponen-komponen sistem secara terpisah
"""

import pandas as pd
import numpy as np
from ML import (
    DriftMonitoringSystem,
    load_models,
    create_voting_classifier,
    simulate_ground_truth_label
)
from sklearn.preprocessing import StandardScaler
from copy import deepcopy
import time

def test_model_loading():
    """Test loading trained models."""
    print("\n" + "="*60)
    print("TEST 1: Model Loading")
    print("="*60)
    
    try:
        base_models, scaler = load_models(prefix="trained")
        print("✓ Models loaded successfully")
        print(f"  Models: {list(base_models.keys())}")
        return base_models, scaler
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        print("\n  Run training mode first:")
        print("  python ML.py --mode training")
        return None, None


def test_voting_classifier(base_models):
    """Test voting classifier creation."""
    print("\n" + "="*60)
    print("TEST 2: Voting Classifier")
    print("="*60)
    
    if base_models is None:
        print("✗ Skipped (models not loaded)")
        return None
    
    try:
        voting_clf = create_voting_classifier(base_models)
        print("✓ Voting classifier created successfully")
        print(f"  Estimators: {[name for name, _ in voting_clf.estimators]}")
        return voting_clf
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def test_drift_system_init(base_models, scaler):
    """Test drift monitoring system initialization."""
    print("\n" + "="*60)
    print("TEST 3: Drift System Initialization")
    print("="*60)
    
    if base_models is None or scaler is None:
        print("✗ Skipped (models not loaded)")
        return None
    
    try:
        adaptive_models = {name: deepcopy(model) for name, model in base_models.items()}
        drift_system = DriftMonitoringSystem(base_models, adaptive_models, scaler)
        print("✓ Drift system initialized successfully")
        return drift_system
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def test_single_prediction(drift_system):
    """Test single data prediction."""
    print("\n" + "="*60)
    print("TEST 4: Single Prediction")
    print("="*60)
    
    if drift_system is None:
        print("✗ Skipped (drift system not initialized)")
        return
    
    # Sample data (NORMAL)
    sample_data = {
        'timestamp': '2024-01-01 12:00:00.000',
        'device_id': 'SGD-0001',
        'voltage': 220.5,
        'current': 5.2,
        'power': 1100.0,
        'frequency': 50.0,
        'temperature': 32.5,
        'latency': 15.2,
        'packet_loss': 0.5,
        'throughput': 95.0,
        'duplicate_packet': 0,
        'checksum_valid': 1,
        'authentication_fail': 0
    }
    
    try:
        base_pred, adaptive_pred = drift_system.process_stream_data(sample_data)
        print(f"✓ Prediction successful")
        print(f"  Base Model prediction: {base_pred} ({LABEL_MAP.get(base_pred, 'Unknown')})")
        print(f"  Adaptive Model prediction: {adaptive_pred} ({LABEL_MAP.get(adaptive_pred, 'Unknown')})")
        print(f"  Match: {'Yes' if base_pred == adaptive_pred else 'No'}")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_batch_prediction(drift_system, n_samples=10):
    """Test batch predictions."""
    print("\n" + "="*60)
    print(f"TEST 5: Batch Prediction ({n_samples} samples)")
    print("="*60)
    
    if drift_system is None:
        print("✗ Skipped (drift system not initialized)")
        return
    
    # Generate sample data
    samples = []
    for i in range(n_samples):
        label_type = i % 3  # 0=Normal, 1=Attack, 2=Fault
        
        if label_type == 0:  # Normal
            sample = {
                'timestamp': f'2024-01-01 12:00:{i:02d}.000',
                'device_id': f'SGD-{i:04d}',
                'voltage': np.random.uniform(218, 222),
                'current': np.random.uniform(4, 7),
                'power': np.random.uniform(900, 1500),
                'frequency': np.random.uniform(49.8, 50.2),
                'temperature': np.random.uniform(28, 35),
                'latency': np.random.uniform(10, 25),
                'packet_loss': np.random.uniform(0, 2),
                'throughput': np.random.uniform(90, 100),
                'duplicate_packet': 0,
                'checksum_valid': 1,
                'authentication_fail': 0
            }
        elif label_type == 1:  # Attack
            sample = {
                'timestamp': f'2024-01-01 12:00:{i:02d}.000',
                'device_id': f'SGD-{i:04d}',
                'voltage': np.random.uniform(200, 240),
                'current': np.random.uniform(2, 15),
                'power': np.random.uniform(500, 2000),
                'frequency': np.random.uniform(48, 52),
                'temperature': np.random.uniform(30, 60),
                'latency': np.random.uniform(50, 150),
                'packet_loss': np.random.uniform(10, 30),
                'throughput': np.random.uniform(20, 60),
                'duplicate_packet': np.random.randint(5, 15),
                'checksum_valid': 0,
                'authentication_fail': np.random.randint(3, 10)
            }
        else:  # Fault
            sample = {
                'timestamp': f'2024-01-01 12:00:{i:02d}.000',
                'device_id': f'SGD-{i:04d}',
                'voltage': np.random.uniform(195, 250),
                'current': np.random.uniform(3, 8),
                'power': np.random.uniform(800, 1600),
                'frequency': np.random.uniform(49.5, 50.5),
                'temperature': np.random.uniform(65, 85),
                'latency': np.random.uniform(20, 40),
                'packet_loss': np.random.uniform(2, 8),
                'throughput': np.random.uniform(70, 95),
                'duplicate_packet': np.random.randint(0, 3),
                'checksum_valid': 1,
                'authentication_fail': 0
            }
        
        samples.append(sample)
    
    # Process samples
    results = []
    for sample in samples:
        try:
            base_pred, adaptive_pred = drift_system.process_stream_data(sample)
            results.append({
                'device_id': sample['device_id'],
                'base_pred': base_pred,
                'adaptive_pred': adaptive_pred,
                'match': base_pred == adaptive_pred
            })
        except Exception as e:
            print(f"✗ Error processing sample: {e}")
    
    # Summary
    if results:
        print(f"✓ Processed {len(results)} samples")
        matches = sum(1 for r in results if r['match'])
        print(f"  Match rate: {matches}/{len(results)} ({matches/len(results)*100:.1f}%)")
        
        # Distribution
        base_dist = {}
        adaptive_dist = {}
        for r in results:
            base_dist[r['base_pred']] = base_dist.get(r['base_pred'], 0) + 1
            adaptive_dist[r['adaptive_pred']] = adaptive_dist.get(r['adaptive_pred'], 0) + 1
        
        print(f"\n  Base Model distribution:")
        for label, count in sorted(base_dist.items()):
            print(f"    {LABEL_MAP.get(label, 'Unknown')}: {count}")
        
        print(f"\n  Adaptive Model distribution:")
        for label, count in sorted(adaptive_dist.items()):
            print(f"    {LABEL_MAP.get(label, 'Unknown')}: {count}")


def test_training_buffer(drift_system):
    """Test training buffer and retraining."""
    print("\n" + "="*60)
    print("TEST 6: Training Buffer & Retraining")
    print("="*60)
    
    if drift_system is None:
        print("✗ Skipped (drift system not initialized)")
        return
    
    print(f"  Training buffer size threshold: {drift_system.training_buffer.maxlen // 2}")
    print(f"  Current buffer size: {len(drift_system.training_buffer)}")
    
    # Add samples to training buffer
    n_samples = 50
    print(f"\n  Adding {n_samples} samples to training buffer...")
    
    for i in range(n_samples):
        # Create sample data
        sample_data = {
            'voltage': np.random.uniform(218, 222),
            'current': np.random.uniform(4, 7),
            'power': np.random.uniform(900, 1500),
            'frequency': np.random.uniform(49.8, 50.2),
            'temperature': np.random.uniform(28, 35),
            'latency': np.random.uniform(10, 25),
            'packet_loss': np.random.uniform(0, 2),
            'throughput': np.random.uniform(90, 100),
            'duplicate_packet': 0,
            'checksum_valid': 1,
            'authentication_fail': 0
        }
        
        X_scaled = drift_system.preprocess_data(sample_data)
        label = simulate_ground_truth_label(sample_data)
        drift_system.add_to_training_buffer(X_scaled, label)
    
    print(f"  ✓ Added {n_samples} samples")
    print(f"  Current buffer size: {len(drift_system.training_buffer)}")
    print(f"  Should retrain: {drift_system.should_retrain()}")


def test_ground_truth_simulation():
    """Test ground truth label simulation."""
    print("\n" + "="*60)
    print("TEST 7: Ground Truth Simulation")
    print("="*60)
    
    test_cases = [
        {
            'name': 'Normal',
            'data': {
                'voltage': 220.0,
                'temperature': 30.0,
                'authentication_fail': 0,
                'packet_loss': 0.5
            },
            'expected': 0
        },
        {
            'name': 'Attack (high auth_fail)',
            'data': {
                'voltage': 220.0,
                'temperature': 30.0,
                'authentication_fail': 5,
                'packet_loss': 0.5
            },
            'expected': 1
        },
        {
            'name': 'Attack (high packet_loss)',
            'data': {
                'voltage': 220.0,
                'temperature': 30.0,
                'authentication_fail': 0,
                'packet_loss': 15.0
            },
            'expected': 1
        },
        {
            'name': 'Fault (high temp)',
            'data': {
                'voltage': 220.0,
                'temperature': 70.0,
                'authentication_fail': 0,
                'packet_loss': 0.5
            },
            'expected': 2
        },
        {
            'name': 'Fault (low voltage)',
            'data': {
                'voltage': 190.0,
                'temperature': 30.0,
                'authentication_fail': 0,
                'packet_loss': 0.5
            },
            'expected': 2
        }
    ]
    
    correct = 0
    for case in test_cases:
        result = simulate_ground_truth_label(case['data'])
        match = "✓" if result == case['expected'] else "✗"
        print(f"  {match} {case['name']}: predicted={result} ({LABEL_MAP.get(result, 'Unknown')}), "
              f"expected={case['expected']} ({LABEL_MAP.get(case['expected'], 'Unknown')})")
        if result == case['expected']:
            correct += 1
    
    print(f"\n  Accuracy: {correct}/{len(test_cases)} ({correct/len(test_cases)*100:.1f}%)")


# Label map for display
LABEL_MAP = {0: "Normal", 1: "Attack", 2: "Fault"}


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  DRIFT MONITORING SYSTEM - TEST SUITE")
    print("="*60)
    
    # Test 1: Model Loading
    base_models, scaler = test_model_loading()
    
    # Test 2: Voting Classifier
    voting_clf = test_voting_classifier(base_models)
    
    # Test 3: Drift System Init
    drift_system = test_drift_system_init(base_models, scaler)
    
    # Test 4: Single Prediction
    test_single_prediction(drift_system)
    
    # Test 5: Batch Prediction
    test_batch_prediction(drift_system, n_samples=20)
    
    # Test 6: Training Buffer
    test_training_buffer(drift_system)
    
    # Test 7: Ground Truth Simulation
    test_ground_truth_simulation()
    
    print("\n" + "="*60)
    print("  TEST SUITE COMPLETED")
    print("="*60)
    
    if drift_system:
        print(f"\n  Final Statistics:")
        print(f"  ├── Total Predictions: {drift_system.total_predictions}")
        print(f"  ├── Total Retrains: {drift_system.total_retrains}")
        print(f"  ├── Stream Buffer: {len(drift_system.stream_buffer)} items")
        print(f"  └── Training Buffer: {len(drift_system.training_buffer)} items")


if __name__ == "__main__":
    main()
