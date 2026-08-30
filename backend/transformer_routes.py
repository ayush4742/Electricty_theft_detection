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

from flask import Blueprint, Flask, jsonify, request

import energy_balance
import transformer_db


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


def register_transformer_routes(app: Flask) -> None:
    """Create the energy-balance tables and register the blueprint."""
    transformer_db.init_transformer_tables()
    app.register_blueprint(transformer_bp)
