"""
Test fraud detection with ₹1000 payment to unknown user
"""
import sys
from datetime import datetime, timezone
from app.scoring import score_transaction

# Create test transaction: ₹1000 to unknown user
test_tx = {
    "tx_id": "test_1000_unknown",
    "user_id": "user123",
    "device_id": "device_123_1",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "amount": 1000.0,
    "recipient_vpa": "unknown_user_999@upi",
    "tx_type": "P2P",
    "channel": "app"
}

print("="*70)
print("TESTING: ₹1000 Payment to Unknown User")
print("="*70)
print(f"\nTransaction Details:")
print(f"  Amount: ₹{test_tx['amount']}")
print(f"  Recipient: {test_tx['recipient_vpa']}")
print(f"  Type: {test_tx['tx_type']}")
print(f"  Channel: {test_tx['channel']}")
print(f"  Time: {test_tx['timestamp']}")

print(f"\n{'='*70}")
print("FRAUD DETECTION RESULTS")
print("="*70)

# Run fraud detection with details
result = score_transaction(test_tx, return_details=True)

print(f"\n📊 ML Model Scores:")
model_scores = result.get('model_scores', {})
print(f"  Isolation Forest: {model_scores.get('iforest', 0.0):.4f}")
print(f"  Random Forest:    {model_scores.get('random_forest', 0.0):.4f}")
print(f"  XGBoost:          {model_scores.get('xgboost', 0.0):.4f}")
print(f"  Ensemble:         {model_scores.get('ensemble', 0.0):.4f}")

print(f"\n🎯 Risk Score: {result.get('risk_score', 0.0):.4f}")
print(f"   Final Risk: {result.get('final_risk_score', 0.0):.4f}")
print(f"   Confidence: {result.get('confidence_level', 'UNKNOWN')}")
print(f"   Disagreement: {result.get('disagreement', 0.0):.4f}")

reasons = result.get('reasons', [])
if reasons:
    print(f"\n🔍 Fraud Indicators ({len(reasons)} detected):")
    for i, reason in enumerate(reasons[:8], 1):
        print(f"\n  {i}. {reason}")
else:
    print(f"\n✅ No fraud indicators detected")

print(f"\n{'='*70}")
risk_score = result.get('final_risk_score', result.get('risk_score', 0.0))
if risk_score >= 0.7:
    print("⛔ VERDICT: BLOCK - High fraud risk")
elif risk_score >= 0.5:
    print("⚠️  VERDICT: REVIEW - Medium fraud risk")
else:
    print("✅ VERDICT: ALLOW - Low fraud risk")
print("="*70)
