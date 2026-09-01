"""API endpoints for distribution-transformer energy balance.

Kept in its own Blueprint so the existing `routes.py` stays untouched. These
endpoints sit alongside the per-meter ML endpoints rather than replacing them:
the model answers "does this meter look suspicious?", these answer "is energy
actually going missing from this part of the network?" - and a case is only
strong when both agree.

Registered from app.py via register_transformer_routes(app).
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Flask, Response, jsonify, request

import energy_balance
import transformer_db
import transformer_upload


logger = logging.getLogger(__name__)
transformer_bp = Blueprint("transformers", __name__)


def _days_arg() -> int:
    """Read ?days= from the query string, clamped to something sensible."""
    return max(1, min(365, request.args.get("days", default=30, type=int)))


@transformer_bp.get("/network-kpis")
def network_kpis() -> Any:
    """Headline numbers for the top of the Network Health page."""
    try:
        return jsonify(energy_balance.get_network_kpis(_days_arg()))
    except Exception as exc:
        logger.exception("Network KPI calculation failed")
        return jsonify({"error": "Network KPI error", "message": str(exc)}), 500


@transformer_bp.get("/transformers")
def transformers() -> Any:
    """Every transformer with its loss percentage, worst first."""
    try:
        days = _days_arg()
        summaries = energy_balance.get_network_summary(days)
        return jsonify(
            {
                "count": len(summaries),
                "days": days,
                "seeded": transformer_db.has_transformer_data(),
                "transformers": summaries,
            }
        )
    except Exception as exc:
        logger.exception("Transformer listing failed")
        return jsonify({"error": "Transformer error", "message": str(exc)}), 500


@transformer_bp.get("/transformers/high-loss")
def high_loss_transformers() -> Any:
    """Only the transformers that need a field visit - the inspection queue."""
    try:
        days = _days_arg()
        summaries = [
            row
            for row in energy_balance.get_network_summary(days)
            if row["status"] in {"WATCH", "CRITICAL"}
        ]
        return jsonify({"count": len(summaries), "days": days, "transformers": summaries})
    except Exception as exc:
        logger.exception("High-loss transformer lookup failed")
        return jsonify({"error": "Transformer error", "message": str(exc)}), 500


@transformer_bp.get("/transformers/<transformer_id>")
def transformer_detail(transformer_id: str) -> Any:
    """One transformer: summary, daily trend, and the meters under it.

    Each already-predicted meter carries a combined priority score - the ML
    confidence blended with this transformer's loss signal - so the inspection
    team gets a ranked list rather than an undifferentiated pile of alerts.
    """
    try:
        days = _days_arg()
        summary = energy_balance.get_transformer_summary(transformer_id, days)
        if summary is None:
            return jsonify(
                {"error": "Not found", "message": f"Unknown transformer '{transformer_id}'"}
            ), 404

        flagged = []
        for meter in transformer_db.get_flagged_meters_for_transformer(transformer_id):
            confidence = float(meter.get("confidence") or 0.0)
            # Confidence is stored as a percentage in some rows and a fraction in
            # others; normalise to 0-1 before scoring.
            if confidence > 1.0:
                confidence = confidence / 100.0
            meter.update(
                energy_balance.combined_priority(
                    confidence, summary["loss_pct"], summary["persistent"]
                )
            )
            flagged.append(meter)
        flagged.sort(key=lambda row: row["priority_score"], reverse=True)

        return jsonify(
            {
                "summary": summary,
                "trend": energy_balance.get_transformer_trend(transformer_id, days),
                "meters": transformer_db.get_meters_for_transformer(transformer_id),
                "flagged_meters": flagged,
            }
        )
    except Exception as exc:
        logger.exception("Transformer detail lookup failed")
        return jsonify({"error": "Transformer error", "message": str(exc)}), 500


@transformer_bp.get("/transformers/<transformer_id>/trend")
def transformer_trend(transformer_id: str) -> Any:
    """Day-by-day supplied vs billed vs loss% for the detail chart."""
    try:
        days = _days_arg()
        if transformer_db.get_transformer(transformer_id) is None:
            return jsonify(
                {"error": "Not found", "message": f"Unknown transformer '{transformer_id}'"}
            ), 404
        trend = energy_balance.get_transformer_trend(transformer_id, days)
        return jsonify({"transformer_id": transformer_id, "count": len(trend), "trend": trend})
    except Exception as exc:
        logger.exception("Transformer trend lookup failed")
        return jsonify({"error": "Transformer error", "message": str(exc)}), 500


# --------------------------------------------------------------------------- #
# Dataset upload — lets the network come from a CSV instead of the seeder
# --------------------------------------------------------------------------- #
@transformer_bp.get("/transformers/dataset")
def transformer_dataset() -> Any:
    """Where the Network Health figures currently come from.

    Reported honestly as one of: 'upload' (a CSV the user loaded), 'seed'
    (generated by seed_transformers.py) or 'none'. The page shows this, so a
    reviewer can never mistake simulated data for a live feed.
    """
    try:
        return jsonify(transformer_upload.dataset_status())
    except Exception as exc:
        logger.exception("Dataset status failed")
        return jsonify({"error": "Dataset error", "message": str(exc)}), 500


@transformer_bp.post("/transformers/upload")
def upload_transformer_dataset() -> Any:
    """Replace the distribution-network dataset from a CSV.

    Validation happens before anything is written, and the write is one
    transaction: a bad file leaves the previous network exactly as it was rather
    than half-replacing it.
    """
    if "file" not in request.files or request.files["file"].filename == "":
        return jsonify({"error": "Missing file",
                        "message": "Choose a transformer CSV to upload."}), 400

    uploaded = request.files["file"]
    if not uploaded.filename.lower().endswith(".csv"):
        return jsonify({"error": "Invalid file type",
                        "message": "Only .csv files are supported."}), 400

    try:
        parsed = transformer_upload.parse_csv(uploaded)
        result = transformer_upload.replace_dataset(parsed, uploaded.filename)
        # Return the recomputed headline numbers so the page can refresh without
        # a second round trip.
        result["kpis"] = energy_balance.get_network_kpis(30)
        return jsonify(result)
    except transformer_upload.UploadError as exc:
        logger.warning("Transformer upload rejected: %s", exc)
        return jsonify({"error": "Invalid dataset", "message": str(exc)}), 400
    except Exception as exc:
        logger.exception("Transformer upload failed")
        return jsonify({"error": "Upload failed", "message": str(exc)}), 500


@transformer_bp.delete("/transformers/dataset")
def clear_transformer_dataset() -> Any:
    """Remove the uploaded network. Predictions and meter data are untouched."""
    try:
        transformer_upload.clear_dataset()
        return jsonify({"cleared": True,
                        "message": "Network dataset cleared. Prediction history was kept."})
    except Exception as exc:
        logger.exception("Clearing the dataset failed")
        return jsonify({"error": "Dataset error", "message": str(exc)}), 500


@transformer_bp.get("/transformers/template")
def transformer_template() -> Any:
    """A two-row CSV showing the expected format, so nobody has to guess it."""
    sample = (
        transformer_upload.CSV_TEMPLATE_HEADER + "\n"
        "DT-001,Sector 4 DT-1,Sector 4,250,88,2026-07-03,4821.40,4530.12\n"
        "DT-001,Sector 4 DT-1,Sector 4,250,88,2026-07-04,4776.05,4498.88\n"
        "DT-002,Old City DT-2,Old City,160,64,2026-07-03,3910.22,3115.90\n"
    )
    return Response(
        sample,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=transformer_template.csv"},
    )


def register_transformer_routes(app: Flask) -> None:
    """Create the energy-balance tables and register the blueprint."""
    transformer_db.init_transformer_tables()
    app.register_blueprint(transformer_bp)
