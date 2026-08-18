# SHAP Integration - Implementation Summary

## Overview
SHAP (SHapley Additive exPlanations) has been successfully integrated into the Electricity Theft Detection project to provide explainable AI explanations for Random Forest predictions.

---

## 1. Backend Files Changed

### Modified Files:

#### [requirements.txt](requirements.txt)
- **Added**: `shap==0.45.1`
- **Changed**: Downgraded `numpy` from 2.1.0 to 1.26.4 for SHAP compatibility
- **Result**: All dependencies compatible and working

#### [routes.py](routes.py)
- **Added import**: `explain_from_features` from utils
- **Added endpoint**: `POST /explain` - generates SHAP explanations for predictions
- **Input validation**: Validates JSON body, readings array, feature_names (optional), top_n (optional)
- **Error handling**: Returns 400 for invalid input, 500 for server errors
- **Response format**: JSON with prediction, risk, confidence, and explanation array

#### [utils.py](utils.py)
- **Added import**: `from shap_explainer import get_shap_manager` (with graceful error handling)
- **Added function**: `explain_from_features(features, feature_names, top_n)`
  - Validates and preprocesses features (imputation + scaling)
  - Calls SHAP explainer
  - Returns structured explanation with top N features
  - Logs timing information

---

## 2. New Backend Files Created

### [backend/shap_explainer.py](shap_explainer.py)
**Purpose**: Manages SHAP TreeExplainer initialization and explanation generation

**Key Components**:
- `ShapExplainerManager` class
  - Initializes TreeExplainer once at module load (not per-request)
  - Safely handles SHAP availability
  - `explain_prediction()` method:
    - Takes scaled features (already imputed & scaled)
    - Extracts SHAP values from TreeExplainer
    - Handles 3D output format: (n_samples, n_features, n_classes)
    - Returns top N contributing features with signed SHAP values
    - Determines impact direction based on SHAP value sign

- `SHAP_MANAGER` singleton instance (module-level)
- `get_shap_manager()` function to access the global manager

**Design Decisions**:
- TreeExplainer initialized once at startup (not recreated per request)
- Proper handling of SHAP output shape for binary classification
- Uses the already-loaded and fitted Random Forest model

---

## 3. Frontend Files Changed

### [src/services/api.js](src/services/api.js)
- **Added export**: `explainPrediction(payload)` - POST request to /explain endpoint

### [src/components/PredictionResultCard.jsx](src/components/PredictionResultCard.jsx)
- **Added props**: `readings`, `featureNames` (optional)
- **Added state**: `explanationOpen`, `explanation`, `isLoadingExplanation`, `explanationError`
- **Added function**: `handleExplainClick()` - calls API and manages explanation state
- **Added UI**: "Why this prediction?" button below prediction card
- **Integrated**: `<PredictionExplanation />` component for displaying results

---

## 4. New Frontend Files Created

### [src/components/PredictionExplanation.jsx](src/components/PredictionExplanation.jsx)
**Purpose**: Material-UI Dialog displaying SHAP explanations

**Features**:
- Responsive Material-UI dialog with title and content
- Summary card showing prediction, risk level, and confidence
- Top contributing features displayed as cards with:
  - Feature name/index
  - SHAP value (signed, rounded to 4 decimals)
  - Impact direction (positive/negative/neutral)
  - Visual bar chart showing relative importance
  - Text description of direction (e.g., "increased theft probability")
- Loading state during API call
- Error state for failed requests
- Color-coded by prediction type (red for theft, green for normal)
- Legend explaining positive vs negative SHAP values

---

## 5. SHAP Processing Pipeline

```
Raw Meter Readings
    ↓
Validation (correct number of features)
    ↓
Imputation (using fitted imputer.pkl)
    ↓
Scaling (using fitted scaler.pkl)
    ↓
Random Forest Prediction
    ↓
SHAP TreeExplainer
    ↓
Extract Top N Features by |SHAP|
    ↓
Format Response (feature name, SHAP value, impact, direction)
    ↓
JSON Response to Frontend
```

