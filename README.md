# Electricity Theft Detection

A full-stack application that detects abnormal electricity usage (possible theft) using a trained machine learning model. This repository contains a Flask backend that loads the model and serves inference APIs, and a React + Vite frontend that provides a dashboard, CSV upload, history and model information pages.

## Features

- Single-record JSON prediction endpoint (`/predict`) for realtime inference
- Batch CSV upload endpoint (`/predict-csv`) for bulk predictions
- Prediction history persisted in a local SQLite database
- Dashboard, history and model information pages in the frontend
- Preprocessing (imputation + scaling) and model artifacts loaded at backend startup

## Repository structure

- backend/
  - `app.py` - Flask application entrypoint
  - `routes.py` - API route handlers
  - `utils.py` - preprocessing, prediction and CSV helpers
  - `model_loader.py` - loads model, scaler, imputer artifacts
  - `database.py` - SQLite helpers for history and dashboard stats
  - `config.py` - configuration values (ports, paths, etc.)
  - `requirements.txt` - Python dependencies

- frontend/
  - React + Vite single-page app
  - `src/services/api.js` - Axios client to talk to backend
  - Pages: Dashboard, Upload (CSV), History, Model Info
  - Components: charts, cards, upload area, sidebar, history table

## Requirements

- Python 3.9+ (backend)
- Node.js 18+ / npm (frontend)

## Backend — quick start

1. Create and activate a Python virtual environment

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate
pip install -r requirements.txt
```

2. Make sure the model artifacts referenced in `backend/config.py` exist (joblib files for `MODEL_PATH`, `SCALER_PATH`, `IMPUTER_PATH`).

3. Run the backend

```bash
python app.py
```

The API will listen on the host/port defined in `backend/config.py` (default `http://localhost:5000`).

## Frontend — quick start

1. Install dependencies and run the Vite dev server

```bash
cd frontend
npm install
npm run dev
```

2. Open the app (usually at `http://localhost:5173`) and use the sidebar to navigate.

> The frontend expects the backend API at `http://localhost:5000`. If your backend runs elsewhere, update `frontend/src/services/api.js` base URL.

## API Endpoints

- `GET /` — health check
- `POST /predict` — JSON body: `{ "readings": [..], "meter_id": "optional" }`, returns a single prediction
- `POST /predict-csv` — multipart form upload with CSV file under key `file`, returns per-row predictions
- `GET /history` — returns recent saved predictions from SQLite
- `GET /dashboard` — returns summary statistics for the dashboard
- `GET /model-info` — returns basic information about the loaded model
- `GET /alert-status` — SMS configuration health (booleans and counts only)
- `GET /alert-history` — recent SMS alert attempts
- `POST /test-alert` — send a test SMS (requires the `X-Alert-Token` header)

## Real-time SMS theft alerts

When the model predicts **Theft**, the backend sends an SMS to the phone numbers
configured in `backend/.env`. Normal predictions never send anything.

    CSV / meter reading -> Flask -> ML model -> Theft -> notification_service -> phone

### Setup

1. Copy the template and fill in your own values:

```bash
cd backend
cp .env.example .env        # Windows: copy .env.example .env
pip install -r requirements.txt
```

2. Set at minimum `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`,
   `ALERT_PHONE_NUMBERS` and `ALERT_TEST_TOKEN`. Every option is documented in
   `backend/.env.example`.

3. Restart the backend and open the **SMS Alerts** page in the frontend to confirm
   the configuration and fire a test message.

`backend/.env` is git-ignored. No credentials or phone numbers appear anywhere in
the Python or React source.

### Spam protection

| Control | Variable | Behaviour |
| --- | --- | --- |
| Per-meter cooldown | `ALERT_COOLDOWN_MINUTES` | The same meter is not texted twice inside the window |
| Per-upload cap | `MAX_ALERTS_PER_BATCH` | Only the highest-confidence theft meters in a CSV get their own SMS |
| Batch summary | `BATCH_SUMMARY_ENABLED` | One summary SMS covers everything above the cap |
| Confidence floor | `ALERT_MIN_CONFIDENCE` | Ignore low-confidence theft predictions |
| Test throttle | `TEST_ALERT_COOLDOWN_SECONDS` | `/test-alert` cannot be hammered |

### Provider options

`SMS_PROVIDER` selects the backend: `twilio` (default), `fast2sms` (easier for
Indian +91 numbers, which Twilio gates behind DLT registration), `console` (logs
the message instead of sending it — useful for offline demos) or `disabled`.

### Testing

```bash
cd backend
python test_sms_integration.py
```

The suite forces `SMS_PROVIDER=console`, so it never sends a real SMS or spends
Twilio credit. It checks that Normal predictions stay silent, Theft predictions
alert, the cooldown blocks duplicates, provider failures never break a
prediction, and no credential ever reaches a response or the log file.

## Notes & Troubleshooting

- Ensure model artifact files exist and are compatible with the preprocessing artifacts (imputer/scaler).
- If CSV uploads fail, check column names and that there are numeric feature columns remaining after dropping metadata columns like `cons_no` / `Unnamed`.
- Prediction results are stored in `predictions` table of the SQLite DB path defined in `backend/config.py`.

## Next steps / Improvements

- Add tests for API endpoints and CSV parsing behavior
- Add Dockerfiles for reproducible deployment of backend and frontend
- Add CI pipeline to run linting and tests

---

If you want a longer README (deployment instructions, architecture diagram, or contributor guide), tell me what to include and I'll expand it.