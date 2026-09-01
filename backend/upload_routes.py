"""API for reading back CSV upload runs.

Its own Blueprint, so routes.py keeps its existing contract untouched. These are
read-only endpoints plus one explicit clear; nothing here re-runs a prediction or
creates a record.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Flask, jsonify, request

import upload_store


logger = logging.getLogger(__name__)
upload_bp = Blueprint("uploads", __name__)


@upload_bp.get("/uploads/latest")
def latest_upload() -> Any:
    """The most recent upload run, with its results.

    This is what the CSV Upload page calls when it mounts. It returns
    `{"batch": null}` rather than a 404 when nothing has been uploaded yet - an
    empty page is a normal state, not an error.
    """
    try:
        batch = upload_store.get_upload(None, include_results=True)
        return jsonify({"batch": batch})
    except Exception as exc:
        logger.exception("Latest upload lookup failed")
        return jsonify({"error": "Upload error", "message": str(exc)}), 500


@upload_bp.get("/uploads")
def list_uploads() -> Any:
    """Recent upload runs, metadata only."""
    try:
        limit = request.args.get("limit", default=10, type=int)
        batches = upload_store.list_uploads(limit)
        return jsonify({"count": len(batches), "batches": batches})
    except Exception as exc:
        logger.exception("Upload listing failed")
        return jsonify({"error": "Upload error", "message": str(exc)}), 500


@upload_bp.get("/uploads/<int:batch_id>")
def one_upload(batch_id: int) -> Any:
    """One specific upload run, with its results."""
    try:
        batch = upload_store.get_upload(batch_id, include_results=True)
        if batch is None:
            return jsonify({"error": "Not found",
                            "message": f"No upload batch with id {batch_id}."}), 404
        return jsonify({"batch": batch})
    except Exception as exc:
        logger.exception("Upload lookup failed")
        return jsonify({"error": "Upload error", "message": str(exc)}), 500


@upload_bp.delete("/uploads")
def clear_uploads() -> Any:
    """Clear the record of past upload runs.

    Deliberately does NOT touch the `predictions` table: the detection history is
    the system's audit record, and a UI action must not be able to erase it.
    """
    try:
        removed = upload_store.clear_uploads()
        return jsonify({"cleared": removed,
                        "message": "Upload history cleared. Prediction records were kept."})
    except Exception as exc:
        logger.exception("Clearing uploads failed")
        return jsonify({"error": "Upload error", "message": str(exc)}), 500


def register_upload_routes(app: Flask) -> None:
    upload_store.init_upload_store()
    app.register_blueprint(upload_bp)
