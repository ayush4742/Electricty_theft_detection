"""Ingest a distribution-network dataset from a CSV upload.

WHY THIS EXISTS

The Network Health figures were never hard-coded — every loss percentage on that
page is computed from rows in SQLite. But those rows came from
`seed_transformers.py`, a script that has to be run from a terminal. That made
the numbers unchangeable from the application, which is functionally the same
problem as hard-coding from a user's point of view.

This module lets the dataset be uploaded instead. The maths, the persistence
rule, the API and the UI are all unchanged — only the source of the rows moves
from a script to a file the user controls.

EXPECTED CSV FORMAT — one row per transformer per day

    transformer_id, name, area, capacity_kva, meters, reading_date,
    energy_supplied, energy_billed

  transformer_id   required   e.g. DT-001
  reading_date     required   YYYY-MM-DD (D/M/YYYY and M/D/YYYY also accepted)
  energy_supplied  required   units into the transformer that day
  energy_billed    required   units billed to consumers under it that day
  name, area       optional   free text; defaults derived from the id
  capacity_kva     optional   number
  meters           optional   how many consumers sit under this transformer

Billed energy is taken per transformer per day rather than per meter, because a
utility exporting this from its billing system has it at that grain, and asking
for 1,700 meter rows in a CSV would make the feature unusable. The database
still supports the per-meter path — `transformer_db` falls back to summing
`meter_readings` whenever the uploaded column is absent — so the seeded dataset
keeps working exactly as before.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import sqlite3
from datetime import datetime
from typing import Any

from config import DB_PATH
import transformer_db


logger = logging.getLogger(__name__)

REQUIRED = ("transformer_id", "reading_date", "energy_supplied", "energy_billed")
MAX_ROWS = 200_000

# Header aliases, so an export that calls it "dt_id" or "supplied_kwh" still works
# rather than failing with an unhelpful "missing column".
ALIASES = {
    "transformer_id": {"transformer_id", "transformer", "dt_id", "dt", "feeder_id"},
    "reading_date": {"reading_date", "date", "reading_day", "day"},
    "energy_supplied": {"energy_supplied", "supplied", "supplied_kwh", "input_units",
                        "energy_input", "kwh_supplied"},
    "energy_billed": {"energy_billed", "billed", "billed_kwh", "billed_units",
                      "energy_output", "kwh_billed"},
    "name": {"name", "transformer_name", "dt_name"},
    "area": {"area", "zone", "locality", "region", "feeder"},
    "capacity_kva": {"capacity_kva", "capacity", "kva", "rating_kva"},
    "meters": {"meters", "meter_count", "consumers", "consumer_count", "connections"},
    "latitude": {"latitude", "lat"},
    "longitude": {"longitude", "lon", "lng", "long"},
}

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S")


class UploadError(ValueError):
    """A problem with the uploaded file that the user can fix."""


def _normalise_headers(fieldnames: list[str]) -> dict[str, str]:
    """Map the file's actual headers onto our canonical names."""
    found: dict[str, str] = {}
    for raw in fieldnames or []:
        key = re.sub(r"[^a-z0-9]+", "_", str(raw).strip().lower()).strip("_")
        for canonical, accepted in ALIASES.items():
            if key in accepted and canonical not in found:
                found[canonical] = raw
                break
    return found


