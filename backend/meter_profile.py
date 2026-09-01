"""Everything the system knows about one consumer meter, in one place.

WHERE THE DATA COMES FROM
-------------------------
Nothing here is invented or hard-coded. Every field is derived from rows the
user's own uploads created:

  predictions.meter_id    the meter, as it appeared in the uploaded CSV
  predictions.features    the consumption readings that were scored (1000+ per
                          meter in the SGCC-style datasets this project uses)
  predictions.prediction  what the model decided, with confidence and risk
  alert_log               any theft alert that was raised for this meter
  meters / transformers   which distribution transformer feeds it, if the
                          network has been seeded

If a meter was never uploaded, this module says so rather than fabricating a
profile for it.

THE DERIVED SIGNALS
-------------------
The consumption statistics below (zero-day runs, sustained drops, volatility)
are the patterns a utility analyst actually looks for when reviewing a meter.
They are computed from the stored readings, and they are DESCRIPTIVE - they
describe the shape of the consumption, they do not accuse anybody. A long run
of zero days can equally be an empty house or a bypassed meter; only a field
visit settles it.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import statistics
from typing import Any

from config import DB_PATH


logger = logging.getLogger(__name__)

# How many points to send to the browser for the consumption chart. 1000+ raw
# points render as noise on a 900px wide chart and make the payload large, so
# they are averaged into buckets. The raw count is always reported alongside.
CHART_POINTS = 180


def _rows(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    try:
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(query, params).fetchall()]
    except Exception:
        logger.exception("Meter query failed: %s", query.strip().split("\n")[0])
        return []


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
def search_meters(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Find meters whose id contains `query`, newest analysis first.

    Matches anywhere in the id, so a user can paste the last six characters of
    a meter number off an inspection sheet instead of the full hash.
    """
    query = str(query or "").strip()
    limit = max(1, min(100, int(limit or 20)))

    if not query:
        # No search term: show the most recently analysed meters, so the page
        # is useful the moment it opens.
        return _rows(
            """
            SELECT p.meter_id,
                   p.prediction,
                   p.confidence,
                   p.risk,
                   p.timestamp,
                   COUNT(*) OVER (PARTITION BY p.meter_id) AS times_analysed
            FROM predictions p
            WHERE p.id = (SELECT MAX(id) FROM predictions p2 WHERE p2.meter_id = p.meter_id)
              AND p.meter_id IS NOT NULL AND p.meter_id != ''
            ORDER BY p.id DESC
            LIMIT ?
            """,
            (limit,),
        )

    return _rows(
        """
        SELECT p.meter_id,
               p.prediction,
               p.confidence,
               p.risk,
               p.timestamp,
               (SELECT COUNT(*) FROM predictions p3 WHERE p3.meter_id = p.meter_id) AS times_analysed
        FROM predictions p
        WHERE p.id = (SELECT MAX(id) FROM predictions p2 WHERE p2.meter_id = p.meter_id)
          AND UPPER(p.meter_id) LIKE UPPER(?)
        ORDER BY p.id DESC
        LIMIT ?
        """,
        (f"%{query}%", limit),
    )


# --------------------------------------------------------------------------- #
# Consumption analysis
# --------------------------------------------------------------------------- #
def _downsample(values: list[float], points: int = CHART_POINTS) -> list[dict[str, Any]]:
    """Average the readings into buckets so the chart stays readable.

    Each bucket keeps its own min and max as well as the mean, so a spike is
    still visible after averaging instead of being smoothed away.
    """
    if not values:
        return []

    # NaN must never reach the browser: json.dumps writes it as a bare NaN,
    # which is not valid JSON, and JSON.parse rejects the whole response - the
    # chart would not just be wrong, the page would fail to load the profile.
    def _finite(chunk: list[float]) -> list[float]:
        return [v for v in chunk if isinstance(v, (int, float)) and math.isfinite(v)]

    if len(values) <= points:
        return [
            {"index": i + 1, "value": round(v, 3), "low": round(v, 3), "high": round(v, 3)}
            for i, v in enumerate(values)
            if isinstance(v, (int, float)) and math.isfinite(v)
        ]

    size = len(values) / points
    series = []
    for i in range(points):
        chunk = _finite(values[int(i * size): int((i + 1) * size)])
        if not chunk:
            continue  # a bucket of entirely missing days simply has no point
        series.append(
            {
                "index": int(i * size) + 1,
                "value": round(sum(chunk) / len(chunk), 3),
                "low": round(min(chunk), 3),
                "high": round(max(chunk), 3),
            }
        )
    return series


