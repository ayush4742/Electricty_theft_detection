from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime
from typing import Any

import numpy as np

from config import DB_PATH


logger = logging.getLogger(__name__)


def init_db() -> None:
    """Create the local SQLite database and prediction history table if missing."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meter_id TEXT,
                prediction TEXT NOT NULL,
                confidence REAL NOT NULL,
                risk TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                features TEXT
            )
            """
        )
        connection.commit()

        # Add features column to existing table if it doesn't exist
        try:
            connection.execute("ALTER TABLE predictions ADD COLUMN features TEXT")
            connection.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

    init_alert_log()


def init_alert_log() -> None:
    """Create the SMS alert log table used for cooldown tracking."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meter_id TEXT NOT NULL,
                alert_type TEXT NOT NULL DEFAULT 'theft',
                channel TEXT,
                status TEXT NOT NULL,
                error TEXT,
                confidence REAL,
                recipients INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                created_epoch REAL NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_log_meter_time "
            "ON alert_log (meter_id, created_epoch DESC)"
        )
        connection.commit()


def save_prediction(
    meter_id: str | None,
    prediction: str,
    confidence: float,
    risk: str,
    timestamp: str,
    features: np.ndarray | list | None = None,
) -> None:
    """Store one prediction result in the SQLite database."""
    features_json = None

    if features is not None:
        try:
            if isinstance(features, np.ndarray):
                features_list = features.flatten().tolist()
            elif isinstance(features, list):
                features_list = features
            else:
                features_list = list(features)

            features_json = json.dumps(features_list)
        except Exception:
            features_json = None

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO predictions
            (meter_id, prediction, confidence, risk, timestamp, features)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                meter_id,
                prediction,
                confidence,
                risk,
                timestamp,
                features_json,
            ),
        )
        connection.commit()


def get_prediction_history(limit: int = 100) -> list[dict[str, Any]]:
    """Return the most recent prediction records from the local database."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT id, meter_id, prediction, confidence, risk, timestamp, features
            FROM predictions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_prediction_by_id(prediction_id: int) -> dict[str, Any] | None:
    """Retrieve a specific prediction record by ID."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT id, meter_id, prediction, confidence, risk, timestamp, features
            FROM predictions
            WHERE id = ?
            """,
            (prediction_id,),
        ).fetchone()

    if row:
        result = dict(row)

        if result.get("features"):
            try:
                result["features"] = json.loads(result["features"])
            except json.JSONDecodeError:
                result["features"] = None

        return result

    return None


def get_dashboard_stats(limit: int = 8) -> dict[str, Any]:
    """Compute dashboard statistics from the local SQLite prediction database."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT id, meter_id, prediction, confidence, risk, timestamp, features
            FROM predictions
            ORDER BY id DESC
            """
        ).fetchall()

    recent_history = [dict(row) for row in rows[:limit]]

    total_predictions = len(rows)
    theft_predictions = sum(
        1 for row in rows
        if str(row["prediction"]).lower() == "theft"
    )
    normal_predictions = total_predictions - theft_predictions

    latest_prediction = None

    if rows:
        latest_row = rows[0]

        latest_prediction = {
            "meter_id": latest_row["meter_id"],
            "prediction": latest_row["prediction"],
            "confidence": float(latest_row["confidence"]),
            "risk": latest_row["risk"],
            "timestamp": latest_row["timestamp"],
        }

    return {
        "total_predictions": total_predictions,
        "theft_predictions": theft_predictions,
        "normal_predictions": normal_predictions,
        "latest_prediction": latest_prediction,
        "recent_history": recent_history,
    }


# --------------------------------------------------------------------------- #
# SMS alert log (used for duplicate-alert / cooldown protection)
# --------------------------------------------------------------------------- #

def record_alert(
    meter_id: str,
    alert_type: str,
    channel: str | None,
    status: str,
    error: str | None,
    confidence: float | None,
    recipients: int = 0,
) -> None:
    """Write one row describing an alert attempt."""
    try:
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute(
                """
                INSERT INTO alert_log
                    (
                        meter_id,
                        alert_type,
                        channel,
                        status,
                        error,
                        confidence,
                        recipients,
                        created_at,
                        created_epoch
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(meter_id),
                    alert_type,
                    channel,
                    status,
                    error,
                    float(confidence) if confidence is not None else None,
                    int(recipients),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    time.time(),
                ),
            )
            connection.commit()

    except Exception:
        logger.exception("Failed to write alert_log entry")


def seconds_since_last_successful_alert(
    meter_id: str,
) -> float | None:
    """Seconds since the last successfully delivered theft alert."""
    try:
        with sqlite3.connect(DB_PATH) as connection:
            row = connection.execute(
                """
                SELECT created_epoch
                FROM alert_log
                WHERE meter_id = ?
                  AND status = 'sent'
                  AND alert_type = 'theft'
                ORDER BY created_epoch DESC
                LIMIT 1
                """,
                (str(meter_id),),
            ).fetchone()

    except Exception:
        logger.exception("Failed to read alert_log for cooldown check")
        return None

    if not row or row[0] is None:
        return None

    return max(0.0, time.time() - float(row[0]))


def get_alert_history(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent alert attempts for the frontend Alerts page."""
    try:
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row

            rows = connection.execute(
                """
                SELECT
                    meter_id,
                    alert_type,
                    channel,
                    status,
                    error,
                    confidence,
                    recipients,
                    created_at
                FROM alert_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    except Exception:
        logger.exception("Failed to read alert history")
        return []

    return [dict(row) for row in rows]


def get_alert_counts() -> dict[str, int]:
    """Aggregate counts for the Alerts page header."""
    try:
        with sqlite3.connect(DB_PATH) as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) FROM alert_log GROUP BY status"
            ).fetchall()

    except Exception:
        logger.exception("Failed to read alert counts")
        return {"sent": 0, "failed": 0, "cooldown": 0}

    counts = {"sent": 0, "failed": 0, "cooldown": 0}

    for status, count in rows:
        counts[str(status)] = int(count)

    return counts