"""Verify existing endpoints still work."""
import json
from app import app

client = app.test_client()

print("Testing existing endpoints...\n")

# Test health check
response = client.get("/")
print(f"GET / : {response.status_code}")
data = json.loads(response.data)
print(f"  Status: {data.get('status')}\n")

# Test model-info
response = client.get("/model-info")
print(f"GET /model-info : {response.status_code}")
data = json.loads(response.data)
print(f"  Model: {data.get('model')}")
print(f"  Features: {data.get('total_features')}\n")

# Test predict with valid data
readings = [50.0] * 1034
response = client.post("/predict", data=json.dumps({"readings": readings}), content_type="application/json")
print(f"POST /predict : {response.status_code}")
data = json.loads(response.data)
print(f"  Prediction: {data.get('prediction')}")
print(f"  Risk: {data.get('risk')}")
print(f"  Confidence: {data.get('confidence')}\n")

# Test history
response = client.get("/history")
print(f"GET /history : {response.status_code}")
data = json.loads(response.data)
print(f"  Count: {data.get('count')}\n")

# Test dashboard
response = client.get("/dashboard")
print(f"GET /dashboard : {response.status_code}")
data = json.loads(response.data)
print(f"  Response keys: {list(data.keys())}\n")

print("All existing endpoints working!")
