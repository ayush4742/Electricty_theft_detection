"""API endpoints for meter search and the meter profile.

Own Blueprint, so routes.py stays untouched. Registered from app.py via
register_meter_routes(app).
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Flask, jsonify, request

import meter_profile


logger = logging.getLogger(__name__)
meter_bp = Blueprint("meters", __name__)


@meter_bp.get("/meters/search")
def meter_search() -> Any:
    """Find meters by full or partial id.

    An empty query returns the most recently analysed meters, so the page has
    something useful in it before the user types anything.
    """
    try:
        query = request.args.get("q", default="", type=str)
        limit = request.args.get("limit", default=20, type=int)
        results = meter_profile.search_meters(query, limit)
        return jsonify({"query": query, "count": len(results), "meters": results})
    except Exception as exc:
        logger.exception("Meter search failed")
        return jsonify({"error": "Search error", "message": str(exc)}), 500


@meter_bp.get("/meters/<meter_id>")
def meter_detail(meter_id: str) -> Any:
    """Everything stored about one meter, assembled from the uploaded data."""
    try:
        full = request.args.get("full", default=0, type=int) == 1
        profile = meter_profile.get_meter_profile(meter_id, include_full_series=full)
        if profile is None:
            return jsonify(
                {
                    "error": "Not found",
                    "message": (
                        f"Meter '{meter_id}' is not in the prediction history. "
                        "Upload a CSV containing this meter to analyse it."
                    ),
                }
            ), 404
        return jsonify(profile)
    except Exception as exc:
        logger.exception("Meter profile failed")
        return jsonify({"error": "Meter error", "message": str(exc)}), 500


def register_meter_routes(app: Flask) -> None:
    """Register the meter search blueprint."""
    app.register_blueprint(meter_bp)
