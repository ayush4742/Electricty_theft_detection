"""Distribution-transformer energy balance: the loss calculation itself.

WHY THIS EXISTS
---------------
A per-meter ML model can only say "this consumption pattern looks odd". It has
no way to know whether energy actually went missing. Energy balance closes that
gap by using conservation of energy at the transformer:

    loss_units = energy supplied by the DT - energy billed to meters under it
    loss_pct   = loss_units / energy supplied * 100

Some loss is unavoidable physics - resistance in the conductors, transformer
core losses. That is "technical loss" and in a healthy Indian LT network it
sits around 4-8%. Anything well above that is "commercial loss": meter
tampering, direct hooking, bypassed meters, or unmetered connections.

THE PERSISTENCE RULE
--------------------
One bad day proves nothing. A meter can fail to communicate, a reading can be
estimated, a big industrial consumer can be billed a day late. So a DT is only
called CRITICAL when it stays above the threshold on most days of the window.
This single rule removes the majority of false alarms and is the difference
between a toy and something an engineer would trust.
"""

from __future__ import annotations

import logging
from typing import Any

import transformer_db


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Tunables - change these to match your utility's own benchmarks
# --------------------------------------------------------------------------- #

# Loss at or below this is considered normal technical loss (heat in the wires).
TECHNICAL_LOSS_THRESHOLD = 8.0

# Above this, commercial loss (theft) is the likely explanation.
SUSPICIOUS_LOSS_THRESHOLD = 15.0

# Fraction of days in the window that must breach the threshold before a DT is
# escalated. 0.6 means "bad on at least 60% of the days we looked at".
PERSISTENCE_RATIO = 0.6

# Average billed tariff, rupees per unit (kWh). Used only to translate lost
# units into a rupee figure for the dashboard.
TARIFF_RATE_PER_UNIT = 8.0

# Weights for blending the DT-level signal with the per-meter ML signal.
DT_WEIGHT = 0.5
ML_WEIGHT = 0.5


# --------------------------------------------------------------------------- #
# Core calculation
# --------------------------------------------------------------------------- #
def calculate_loss(energy_supplied: float, energy_billed: float) -> dict[str, Any] | None:
    """Loss for a single day. Returns None when the reading is unusable.

    Negative loss (billed > supplied) is physically impossible and always means
    a data problem - a missing feeder reading, or meters mapped to the wrong
    DT. We surface it as 0% rather than pretending it is a good result.
    """
    supplied = float(energy_supplied or 0.0)
    billed = float(energy_billed or 0.0)

    if supplied <= 0:
        return None

    loss_units = supplied - billed
    loss_pct = (loss_units / supplied) * 100.0

    data_issue = loss_units < 0
    if data_issue:
        loss_units = 0.0
        loss_pct = 0.0

    return {
        "energy_supplied": round(supplied, 2),
        "energy_billed": round(billed, 2),
        "loss_units": round(loss_units, 2),
        "loss_pct": round(loss_pct, 2),
        "data_issue": data_issue,
    }


def classify(loss_pct: float) -> str:
    """Bucket a single loss percentage."""
    if loss_pct <= TECHNICAL_LOSS_THRESHOLD:
        return "NORMAL"
    if loss_pct <= SUSPICIOUS_LOSS_THRESHOLD:
        return "WATCH"
    return "CRITICAL"


