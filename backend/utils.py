from __future__ import annotations

import logging
import sys
import time
import traceback
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from database import save_prediction
from model_loader import IMPUTER, MODEL, SCALER
from notification_service import get_settings, scrub, send_batch_summary, send_theft_alert


logger = logging.getLogger(__name__)

# Import SHAP explainer lazily to avoid errors if SHAP is not installed
try:
    import shap
    from shap_explainer import get_shap_manager

    SHAP_AVAILABLE = True
    logger.info("SHAP import succeeded: sys.executable=%s", sys.executable)
    logger.info("SHAP import succeeded: shap.__version__=%s", getattr(shap, "__version__", "unknown"))
    logger.info("SHAP import succeeded: shap.__file__=%s", getattr(shap, "__file__", "unknown"))
except Exception as exc:
    SHAP_AVAILABLE = False
    logger.exception("SHAP import failed in utils.py; sys.executable=%s", sys.executable)
    logger.error("SHAP import traceback:\n%s", traceback.format_exc())
    logger.warning("SHAP not available; explain endpoint will not function. Original error: %s", exc)


def _no_alert(reason: str) -> dict[str, Any]:
    """Default alert fields for rows that were never considered for an SMS."""
    return {"alert_sent": False, "alert_error": None, "alert_skipped": reason}


def _build_response(prediction_value: Any, confidence: float, timestamp: str, meter_id: str | None = None) -> dict[str, Any]:
    """Create a consistent JSON response for prediction results."""
    is_theft = prediction_value not in (0, False)
    prediction_label = "Theft" if is_theft else "Normal"
    risk_label = "High" if is_theft else "Low"
    reason = (
        "Abnormal electricity consumption pattern detected."
        if is_theft
        else "Consumption pattern appears normal."
    )

    response = {
        "prediction": prediction_label,
        "risk": risk_label,
        "confidence": round(float(confidence), 2),
        "reason": reason,
        "timestamp": timestamp,
    }

    if meter_id is not None:
        response["meter_id"] = meter_id

    return response


def validate_readings(readings: Any) -> np.ndarray:
    """Validate the JSON list input and convert it into a NumPy array."""
    if not isinstance(readings, list):
        raise ValueError("The 'readings' field must be a list of numbers.")

    if len(readings) == 0:
        raise ValueError("The 'readings' list cannot be empty.")

    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in readings):
        raise ValueError("All values in 'readings' must be numeric.")

    numeric_values = np.asarray(readings, dtype=float)
    if np.isnan(numeric_values).any():
        raise ValueError("The 'readings' array contains NaN values.")

    return numeric_values.reshape(1, -1)


def validate_feature_matrix(features: np.ndarray) -> np.ndarray:
    """Ensure the feature matrix has the correct number of features for the loaded model."""
    features_array = np.asarray(features, dtype=float)

    if features_array.ndim == 1:
        features_array = features_array.reshape(1, -1)

    expected_features = getattr(MODEL, "n_features_in_", None)
    if expected_features is not None and features_array.shape[1] != expected_features:
        raise ValueError(f"Expected {expected_features} features but found {features_array.shape[1]} features.")

    logger.info("Feature matrix validated successfully; shape=%s", features_array.shape)
    return features_array


