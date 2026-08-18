from __future__ import annotations

import logging
import sys
import traceback
from typing import Any

import numpy as np
import shap

from model_loader import IMPUTER, MODEL, SCALER


def log_shap_runtime_state(context: str = "startup") -> None:
    """Log the active Python environment and SHAP installation details."""
    logger = logging.getLogger(__name__)
    try:
        logger.info("%s: sys.executable=%s", context, sys.executable)
        logger.info("%s: shap.__version__=%s", context, getattr(shap, "__version__", "unknown"))
        logger.info("%s: shap.__file__=%s", context, getattr(shap, "__file__", "unknown"))
    except Exception:
        logger.exception("Failed to read SHAP runtime metadata for %s", context)


logger = logging.getLogger(__name__)


class ShapExplainerManager:
    """Manages SHAP TreeExplainer for Random Forest model explanations."""

    def __init__(self):
        """Initialize the SHAP TreeExplainer with the loaded model."""
        log_shap_runtime_state("TreeExplainer init")
        try:
            logger.info("Initializing SHAP TreeExplainer...")
            self.explainer = shap.TreeExplainer(MODEL)
            logger.info("SHAP TreeExplainer initialized successfully")
        except Exception as exc:
            logger.error("Failed to initialize SHAP TreeExplainer: %s", exc)
            logger.error("TreeExplainer traceback:\n%s", traceback.format_exc())
            self.explainer = None
            self.init_error = str(exc)
        else:
            self.init_error = None

    def is_available(self) -> bool:
        """Check if the SHAP explainer is available."""
        return self.explainer is not None

    def explain_prediction(self, scaled_features: np.ndarray, feature_names: list[str] | None = None, top_n: int = 10) -> dict[str, Any]:
        """
        Generate SHAP explanations for a prediction.

        Args:
            scaled_features: The scaled feature array ready for the model.
            feature_names: Optional list of feature names (dates/columns).
            top_n: Number of top contributing features to return (default 10).

        Returns:
            Dictionary with prediction, risk, confidence, and top contributing features.
        """
        if not self.is_available():
            raise ValueError("SHAP explainer is not available")

        try:
            # Ensure input is 2D array
            if scaled_features.ndim == 1:
                scaled_features = scaled_features.reshape(1, -1)

            # Get prediction and probabilities
            predictions = MODEL.predict(scaled_features)
            probabilities = MODEL.predict_proba(scaled_features)

            prediction_value = predictions[0]
            if isinstance(prediction_value, np.generic):
                prediction_value = prediction_value.item()

            is_theft = prediction_value not in (0, False)
            prediction_label = "Theft" if is_theft else "Normal"
            risk_label = "High" if is_theft else "Low"
            confidence = float(np.max(probabilities[0])) * 100

            # Calculate SHAP values
            # For TreeExplainer on binary classification, output is shape (n_samples, n_features, n_classes)
            shap_values = self.explainer.shap_values(scaled_features)

            # Extract SHAP values for the single sample and the predicted class
            # shap_values shape is (1, n_features, n_classes)
            if shap_values.ndim == 3:
                # Binary classification case
                shap_values_for_prediction = shap_values[0, :, int(prediction_value)]
            elif shap_values.ndim == 2:
                # Single class case
                shap_values_for_prediction = shap_values[0, :]
            else:
                raise ValueError(f"Unexpected SHAP values shape: {shap_values.shape}")

            # Get top contributing features (by absolute SHAP value)
            abs_shap_values = np.abs(shap_values_for_prediction)
            top_indices = np.argsort(abs_shap_values)[::-1][:top_n]

            explanation = []
            for idx in top_indices:
                # Get the signed SHAP value
                signed_shap_val = float(shap_values_for_prediction[idx])

                feature_name = feature_names[idx] if feature_names and idx < len(feature_names) else f"feature_{idx}"

                # Determine impact direction
                if signed_shap_val > 0:
                    impact = "positive"
                    direction = "increased_theft_probability" if is_theft else "increased_normal_probability"
                elif signed_shap_val < 0:
                    impact = "negative"
                    direction = "decreased_theft_probability" if is_theft else "decreased_normal_probability"
                else:
                    impact = "neutral"
                    direction = "no_significant_impact"

                explanation.append({
                    "feature": feature_name,
                    "shap_value": round(signed_shap_val, 4),
                    "impact": impact,
                    "direction": direction,
                })

            result = {
                "prediction": prediction_label,
                "risk": risk_label,
                "confidence": round(confidence, 2),
                "explanation": explanation,
            }

            logger.info("SHAP explanation generated successfully for prediction: %s", prediction_label)
            return result

        except Exception as exc:
            logger.exception("Failed to generate SHAP explanation: %s", exc)
            raise ValueError(f"SHAP explanation generation failed: {exc}") from exc


# Initialize the SHAP explainer once at module load time
SHAP_MANAGER = ShapExplainerManager()


def get_shap_manager() -> ShapExplainerManager:
    """Get the global SHAP explainer manager instance."""
    return SHAP_MANAGER
