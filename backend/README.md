# Electricity Theft Detection Backend

This Flask backend provides a production-ready API for electricity theft detection using a pre-trained machine learning model.

## Features
- JSON-based prediction endpoint: /predict
- CSV upload prediction endpoint: /predict-csv
- Prediction history stored locally in SQLite
- Model information endpoint: /model-info
- CORS support for React frontend integration

## Installation
```bash
cd backend
pip install -r requirements.txt
```

## Run the backend
```bash
python app.py
```

The server will start at:
- http://0.0.0.0:5000

## API Endpoints

### GET /
Health check endpoint.

### POST /predict
Accepts JSON input with a readings array.

Example request:
```bash
curl -X POST http://127.0.0.1:5000/predict \
  -H "Content-Type: application/json" \
  -d '{"readings": [3.2, 4.1, 2.9, 3.8]}'
```

### POST /predict-csv
Accepts a CSV file upload using multipart/form-data.

Example request:
```bash
curl -X POST http://127.0.0.1:5000/predict-csv \
  -F "file=@sample.csv"
```

### GET /history
Returns prediction history stored in SQLite.

### GET /model-info
Returns information about the loaded model.