def predict_from_features(
    features: np.ndarray,
    meter_id: str | None = None,
    store_history: bool = True,
    send_alert: bool = True,
) -> dict[str, Any]:
    """Apply imputation, scaling, and model prediction to a single feature vector."""
    validated_features = validate_feature_matrix(features)
    start_time = time.perf_counter()
    imputed_features = IMPUTER.transform(validated_features)
    logger.info("Imputation completed in %.3f seconds", time.perf_counter() - start_time)

    start_time = time.perf_counter()
    scaled_features = SCALER.transform(imputed_features)
    logger.info("Scaling completed in %.3f seconds", time.perf_counter() - start_time)

    start_time = time.perf_counter()
    predictions = MODEL.predict(scaled_features)
    probabilities = MODEL.predict_proba(scaled_features)
    logger.info("Prediction completed in %.3f seconds", time.perf_counter() - start_time)

    probabilities = np.atleast_2d(probabilities)

    prediction_value = predictions[0]
    if isinstance(prediction_value, np.generic):
        prediction_value = prediction_value.item()

    confidence = float(np.max(probabilities[0])) * 100
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response = _build_response(prediction_value, confidence, timestamp, meter_id=meter_id)

    if store_history:
        save_prediction(
            meter_id=meter_id,
            prediction=response["prediction"],
            confidence=response["confidence"],
            risk=response["risk"],
            timestamp=timestamp,
            features=features,
        )

    # --- SMS alerting -------------------------------------------------------
    # Runs only after the prediction is complete and safely stored. Theft only,
    # never for Normal, and wrapped so that no SMS problem can affect the
    # prediction response the caller receives.
    if response["prediction"] == "Theft" and send_alert:
        response.update(
            send_theft_alert(
                meter_id=meter_id,
                confidence=response["confidence"],
                timestamp=timestamp,
                risk=response["risk"],
            )
        )
    else:
        response.update(_no_alert("normal_prediction" if response["prediction"] != "Theft" else "alerting_skipped"))

    return response


def prepare_csv_features(uploaded_file: Any) -> tuple[pd.DataFrame, list[Any]]:
    """Read, clean, and validate an uploaded CSV file for model inference."""
    logger.info(
        "CSV upload received: filename=%s content_type=%s",
        getattr(uploaded_file, "filename", None),
        getattr(uploaded_file, "content_type", None),
    )

    start_time = time.perf_counter()
    try:
        uploaded_file.stream.seek(0)
        dataframe = pd.read_csv(
            uploaded_file.stream,
            encoding="utf-8-sig",
            sep=None,
            engine="python",
        )
    except Exception as exc:
        logger.exception("Failed to read uploaded CSV")
        raise ValueError(f"Could not read CSV file: {exc}") from exc
    logger.info("CSV reading completed in %.3f seconds", time.perf_counter() - start_time)

    logger.info("Original CSV shape: %s", dataframe.shape)
    logger.info("Original CSV columns: %s", list(dataframe.columns))

    if dataframe.empty:
        raise ValueError("The uploaded CSV file is empty.")

    def is_metadata_column(column_name: str) -> bool:
        normalized_name = str(column_name).strip().lower()
        return normalized_name in {"cons_no", "flag", "index"} or normalized_name.startswith("unnamed") or normalized_name == ""

    start_time = time.perf_counter()
    drop_columns = [column for column in dataframe.columns if is_metadata_column(column)]
    cleaned_dataframe = dataframe.drop(columns=drop_columns, errors="ignore")
    logger.info("Preprocessing completed in %.3f seconds", time.perf_counter() - start_time)

    logger.info("Columns removed during preprocessing: %s", drop_columns or "none")
    logger.info("Shape after dropping metadata columns: %s", cleaned_dataframe.shape)
    logger.info("Remaining feature columns: %s", list(cleaned_dataframe.columns))
    logger.info("Number of remaining feature columns: %s", cleaned_dataframe.shape[1])

    if cleaned_dataframe.shape[1] == 0:
        raise ValueError("No usable feature columns remain after cleaning the uploaded CSV.")

    expected_features = getattr(MODEL, "n_features_in_", None)
    if expected_features is not None and cleaned_dataframe.shape[1] != expected_features:
        raise ValueError(f"Expected {expected_features} features but found {cleaned_dataframe.shape[1]} features.")

    start_time = time.perf_counter()
    numeric_dataframe = cleaned_dataframe.apply(pd.to_numeric, errors="coerce")
    logger.info("Numeric conversion completed in %.3f seconds", time.perf_counter() - start_time)
    logger.info("CSV shape after numeric conversion: %s", numeric_dataframe.shape)

    if numeric_dataframe.shape[1] == 0:
        raise ValueError("No numeric feature columns were found in the uploaded CSV.")

    meter_ids: list[Any] = []
    for column in dataframe.columns:
        normalized_name = str(column).strip().lower()
        if normalized_name == "cons_no":
            meter_ids = dataframe[column].fillna("N/A").astype(str).tolist()
            break

    logger.info("Meter IDs extracted count=%s", len(meter_ids))
    return numeric_dataframe, meter_ids


