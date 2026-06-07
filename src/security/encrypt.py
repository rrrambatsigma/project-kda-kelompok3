"""
encrypt.py — Hybrid Encryption Utility
=======================================
Kelompok 3 - Keamanan Data
Bagian: AES-GCM Encrypt/Decrypt + RSA-OAEP Encrypt/Decrypt

Dipakai oleh:
  - ML.py (Raihan) → import build_packet()
  - dashboard.py (Rambat + Vio) → import unpack_packet()

Alur:
  SENDER  : build_packet(payload_dict)   → encrypted_packet (dict, JSON-safe)
  RECEIVER: unpack_packet(encrypted_packet) → payload_dict (asli)
"""

import os
import json
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend

# ─────────────────────────────────────────────
# PATH KONFIGURASI
# ─────────────────────────────────────────────

# encrypt.py → security/ → src/ → project-root/ (3 level naik)
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEY_DIR     = os.path.join(BASE_DIR, "hasil", "keys")
PRIVATE_KEY_PATH = os.path.join(KEY_DIR, "private_key.pem")
PUBLIC_KEY_PATH  = os.path.join(KEY_DIR, "public_key.pem")


# ─────────────────────────────────────────────
# KEY MANAGEMENT — RSA
# ─────────────────────────────────────────────

def generate_rsa_keypair(force: bool = False) -> tuple[RSAPrivateKey, RSAPublicKey]:
    """
    Generate RSA-2048 key pair dan simpan ke file .pem.

    Hanya generate SEKALI. Jika sudah ada dan force=False,
    langsung load dari file (anti-duplicate key).

    Args:
        force: Jika True, paksa generate ulang meskipun key sudah ada.

    Returns:
        (private_key, public_key)
    """
    os.makedirs(KEY_DIR, exist_ok=True)

    if not force and os.path.exists(PRIVATE_KEY_PATH) and os.path.exists(PUBLIC_KEY_PATH):
        print(f"[🔑 KEY] RSA key sudah ada, load dari file (tidak generate ulang)")
        return load_rsa_keys()

    print(f"[🔑 KEY] Generating RSA-2048 key pair...")

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    public_key = private_key.public_key()

    # Simpan private key
    with open(PRIVATE_KEY_PATH, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # Simpan public key
    with open(PUBLIC_KEY_PATH, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))

    print(f"[✓ KEY] Private key → {PRIVATE_KEY_PATH}")
    print(f"[✓ KEY] Public key  → {PUBLIC_KEY_PATH}")

    return private_key, public_key


def load_rsa_keys() -> tuple[RSAPrivateKey, RSAPublicKey]:
    """
    Load RSA key pair dari file .pem.

    Returns:
        (private_key, public_key)

    Raises:
        FileNotFoundError: Jika file .pem belum ada (belum generate).
    """
    if not os.path.exists(PRIVATE_KEY_PATH):
        raise FileNotFoundError(
            f"Private key tidak ditemukan: {PRIVATE_KEY_PATH}\n"
            f"Jalankan generate_rsa_keypair() terlebih dahulu."
        )
    if not os.path.exists(PUBLIC_KEY_PATH):
        raise FileNotFoundError(
            f"Public key tidak ditemukan: {PUBLIC_KEY_PATH}\n"
            f"Jalankan generate_rsa_keypair() terlebih dahulu."
        )

    with open(PRIVATE_KEY_PATH, "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(), password=None, backend=default_backend()
        )

    with open(PUBLIC_KEY_PATH, "rb") as f:
        public_key = serialization.load_pem_public_key(
            f.read(), backend=default_backend()
        )

    return private_key, public_key


def get_public_key() -> RSAPublicKey:
    """Shortcut: load hanya public key (untuk sender)."""
    _, public_key = load_rsa_keys()
    return public_key


def get_private_key() -> RSAPrivateKey:
    """Shortcut: load hanya private key (untuk receiver)."""
    private_key, _ = load_rsa_keys()
    return private_key


# ─────────────────────────────────────────────
# AES-GCM ENCRYPT / DECRYPT
# ─────────────────────────────────────────────