def analyse_consumption(values: list[float]) -> dict[str, Any]:
    """Descriptive statistics over a meter's stored readings.

    Every number here is computed from the uploaded readings. None of it is a
    verdict - it is the evidence an analyst reads before forming one.
    """
    # Real meter data has holes. The SGCC-style datasets this project uses carry
    # NaN for days a meter did not report, and those survive into the stored
    # feature vector even though the imputer fills them before the model sees
    # them. Averaging over a NaN poisons every statistic, so drop them here and
    # report how many there were - a meter with many missing days is itself
    # worth knowing about.
    clean = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    missing = len(values) - len(clean)
    if not clean:
        return {"readings": 0, "missing_readings": missing}

    total = sum(clean)
    mean = total / len(clean)
    peak = max(clean)
    low = min(clean)

    # Zero-consumption days. A meter that records nothing for weeks is either an
    # empty property or one that stopped recording - both worth knowing about.
    zero_days = sum(1 for v in clean if v <= 0.0001)
    longest_zero = current = 0
    for value in clean:
        if value <= 0.0001:
            current += 1
            longest_zero = max(longest_zero, current)
        else:
            current = 0

    # Sustained drop: compare the second half of the record with the first. A
    # large negative shift is the classic signature of a meter that was
    # tampered with partway through - and equally of a family that moved out.
    half = len(clean) // 2
    first_half = clean[:half] or clean
    second_half = clean[half:] or clean
    first_avg = sum(first_half) / len(first_half)
    second_avg = sum(second_half) / len(second_half)
    change_pct = ((second_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0.0

    # Volatility. Very low variation on a domestic meter can mean a flat,
    # fabricated-looking profile; very high can just mean seasonal use.
    try:
        deviation = statistics.pstdev(clean)
    except statistics.StatisticsError:
        deviation = 0.0
    variation = (deviation / mean * 100) if mean > 0 else 0.0

    return {
        "readings": len(clean),
        "missing_readings": missing,
        "missing_percent": round(missing / len(values) * 100, 1) if values else 0.0,
        "total_units": round(total, 2),
        "average_daily": round(mean, 3),
        "peak": round(peak, 3),
        "minimum": round(low, 3),
        "std_deviation": round(deviation, 3),
        "variation_percent": round(variation, 1),
        "zero_days": zero_days,
        "zero_days_percent": round(zero_days / len(clean) * 100, 1),
        "longest_zero_run": longest_zero,
        "first_half_average": round(first_avg, 3),
        "second_half_average": round(second_avg, 3),
        "change_percent": round(change_pct, 1),
    }


def consumption_flags(stats: dict[str, Any]) -> list[dict[str, str]]:
    """Plain-language observations about the consumption shape.

    Deliberately worded as observations with their innocent explanation
    included. The system flags patterns for a human to check; it does not
    conclude that anyone is stealing.
    """
    flags: list[dict[str, str]] = []
    if not stats.get("readings"):
        return flags

    # Threshold set from the data, not from a guess: in the SGCC-style dataset
    # this project uses, meters average roughly 30% missing days, so flagging at
    # 10% would fire on almost everything and mean nothing. 40% marks the meters
    # whose record is genuinely too patchy to draw conclusions from.
    if stats.get("missing_percent", 0) >= 40:
        flags.append({
            "level": "info",
            "label": f"{stats['missing_percent']}% of days have no reading at all",
            "detail": "Gaps in the record itself - a communication or meter-reading problem, "
                      "not necessarily a consumption one.",
        })

    if stats["longest_zero_run"] >= 30:
        flags.append({
            "level": "warning",
            "label": f"{stats['longest_zero_run']} consecutive days at zero",
            "detail": "Could be a vacant property, a failed meter, or a bypassed one. Worth a look.",
        })
    elif stats["zero_days_percent"] >= 20:
        flags.append({
            "level": "info",
            "label": f"{stats['zero_days_percent']}% of days recorded zero",
            "detail": "Intermittent occupancy or intermittent recording.",
        })

    if stats["change_percent"] <= -40:
        flags.append({
            "level": "warning",
            "label": f"Consumption fell {abs(stats['change_percent'])}% in the second half",
            "detail": "A sustained drop like this follows a move-out, a meter fault, or tampering.",
        })
    elif stats["change_percent"] >= 60:
        flags.append({
            "level": "info",
            "label": f"Consumption rose {stats['change_percent']}% in the second half",
            "detail": "New appliance, new occupants, or a corrected meter.",
        })

    if stats["variation_percent"] <= 12 and stats["average_daily"] > 0:
        flags.append({
            "level": "info",
            "label": f"Unusually flat usage (variation {stats['variation_percent']}%)",
            "detail": "Real households vary day to day. A very flat profile is worth confirming.",
        })

    if not flags:
        flags.append({
            "level": "ok",
            "label": "No unusual pattern in the stored readings",
            "detail": "Usage is varied, with no long zero runs or sustained step change.",
        })
    return flags


# --------------------------------------------------------------------------- #
# The profile
# --------------------------------------------------------------------------- #
def get_meter_profile(meter_id: str, include_full_series: bool = False) -> dict[str, Any] | None:
    """Assemble everything stored about one meter. None if it was never uploaded."""
    meter_id = str(meter_id or "").strip()
    if not meter_id:
        return None

    history = _rows(
        """
        SELECT id, meter_id, prediction, confidence, risk, timestamp
        FROM predictions
        WHERE UPPER(meter_id) = UPPER(?)
        ORDER BY id DESC
        """,
        (meter_id,),
    )
    if not history:
        return None

    # Use the id as stored, not as typed, so the page shows the real casing.
    meter_id = history[0]["meter_id"]
    latest = history[0]

    # Readings come from the most recent prediction that actually stored them.
    readings: list[float] = []
    readings_from = None
    for row in history:
        raw = _rows("SELECT features FROM predictions WHERE id = ?", (row["id"],))
        blob = raw[0]["features"] if raw else None
        if not blob:
            continue
        try:
            parsed = json.loads(blob)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, list) and parsed:
            readings = [float(v) for v in parsed if isinstance(v, (int, float))]
            readings_from = row["id"]
            break

    stats = analyse_consumption(readings)

    # Did the model change its mind between uploads? Worth surfacing - it means
    # the meter's behaviour shifted, or the same meter was uploaded twice with
    # different data.
    verdicts = {str(row["prediction"]).lower() for row in history}

    profile: dict[str, Any] = {
        "meter_id": meter_id,
        "times_analysed": len(history),
        "first_analysed": history[-1]["timestamp"],
        "last_analysed": latest["timestamp"],
        "latest": {
            "prediction_id": latest["id"],
            "prediction": latest["prediction"],
            "confidence": latest["confidence"],
            "risk": latest["risk"],
            "timestamp": latest["timestamp"],
        },
        "verdict_changed": len(verdicts) > 1,
        "history": history,
        "consumption": {
            "readings_stored": len(readings),
            "from_prediction_id": readings_from,
            "stats": stats,
            "series": _downsample(readings) if readings else [],
            # null, not NaN - a missing day is representable in JSON as null.
            "full_series": (
                [round(v, 3) if math.isfinite(v) else None for v in readings]
                if include_full_series
                else None
            ),
        },
        "flags": consumption_flags(stats),
    }

    # --- alerts raised for this meter --------------------------------------
    profile["alerts"] = _rows(
        """
        SELECT alert_type, channel, status, error, confidence, recipients, created_at
        FROM alert_log
        WHERE UPPER(meter_id) = UPPER(?)
        ORDER BY id DESC
        LIMIT 20
        """,
        (meter_id,),
    )

    # --- transformer context, if the network has been seeded ---------------
    profile["transformer"] = None
    try:
        import energy_balance
        import transformer_db

        transformer_id = transformer_db.get_meter_transformer_map().get(meter_id)
        if transformer_id:
            summary = energy_balance.get_transformer_summary(transformer_id)
            if summary:
                confidence = float(latest["confidence"] or 0.0)
                if confidence > 1.0:
                    confidence = confidence / 100.0
                priority = energy_balance.combined_priority(
                    confidence, summary["loss_pct"], summary["persistent"]
                )
                profile["transformer"] = {
                    "transformer_id": summary["transformer_id"],
                    "name": summary["name"],
                    "area": summary["area"],
                    "loss_percent": summary["loss_pct"],
                    "status": summary["status"],
                    "persistent": summary["persistent"],
                    "meters_on_transformer": summary["meter_count"],
                    **priority,
                }
    except Exception:
        logger.exception("Transformer context unavailable for meter %s", meter_id)

    return profile
