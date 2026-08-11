from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from database import save_prediction
from model_loader import IMPUTER, MODEL, SCALER


logger = logging.getLogger(__name__)


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


def predict_from_features(features: np.ndarray, meter_id: str | None = None, store_history: bool = True) -> dict[str, Any]:
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
        )

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
            save_prediction(
                meter_id=meter_id,
                prediction=response["prediction"],
                confidence=response["confidence"],
                risk=response["risk"],
                timestamp=timestamp,
            )

    logger.info("Batch prediction completed in %.3f seconds for %s rows", time.perf_counter() - start_time, total_rows)
    return results