def predict_from_csv(dataframe: pd.DataFrame, meter_ids: list[Any] | None = None, batch_size: int = 1000) -> list[dict[str, Any]]:
    """Run predictions for every row in a cleaned CSV DataFrame using batched inference."""
    if dataframe.empty:
        raise ValueError("The uploaded CSV file is empty.")

    feature_matrix = dataframe.to_numpy(dtype=float, copy=False)
    logger.info("Feature matrix shape before model prediction: %s", feature_matrix.shape)
    feature_matrix = validate_feature_matrix(feature_matrix)

    results: list[dict[str, Any]] = []
    total_rows = feature_matrix.shape[0]

    start_time = time.perf_counter()
    for start_index in range(0, total_rows, batch_size):
        end_index = min(start_index + batch_size, total_rows)
        batch = feature_matrix[start_index:end_index]
        batch_meter_ids = meter_ids[start_index:end_index] if meter_ids else None

        batch_start = time.perf_counter()
        imputed_batch = IMPUTER.transform(batch)
        logger.info("Imputation batch %s-%s completed in %.3f seconds", start_index, end_index, time.perf_counter() - batch_start)

        batch_start = time.perf_counter()
        scaled_batch = SCALER.transform(imputed_batch)
        logger.info("Scaling batch %s-%s completed in %.3f seconds", start_index, end_index, time.perf_counter() - batch_start)

        batch_start = time.perf_counter()
        predictions = MODEL.predict(scaled_batch)
        probabilities = MODEL.predict_proba(scaled_batch)
        logger.info("Prediction batch %s-%s completed in %.3f seconds", start_index, end_index, time.perf_counter() - batch_start)

        for offset, prediction_value in enumerate(predictions):
            meter_id = batch_meter_ids[offset] if batch_meter_ids else None
            confidence = float(np.max(probabilities[offset])) * 100
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            response = _build_response(prediction_value, confidence, timestamp, meter_id=meter_id)
            results.append(response)
            # Extract the raw features for this row
            row_features = feature_matrix[start_index + offset]
            save_prediction(
                meter_id=meter_id,
                prediction=response["prediction"],
                confidence=response["confidence"],
                risk=response["risk"],
                timestamp=timestamp,
                features=row_features,
            )

    logger.info("Batch prediction completed in %.3f seconds for %s rows", time.perf_counter() - start_time, total_rows)
    return results