### Key Preprocessing Rule:
SHAP explains the exact representation that the Random Forest receives:
```
Raw input → imputer.pkl → scaler.pkl → Model Input → SHAP Explanation
```
This ensures consistency between training and explanation.

---

## 6. Feature Selection & Ranking

**How Top Features are Selected**:
1. SHAP values calculated for all 1034 features
2. Absolute values computed: `abs(shap_values)`
3. Sorted in descending order
4. Top N selected (default: 10, configurable via `top_n` parameter)

**Impact Interpretation**:
- **Positive SHAP**: Feature increased prediction probability
- **Negative SHAP**: Feature decreased prediction probability  
- **Magnitude**: Larger |SHAP| = stronger influence

**Direction Labels** (user-friendly):
- Theft prediction + positive SHAP: "increased_theft_probability"
- Theft prediction + negative SHAP: "decreased_theft_probability"
- Normal prediction + positive SHAP: "increased_normal_probability"
- Normal prediction + negative SHAP: "decreased_normal_probability"

---

## 7. API Endpoints

### Existing Endpoints (Unchanged)
- `GET /` - Health check
- `GET /model-info` - Model information
- `POST /predict` - Single prediction
- `POST /predict-csv` - Batch predictions from CSV
- `GET /history` - Prediction history
- `GET /dashboard` - Dashboard statistics

### New Endpoint

#### `POST /explain`
**Purpose**: Generate SHAP explanations for a single prediction

**Request Format**:
```json
{
    "readings": [50.0, 45.0, ..., 52.0],
    "feature_names": ["2016/05/01", "2016/05/02", ...],
    "top_n": 10
}
```

**Request Fields**:
- `readings` (required): Array of 1034 numeric values
- `feature_names` (optional): Array of 1034 feature names (defaults to "feature_0", etc.)
- `top_n` (optional): Number of top features to return (default: 10, min: 1)

**Response Format**:
```json
{
    "prediction": "Theft",
    "risk": "High",
    "confidence": 91.42,
    "explanation": [
        {
            "feature": "2016/05/12",
            "shap_value": 0.8234,
            "impact": "positive",
            "direction": "increased_theft_probability"
        },
        {
            "feature": "2016/05/13",
            "shap_value": 0.6125,
            "impact": "positive",
            "direction": "increased_theft_probability"
        },
        {
            "feature": "2016/05/14",
            "shap_value": -0.4231,
            "impact": "negative",
            "direction": "decreased_theft_probability"
        }
    ]
}
```

**Response Fields**:
- `prediction`: "Theft" or "Normal"
- `risk`: "High" or "Low"
- `confidence`: 0-100 percentage
- `explanation`: Array of up to N features (ordered by |SHAP| value)

**Error Responses**:
```json
{
    "error": "Invalid input",
    "message": "Expected 1034 features but found 100 features."
}
```

**Status Codes**:
- 200: Success
- 400: Invalid input (wrong feature count, missing readings, etc.)
- 500: Server error (SHAP generation failed)

---

## 8. Example Usage

### Backend API Test
```bash
cd backend
python test_shap.py
# Output: "Results: 11 passed, 0 failed"
```

### Curl Example
```bash
curl -X POST http://localhost:5000/explain \
  -H "Content-Type: application/json" \
  -d '{
    "readings": [50.0, 45.0, 48.0, ..., 52.0],
    "feature_names": ["2016/05/01", "2016/05/02", ...],
    "top_n": 5
  }'
```

### Frontend Usage
In any React component that uses `PredictionResultCard`:
```jsx
<PredictionResultCard 
  result={predictionResult}
  readings={meterReadings}
  featureNames={dateLabels}
/>
```

User clicks "Why this prediction?" → Dialog opens → Explanation loads → Displays top features

---

## 9. Performance Optimization

**Single Predictions**:
- TreeExplainer initialized once at startup
- SHAP calculation on-demand per request
- No caching needed (fast enough for real-time)
- ~500ms per explanation (depending on system)

