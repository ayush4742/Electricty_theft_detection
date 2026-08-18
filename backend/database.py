from __future__ import annotations

import json
import sqlite3
from typing import Any

import numpy as np

from config import DB_PATH


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


def save_prediction(meter_id: str | None, prediction: str, confidence: float, risk: str, timestamp: str, features: np.ndarray | list | None = None) -> None:
    """Store one prediction result in the SQLite database."""
    features_json = None
    if features is not None:
        try:
            # Convert numpy array to list if needed
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
            "INSERT INTO predictions (meter_id, prediction, confidence, risk, timestamp, features) VALUES (?, ?, ?, ?, ?, ?)",
            (meter_id, prediction, confidence, risk, timestamp, features_json),
        )
        connection.commit()


def get_prediction_history(limit: int = 100) -> list[dict[str, Any]]:
    """Return the most recent prediction records from the local database."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT id, meter_id, prediction, confidence, risk, timestamp, features FROM predictions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_prediction_by_id(prediction_id: int) -> dict[str, Any] | None:
    """Retrieve a specific prediction record by ID."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT id, meter_id, prediction, confidence, risk, timestamp, features FROM predictions WHERE id = ?",
            (prediction_id,),
        ).fetchone()
    
    if row:
        result = dict(row)
        # Parse features if available
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
            "SELECT id, meter_id, prediction, confidence, risk, timestamp, features FROM predictions ORDER BY id DESC"
        ).fetchall()

    recent_history = [dict(row) for row in rows[:limit]]
    total_predictions = len(rows)
    theft_predictions = sum(1 for row in rows if str(row["prediction"]).lower() == "theft")
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
