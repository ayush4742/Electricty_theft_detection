from __future__ import annotations

from typing import Any

import joblib

from config import IMPUTER_PATH, MODEL_PATH, SCALER_PATH


def load_artifacts() -> dict[str, Any]:
    """Load the trained model and preprocessing artifacts once at startup."""
    return {
        "model": joblib.load(MODEL_PATH),
        "scaler": joblib.load(SCALER_PATH),
        "imputer": joblib.load(IMPUTER_PATH),
    }


ARTIFACTS = load_artifacts()
MODEL = ARTIFACTS["model"]
SCALER = ARTIFACTS["scaler"]
IMPUTER = ARTIFACTS["imputer"]


def get_model_info() -> dict[str, Any]:
    """Return a small summary of the loaded model for the /model-info endpoint."""
    model_name = MODEL.__class__.__name__
    if "RandomForest" in model_name:
        model_name = "Random Forest"

    return {
        "model": model_name,
        "total_features": getattr(MODEL, "n_features_in_", None),
        "status": "Loaded",
    }
