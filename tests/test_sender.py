import sys
import os
import requests

sys.path.append(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "src", "security"
    )
)

from encrypt import build_packet

payload = {
    "timestamp": "2026-05-28 22:00:00",
    "device_id": "SGD-0001",
    "voltage": 220.5,
    "current": 5.1,
    "power": 1100,
    "frequency": 50.0,
    "temperature": 35.0,
    "latency": 10.0,
    "packet_loss": 0.0,
    "throughput": 90.0,
    "duplicate_packet": 0,
    "checksum_valid": 1,
    "authentication_fail": 0,
    "voting_prediction": 1,
    "label_name": "Attack"
}

packet = build_packet(payload)

print("\n=== ENCRYPTED PACKET ===")
print(packet)

_post_url = os.environ.get("PREDICTION_POST_URL", "http://localhost:8001/prediction/receive")
response = requests.post(
    _post_url,
    json=packet
)

print("\n=== SERVER RESPONSE ===")
print(response.json())