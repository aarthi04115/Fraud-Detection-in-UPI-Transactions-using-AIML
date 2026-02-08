"""
Test fraud detection against realistic fraud scenarios
"""
from datetime import datetime, timezone, timedelta
from app.scoring import score_transaction

def print_result(scenario_name, tx, result):
    """Pretty print test results"""
    print(f"\n{'='*70}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'='*70}")
    print(f"Transaction: ₹{tx['amount']} to {tx['recipient_vpa']}")
    print(f"Time: {tx['timestamp']}")
    print(f"Channel: {tx['channel']} | Type: {tx['tx_type']} | Device: {tx['device_id']}")
    
    model_scores = result.get('model_scores', {})
    print(f"\n📊 ML Scores:")
    print(f"  Isolation Forest: {model_scores.get('iforest', 0.0):.2%}")
    print(f"  Random Forest:    {model_scores.get('random_forest', 0.0):.2%}")
    print(f"  XGBoost:          {model_scores.get('xgboost', 0.0):.2%}")
    print(f"  Ensemble:         {model_scores.get('ensemble', 0.0):.2%}")
    
    risk_score = result.get('final_risk_score', result.get('risk_score', 0.0))
    print(f"\n🎯 Final Risk: {risk_score:.2%} | Confidence: {result.get('confidence_level', 'UNKNOWN')}")
    
    reasons = result.get('reasons', [])
    if reasons and len(reasons) > 1:
        print(f"\n🚨 Fraud Indicators ({len(reasons)}):")
        for i, reason in enumerate(reasons[:6], 1):
            print(f"  {i}. {reason}")
    
    if risk_score >= 0.7:
        print(f"\n⛔ VERDICT: BLOCK TRANSACTION")
    elif risk_score >= 0.5:
        print(f"\n⚠️  VERDICT: MANUAL REVIEW REQUIRED")
    else:
        print(f"\n✅ VERDICT: ALLOW")


print("="*70)
print("FRAUD DETECTION TEST SUITE - Real Fraud Scenarios")
print("="*70)

# ===================================================================
# SCENARIO 1: High Amount Late Night Transaction
# ===================================================================
print("\n\n🌙 Test 1: High Amount at 2 AM")
scenario1 = {
    "tx_id": "test_night_fraud",
    "user_id": "user123",
    "device_id": "device_123_1",
    "timestamp": (datetime.now(timezone.utc).replace(hour=2, minute=15)).isoformat(),
    "amount": 15000.0,
    "recipient_vpa": "unknown_merchant_888@upi",
    "tx_type": "P2M",
    "channel": "qr"
}
result1 = score_transaction(scenario1, return_details=True)
print_result("HIGH AMOUNT + LATE NIGHT", scenario1, result1)


# ===================================================================
# SCENARIO 2: Account Takeover Pattern
# ===================================================================
print("\n\n🔓 Test 2: Account Takeover (New Device + Night + High Amount)")
scenario2 = {
    "tx_id": "test_takeover",
    "user_id": "user456",
    "device_id": "device_new_suspicious_xyz",  # New device
    "timestamp": (datetime.now(timezone.utc).replace(hour=3, minute=45)).isoformat(),
    "amount": 18500.0,
    "recipient_vpa": "987654321@upi",  # Suspicious numeric VPA
    "tx_type": "P2P",
    "channel": "web"  # Web channel (less common)
}
result2 = score_transaction(scenario2, return_details=True)
print_result("ACCOUNT TAKEOVER", scenario2, result2)


# ===================================================================
# SCENARIO 3: Suspicious Round Amount Pattern
# ===================================================================
print("\n\n💰 Test 3: Suspicious Round Amount")
scenario3 = {
    "tx_id": "test_round",
    "user_id": "user789",
    "device_id": "device_789_1",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "amount": 10000.0,  # Exactly ₹10,000 (very round)
    "recipient_vpa": "quickpay@upi",
    "tx_type": "P2M",
    "channel": "qr"
}
result3 = score_transaction(scenario3, return_details=True)
print_result("ROUND AMOUNT PATTERN", scenario3, result3)


# ===================================================================
# SCENARIO 4: Extremely High Amount
# ===================================================================
print("\n\n💸 Test 4: Extremely High Amount (₹50,000)")
scenario4 = {
    "tx_id": "test_high_amount",
    "user_id": "user321",
    "device_id": "device_321_1",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "amount": 50000.0,  # Way above normal (₹5k cap for training)
    "recipient_vpa": "merchant999@upi",
    "tx_type": "P2M",
    "channel": "app"
}
result4 = score_transaction(scenario4, return_details=True)
print_result("EXTREMELY HIGH AMOUNT", scenario4, result4)


# ===================================================================
# SCENARIO 5: Weekend Night Transaction
# ===================================================================
print("\n\n🌃 Test 5: Weekend Night Transaction")
# Calculate next Sunday at 1 AM
now = datetime.now(timezone.utc)
days_ahead = 6 - now.weekday()  # Sunday is 6
if days_ahead <= 0:
    days_ahead += 7
next_sunday = now + timedelta(days=days_ahead)
scenario5 = {
    "tx_id": "test_weekend_night",
    "user_id": "user555",
    "device_id": "device_555_1",
    "timestamp": next_sunday.replace(hour=1, minute=30).isoformat(),
    "amount": 8500.0,
    "recipient_vpa": "late_night_store@upi",
    "tx_type": "P2M",
    "channel": "qr"
}
result5 = score_transaction(scenario5, return_details=True)
print_result("WEEKEND NIGHT ACTIVITY", scenario5, result5)


# ===================================================================
# SUMMARY
# ===================================================================
print("\n\n" + "="*70)
print("TEST SUMMARY")
print("="*70)

scenarios = [
    ("High Amount at 2 AM", result1),
    ("Account Takeover", result2),
    ("Round Amount", result3),
    ("Extremely High (₹50k)", result4),
    ("Weekend Night", result5)
]

print(f"\n{'Scenario':<30} {'Risk Score':<15} {'Verdict':<20}")
print("-"*70)

for name, result in scenarios:
    risk = result.get('final_risk_score', result.get('risk_score', 0.0))
    if risk >= 0.7:
        verdict = "⛔ BLOCK"
    elif risk >= 0.5:
        verdict = "⚠️  REVIEW"
    else:
        verdict = "✅ ALLOW"
    print(f"{name:<30} {risk:>6.2%}        {verdict:<20}")

print("\n" + "="*70)
print("✓ All fraud scenarios tested")
print("="*70)
