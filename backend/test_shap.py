"""
Test suite for SHAP integration.

Run with: python -m pytest test_shap.py -v
or: python test_shap.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app import app
from model_loader import IMPUTER, MODEL, SCALER
from shap_explainer import SHAP_MANAGER
from utils import explain_from_features, predict_from_features, validate_readings


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestSHAPIntegration:
    """Test SHAP integration with the existing model."""

    @staticmethod
    def test_shap_manager_available():
        """Test that SHAP manager is initialized."""
        assert SHAP_MANAGER is not None, "SHAP manager not initialized"
        assert SHAP_MANAGER.is_available(), "SHAP explainer not available"
        print("[OK] SHAP manager is available")

    @staticmethod
    def test_model_loaded():
        """Test that the Random Forest model is loaded."""
        assert MODEL is not None, "Model not loaded"
        assert hasattr(MODEL, "n_features_in_"), "Model missing n_features_in_"
        expected_features = MODEL.n_features_in_
        assert expected_features == 1034, f"Expected 1034 features, got {expected_features}"
        print(f"[OK] Model loaded with {expected_features} features")

    @staticmethod
    def test_preprocessing_loaded():
        """Test that imputer and scaler are loaded."""
        assert IMPUTER is not None, "Imputer not loaded"
        assert SCALER is not None, "Scaler not loaded"
        print("[OK] Imputer and scaler loaded")

    @staticmethod
    def test_predict_endpoint():
        """Test the /predict endpoint."""
        client = app.test_client()
        readings = [50.0] * 1034  # Create a sample with 1034 features

        response = client.post(
            "/predict",
            data=json.dumps({"readings": readings}),
            content_type="application/json",
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data}"
        data = json.loads(response.data)
        assert "prediction" in data, "Missing 'prediction' in response"
        assert "confidence" in data, "Missing 'confidence' in response"
        assert "risk" in data, "Missing 'risk' in response"
        print("[OK] /predict endpoint works")

    @staticmethod
    def test_explain_endpoint():
        """Test the /explain endpoint."""
        client = app.test_client()
        readings = [50.0] * 1034  # Create a sample with 1034 features

        response = client.post(
            "/explain",
            data=json.dumps({"readings": readings}),
            content_type="application/json",
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data}"
        data = json.loads(response.data)
        assert "prediction" in data, "Missing 'prediction' in response"
        assert "confidence" in data, "Missing 'confidence' in response"
        assert "risk" in data, "Missing 'risk' in response"
        assert "explanation" in data, "Missing 'explanation' in response"
        assert isinstance(data["explanation"], list), "Explanation should be a list"
        assert len(data["explanation"]) > 0, "Explanation should contain features"
        assert len(data["explanation"]) <= 10, "Explanation should contain max 10 features by default"

        # Check structure of each explanation feature
        for feature in data["explanation"]:
            assert "feature" in feature, "Missing 'feature' in explanation"
            assert "shap_value" in feature, "Missing 'shap_value' in explanation"
            assert "impact" in feature, "Missing 'impact' in explanation"
            assert "direction" in feature, "Missing 'direction' in explanation"
            assert feature["impact"] in ["positive", "negative", "neutral"], "Invalid impact value"

        print(f"[OK] /explain endpoint works and returns {len(data['explanation'])} features")

    @staticmethod
    def test_explain_with_feature_names():
        """Test the /explain endpoint with custom feature names."""
        client = app.test_client()
        readings = [50.0] * 1034
        feature_names = [f"2016/05/{i%30+1:02d}" for i in range(1034)]

        response = client.post(
            "/explain",
            data=json.dumps({"readings": readings, "feature_names": feature_names}),
            content_type="application/json",
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data}"
        data = json.loads(response.data)
        assert "explanation" in data

        # Verify that feature names from the custom list are used
        for feature in data["explanation"]:
            assert feature["feature"] in feature_names or feature["feature"].startswith("feature_"), "Feature name not in provided list"

        print("[OK] /explain endpoint works with custom feature names")

    @staticmethod
    def test_explain_with_top_n():
        """Test the /explain endpoint with custom top_n."""
        client = app.test_client()
        readings = [50.0] * 1034

        response = client.post(
            "/explain",
            data=json.dumps({"readings": readings, "top_n": 5}),
            content_type="application/json",
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data}"
        data = json.loads(response.data)
        assert len(data["explanation"]) == 5, f"Expected 5 features, got {len(data['explanation'])}"

        print("[OK] /explain endpoint respects top_n parameter")

    @staticmethod
    def test_invalid_readings():
        """Test the /explain endpoint with invalid readings."""
        client = app.test_client()

        # Test with wrong number of features
        readings = [50.0] * 100  # Only 100 features instead of 1034
        response = client.post(
            "/explain",
            data=json.dumps({"readings": readings}),
            content_type="application/json",
        )

        assert response.status_code == 400, f"Expected 400 for invalid input, got {response.status_code}"
        print("[OK] /explain endpoint rejects invalid feature count")

    @staticmethod
    def test_health_check():
        """Test the health check endpoint."""
        client = app.test_client()
        response = client.get("/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = json.loads(response.data)
        assert data["status"] == "running", "API is not running"
        print("[OK] Health check endpoint works")

    @staticmethod
    def test_model_info():
        """Test the /model-info endpoint."""
        client = app.test_client()
        response = client.get("/model-info")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = json.loads(response.data)
        assert "model" in data, "Missing 'model' in response"
        assert "total_features" in data, "Missing 'total_features' in response"
        print("[OK] /model-info endpoint works")

    @staticmethod
    def test_utility_functions():
        """Test the utility functions directly."""
        readings = np.array([50.0] * 1034).reshape(1, -1)
        feature_names = [f"feature_{i}" for i in range(1034)]

        # Test explain_from_features
        result = explain_from_features(readings, feature_names=feature_names, top_n=5)
        assert "prediction" in result, "Missing 'prediction' in result"
        assert "confidence" in result, "Missing 'confidence' in result"
        assert "explanation" in result, "Missing 'explanation' in result"
        assert len(result["explanation"]) == 5, f"Expected 5 features, got {len(result['explanation'])}"
        print("[OK] explain_from_features utility function works")

    @staticmethod
    def run_all_tests():
        """Run all tests."""
        tests = [
            TestSHAPIntegration.test_model_loaded,
            TestSHAPIntegration.test_preprocessing_loaded,
            TestSHAPIntegration.test_shap_manager_available,
            TestSHAPIntegration.test_health_check,
            TestSHAPIntegration.test_model_info,
            TestSHAPIntegration.test_predict_endpoint,
            TestSHAPIntegration.test_utility_functions,
            TestSHAPIntegration.test_explain_endpoint,
            TestSHAPIntegration.test_explain_with_feature_names,
            TestSHAPIntegration.test_explain_with_top_n,
            TestSHAPIntegration.test_invalid_readings,
        ]

        print("\n" + "=" * 60)
        print("SHAP INTEGRATION TEST SUITE")
        print("=" * 60 + "\n")

        passed = 0
        failed = 0

        for test in tests:
            try:
                test()
                passed += 1
            except AssertionError as exc:
                print(f"[FAIL] {test.__name__} failed: {exc}")
                failed += 1
            except Exception as exc:
                print(f"[FAIL] {test.__name__} error: {exc}")
                failed += 1

        print("\n" + "=" * 60)
        print(f"Results: {passed} passed, {failed} failed")
        print("=" * 60 + "\n")

        return failed == 0


if __name__ == "__main__":
    success = TestSHAPIntegration.run_all_tests()
    sys.exit(0 if success else 1)