def aes_gcm_encrypt(payload: dict) -> tuple[bytes, bytes, bytes]:
    """
    Enkripsi payload dict menggunakan AES-256-GCM.

    AES key di-generate FRESH setiap pemanggilan (ini yang benar
    untuk hybrid encryption — setiap packet punya key berbeda).

    Args:
        payload: Dict hasil prediksi (akan di-serialize ke JSON).

    Returns:
        (ciphertext_with_tag, aes_key, nonce)
        - ciphertext_with_tag : data terenkripsi + tag integritas (16 byte terakhir)
        - aes_key             : 32-byte random key (harus dienkripsi dengan RSA)
        - nonce               : 12-byte random nonce (boleh dikirim plaintext)
    """
    aes_key = os.urandom(32)   # AES-256 → 32 byte
    nonce   = os.urandom(12)   # GCM standard nonce → 12 byte

    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    aesgcm = AESGCM(aes_key)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)
    # AESGCM.encrypt() otomatis append 16-byte authentication tag di akhir

    return ciphertext_with_tag, aes_key, nonce


def aes_gcm_decrypt(ciphertext_with_tag: bytes, aes_key: bytes, nonce: bytes) -> dict:
    """
    Dekripsi ciphertext menggunakan AES-256-GCM sekaligus verifikasi integritas.

    Args:
        ciphertext_with_tag : output dari aes_gcm_encrypt()
        aes_key             : AES key asli (sudah di-decrypt dari RSA)
        nonce               : nonce dari packet

    Returns:
        Dict payload asli.

    Raises:
        cryptography.exceptions.InvalidTag: Jika data dimodifikasi / tag tidak cocok.
    """
    aesgcm = AESGCM(aes_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    # Jika tag tidak valid, decrypt() akan raise InvalidTag — data ditolak!

    return json.loads(plaintext.decode("utf-8"))


# ─────────────────────────────────────────────
# RSA-OAEP ENCRYPT / DECRYPT (untuk AES key)
# ─────────────────────────────────────────────

def rsa_encrypt_aes_key(aes_key: bytes, public_key: RSAPublicKey) -> bytes:
    """
    Enkripsi AES key menggunakan RSA-OAEP dengan SHA-256.

    Args:
        aes_key    : 32-byte AES key dari aes_gcm_encrypt()
        public_key : RSA public key (load dari get_public_key())

    Returns:
        encrypted_aes_key (bytes)
    """
    encrypted_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return encrypted_key


def rsa_decrypt_aes_key(encrypted_aes_key: bytes, private_key: RSAPrivateKey) -> bytes:
    """
    Dekripsi AES key menggunakan RSA private key.

    Args:
        encrypted_aes_key : output dari rsa_encrypt_aes_key()
        private_key       : RSA private key (load dari get_private_key())

    Returns:
        aes_key asli (32 bytes)
    """
    aes_key = private_key.decrypt(
        encrypted_aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return aes_key


# ─────────────────────────────────────────────
# HIGH-LEVEL API — yang dipanggil ML.py & dashboard.py
# ─────────────────────────────────────────────

def build_packet(payload: dict) -> dict:
    """
    [SENDER SIDE] Enkripsi payload menjadi encrypted packet siap kirim.

    Dipanggil oleh ML.py (Raihan) setelah dapat hasil voting prediction.

    Contoh payload yang masuk:
        {
            "timestamp": "2024-01-01 03:21:30",
            "device_id": "SGD-0029",
            "voltage": 218.25,
            "current": 4.33,
            "power": 894.02,
            "frequency": 49.81,
            "temperature": 24.76,
            "latency": 18.09,
            "packet_loss": 0.17,
            "throughput": 85.21,
            "duplicate_packet": 1,
            "checksum_valid": 1,
            "authentication_fail": 0,
            "voting_prediction": 0,
            "label_name": "Normal"
        }

    Returns:
        Dict JSON-serializable dengan struktur:
        {
            "encrypted_payload": "<base64>",
            "encrypted_aes_key": "<base64>",
            "nonce":             "<base64>"
        }

    Raises:
        FileNotFoundError: Jika RSA key belum di-generate.
    """
    # Load public key (untuk enkripsi AES key)
    public_key = get_public_key()

    # Step 1: AES-GCM encrypt payload
    ciphertext_with_tag, aes_key, nonce = aes_gcm_encrypt(payload)

    # Step 2: RSA-OAEP encrypt AES key
    encrypted_aes_key = rsa_encrypt_aes_key(aes_key, public_key)

    # Step 3: Base64 encode semua bytes → agar JSON-serializable
    packet = {
        "encrypted_payload": base64.b64encode(ciphertext_with_tag).decode("utf-8"),
        "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode("utf-8"),
        "nonce":             base64.b64encode(nonce).decode("utf-8"),
    }

    return packet


def unpack_packet(packet: dict) -> dict:
    """
    [RECEIVER SIDE] Dekripsi encrypted packet kembali ke payload asli.

    Dipanggil oleh dashboard.py (Rambat + Vio) saat terima data dari server.

    Args:
        packet: Dict dengan key "encrypted_payload", "encrypted_aes_key", "nonce"
                (output dari build_packet())

    Returns:
        Dict payload asli (sama persis dengan yang dimasukkan ke build_packet()).

    Raises:
        FileNotFoundError: Jika RSA key belum di-generate.
        cryptography.exceptions.InvalidTag: Jika data dimodifikasi di tengah jalan.
        KeyError: Jika format packet tidak valid.
    """
    # Load private key (untuk dekripsi AES key)
    private_key = get_private_key()

    # Step 1: Base64 decode
    ciphertext_with_tag = base64.b64decode(packet["encrypted_payload"])
    encrypted_aes_key   = base64.b64decode(packet["encrypted_aes_key"])
    nonce               = base64.b64decode(packet["nonce"])

    # Step 2: RSA-OAEP decrypt AES key
    aes_key = rsa_decrypt_aes_key(encrypted_aes_key, private_key)

    # Step 3: AES-GCM decrypt payload (sekaligus verifikasi integritas)
    payload = aes_gcm_decrypt(ciphertext_with_tag, aes_key, nonce)

    return payload


# ─────────────────────────────────────────────
# SETUP — jalankan sekali di awal project
# ─────────────────────────────────────────────

def setup_keys():
    """
    Generate RSA key pair jika belum ada.
    Jalankan ini SEKALI di awal sebelum sistem dipakai.

    Aman dipanggil berkali-kali — tidak akan generate ulang
    jika key sudah ada (kecuali force=True).
    """
    generate_rsa_keypair(force=False)
    print("[✓ SETUP] Key management siap.")


# ─────────────────────────────────────────────
# QUICK TEST — jalankan: python encrypt.py
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  ENCRYPT.PY — Quick Test")
    print("=" * 60)

    # 1. Setup keys
    print("\n[1] Setup RSA keys...")
    setup_keys()

    # 2. Simulasi payload dari ML.py
    dummy_payload = {
        "timestamp":          "2024-01-01 03:21:30",
        "device_id":          "SGD-0029",
        "voltage":            218.2535,
        "current":            4.3345,
        "power":              894.0249,
        "frequency":          49.809,
        "temperature":        24.763,
        "latency":            18.09,
        "packet_loss":        0.17,
        "throughput":         85.21,
        "duplicate_packet":   1,
        "checksum_valid":     1,
        "authentication_fail":0,
        "voting_prediction":  0,
        "label_name":         "Normal"
    }

    print(f"\n[2] Payload asli:")
    for k, v in dummy_payload.items():
        print(f"    {k:<22}: {v}")

    # 3. Enkripsi (SENDER)
    print(f"\n[3] Enkripsi (build_packet)...")
    packet = build_packet(dummy_payload)
    print(f"    encrypted_payload : {packet['encrypted_payload'][:40]}...")
    print(f"    encrypted_aes_key : {packet['encrypted_aes_key'][:40]}...")
    print(f"    nonce             : {packet['nonce']}")

    # 4. Dekripsi (RECEIVER)
    print(f"\n[4] Dekripsi (unpack_packet)...")
    result = unpack_packet(packet)
    print(f"    Hasil dekripsi:")
    for k, v in result.items():
        print(f"    {k:<22}: {v}")

    # 5. Verifikasi
    print(f"\n[5] Verifikasi integritas...")
    assert result == dummy_payload, "❌ GAGAL: payload tidak cocok!"
    print(f"    ✅ BERHASIL: payload asli == hasil dekripsi")

    # 6. Test anti-tamper
    print(f"\n[6] Test anti-tamper (modifikasi packet)...")
    import copy
    tampered = copy.deepcopy(packet)
    raw = bytearray(base64.b64decode(tampered["encrypted_payload"]))
    raw[10] ^= 0xFF  # flip beberapa bit
    tampered["encrypted_payload"] = base64.b64encode(bytes(raw)).decode()

    try:
        unpack_packet(tampered)
        print("    ❌ GAGAL: harusnya error!")
    except Exception as e:
        print(f"    ✅ BERHASIL: tampered packet ditolak → {type(e).__name__}")

    print("\n" + "=" * 60)
    print("  Semua test passed! encrypt.py siap dipakai.")
    print("=" * 60)
    print(f"\n  Cara pakai di ML.py (Raihan):")
    print(f"    from encrypt import build_packet, setup_keys")
    print(f"    setup_keys()  # sekali saja di awal")
    print(f"    packet = build_packet(payload_dict)")
    print(f"\n  Cara pakai di dashboard.py (Rambat):")
    print(f"    from encrypt import unpack_packet")
    print(f"    payload = unpack_packet(packet)")