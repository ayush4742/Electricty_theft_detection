"""Debug script to understand SHAP output format."""
import numpy as np
from model_loader import MODEL, IMPUTER, SCALER
import shap

# Create a sample input
readings = np.array([50.0] * 1034).reshape(1, -1)

# Apply preprocessing
imputed = IMPUTER.transform(readings)
scaled = SCALER.transform(imputed)

# Initialize SHAP explainer
explainer = shap.TreeExplainer(MODEL)

# Get SHAP values
shap_values = explainer.shap_values(scaled)

print(f"Type of shap_values: {type(shap_values)}")
print(f"Is list: {isinstance(shap_values, list)}")

if isinstance(shap_values, list):
    print(f"Length of list: {len(shap_values)}")
    for i, sv in enumerate(shap_values):
        print(f"  Element {i}: type={type(sv)}, shape={sv.shape if hasattr(sv, 'shape') else 'N/A'}")
else:
    print(f"Shape: {shap_values.shape}")
    print(f"ndim: {shap_values.ndim}")

# Make prediction
pred = MODEL.predict(scaled)[0]
print(f"\nPrediction: {pred} (type: {type(pred)})")

# Get probabilities
proba = MODEL.predict_proba(scaled)[0]
print(f"Probabilities: {proba}")
