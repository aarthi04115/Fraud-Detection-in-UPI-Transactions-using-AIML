import random
import uuid
from datetime import datetime, timedelta, timezone
import numpy as np
from sklearn.ensemble import IsolationForest
import joblib
from app.feature_engine import extract_features

# ----------------------------
# Generate normal synthetic transactions
# ----------------------------
def generate_tx():
    ts = datetime.now(timezone.utc) - timedelta(seconds=random.randint(0, 86400))
    return {
        "tx_id": str(uuid.uuid4()),
        "user_id": f"user{random.randint(1, 300)}",
        "device_id": str(uuid.uuid4()),
        "timestamp": ts.isoformat(),
        "amount": round(abs(random.gauss(300, 200)) + 1, 2),
        "recipient_vpa": f"merchant{random.randint(1,200)}@upi",
        "tx_type": random.choice(["P2P", "P2M"]),
        "channel": random.choice(["app", "qr", "web"])
    }

# ----------------------------
# Feature extraction loop
# ----------------------------
def create_dataset(n=1500, n_anom=30):
    X = []
    for _ in range(n):
        tx = generate_tx()
        feats = extract_features(tx)
        X.append(feats)
    # inject anomalies
    for _ in range(n_anom):
        tx = generate_tx()
        tx["amount"] = round(random.uniform(5000, 20000),2)        # very large amounts
        tx["channel"] = "unknown_channel"
        tx["tx_type"] = "SUSPICIOUS"
        feats = extract_features(tx)
        X.append(feats)
    return np.array(X)

# ----------------------------
# Train Isolation Forest
# ----------------------------
def train():
    print("Generating dataset...")
    X = create_dataset()

    print("Training Isolation Forest...")
    model = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)

    model.fit(X)

    joblib.dump(model, "models/iforest.joblib")
    print("Model saved: models/iforest.joblib")

if __name__ == "__main__":
    train()