def _parse_date(value: str) -> str:
    raw = str(value or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise UploadError(f"Could not read '{raw}' as a date. Use YYYY-MM-DD.")


def _parse_number(value: str, field: str, row_no: int) -> float:
    raw = str(value or "").strip().replace(",", "")
    if raw == "":
        raise UploadError(f"Row {row_no}: '{field}' is empty.")
    try:
        number = float(raw)
    except ValueError:
        raise UploadError(f"Row {row_no}: '{field}' is not a number ('{value}').")
    if number < 0:
        raise UploadError(f"Row {row_no}: '{field}' is negative ({number}).")
    return number


def parse_csv(file_storage) -> dict[str, Any]:
    """Read and validate the upload. Raises UploadError with a fixable message."""
    try:
        text = file_storage.read().decode("utf-8-sig", errors="replace")
    except Exception as exc:
        raise UploadError(f"Could not read the file: {exc}")

    reader = csv.DictReader(io.StringIO(text))
    headers = _normalise_headers(reader.fieldnames)

    missing = [c for c in REQUIRED if c not in headers]
    if missing:
        raise UploadError(
            "Missing required column(s): " + ", ".join(missing) +
            ". Expected at least: " + ", ".join(REQUIRED) +
            f". Found: {', '.join(reader.fieldnames or []) or 'nothing'}."
        )

    transformers: dict[str, dict[str, Any]] = {}
    readings: list[tuple] = []
    seen: set[tuple[str, str]] = set()
    warnings: list[str] = []

    for row_no, row in enumerate(reader, start=2):     # row 1 is the header
        if row_no - 1 > MAX_ROWS:
            raise UploadError(f"File has more than {MAX_ROWS:,} rows.")
        if not any((v or "").strip() for v in row.values()):
            continue                                    # blank line

        tid = str(row.get(headers["transformer_id"], "") or "").strip().upper()
        if not tid:
            raise UploadError(f"Row {row_no}: transformer_id is empty.")

        date = _parse_date(row.get(headers["reading_date"]))
        supplied = _parse_number(row.get(headers["energy_supplied"]), "energy_supplied", row_no)
        billed = _parse_number(row.get(headers["energy_billed"]), "energy_billed", row_no)

        if (tid, date) in seen:
            raise UploadError(f"Row {row_no}: {tid} already has a reading for {date}.")
        seen.add((tid, date))

        if billed > supplied and len(warnings) < 5:
            warnings.append(
                f"{tid} on {date}: billed ({billed:,.0f}) exceeds supplied ({supplied:,.0f}). "
                "That is physically impossible and usually means meters are mapped to the "
                "wrong transformer. It is reported as 0% loss, not negative."
            )

        readings.append((tid, date, supplied, billed))

        if tid not in transformers:
            def opt(field, default=None):
                col = headers.get(field)
                value = (row.get(col) or "").strip() if col else ""
                return value or default

            capacity = opt("capacity_kva")
            meters = opt("meters")
            transformers[tid] = {
                "transformer_id": tid,
                "name": opt("name", tid),
                "area": opt("area", "Unassigned"),
                "capacity_kva": float(capacity) if capacity else None,
                "declared_meters": int(float(meters)) if meters else None,
                "latitude": float(opt("latitude")) if opt("latitude") else None,
                "longitude": float(opt("longitude")) if opt("longitude") else None,
            }

    if not readings:
        raise UploadError("The file contains no data rows.")

    dates = sorted({r[1] for r in readings})
    return {
        "transformers": list(transformers.values()),
        "readings": readings,
        "row_count": len(readings),
        "date_from": dates[0],
        "date_to": dates[-1],
        "days": len(dates),
        "warnings": warnings,
    }


def replace_dataset(parsed: dict[str, Any], filename: str) -> dict[str, Any]:
    """Swap in the uploaded dataset, inside one transaction.

    Replacing rather than appending is deliberate: Network Health describes one
    network over one window, and merging two uploads would silently produce a
    network that never existed. The previous dataset is removed only once the
    new one has been written successfully.

    The `predictions`, `alert_log`, `meters` and `meter_readings` tables are not
    touched, so ML history and the seeded per-meter data survive an upload.
    """
    transformer_db.init_transformer_tables()

    with sqlite3.connect(DB_PATH) as connection:
        try:
            connection.execute("BEGIN")
            connection.execute("DELETE FROM transformer_readings")
            connection.execute("DELETE FROM transformers")

            connection.executemany(
                """
                INSERT INTO transformers
                    (transformer_id, name, area, capacity_kva, latitude, longitude,
                     declared_meters, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'upload')
                """,
                [(t["transformer_id"], t["name"], t["area"], t["capacity_kva"],
                  t["latitude"], t["longitude"], t["declared_meters"])
                 for t in parsed["transformers"]],
            )
            connection.executemany(
                """
                INSERT INTO transformer_readings
                    (transformer_id, reading_date, energy_supplied, energy_billed)
                VALUES (?, ?, ?, ?)
                """,
                parsed["readings"],
            )
            connection.execute("DELETE FROM transformer_dataset")
            connection.execute(
                """
                INSERT INTO transformer_dataset
                    (filename, uploaded_at, transformers, rows, date_from, date_to, source)
                VALUES (?, ?, ?, ?, ?, ?, 'upload')
                """,
                (filename, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 len(parsed["transformers"]), parsed["row_count"],
                 parsed["date_from"], parsed["date_to"]),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            logger.exception("[DT] dataset replace failed; previous data left in place")
            raise

    logger.info("[DT] loaded %s transformers / %s rows from %s",
                len(parsed["transformers"]), parsed["row_count"], filename)

    return {
        "filename": filename,
        "transformers": len(parsed["transformers"]),
        "rows": parsed["row_count"],
        "days": parsed["days"],
        "date_from": parsed["date_from"],
        "date_to": parsed["date_to"],
        "warnings": parsed["warnings"],
    }


def dataset_status() -> dict[str, Any]:
    """Where the network figures currently come from."""
    try:
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM transformer_dataset ORDER BY id DESC LIMIT 1").fetchone()
            counts = connection.execute(
                "SELECT COUNT(*) FROM transformers").fetchone()[0]
            readings = connection.execute(
                "SELECT COUNT(*) FROM transformer_readings").fetchone()[0]
    except sqlite3.OperationalError:
        return {"source": "none", "transformers": 0, "rows": 0}

    if row is not None:
        return {"source": "upload", **dict(row)}
    if counts:
        return {
            "source": "seed",
            "transformers": counts,
            "rows": readings,
            "message": "Generated by seed_transformers.py. Upload a CSV to replace it.",
        }
    return {"source": "none", "transformers": 0, "rows": 0,
            "message": "No network data. Upload a transformer CSV to populate this page."}


def clear_dataset() -> int:
    """Remove the uploaded network. Leaves predictions and meter data untouched."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("DELETE FROM transformer_readings")
        connection.execute("DELETE FROM transformers")
        cur = connection.execute("DELETE FROM transformer_dataset")
        connection.commit()
        return int(cur.rowcount or 0)


CSV_TEMPLATE_HEADER = (
    "transformer_id,name,area,capacity_kva,meters,reading_date,energy_supplied,energy_billed"
)
