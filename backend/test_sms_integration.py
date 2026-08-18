"""End-to-end checks for the SMS alerting feature.

Run it from the backend folder with the virtual environment active:

    python test_sms_integration.py

It uses Flask's built-in test client, so nothing has to be running first, and
it forces SMS_PROVIDER=console so **no real SMS is ever sent and no Twilio
credits are used**. Your model.pkl / scaler.pkl / imputer.pkl are only read,
never written.

To make the results deterministic the script temporarily swaps utils.MODEL for
a tiny stub during the theft/normal tests. The real model is restored
immediately afterwards; the file on disk is never touched.
"""

from __future__ import annotations

import io
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Point the whole test run at a throwaway database and a console SMS provider
# BEFORE any project module is imported.
TEMP_DB = Path(tempfile.gettempdir()) / "etd_sms_test.db"
if TEMP_DB.exists():
    TEMP_DB.unlink()

os.environ["SMS_PROVIDER"] = "console"
os.environ["SMS_ALERTS_ENABLED"] = "true"
os.environ["ALERT_PHONE_NUMBERS"] = "+10000000000"
os.environ["ALERT_COOLDOWN_MINUTES"] = "60"
os.environ["MAX_ALERTS_PER_BATCH"] = "3"
os.environ["BATCH_SUMMARY_ENABLED"] = "true"
os.environ["ALERT_MIN_CONFIDENCE"] = "0"
os.environ["ALERT_TEST_TOKEN"] = "unit-test-token"
os.environ["TEST_ALERT_COOLDOWN_SECONDS"] = "300"

import config  # noqa: E402

config.DB_PATH = TEMP_DB

import database  # noqa: E402

database.DB_PATH = TEMP_DB
database.init_db()

import notification_service  # noqa: E402
import utils  # noqa: E402
from app import app  # noqa: E402

notification_service.reload_settings()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append(f"{name} :: {detail}")
        print(f"  FAIL  {name} :: {detail}")


class StubModel:
    """Deterministic stand-in so we can force Theft or Normal on demand."""

    def __init__(self, label: int, n_features: int) -> None:
        self.label = label
        self.n_features_in_ = n_features

    def predict(self, features):
        return [self.label] * len(features)

    def predict_proba(self, features):
        row = [0.06, 0.94] if self.label == 1 else [0.91, 0.09]
        return [row] * len(features)


class FailingProvider(notification_service.BaseProvider):
    """Simulates a provider outage."""

    name = "failing"

    def check_config(self) -> None:
        return None

    def send(self, to_number: str, body: str) -> str:
        raise notification_service.ProviderNetworkError("simulated connection reset")


notification_service._PROVIDERS["failing"] = FailingProvider

FEATURE_COUNT = int(getattr(utils.MODEL, "n_features_in_", 0) or 1034)
READINGS = [1.5] * FEATURE_COUNT


def set_model(label: int) -> None:
    utils.MODEL = StubModel(label, FEATURE_COUNT)


def restore_model() -> None:
    import model_loader

    utils.MODEL = model_loader.MODEL


def set_provider(name: str) -> None:
    os.environ["SMS_PROVIDER"] = name
    notification_service.reload_settings()


def alert_rows() -> list[tuple]:
    with sqlite3.connect(TEMP_DB) as connection:
        return connection.execute(
            "SELECT meter_id, alert_type, status FROM alert_log ORDER BY id"
        ).fetchall()