**Batch Predictions (CSV)**:
- Existing `/predict-csv` remains unchanged
- SHAP explanations available on-demand via `/explain`
- Users can request explanations for selected rows
- Prevents expensive calculation on all 500+ rows

**Memory Efficiency**:
- Model, imputer, scaler loaded once and reused
- Feature importance computed only for top N
- No persistent storage of SHAP values

---

## 10. Preprocessing Verification

**Preprocessing is Consistent**:
✓ Uses existing imputer.pkl
✓ Uses existing scaler.pkl
✓ Uses existing random forest model
✓ SHAP explains preprocessed features
✓ No unnecessary refitting

**Feature Count Validation**:
- Model expects exactly 1034 features
- Validated before and after preprocessing
- Clear error messages if count mismatches

---

## 11. Error Handling

**Graceful Degradation**:
- If SHAP initialization fails: Returns 500 with clear message
- Invalid input: Returns 400 with specific validation error
- Missing model artifacts: Caught at startup
- SHAP calculation errors: Logged and returned as 500 error

**No Breaking Changes**:
- Existing endpoints continue working if SHAP fails
- `/explain` endpoint is optional for users
- Normal predictions (`/predict`) unaffected

---

## 12. Testing

### Test Suite: [backend/test_shap.py](test_shap.py)

**11 Tests Included**:
1. Model loaded correctly
2. Preprocessing artifacts loaded
3. SHAP manager available
4. Health check endpoint
5. Model info endpoint
6. Predict endpoint
7. Explain utility function
8. Explain endpoint (default parameters)
9. Explain endpoint with custom feature names
10. Explain endpoint with custom top_n
11. Explain endpoint validation (rejects invalid input)

**Run Tests**:
```bash
cd backend
pip install -r requirements.txt
python test_shap.py
```

**Expected Output**:
```
============================================================
SHAP INTEGRATION TEST SUITE
============================================================

[OK] Model loaded with 1034 features
[OK] Imputer and scaler loaded
[OK] SHAP manager is available
[OK] Health check endpoint works
[OK] /model-info endpoint works
[OK] /predict endpoint works
[OK] explain_from_features utility function works
[OK] /explain endpoint works and returns 10 features
[OK] /explain endpoint works with custom feature names
[OK] /explain endpoint respects top_n parameter
[OK] /explain endpoint rejects invalid feature count

============================================================
Results: 11 passed, 0 failed
============================================================
```

---

## 13. Running the Project

### Backend
```bash
cd backend
pip install -r requirements.txt
python app.py
# Server runs on http://localhost:5000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# App runs on http://localhost:5173 (Vite default)
```

### Verify Integration
```bash
# In another terminal
cd backend
python verify_endpoints.py
```

---

## 14. What Was NOT Changed

✓ **Random Forest model** - Unchanged (model.pkl untouched)
✓ **Model training** - No retraining performed
✓ **Prediction logic** - `/predict` endpoint unchanged
✓ **CSV predictions** - `/predict-csv` endpoint unchanged
✓ **Database** - History and dashboard unchanged
✓ **Scaler/Imputer** - Existing artifacts used as-is

---

## 15. Dependencies Added

```
shap==0.45.1
```

**Dependencies from SHAP**:
- tqdm>=4.27.0
- numba
- cloudpickle
- llvmlite
- slicer==0.0.8

**NumPy Compatibility**:
- Downgraded numpy to 1.26.4 (from 2.1.0)
- SHAP 0.45.1 incompatible with NumPy 2.x
- All other packages remain compatible

---

## 16. Summary

✅ **SHAP fully integrated** without breaking existing functionality
✅ **TreeExplainer** initialized once for efficiency
✅ **Proper preprocessing pipeline** maintained (impute → scale → explain)
✅ **Top N feature selection** with directional impact
✅ **Frontend UI component** for displaying explanations
✅ **Complete test coverage** (11 tests, all passing)
✅ **Error handling** for all edge cases
✅ **Documentation** complete

The Random Forest model remains the authoritative predictor. SHAP is purely an explanatory layer that helps users understand why the model made specific predictions.