def _summarise(transformer: dict[str, Any], daily: list[dict[str, Any]], days: int) -> dict[str, Any]:
    """Turn a DT's daily readings into one summary row for the UI."""
    points = []
    for row in daily:
        result = calculate_loss(row["energy_supplied"], row["energy_billed"])
        if result is None:
            continue
        result["reading_date"] = row["reading_date"]
        result["status"] = classify(result["loss_pct"])
        points.append(result)

    base = {
        "transformer_id": transformer["transformer_id"],
        "name": transformer.get("name"),
        "area": transformer.get("area"),
        "capacity_kva": transformer.get("capacity_kva"),
        "latitude": transformer.get("latitude"),
        "longitude": transformer.get("longitude"),
        "meter_count": transformer.get("meter_count", 0),
        "days_monitored": len(points),
    }

    if not points:
        base.update(
            {
                "energy_supplied": 0.0,
                "energy_billed": 0.0,
                "loss_units": 0.0,
                "loss_pct": 0.0,
                "status": "NO_DATA",
                "days_above_threshold": 0,
                "persistent": False,
                "estimated_monthly_revenue_loss": 0.0,
                "trend": "flat",
            }
        )
        return base

    total_supplied = sum(p["energy_supplied"] for p in points)
    total_billed = sum(p["energy_billed"] for p in points)
    total_loss = max(0.0, total_supplied - total_billed)
    avg_loss_pct = (total_loss / total_supplied * 100.0) if total_supplied else 0.0

    # Persistence: how many of the days we looked at breached the technical limit
    days_above = sum(1 for p in points if p["loss_pct"] > TECHNICAL_LOSS_THRESHOLD)
    persistent = days_above >= max(1, int(len(points) * PERSISTENCE_RATIO))

    # A DT is only escalated to CRITICAL if the average is high AND it is
    # persistent. A high average driven by two freak days stays at WATCH.
    status = classify(avg_loss_pct)
    if status == "CRITICAL" and not persistent:
        status = "WATCH"

    # Is it getting worse? Compare the last third of the window to the first.
    third = max(1, len(points) // 3)
    early = sum(p["loss_pct"] for p in points[:third]) / third
    late = sum(p["loss_pct"] for p in points[-third:]) / third
    if late - early > 2.0:
        trend = "worsening"
    elif early - late > 2.0:
        trend = "improving"
    else:
        trend = "flat"

    # Scale the window's loss to a 30-day month so the rupee figure is
    # comparable across transformers regardless of how much data exists.
    daily_loss_units = total_loss / len(points)
    monthly_revenue_loss = daily_loss_units * 30 * TARIFF_RATE_PER_UNIT

    base.update(
        {
            "energy_supplied": round(total_supplied, 2),
            "energy_billed": round(total_billed, 2),
            "loss_units": round(total_loss, 2),
            "loss_pct": round(avg_loss_pct, 2),
            "status": status,
            "days_above_threshold": days_above,
            "persistent": persistent,
            "estimated_monthly_revenue_loss": round(monthly_revenue_loss, 0),
            "trend": trend,
        }
    )
    return base


# --------------------------------------------------------------------------- #
# Public API used by routes.py
# --------------------------------------------------------------------------- #
def get_transformer_summary(transformer_id: str, days: int = 30) -> dict[str, Any] | None:
    """Summary row for one transformer, or None if the id is unknown."""
    transformer = transformer_db.get_transformer(transformer_id)
    if transformer is None:
        return None
    daily = transformer_db.get_daily_balance(transformer_id, days)
    return _summarise(transformer, daily, days)


def get_network_summary(days: int = 30) -> list[dict[str, Any]]:
    """Every transformer, worst loss first - this is the inspection priority list."""
    transformers = transformer_db.list_transformers()
    balances = transformer_db.get_all_daily_balances(days)

    summaries = [
        _summarise(transformer, balances.get(transformer["transformer_id"], []), days)
        for transformer in transformers
    ]
    summaries.sort(key=lambda item: item["loss_pct"], reverse=True)
    return summaries


def get_transformer_trend(transformer_id: str, days: int = 30) -> list[dict[str, Any]]:
    """Day-by-day series for the detail-page chart, oldest first."""
    trend = []
    for row in transformer_db.get_daily_balance(transformer_id, days):
        result = calculate_loss(row["energy_supplied"], row["energy_billed"])
        if result is None:
            continue
        result["reading_date"] = row["reading_date"]
        result["status"] = classify(result["loss_pct"])
        trend.append(result)
    return trend


def get_network_kpis(days: int = 30) -> dict[str, Any]:
    """Headline numbers for the top of the Network Health page."""
    summaries = get_network_summary(days)
    with_data = [s for s in summaries if s["status"] != "NO_DATA"]

    total_supplied = sum(s["energy_supplied"] for s in with_data)
    total_billed = sum(s["energy_billed"] for s in with_data)
    total_loss = max(0.0, total_supplied - total_billed)
    avg_loss_pct = (total_loss / total_supplied * 100.0) if total_supplied else 0.0

    return {
        "total_transformers": len(summaries),
        "critical_count": sum(1 for s in with_data if s["status"] == "CRITICAL"),
        "watch_count": sum(1 for s in with_data if s["status"] == "WATCH"),
        "normal_count": sum(1 for s in with_data if s["status"] == "NORMAL"),
        "total_meters": sum(s["meter_count"] for s in summaries),
        "total_supplied": round(total_supplied, 2),
        "total_billed": round(total_billed, 2),
        "total_loss_units": round(total_loss, 2),
        "avg_loss_pct": round(avg_loss_pct, 2),
        "estimated_monthly_revenue_loss": round(
            sum(s["estimated_monthly_revenue_loss"] for s in with_data), 0
        ),
        "worsening_count": sum(1 for s in with_data if s["trend"] == "worsening"),
        "days_analysed": days,
        "technical_loss_threshold": TECHNICAL_LOSS_THRESHOLD,
        "suspicious_loss_threshold": SUSPICIOUS_LOSS_THRESHOLD,
    }


# --------------------------------------------------------------------------- #
# Blending the two signals
# --------------------------------------------------------------------------- #
def dt_loss_score(loss_pct: float, persistent: bool) -> float:
    """Map a DT's loss percentage to a 0-1 risk score.

    Below the technical threshold the score is 0 - normal physics is not
    evidence of anything. Above it, the score ramps up linearly and saturates at
    30% loss. A non-persistent breach is halved.
    """
    if loss_pct <= TECHNICAL_LOSS_THRESHOLD:
        return 0.0
    score = min(1.0, (loss_pct - TECHNICAL_LOSS_THRESHOLD) / (30.0 - TECHNICAL_LOSS_THRESHOLD))
    return score if persistent else score * 0.5


def combined_priority(ml_confidence: float, loss_pct: float, persistent: bool) -> dict[str, Any]:
    """Blend the per-meter ML confidence with its transformer's loss signal.

    This is the point of the whole feature. A meter the model dislikes, sitting
    under a transformer that is provably losing energy, is a far stronger case
    than either signal alone - and a model hit under a perfectly balanced
    transformer is probably a false positive worth deprioritising.
    """
    dt_score = dt_loss_score(loss_pct, persistent)
    ml_score = max(0.0, min(1.0, float(ml_confidence or 0.0)))
    score = (DT_WEIGHT * dt_score) + (ML_WEIGHT * ml_score)

    if score >= 0.7:
        priority = "HIGH"
    elif score >= 0.4:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    return {
        "priority_score": round(score, 3),
        "priority": priority,
        "ml_score": round(ml_score, 3),
        "dt_score": round(dt_score, 3),
    }
