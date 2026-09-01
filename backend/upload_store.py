"""Server-side memory of CSV upload runs.

WHY THIS EXISTS

The CSV Upload page used to lose everything the moment the user navigated away.
The cause was not a bug in the upload itself: `POST /predict-csv` already stores
every row it scores into the `predictions` table. What was missing was any record
of the RUN - which file produced which rows, how many there were, how long it
took. Without that the page had nothing to re-read on mount, so it kept the whole
result set in React state, and React state dies when the route unmounts.

So this module records one lightweight row per upload: the filename, the counts,
and the id range of the predictions that run created. The results themselves are
never duplicated - they are re-read from `predictions` by that id range. Nothing
here stores the raw CSV.

Additive only: a new table, its own file. The `predictions` and `alert_log`
tables and their data are untouched.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

from config import DB_PATH


logger = logging.getLogger(__name__)


def init_upload_store() -> None:
    """Create the upload-batch table if it does not exist."""
    try:
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS upload_batches (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename            TEXT NOT NULL,
                    uploaded_at         TEXT NOT NULL,
                    total_rows          INTEGER NOT NULL DEFAULT 0,
                    theft_count         INTEGER NOT NULL DEFAULT 0,
                    normal_count        INTEGER NOT NULL DEFAULT 0,
                    average_confidence  REAL NOT NULL DEFAULT 0,
                    processing_seconds  REAL NOT NULL DEFAULT 0,
                    first_prediction_id INTEGER,
                    last_prediction_id  INTEGER,
                    alert_summary       TEXT,
                    status              TEXT NOT NULL DEFAULT 'completed'
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_upload_batches_time ON upload_batches (id DESC)"
            )
            connection.commit()
        logger.info("[UPLOAD] upload_batches table ready")
    except Exception:
        logger.exception("[UPLOAD] could not initialise upload_batches")


def max_prediction_id() -> int:
    """Highest id currently in `predictions`.

    Captured immediately before and after a run so the batch can point at exactly
    the rows that run produced, without storing a second copy of them.
    """
    try:
        with sqlite3.connect(DB_PATH) as connection:
            row = connection.execute("SELECT COALESCE(MAX(id), 0) FROM predictions").fetchone()
        return int(row[0]) if row else 0
    except Exception:
        logger.exception("[UPLOAD] could not read max prediction id")
        return 0


def record_upload(filename: str, results: list[dict[str, Any]], processing_seconds: float,
                  alert_summary: dict[str, Any] | None, first_id: int, last_id: int) -> int | None:
    """Store one upload run. Never raises - bookkeeping must not fail a prediction."""
    try:
        total = len(results)
        theft = sum(1 for r in results if str(r.get("prediction", "")).lower() == "theft")
        confidences = [float(r["confidence"]) for r in results
                       if isinstance(r.get("confidence"), (int, float))]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        with sqlite3.connect(DB_PATH) as connection:
            cursor = connection.execute(
                """
                INSERT INTO upload_batches
                    (filename, uploaded_at, total_rows, theft_count, normal_count,
                     average_confidence, processing_seconds, first_prediction_id,
                     last_prediction_id, alert_summary, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed')
                """,
                (
                    str(filename or "upload.csv"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    total, theft, total - theft,
                    round(avg_conf, 2), round(float(processing_seconds), 3),
                    int(first_id), int(last_id),
                    json.dumps(alert_summary) if alert_summary else None,
                ),
            )
            connection.commit()
            logger.info("[UPLOAD] recorded batch %s: %s rows from %s",
                        cursor.lastrowid, total, filename)
            return int(cursor.lastrowid)
    except Exception:
        logger.exception("[UPLOAD] could not record upload batch")
        return None


def _rows(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    try:
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(r) for r in connection.execute(query, params).fetchall()]
    except Exception:
        logger.exception("[UPLOAD] query failed")
        return []


def list_uploads(limit: int = 10) -> list[dict[str, Any]]:
    """Recent upload runs, newest first - metadata only, no result rows."""
    return _rows(
        """
        SELECT id, filename, uploaded_at, total_rows, theft_count, normal_count,
               average_confidence, processing_seconds, status
        FROM upload_batches ORDER BY id DESC LIMIT ?
        """,
        (max(1, min(50, int(limit or 10))),),
    )


def get_upload(batch_id: int | None = None, include_results: bool = True) -> dict[str, Any] | None:
    """One upload run, with its result rows re-read from `predictions`.

    Passing no id returns the most recent run, which is what the Upload page asks
    for when it mounts. The results are fetched by id range, so revisiting the
    page creates no new records and re-runs no prediction.
    """
    if batch_id is None:
        batches = _rows("SELECT * FROM upload_batches ORDER BY id DESC LIMIT 1")
    else:
        batches = _rows("SELECT * FROM upload_batches WHERE id = ?", (int(batch_id),))
    if not batches:
        return None

    batch = batches[0]
    if batch.get("alert_summary"):
        try:
            batch["alert_summary"] = json.loads(batch["alert_summary"])
        except (TypeError, json.JSONDecodeError):
            batch["alert_summary"] = None

    if not include_results:
        batch["results"] = []
        return batch

    first_id = batch.get("first_prediction_id") or 0
    last_id = batch.get("last_prediction_id") or 0
    batch["results"] = _rows(
        """
        SELECT meter_id, prediction, confidence, risk, timestamp
        FROM predictions
        WHERE id > ? AND id <= ?
        ORDER BY id ASC
        """,
        (int(first_id), int(last_id)),
    )
    # The alert outcome per meter lives in alert_log, not in predictions, so the
    # SMS column can be restored too rather than showing "Not sent" for
    # everything after a page revisit.
    sent = {r["meter_id"] for r in _rows(
        "SELECT DISTINCT meter_id FROM alert_log WHERE status = 'sent'")}
    failed = {r["meter_id"] for r in _rows(
        "SELECT DISTINCT meter_id FROM alert_log WHERE status = 'failed'")}
    for row in batch["results"]:
        mid = row.get("meter_id")
        row["alert_sent"] = mid in sent
        row["alert_error"] = "delivery failed" if (mid in failed and mid not in sent) else None

    return batch


def clear_uploads() -> int:
    """Forget recorded upload runs. Does NOT delete predictions - the detection
    history is the system's record and is never removed by a UI action."""
    try:
        with sqlite3.connect(DB_PATH) as connection:
            cur = connection.execute("DELETE FROM upload_batches")
            connection.commit()
            return int(cur.rowcount or 0)
    except Exception:
        logger.exception("[UPLOAD] could not clear upload batches")
        return 0
