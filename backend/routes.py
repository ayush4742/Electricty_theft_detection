from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime
from typing import Any

import numpy as np
from flask import Blueprint, Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from database import (
    get_alert_counts,
    get_alert_history,
    get_dashboard_stats,
    get_prediction_history,
    get_prediction_by_id,
)
from model_loader import get_model_info
from notification_service import get_alert_status, send_test_alert
from utils import (
    dispatch_batch_alerts,
    explain_from_features,
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
    return jsonify({
        "error": error.name,
        "message": error.description or "Request could not be processed.",
    }), error.code


@bp.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    """Catch unexpected errors and return a user-friendly JSON response."""
    logger.exception("Unhandled exception occurred", exc_info=error)
    return jsonify({
        "error": "Internal server error",
        "message": "An unexpected error occurred while processing your request.",
    }), 500


@bp.get("/")
def health_check() -> Any:
    """Home endpoint for the API service."""
    return jsonify({
        "status": "running",
        "message": "Electricity Theft Detection API",
    })


@bp.post("/predict")
def predict_json() -> Any:
    """Accept JSON readings and return a single prediction response."""
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "Invalid request",
            "message": "Request body must be a JSON object.",
        }), 400

    if "readings" not in payload:
        return jsonify({
            "error": "Missing field",
            "message": "JSON body must contain a 'readings' array.",
        }), 400

    meter_id = payload.get("meter_id")

    if meter_id is not None and not isinstance(meter_id, str):
        return jsonify({
            "error": "Invalid input",
            "message": "The 'meter_id' field must be a string when provided.",
        }), 400

    try:
        features = validate_readings(payload["readings"])
        result = predict_from_features(features, meter_id=meter_id)
        return jsonify(result)

    except ValueError as exc:
        logger.warning("Prediction validation failed: %s", exc)
        return jsonify({
            "error": "Invalid input",
            "message": str(exc),
        }), 400

    except Exception as exc:
        logger.exception("JSON prediction failed")
        return jsonify({
            "error": "Prediction failed",
            "message": f"Unable to process the provided readings: {exc}",
        }), 500


@bp.post("/predict-csv")
def predict_csv() -> Any:
    """Accept a CSV upload and return prediction results for each row."""
    if "file" not in request.files or request.files["file"].filename == "":
        return jsonify({
            "error": "Missing file",
            "message": "Please upload a CSV file.",
        }), 400

    uploaded_file = request.files["file"]

    logger.info(
        "Route /predict-csv received file: %s",
        uploaded_file.filename,
    )

    if not uploaded_file.filename.lower().endswith(".csv"):
        return jsonify({
            "error": "Invalid file type",
            "message": "Only CSV files are supported.",
        }), 400

    try:
        dataframe, meter_ids = prepare_csv_features(uploaded_file)
        results = predict_from_csv(dataframe, meter_ids=meter_ids)

        logger.info("CSV prediction completed successfully")

        # SMS alerts are dispatched only after predictions are completed
        # and stored. Notification failures must never break prediction.
        alert_summary = dispatch_batch_alerts(results)

        return jsonify({
            "total_predictions": len(results),
            "results": results,
            "alert_summary": alert_summary,
        })

    except ValueError as exc:
        logger.warning("CSV prediction validation failed: %s", exc)
        return jsonify({
            "error": "Invalid input",
            "message": str(exc),
        }), 400

    except Exception as exc:
        logger.exception("CSV prediction failed")
        return jsonify({
            "error": "Prediction failed",
            "message": str(exc),
        }), 500


@bp.get("/history")
def history() -> Any:
    """Return the most recent stored predictions from SQLite."""
    try:
        history_entries = get_prediction_history(limit=100)

        return jsonify({
            "count": len(history_entries),
            "history": history_entries,
        })

    except Exception as exc:
        logger.exception("History retrieval failed")
        return jsonify({
            "error": "History error",
            "message": str(exc),
        }), 500


@bp.get("/dashboard")
def dashboard() -> Any:
    """Return live dashboard statistics."""
    try:
        return jsonify(get_dashboard_stats())

    except Exception as exc:
        logger.exception("Dashboard retrieval failed")
        return jsonify({
            "error": "Dashboard error",
            "message": str(exc),
        }), 500


@bp.get("/model-info")
def model_info() -> Any:
    """Return basic information about the ML model."""
    return jsonify(get_model_info())


# --------------------------------------------------------------------------- #
# SHAP EXPLAINABILITY
# --------------------------------------------------------------------------- #

