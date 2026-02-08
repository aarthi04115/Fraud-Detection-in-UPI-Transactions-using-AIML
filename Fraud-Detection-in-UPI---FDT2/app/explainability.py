"""
Explainability module: converts features and model outputs into human-readable reasons.
This module does NOT calculate any risk scores; it only explains the inputs it receives.
"""
from __future__ import annotations

from typing import Dict, List, Any

# Default thresholds for qualitative explanations
DEFAULT_THRESHOLDS = {
    "amount_high": 10000.0,
    "amount_medium": 5000.0,
    "device_age_days_new": 7,
    "txn_per_hour_high": 8,
    "txn_per_hour_medium": 4,
    "distance_km_high": 500.0,
    "distance_km_medium": 100.0,
    "iforest_anomaly": 0.7,
    "rf_prob_high": 0.7,
    "rf_prob_medium": 0.4,
    "xgb_prob_high": 0.7,
    "xgb_prob_medium": 0.4,
    "hour_night_start": 0,
    "hour_night_end": 5,
}


def _maybe(features: Dict[str, Any], key: str, default=None):
    return features.get(key, default)


def _add(reason: str, reasons: List[str]):
    if reason and reason not in reasons:
        reasons.append(reason)


def explain_transaction(
    features: Dict[str, Any],
    model_outputs: Dict[str, Any],
    thresholds: Dict[str, float] | None = None,
) -> List[str]:
    """
    Build human-readable reasons from transaction features and model outputs.

    Parameters
    ----------
    features : dict
        Extracted transaction features (already computed elsewhere).
    model_outputs : dict
        Individual model outputs, e.g. {
            "iforest_score": float,   # anomaly score or 1 - anomaly probability
            "rf_proba": float,        # probability of fraud
            "xgb_proba": float        # probability of fraud
        }
    thresholds : dict, optional
        Override defaults for explanation thresholds.

    Returns
    -------
    list[str]
        Human-readable reasons. No scoring or actions are produced here.
    """

    t = DEFAULT_THRESHOLDS.copy()
    if thresholds:
        t.update(thresholds)

    reasons: List[str] = []

    amount = float(_maybe(features, "amount", 0) or 0)
    if amount >= t["amount_high"]:
        _add(f"Very high amount {amount:,.0f} detected", reasons)
    elif amount >= t["amount_medium"]:
        _add(f"High amount {amount:,.0f} detected", reasons)

    device_age_days = _maybe(features, "device_age_days")
    if device_age_days is not None and device_age_days <= t["device_age_days_new"]:
        _add("New or recently seen device", reasons)

    dist_km = _maybe(features, "distance_from_last_km")
    if dist_km is not None:
        if dist_km >= t["distance_km_high"]:
            _add("Large geo-distance since last transaction", reasons)
        elif dist_km >= t["distance_km_medium"]:
            _add("Unusual geo-distance since last transaction", reasons)

    txn_per_hour = _maybe(features, "txn_count_last_hour")
    if txn_per_hour is not None:
        if txn_per_hour >= t["txn_per_hour_high"]:
            _add("Transaction burst detected in the last hour", reasons)
        elif txn_per_hour >= t["txn_per_hour_medium"]:
            _add("Elevated transaction velocity in the last hour", reasons)

    hour_of_day = _maybe(features, "hour_of_day")
    if hour_of_day is not None:
        try:
            hour_val = int(hour_of_day)
            if t["hour_night_start"] <= hour_val <= t["hour_night_end"]:
                _add("Night-time transaction", reasons)
        except (TypeError, ValueError):
            pass

    channel = _maybe(features, "channel")
    if channel:
        if str(channel).lower() in {"p2p", "wallet"}:
            _add("Peer-to-peer or wallet channel", reasons)

    tx_type = _maybe(features, "tx_type")
    if tx_type:
        tx_type_l = str(tx_type).lower()
        if tx_type_l in {"refund", "reversal"}:
            _add("Uncommon transaction type (refund/reversal)", reasons)
        elif tx_type_l in {"intl", "crossborder"}:
            _add("Cross-border transaction", reasons)

    recipient_risk = _maybe(features, "recipient_risk_score")
    if recipient_risk is not None:
        try:
            r = float(recipient_risk)
            if r >= 0.8:
                _add("Recipient has high historical risk", reasons)
            elif r >= 0.5:
                _add("Recipient has moderate historical risk", reasons)
        except (TypeError, ValueError):
            pass

    # Model-driven signals (no aggregation, no scoring)
    iforest_score = model_outputs.get("iforest_score")
    if iforest_score is not None:
        try:
            s = float(iforest_score)
            if s >= t["iforest_anomaly"]:
                _add("Isolation Forest flags this as anomalous", reasons)
        except (TypeError, ValueError):
            pass

    rf_proba = model_outputs.get("rf_proba")
    if rf_proba is not None:
        try:
            p = float(rf_proba)
            if p >= t["rf_prob_high"]:
                _add("Random Forest predicts high fraud likelihood", reasons)
            elif p >= t["rf_prob_medium"]:
                _add("Random Forest predicts moderate fraud likelihood", reasons)
        except (TypeError, ValueError):
            pass

    xgb_proba = model_outputs.get("xgb_proba")
    if xgb_proba is not None:
        try:
            p = float(xgb_proba)
            if p >= t["xgb_prob_high"]:
                _add("XGBoost predicts high fraud likelihood", reasons)
            elif p >= t["xgb_prob_medium"]:
                _add("XGBoost predicts moderate fraud likelihood", reasons)
        except (TypeError, ValueError):
            pass

    # Fallback when nothing notable was triggered
    if not reasons:
        _add("No elevated risk indicators detected; transaction appears typical", reasons)

    return reasons


__all__ = [
    "explain_transaction",
    "DEFAULT_THRESHOLDS",
]
