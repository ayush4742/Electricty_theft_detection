"""Database layer for distribution-transformer level energy balance.

This module is ADDITIVE. It creates its own tables and never touches the
existing `predictions` or `alert_log` tables.

Tables created here
-------------------
transformers          One row per distribution transformer (DT).
meters                Maps every consumer meter to the DT that feeds it.
meter_readings        Daily units consumed by each meter (billed side).
transformer_readings  Daily units supplied by each DT (feeder-meter side).

The whole feature rests on one comparison:

    energy supplied by the DT   vs   sum of energy billed to meters under it

The gap is "distribution loss". A small gap is normal physics (heat in the
wires). A large, persistent gap means energy is leaving the network without
being billed - i.e. theft.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from config import DB_PATH


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #
def init_transformer_tables() -> None:
    """Create the energy-balance tables if they do not already exist."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS transformers (
                transformer_id TEXT PRIMARY KEY,
                name           TEXT NOT NULL,
                area           TEXT,
                capacity_kva   REAL,
                latitude       REAL,
                longitude      REAL,
                commissioned   TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS meters (
                meter_id       TEXT PRIMARY KEY,
                transformer_id TEXT NOT NULL,
                consumer_name  TEXT,
                tariff_type    TEXT,
                sanctioned_load REAL,
                FOREIGN KEY (transformer_id) REFERENCES transformers (transformer_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS meter_readings (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                meter_id       TEXT NOT NULL,
                reading_date   TEXT NOT NULL,
                units_consumed REAL NOT NULL,
                UNIQUE (meter_id, reading_date)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS transformer_readings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                transformer_id  TEXT NOT NULL,
                reading_date    TEXT NOT NULL,
                energy_supplied REAL NOT NULL,
                UNIQUE (transformer_id, reading_date)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_meters_dt ON meters (transformer_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_meter_readings_date ON meter_readings (reading_date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_dt_readings_date ON transformer_readings (transformer_id, reading_date)"
        )
        connection.commit()

    logger.info("Transformer energy-balance tables ready")


def _rows(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Run a SELECT and return plain dicts. Never raises - returns [] on error."""
    try:
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(query, params).fetchall()]
    except Exception:
        logger.exception("Transformer query failed: %s", query.strip().split("\n")[0])
        return []


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def list_transformers() -> list[dict[str, Any]]:
    """Every transformer with a count of the meters hanging off it."""
    return _rows(
        """
        SELECT t.transformer_id,
               t.name,
               t.area,
               t.capacity_kva,
               t.latitude,
               t.longitude,
               COUNT(m.meter_id) AS meter_count
        FROM transformers t
        LEFT JOIN meters m ON m.transformer_id = t.transformer_id
        GROUP BY t.transformer_id
        ORDER BY t.transformer_id
        """
    )


def get_transformer(transformer_id: str) -> dict[str, Any] | None:
    """One transformer's static details, or None if the id is unknown."""
    rows = _rows(
        """
        SELECT t.transformer_id,
               t.name,
               t.area,
               t.capacity_kva,
               t.latitude,
               t.longitude,
               t.commissioned,
               COUNT(m.meter_id) AS meter_count
        FROM transformers t
        LEFT JOIN meters m ON m.transformer_id = t.transformer_id
        WHERE t.transformer_id = ?
        GROUP BY t.transformer_id
        """,
        (transformer_id,),
    )
    return rows[0] if rows else None


def get_daily_balance(transformer_id: str, days: int = 30) -> list[dict[str, Any]]:
    """Day-by-day supplied vs billed units for one transformer.

    This is the heart of the feature. `energy_supplied` comes from the DT's own
    feeder meter; `energy_billed` is the SUM of every consumer meter mapped to
    that DT on the same date. The join is what makes the comparison meaningful.

    Returned oldest-first so a chart can plot it straight through.
    """
    return _rows(
        """
        SELECT tr.reading_date,
               tr.energy_supplied,
               COALESCE((
                   SELECT SUM(mr.units_consumed)
                   FROM meter_readings mr
                   JOIN meters m ON m.meter_id = mr.meter_id
                   WHERE m.transformer_id = tr.transformer_id
                     AND mr.reading_date = tr.reading_date
               ), 0) AS energy_billed
        FROM transformer_readings tr
        WHERE tr.transformer_id = ?
        ORDER BY tr.reading_date DESC
        LIMIT ?
        """,
        (transformer_id, days),
    )[::-1]


def get_all_daily_balances(days: int = 30) -> dict[str, list[dict[str, Any]]]:
    """Same as get_daily_balance but for every transformer, in ONE query.

    Used by the network overview so we do not fire N separate queries when the
    dashboard loads.
    """
    rows = _rows(
        """
        SELECT tr.transformer_id,
               tr.reading_date,
               tr.energy_supplied,
               COALESCE((
                   SELECT SUM(mr.units_consumed)
                   FROM meter_readings mr
                   JOIN meters m ON m.meter_id = mr.meter_id
                   WHERE m.transformer_id = tr.transformer_id
                     AND mr.reading_date = tr.reading_date
               ), 0) AS energy_billed
        FROM transformer_readings tr
        WHERE tr.reading_date >= (
            SELECT MIN(reading_date) FROM (
                SELECT DISTINCT reading_date FROM transformer_readings
                ORDER BY reading_date DESC LIMIT ?
            )
        )
        ORDER BY tr.transformer_id, tr.reading_date
        """,
        (days,),
    )

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["transformer_id"], []).append(
            {
                "reading_date": row["reading_date"],
                "energy_supplied": row["energy_supplied"],
                "energy_billed": row["energy_billed"],
            }
        )
    return grouped


def get_meters_for_transformer(transformer_id: str) -> list[dict[str, Any]]:
    """Consumer meters fed by one transformer."""
    return _rows(
        """
        SELECT meter_id, consumer_name, tariff_type, sanctioned_load
        FROM meters
        WHERE transformer_id = ?
        ORDER BY meter_id
        """,
        (transformer_id,),
    )


def get_meter_transformer_map() -> dict[str, str]:
    """meter_id -> transformer_id, for joining ML predictions to a DT."""
    return {
        row["meter_id"]: row["transformer_id"]
        for row in _rows("SELECT meter_id, transformer_id FROM meters")
    }


def get_flagged_meters_for_transformer(transformer_id: str) -> list[dict[str, Any]]:
    """Meters under this DT that the ML model has already looked at.

    Joins the existing `predictions` table to the new `meters` table, taking the
    most recent prediction per meter. This is where the two halves of the system
    meet: the model says which meters look wrong, the energy balance says
    whether energy is actually missing from this cluster.
    """
    return _rows(
        """
        SELECT m.meter_id,
               m.consumer_name,
               m.tariff_type,
               p.prediction,
               p.confidence,
               p.risk,
               p.timestamp
        FROM meters m
        JOIN predictions p ON p.meter_id = m.meter_id
        WHERE m.transformer_id = ?
          AND p.id = (
              SELECT MAX(id) FROM predictions p2 WHERE p2.meter_id = m.meter_id
          )
        ORDER BY p.confidence DESC
        """,
        (transformer_id,),
    )


def has_transformer_data() -> bool:
    """True once the seeder has been run at least once."""
    rows = _rows("SELECT COUNT(*) AS n FROM transformer_readings")
    return bool(rows and rows[0]["n"] > 0)