@bp.post("/explain")
def explain_prediction() -> Any:
    """Generate SHAP explanations for a single prediction."""
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "Invalid request",
            "message": "Request body must be a JSON object.",
        }), 400

    if "readings" not in payload:
        return jsonify({
            "error": "Missing field",
            "message": "JSON body must contain a 'readings' array.",
        }), 400

    feature_names = payload.get("feature_names")

    if feature_names is not None and not isinstance(feature_names, list):
        return jsonify({
            "error": "Invalid input",
            "message": "The 'feature_names' field must be a list when provided.",
        }), 400

    top_n = payload.get("top_n", 10)

    if not isinstance(top_n, int) or top_n < 1:
        return jsonify({
            "error": "Invalid input",
            "message": "The 'top_n' field must be a positive integer.",
        }), 400

    try:
        features = validate_readings(payload["readings"])

        explanation = explain_from_features(
            features,
            feature_names=feature_names,
            top_n=top_n,
        )

        return jsonify(explanation)

    except ValueError as exc:
        logger.warning("Explanation validation failed: %s", exc)

        return jsonify({
            "error": "Invalid input",
            "message": str(exc),
        }), 400

    except Exception as exc:
        logger.exception("Explanation generation failed")

        return jsonify({
            "error": "Explanation failed",
            "message": f"Unable to generate explanation: {exc}",
        }), 500


@bp.get("/history/<int:prediction_id>/explain")
def explain_from_history(prediction_id: int) -> Any:
    """Generate SHAP explanation for a prediction stored in history."""
    top_n = request.args.get("top_n", 10, type=int)

    logger.info(
        "History explain request: prediction_id=%s top_n=%s sys.executable=%s",
        prediction_id,
        top_n,
        sys.executable,
    )

    if top_n < 1:
        return jsonify({
            "error": "Invalid input",
            "message": "The 'top_n' parameter must be a positive integer.",
        }), 400

    try:
        prediction = get_prediction_by_id(prediction_id)

        if not prediction:
            return jsonify({
                "error": "Not found",
                "message": f"Prediction with ID {prediction_id} not found.",
            }), 404

        if not prediction.get("features"):
            return jsonify({
                "error": "No features",
                "message": "Features not available for this prediction. Cannot generate explanation.",
            }), 400

        features = np.array(
            prediction["features"]
        ).reshape(1, -1)

        logger.info(
            "History explain feature vector loaded: shape=%s",
            features.shape,
        )

        explanation = explain_from_features(
            features,
            feature_names=None,
            top_n=top_n,
        )

        return jsonify(explanation)

    except ValueError as exc:
        logger.warning("Explanation validation failed: %s", exc)

        return jsonify({
            "error": "Invalid input",
            "message": str(exc),
        }), 400

    except Exception as exc:
        logger.exception("Explanation from history failed")
        logger.error(
            "History explain traceback:\n%s",
            traceback.format_exc(),
        )

        return jsonify({
            "error": "Explanation failed",
            "message": f"Unable to generate explanation: {exc}",
        }), 500


# --------------------------------------------------------------------------- #
# SMS ALERTING
# --------------------------------------------------------------------------- #

@bp.get("/alert-status")
def alert_status() -> Any:
    """Report SMS configuration health."""
    try:
        status = get_alert_status()
        status["counts"] = get_alert_counts()

        return jsonify(status)

    except Exception as exc:
        logger.exception("Alert status retrieval failed")

        return jsonify({
            "error": "Alert status error",
            "message": str(exc),
        }), 500


@bp.get("/alert-history")
def alert_history() -> Any:
    """Return recent SMS alert attempts."""
    try:
        entries = get_alert_history(limit=50)

        return jsonify({
            "count": len(entries),
            "alerts": entries,
        })

    except Exception as exc:
        logger.exception("Alert history retrieval failed")

        return jsonify({
            "error": "Alert history error",
            "message": str(exc),
        }), 500


@bp.post("/test-alert")
def test_alert() -> Any:
    """Send a test SMS."""
    payload = request.get_json(silent=True) or {}

    token = (
        request.headers.get("X-Alert-Token")
        or payload.get("token")
    )

    result = send_test_alert(
        token=token,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    status_code = int(
        result.pop("status_code", 200)
    )

    return jsonify(result), status_code


def register_routes(app: Flask) -> None:
    """Register the API blueprints inside the Flask application."""
    app.register_blueprint(bp)