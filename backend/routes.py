from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from flask import Blueprint, Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from database import get_alert_counts, get_alert_history, get_dashboard_stats, get_prediction_history
from model_loader import get_model_info
from notification_service import get_alert_status, send_test_alert
from utils import (
    dispatch_batch_alerts,
    predict_from_csv,
    predict_from_features,
    prepare_csv_features,
    validate_readings,
)


logger = logging.getLogger(__name__)
bp = Blueprint("main", __name__)


@bp.errorhandler(HTTPException)
def handle_http_error(error: HTTPException):
    """Return clean JSON responses for invalid HTTP requests."""
    return jsonify({"error": error.name, "message": error.description or "Request could not be processed."}), error.code


@bp.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    """Catch unexpected errors and return a user-friendly JSON response."""
    logger.exception("Unhandled exception occurred", exc_info=error)
    return jsonify({"error": "Internal server error", "message": "An unexpected error occurred while processing your request."}), 500


@bp.get("/")
def health_check() -> Any:
    """Home endpoint for the API service."""
    return jsonify({"status": "running", "message": "Electricity Theft Detection API"})


@bp.post("/predict")
def predict_json() -> Any:
    """Accept JSON readings and return a single prediction response."""
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid request", "message": "Request body must be a JSON object."}), 400

    if "readings" not in payload:
        return jsonify({"error": "Missing field", "message": "JSON body must contain a 'readings' array."}), 400

    meter_id = payload.get("meter_id")
    if meter_id is not None and not isinstance(meter_id, str):
        return jsonify({"error": "Invalid input", "message": "The 'meter_id' field must be a string when provided."}), 400

    try:
        features = validate_readings(payload["readings"])
        result = predict_from_features(features, meter_id=meter_id)
        return jsonify(result)
    except ValueError as exc:
        logger.warning("Prediction validation failed: %s", exc)
        return jsonify({"error": "Invalid input", "message": str(exc)}), 400
    except Exception as exc:
        logger.exception("JSON prediction failed")
        return jsonify({"error": "Prediction failed", "message": f"Unable to process the provided readings: {exc}"}), 500


@bp.post("/predict-csv")
def predict_csv() -> Any:
    """Accept a CSV upload and return prediction results for each row."""
    if "file" not in request.files or request.files["file"].filename == "":
        return jsonify({"error": "Missing file", "message": "Please upload a CSV file."}), 400

    uploaded_file = request.files["file"]
    logger.info("Route /predict-csv received file: %s", uploaded_file.filename)
    if not uploaded_file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Invalid file type", "message": "Only CSV files are supported."}), 400

    try:
        dataframe, meter_ids = prepare_csv_features(uploaded_file)
        results = predict_from_csv(dataframe, meter_ids=meter_ids)
        logger.info("CSV prediction completed successfully")

        # Alerts are dispatched only after every row is predicted and stored,
        # so SMS problems can never affect the prediction results below.
        alert_summary = dispatch_batch_alerts(results)

        return jsonify(
            {
                "total_predictions": len(results),
                "results": results,
                "alert_summary": alert_summary,
            }
        )
    except ValueError as exc:
        logger.warning("CSV prediction validation failed: %s", exc)
        return jsonify({"error": "Invalid input", "message": str(exc)}), 400
    except Exception as exc:
        logger.exception("CSV prediction failed")
        return jsonify({"error": "Prediction failed", "message": str(exc)}), 500


@bp.get("/history")
def history() -> Any:
    """Return the most recent stored predictions from the local SQLite database."""
    try:
        history_entries = get_prediction_history(limit=100)
        return jsonify({"count": len(history_entries), "history": history_entries})
    except Exception as exc:
        logger.exception("History retrieval failed")
        return jsonify({"error": "History error", "message": str(exc)}), 500


@bp.get("/dashboard")
def dashboard() -> Any:
    """Return live dashboard statistics derived from the prediction database."""
    try:
        return jsonify(get_dashboard_stats())
    except Exception as exc:
        logger.exception("Dashboard retrieval failed")
        return jsonify({"error": "Dashboard error", "message": str(exc)}), 500


@bp.get("/model-info")
def model_info() -> Any:
    """Return basic information about the loaded machine-learning model."""
    return jsonify(get_model_info())


# --------------------------------------------------------------------------- #
# SMS alerting endpoints
# --------------------------------------------------------------------------- #
@bp.get("/alert-status")
def alert_status() -> Any:
    """Report SMS configuration health.

    Returns booleans and counts only. No tokens, no account SIDs and no phone
    numbers are ever included in this response.
    """
    try:
        status = get_alert_status()
        status["counts"] = get_alert_counts()
        return jsonify(status)
    except Exception as exc:
        logger.exception("Alert status retrieval failed")
        return jsonify({"error": "Alert status error", "message": str(exc)}), 500


@bp.get("/alert-history")
def alert_history() -> Any:
    """Return recent SMS alert attempts (no recipient numbers are stored)."""
    try:
        entries = get_alert_history(limit=50)
        return jsonify({"count": len(entries), "alerts": entries})
    except Exception as exc:
        logger.exception("Alert history retrieval failed")
        return jsonify({"error": "Alert history error", "message": str(exc)}), 500


@bp.post("/test-alert")
def test_alert() -> Any:
    """Send a test SMS without needing a real theft prediction.

    Protected two ways so it cannot be used to spam messages:
      1. ALERT_TEST_TOKEN must be set on the server and supplied by the caller
         via the X-Alert-Token header (or a 'token' field in the JSON body).
      2. TEST_ALERT_COOLDOWN_SECONDS throttles repeat calls.
    """
    payload = request.get_json(silent=True) or {}
    token = request.headers.get("X-Alert-Token") or payload.get("token")

    result = send_test_alert(token=token, timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    status_code = int(result.pop("status_code", 200))
    return jsonify(result), status_code


def register_routes(app: Flask) -> None:
    """Register the API blueprints inside the Flask application."""
    app.register_blueprint(bp)