def make_csv(meter_ids: list[str]) -> bytes:
    header = "cons_no," + ",".join(f"d{index}" for index in range(FEATURE_COUNT))
    lines = [header]
    for meter_id in meter_ids:
        lines.append(meter_id + "," + ",".join("1.5" for _ in range(FEATURE_COUNT)))
    return ("\n".join(lines)).encode("utf-8")


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def main() -> int:
    client = app.test_client()

    print("\n[1] Health check")
    response = client.get("/")
    check("GET / returns 200", response.status_code == 200, str(response.status_code))
    check("GET / reports running", response.get_json().get("status") == "running", str(response.get_json()))

    print("\n[2] Alert status endpoint leaks no secrets")
    response = client.get("/alert-status")
    body = response.get_data(as_text=True)
    payload = response.get_json()
    check("GET /alert-status returns 200", response.status_code == 200, str(response.status_code))
    check("status reports the provider", payload.get("provider") == "console", str(payload))
    check("status has no auth token key", "auth_token" not in body.lower(), body[:200])
    check("status has no phone numbers", "+10000000000" not in body, body[:200])
    check("status has no account sid", "account_sid" not in body.lower(), body[:200])

    print("\n[3] /test-alert rejects a missing or wrong token")
    notification_service.reset_test_throttle()
    response = client.post("/test-alert", json={})
    check("no token returns 401", response.status_code == 401, str(response.status_code))
    response = client.post("/test-alert", headers={"X-Alert-Token": "wrong"})
    check("wrong token returns 401", response.status_code == 401, str(response.status_code))

    print("\n[4] /test-alert works with the correct token")
    response = client.post("/test-alert", headers={"X-Alert-Token": "unit-test-token"})
    payload = response.get_json()
    check("valid token returns 200", response.status_code == 200, str(response.status_code))
    check("test alert reports success", payload.get("success") is True, str(payload))
    check(
        "test alert message matches spec",
        payload.get("message") == "Test SMS sent successfully",
        str(payload),
    )

    print("\n[5] /test-alert is throttled against spam")
    response = client.post("/test-alert", headers={"X-Alert-Token": "unit-test-token"})
    check("second call is throttled with 429", response.status_code == 429, str(response.status_code))
    check("throttle response is not success", response.get_json().get("success") is False, str(response.get_json()))

    print("\n[6] Normal prediction sends no SMS")
    set_model(0)
    before = len(alert_rows())
    response = client.post("/predict", json={"readings": READINGS, "meter_id": "METER-NORMAL-1"})
    payload = response.get_json()
    check("normal prediction returns 200", response.status_code == 200, str(response.status_code))
    check("prediction is Normal", payload.get("prediction") == "Normal", str(payload))
    check("alert_sent is false", payload.get("alert_sent") is False, str(payload))
    check("reason is normal_prediction", payload.get("alert_skipped") == "normal_prediction", str(payload))
    check("no alert row written", len(alert_rows()) == before, f"{before} -> {len(alert_rows())}")

    print("\n[7] Theft prediction sends an SMS")
    set_model(1)
    response = client.post("/predict", json={"readings": READINGS, "meter_id": "METER-THEFT-1"})
    payload = response.get_json()
    check("theft prediction returns 200", response.status_code == 200, str(response.status_code))
    check("prediction is Theft", payload.get("prediction") == "Theft", str(payload))
    check("risk is High", payload.get("risk") == "High", str(payload))
    check("alert_sent is true", payload.get("alert_sent") is True, str(payload))
    check("alert_error is null", payload.get("alert_error") is None, str(payload))
    check(
        "alert_log recorded a sent theft alert",
        ("METER-THEFT-1", "theft", "sent") in alert_rows(),
        str(alert_rows()),
    )

    print("\n[8] Repeat theft on the same meter is blocked by the cooldown")
    response = client.post("/predict", json={"readings": READINGS, "meter_id": "METER-THEFT-1"})
    payload = response.get_json()
    check("repeat prediction still returns 200", response.status_code == 200, str(response.status_code))
    check("repeat prediction is still Theft", payload.get("prediction") == "Theft", str(payload))
    check("repeat alert_sent is false", payload.get("alert_sent") is False, str(payload))
    check("repeat reason is cooldown", payload.get("alert_skipped") == "cooldown", str(payload))
    check("repeat has no error", payload.get("alert_error") is None, str(payload))

    print("\n[9] A different meter still alerts during another meter's cooldown")
    response = client.post("/predict", json={"readings": READINGS, "meter_id": "METER-THEFT-2"})
    payload = response.get_json()
    check("different meter alert_sent is true", payload.get("alert_sent") is True, str(payload))

    print("\n[10] SMS provider failure does not break the prediction")
    set_provider("failing")
    response = client.post("/predict", json={"readings": READINGS, "meter_id": "METER-THEFT-3"})
    payload = response.get_json()
    check("prediction still returns 200 when SMS fails", response.status_code == 200, str(response.status_code))
    check("prediction value survives SMS failure", payload.get("prediction") == "Theft", str(payload))
    check("confidence survives SMS failure", isinstance(payload.get("confidence"), (int, float)), str(payload))
    check("alert_sent is false on failure", payload.get("alert_sent") is False, str(payload))
    check("alert_error is populated", bool(payload.get("alert_error")), str(payload))
    check(
        "alert_error mentions the network failure",
        "network failure" in str(payload.get("alert_error")).lower(),
        str(payload.get("alert_error")),
    )

    print("\n[11] Missing credentials are reported, not crashed on")
    set_provider("twilio")
    for key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"):
        os.environ.pop(key, None)
    notification_service.reload_settings()
    response = client.post("/predict", json={"readings": READINGS, "meter_id": "METER-THEFT-4"})
    payload = response.get_json()
    check("prediction succeeds without credentials", response.status_code == 200, str(response.status_code))
    check("alert_sent false without credentials", payload.get("alert_sent") is False, str(payload))
    check(
        "error explains the missing configuration",
        "not configured" in str(payload.get("alert_error")).lower(),
        str(payload.get("alert_error")),
    )

    print("\n[12] Invalid destination number is handled")
    set_provider("fast2sms")
    os.environ["FAST2SMS_API_KEY"] = "dummy-key-for-validation-only"
    os.environ["ALERT_PHONE_NUMBERS"] = "12345"
    notification_service.reload_settings()
    response = client.post("/predict", json={"readings": READINGS, "meter_id": "METER-THEFT-5"})
    payload = response.get_json()
    check("prediction survives invalid number", response.status_code == 200, str(response.status_code))
    check(
        "invalid number reported cleanly",
        "invalid phone number" in str(payload.get("alert_error")).lower(),
        str(payload.get("alert_error")),
    )
    os.environ["ALERT_PHONE_NUMBERS"] = "+10000000000"
    os.environ.pop("FAST2SMS_API_KEY", None)

    print("\n[13] CSV upload: per-meter cap plus a summary SMS")
    set_provider("console")
    set_model(1)
    meter_ids = [f"CSV-METER-{index}" for index in range(8)]
    csv_bytes = make_csv(meter_ids)
    response = client.post(
        "/predict-csv",
        data={"file": (io.BytesIO(csv_bytes), "meters.csv")},
        content_type="multipart/form-data",
    )
    payload = response.get_json()
    summary = payload.get("alert_summary", {})
    check("CSV upload returns 200", response.status_code == 200, str(response.status_code))
    check("all 8 rows predicted", payload.get("total_predictions") == 8, str(payload.get("total_predictions")))
    check("summary counts 8 theft rows", summary.get("theft_count") == 8, str(summary))
    check("only MAX_ALERTS_PER_BATCH=3 texted", summary.get("alerts_sent") == 3, str(summary))
    check("remaining 5 suppressed", summary.get("alerts_suppressed") == 5, str(summary))
    check("batch summary SMS sent", summary.get("summary_sms_sent") is True, str(summary))
    capped = [row for row in payload["results"] if row.get("alert_skipped") == "batch_limit"]
    check("rows marked batch_limit", len(capped) == 5, str(len(capped)))
    check(
        "every result row carries alert fields",
        all("alert_sent" in row for row in payload["results"]),
        "missing alert_sent on some rows",
    )

    print("\n[14] CSV upload with only Normal rows sends nothing")
    set_model(0)
    before = len(alert_rows())
    response = client.post(
        "/predict-csv",
        data={"file": (io.BytesIO(make_csv(["CSV-OK-1", "CSV-OK-2"])), "ok.csv")},
        content_type="multipart/form-data",
    )
    payload = response.get_json()
    summary = payload.get("alert_summary", {})
    check("normal CSV returns 200", response.status_code == 200, str(response.status_code))
    check("no theft counted", summary.get("theft_count") == 0, str(summary))
    check("no alerts sent", summary.get("alerts_sent") == 0, str(summary))
    check("no summary SMS sent", summary.get("summary_sms_sent") is False, str(summary))
    check("no new alert rows", len(alert_rows()) == before, f"{before} -> {len(alert_rows())}")

    print("\n[15] Existing endpoints still work")
    restore_model()
    check("GET /history returns 200", client.get("/history").status_code == 200)
    check("GET /dashboard returns 200", client.get("/dashboard").status_code == 200)
    check("GET /model-info returns 200", client.get("/model-info").status_code == 200)
    check("GET /alert-history returns 200", client.get("/alert-history").status_code == 200)
    dashboard = client.get("/dashboard").get_json()
    check(
        "dashboard still reports the original keys",
        {"total_predictions", "theft_predictions", "normal_predictions", "latest_prediction", "recent_history"}
        <= set(dashboard),
        str(list(dashboard)),
    )

    print("\n[16] Predictions table schema is unchanged")
    with sqlite3.connect(TEMP_DB) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(predictions)")]
    # Other features may add columns (e.g. SHAP stores 'features'). What matters
    # for alerting is that the original columns still exist and still work.
    check(
        "original prediction columns still present",
        {"id", "meter_id", "prediction", "confidence", "risk", "timestamp"} <= set(columns),
        str(columns),
    )

    print("\n[17] Credentials are scrubbed from errors, responses and logs")
    # These fakes are assembled at runtime on purpose. Writing a full Twilio
    # SID or auth token as a literal here would make automated secret scanners
    # (for example GitHub push protection) reject the whole repository, even
    # though the values are obviously not real.
    fake_sid = "AC" + ("0123456789abcdef" * 2)
    fake_auth = "fake" + "AuthToken" + "ForTestsOnly" + "1234567890"
    fake_phone = "+9199999" + "11111"

    os.environ.update(
        {
            "SMS_PROVIDER": "twilio",
            "TWILIO_ACCOUNT_SID": fake_sid,
            "TWILIO_AUTH_TOKEN": fake_auth,
            "TWILIO_PHONE_NUMBER": "+15550001111",
            "ALERT_PHONE_NUMBERS": fake_phone,
        }
    )
    notification_service.reload_settings()
    dirty = (
        f"POST https://api.twilio.com/2010-04-01/Accounts/{fake_sid}/Messages.json "
        f"auth={fake_auth} to={fake_phone}"
    )
    cleaned = notification_service.scrub(dirty)
    check("auth token removed", fake_auth not in cleaned, cleaned)
    check("account sid removed", fake_sid not in cleaned, cleaned)
    check("destination number masked", fake_phone not in cleaned, cleaned)

    status_body = client.get("/alert-status").get_data(as_text=True)
    for secret in (fake_sid, fake_auth, fake_phone, "unit-test-token"):
        check(f"/alert-status hides {secret[:12]}...", secret not in status_body, status_body[:200])

    set_provider("console")
    os.environ["ALERT_PHONE_NUMBERS"] = "+10000000000"
    notification_service.reload_settings()

    print("\n[18] Telegram provider")
    import notification_service as ns

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = str(payload)

        def json(self):
            return self._payload

    calls: list[dict] = []

    class FakeRequests:
        @staticmethod
        def post(url, **kwargs):
            calls.append({"url": url, **kwargs})
            return FakeResponse(200, {"ok": True, "result": {"message_id": 4242}})

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *args, **kwargs):
        if name == "requests":
            return FakeRequests
        return real_import(name, *args, **kwargs)

    # Assembled at runtime for the same secret-scanner reason as test [17].
    fake_bot_token = "123456789" + ":" + "AAE" + "fakeBotTokenForTestsOnly" + "1234567890"

    os.environ.update(
        {
            "SMS_PROVIDER": "telegram",
            "TELEGRAM_BOT_TOKEN": fake_bot_token,
            "TELEGRAM_CHAT_IDS": "555000111",
            "ALERT_PHONE_NUMBERS": "",
        }
    )
    ns.reload_settings()

    status = client.get("/alert-status").get_json()
    check("telegram reported as provider", status.get("provider") == "telegram", str(status))
    check("telegram credentials detected", status.get("provider_configured") is True, str(status))
    check("chat id counted as a destination", status.get("recipients_configured") == 1, str(status))
    check("telegram reports ready", status.get("ready") is True, str(status))

    if isinstance(__builtins__, dict):
        __builtins__["__import__"] = fake_import
    else:
        __builtins__.__import__ = fake_import
    try:
        set_model(1)
        response = client.post("/predict", json={"readings": READINGS, "meter_id": "TG-METER-1"})
        payload = response.get_json()
    finally:
        if isinstance(__builtins__, dict):
            __builtins__["__import__"] = real_import
        else:
            __builtins__.__import__ = real_import

    check("telegram alert sent", payload.get("alert_sent") is True, str(payload))
    check("one telegram call made", len(calls) == 1, str(len(calls)))
    if calls:
        check("posted to sendMessage", calls[0]["url"].endswith("/sendMessage"), calls[0]["url"])
        body = calls[0].get("json", {})
        check("correct chat id used", str(body.get("chat_id")) == "555000111", str(body))
        check("emoji preserved for telegram", "\U0001f6a8" in str(body.get("text")), str(body.get("text")))

    print("\n[19] Missing Telegram chat id is reported clearly")
    os.environ["TELEGRAM_CHAT_IDS"] = ""
    ns.reload_settings()
    response = client.post("/predict", json={"readings": READINGS, "meter_id": "TG-METER-2"})
    payload = response.get_json()
    check("prediction still succeeds", response.status_code == 200, str(response.status_code))
    check(
        "error names TELEGRAM_CHAT_IDS",
        "TELEGRAM_CHAT_IDS" in str(payload.get("alert_error")),
        str(payload.get("alert_error")),
    )

    print("\n[20] Telegram bot token is scrubbed from errors")
    os.environ["TELEGRAM_CHAT_IDS"] = "555000111"
    ns.reload_settings()
    dirty_url = (
        f"HTTPSConnectionPool: POST https://api.telegram.org/bot{fake_bot_token}/sendMessage failed"
    )
    cleaned = ns.scrub(dirty_url)
    check("bot token removed", fake_bot_token not in cleaned, cleaned)
    check("bot url path masked", "/bot***" in cleaned or "***" in cleaned, cleaned)

    print("\n[21] Fast2SMS strips emoji for the plain-GSM route")
    ascii_body = ns.to_ascii(ns.build_theft_message("M-1", 94.2, "2026-01-01 00:00:00"))
    check("result is pure ascii", all(ord(character) < 128 for character in ascii_body), ascii_body)
    check("alert tag kept", "[ALERT]" in ascii_body, ascii_body)
    check("meter id kept", "M-1" in ascii_body, ascii_body)

    set_provider("console")
    os.environ["ALERT_PHONE_NUMBERS"] = "+10000000000"
    notification_service.reload_settings()

    print("\n" + "=" * 62)
    print(f"  {len(PASSED)} passed, {len(FAILED)} failed")
    print("=" * 62)
    for failure in FAILED:
        print(f"  FAILED: {failure}")

    if TEMP_DB.exists():
        TEMP_DB.unlink()

    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