<<<<<<< HEAD
def dispatch_batch_alerts(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Send SMS alerts for a completed CSV run.

    Called by the /predict-csv route *after* every row has been predicted and
    stored, so alerting never slows down or endangers inference.

    Spam control has three layers:
      1. Normal rows are ignored entirely.
      2. Only the MAX_ALERTS_PER_BATCH highest-confidence theft meters get an
         individual SMS. The rest are marked 'batch_limit'.
      3. Each individual alert still passes through the per-meter cooldown.
    Finally one summary SMS reports the totals for the whole upload.

    Mutates `results` in place with alert_sent / alert_error / alert_skipped and
    returns a summary dict. Never raises.
    """
    summary: dict[str, Any] = {
        "theft_count": 0,
        "alerts_attempted": 0,
        "alerts_sent": 0,
        "alerts_failed": 0,
        "alerts_suppressed": 0,
        "summary_sms_sent": False,
        "alert_error": None,
    }

    try:
        for result in results:
            result.setdefault("alert_sent", False)
            result.setdefault("alert_error", None)
            result.setdefault("alert_skipped", None)

        theft_rows = [result for result in results if result.get("prediction") == "Theft"]
        summary["theft_count"] = len(theft_rows)

        for result in results:
            if result.get("prediction") != "Theft":
                result["alert_skipped"] = "normal_prediction"

        if not theft_rows:
            logger.info("[SMS] No theft rows in this upload; no alerts sent")
            return summary

        settings = get_settings()

        if not settings.enabled:
            for result in theft_rows:
                result["alert_skipped"] = "alerts_disabled"
            summary["alerts_suppressed"] = len(theft_rows)
            logger.info("[SMS] Alerting is disabled; %s theft row(s) not alerted", len(theft_rows))
            return summary

        ranked = sorted(theft_rows, key=lambda item: float(item.get("confidence") or 0.0), reverse=True)
        limit = max(0, settings.max_alerts_per_batch)
        to_alert = ranked[:limit]
        suppressed = ranked[limit:]

        for result in suppressed:
            result["alert_skipped"] = "batch_limit"
        summary["alerts_suppressed"] = len(suppressed)

        if suppressed:
            logger.info(
                "[SMS] %s theft meter(s) exceeded MAX_ALERTS_PER_BATCH=%s and were summarised instead of texted",
                len(suppressed),
                limit,
            )

        for result in to_alert:
            summary["alerts_attempted"] += 1
            outcome = send_theft_alert(
                meter_id=result.get("meter_id"),
                confidence=result.get("confidence") or 0.0,
                timestamp=result.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                risk=result.get("risk") or "High",
            )
            result.update(outcome)
            if outcome["alert_sent"]:
                summary["alerts_sent"] += 1
            elif outcome["alert_error"]:
                summary["alerts_failed"] += 1
                summary["alert_error"] = summary["alert_error"] or outcome["alert_error"]
            else:
                summary["alerts_suppressed"] += 1

        summary_outcome = send_batch_summary(
            total_rows=len(results),
            theft_count=summary["theft_count"],
            alerted_count=summary["alerts_sent"],
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        summary["summary_sms_sent"] = summary_outcome["alert_sent"]
        if summary_outcome["alert_error"]:
            summary["alert_error"] = summary["alert_error"] or summary_outcome["alert_error"]

    except Exception as exc:  # alerting must never break a completed prediction
        message = scrub(f"Unexpected SMS failure: {exc}")
        logger.error("[SMS] Batch alert dispatch failed: %s", message)
        summary["alert_error"] = message

    return summary
=======
def explain_from_features(features: np.ndarray, feature_names: list[str] | None = None, top_n: int = 10) -> dict[str, Any]:
    """
    Generate SHAP explanations for a prediction.

    Args:
        features: Raw feature array (will be imputed and scaled).
        feature_names: Optional list of feature names from the CSV columns.
        top_n: Number of top contributing features to return.

    Returns:
        Dictionary with prediction, risk, confidence, and explanation.
    """
    logger.info("explain_from_features called: sys.executable=%s top_n=%s input_shape=%s", sys.executable, top_n, np.asarray(features).shape)
    if not SHAP_AVAILABLE:
        logger.error("SHAP is unavailable at runtime: sys.executable=%s", sys.executable)
        raise ValueError(
            "SHAP is not available in the active Flask environment. "
            "This app is running under a Python interpreter without the shap package installed. "
            f"sys.executable={sys.executable}"
        )

    # Validate and preprocess features (same as predict_from_features)
    validated_features = validate_feature_matrix(features)
    start_time = time.perf_counter()
    imputed_features = IMPUTER.transform(validated_features)
    logger.info("Imputation completed in %.3f seconds", time.perf_counter() - start_time)

    start_time = time.perf_counter()
    scaled_features = SCALER.transform(imputed_features)
    logger.info("Scaling completed in %.3f seconds", time.perf_counter() - start_time)

    # Get feature names from the input features if not provided
    if feature_names is None:
        feature_names = [f"feature_{i}" for i in range(validated_features.shape[1])]

    # Get SHAP explanation
    shap_manager = get_shap_manager()
    logger.info("SHAP manager resolved: %s", type(shap_manager).__name__)
    if not shap_manager.is_available():
        logger.error("SHAP manager exists but TreeExplainer is not initialized: sys.executable=%s", sys.executable)
        if hasattr(shap_manager, "init_error"):
            logger.error("TreeExplainer init error: %s", shap_manager.init_error)
        raise ValueError(
            "SHAP explainer is not initialized in the active Flask environment. "
            f"sys.executable={sys.executable}"
        )

    start_time = time.perf_counter()
    explanation_result = shap_manager.explain_prediction(scaled_features, feature_names=feature_names, top_n=top_n)
    logger.info("SHAP explanation generated in %.3f seconds", time.perf_counter() - start_time)

    return explanation_result

>>>>>>> origin/main
