"""
encrypt.py — Hybrid Encryption Module (AES-GCM + RSA-OAEP)
Kelompok 3 - Keamanan Data
"""

import json
import os
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes

# Path untuk menyimpan kunci RSA
KEY_DIR = os.path.join(os.path.dirname(__file__), ".keys")
PRIVATE_KEY_PATH = os.path.join(KEY_DIR, "private_key.pem")
PUBLIC_KEY_PATH = os.path.join(KEY_DIR, "public_key.pem")

# Global variables untuk kunci
_rsa_key = None
_public_key = None


def setup_keys():
    """
    Generate atau load kunci RSA.
    Jika kunci sudah ada, load dari file.
    Jika belum ada, generate baru dan simpan.
    """
    global _rsa_key, _public_key
    
    # Buat folder .keys jika belum ada
    os.makedirs(KEY_DIR, exist_ok=True)
    
    # Cek apakah kunci sudah ada
    if os.path.exists(PRIVATE_KEY_PATH) and os.path.exists(PUBLIC_KEY_PATH):
        # Load kunci yang sudah ada
        with open(PRIVATE_KEY_PATH, 'rb') as f:
            _rsa_key = RSA.import_key(f.read())
        with open(PUBLIC_KEY_PATH, 'rb') as f:
            _public_key = f.read()
        print("[ENCRYPT] RSA keys loaded from disk")
    else:
        # Generate kunci baru
        _rsa_key = RSA.generate(2048)
        _public_key = _rsa_key.public_key().export_key()
        
        # Simpan ke file
        with open(PRIVATE_KEY_PATH, 'wb') as f:
            f.write(_rsa_key.export_key())
        with open(PUBLIC_KEY_PATH, 'wb') as f:
            f.write(_public_key)
        print("[ENCRYPT] New RSA keys generated and saved")


def build_packet(data_dict):
    """
    Enkripsi data menggunakan hybrid encryption (AES-GCM + RSA-OAEP).
    
    Args:
        data_dict: Dictionary berisi data yang akan dienkripsi
        
    Returns:
        Dictionary berisi:
        - encrypted_payload: Data terenkripsi (hex)
        - encrypted_aes_key: AES key terenkripsi dengan RSA (hex)
        - nonce: Nonce untuk AES-GCM (hex)
    """
    if _rsa_key is None or _public_key is None:
        setup_keys()
    
    # 1. Konversi data ke JSON bytes
    data_bytes = json.dumps(data_dict).encode('utf-8')
    
    # 2. Generate AES key random (16 bytes = 128 bit)
    aes_key = get_random_bytes(16)
    
    # 3. Enkripsi data dengan AES-GCM
    cipher_aes = AES.new(aes_key, AES.MODE_GCM)
    ciphertext, tag = cipher_aes.encrypt_and_digest(data_bytes)
    
    # 4. Enkripsi AES key dengan RSA public key
    recipient_key = RSA.import_key(_public_key)
    cipher_rsa = PKCS1_OAEP.new(recipient_key)
    enc_aes_key = cipher_rsa.encrypt(aes_key)
    
    # 5. Return packet terenkripsi
    return {
        "encrypted_payload": ciphertext.hex(),
        "encrypted_aes_key": enc_aes_key.hex(),
        "nonce": cipher_aes.nonce.hex(),
        "tag": tag.hex()  # Authentication tag untuk verifikasi integritas
    }


def unpack_packet(encrypted_packet):
    """
    Dekripsi packet yang sudah dienkripsi.
    
    Args:
        encrypted_packet: Dictionary berisi encrypted_payload, encrypted_aes_key, nonce, tag
        
    Returns:
        Dictionary berisi data asli yang sudah didekripsi
    """
    if _rsa_key is None or _public_key is None:
        setup_keys()
    
    try:
        # 1. Dekripsi AES key menggunakan RSA private key
        cipher_rsa = PKCS1_OAEP.new(_rsa_key)
        aes_key = cipher_rsa.decrypt(bytes.fromhex(encrypted_packet['encrypted_aes_key']))
        
        # 2. Dekripsi data menggunakan AES key
        cipher_aes = AES.new(
            aes_key, 
            AES.MODE_GCM, 
            nonce=bytes.fromhex(encrypted_packet['nonce'])
        )
        
        # 3. Verifikasi integritas dan dekripsi
        tag = bytes.fromhex(encrypted_packet.get('tag', '00' * 16))
        decrypted_data = cipher_aes.decrypt_and_verify(
            bytes.fromhex(encrypted_packet['encrypted_payload']),
            tag
        )
        
        # 4. Parse JSON dan return
        return json.loads(decrypted_data.decode('utf-8'))
        
    except Exception as e:
        print(f"[ENCRYPT] Decryption error: {e}")
        # Return data kosong jika dekripsi gagal
        return {
            "timestamp": "N/A",
            "device_id": "N/A",
            "voltage": 0,
            "current": 0,
            "temperature": 0,
            "latency": 0,
            "packet_loss": 0,
            "authentication_fail": 0,
            "label_name": "NORMAL",
            "voting_prediction": 0
        }


def encrypt_laporan(data_dict, pub_key_str):
    """
    Alias untuk build_packet (kompatibilitas dengan encryption.ipynb).
    """
    return build_packet(data_dict)


# Auto-setup keys saat module di-import
try:
    setup_keys()
except Exception as e:
    print(f"[ENCRYPT] Warning: Failed to setup keys: {e}")


if __name__ == "__main__":
    # Test enkripsi/dekripsi
    print("="*60)
    print("Testing Hybrid Encryption (AES-GCM + RSA-OAEP)")
    print("="*60)
    
    # Test data
    test_data = {
        "timestamp": "2024-01-01 12:00:00",
        "device_id": "SGD-0001",
        "voltage": 220.5,
        "current": 5.2,
        "temperature": 35.8,
        "latency": 25.3,
        "packet_loss": 1.2,
        "authentication_fail": 0,
        "label_name": "NORMAL",
        "voting_prediction": 0
    }
    
    print("\n[1] Original Data:")
    print(json.dumps(test_data, indent=2))
    
    print("\n[2] Encrypting...")
    encrypted = build_packet(test_data)
    print(f"  - Encrypted payload: {encrypted['encrypted_payload'][:60]}...")
    print(f"  - Encrypted AES key: {encrypted['encrypted_aes_key'][:60]}...")
    print(f"  - Nonce: {encrypted['nonce']}")
    print(f"  - Tag: {encrypted['tag']}")
    
    print("\n[3] Decrypting...")
    decrypted = unpack_packet(encrypted)
    print(json.dumps(decrypted, indent=2))
    
    print("\n[4] Verification:")
    if test_data == decrypted:
        print("  ✅ SUCCESS: Decrypted data matches original!")
    else:
        print("  ❌ FAILED: Data mismatch!")
    
    print("\n" + "="*60)
    print("Encryption module ready!")
    print("="*60)
