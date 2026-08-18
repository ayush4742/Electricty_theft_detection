"""SMS alerting for electricity theft predictions.

This module is completely independent of the ML pipeline. It never raises:
every public function returns a plain dictionary describing what happened, so a
failed SMS can never break a prediction request.

Provider selection is driven by the SMS_PROVIDER environment variable:

    twilio    -> real SMS through the Twilio REST API (default)
    fast2sms  -> real SMS through Fast2SMS (India friendly, no DLT for OTP route)
    console   -> no network call, the message is written to the log (safe demos)
    disabled  -> alerting is switched off entirely

Adding another provider means writing one small class and registering it in
_PROVIDERS. Nothing else in the project has to change.

Secrets (auth tokens, API keys) are read from the environment and are never
logged, never returned by any function, and never sent to the frontend.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from database import record_alert, seconds_since_last_successful_alert

logger = logging.getLogger(__name__)

# The Twilio SDK logs every request URL at INFO level, and that URL contains the
# account SID. Keep it quiet so credentials never reach app.log.
for _noisy_logger in ("twilio", "twilio.http_client", "urllib3.connectionpool"):
    logging.getLogger(_noisy_logger).setLevel(logging.WARNING)

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

# Load backend/.env if python-dotenv is installed. It is listed in
# requirements.txt, but the import is guarded so the backend still boots
# without it (the variables can also come from the real environment).
try:  # pragma: no cover - trivial import guard
    from dotenv import load_dotenv

    load_dotenv(ENV_PATH)
except ImportError:  # pragma: no cover
    logger.warning("[SMS] python-dotenv is not installed; reading OS environment only")


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class SmsError(Exception):
    """Base class for every SMS failure this module knows how to describe."""


class MissingCredentialsError(SmsError):
    """The selected provider has not been fully configured."""


class InvalidPhoneNumberError(SmsError):
    """A destination or sender number was rejected by the provider."""


class ProviderNetworkError(SmsError):
    """The provider could not be reached (DNS, timeout, connection reset)."""


class ProviderApiError(SmsError):
    """The provider was reached but returned an error response."""


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
def _env_str(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = _env_str(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name)
    try:
        return int(float(raw)) if raw else default
    except ValueError:
        logger.warning("[SMS] %s is not a number ('%s'); falling back to %s", name, raw, default)
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env_str(name)
    try:
        return float(raw) if raw else default
    except ValueError:
        logger.warning("[SMS] %s is not a number ('%s'); falling back to %s", name, raw, default)
        return default


def _split_numbers(raw: str) -> list[str]:
    """Split ALERT_PHONE_NUMBERS on commas / semicolons / whitespace."""
    parts = raw.replace(";", ",").replace("\n", ",").split(",")
    return [part.strip() for part in parts if part.strip()]


@dataclass(frozen=True)
class AlertSettings:
    """All alerting configuration, read once and cached."""

    enabled: bool = True
    provider: str = "twilio"
    recipients: list[str] = field(default_factory=list)
    cooldown_minutes: int = 60
    max_alerts_per_batch: int = 10
    batch_summary_enabled: bool = True
    min_confidence: float = 0.0
    test_token: str = ""
    test_cooldown_seconds: int = 300

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Fast2SMS
    fast2sms_api_key: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_ids: list[str] = field(default_factory=list)

    @property
    def cooldown_seconds(self) -> int:
        return max(0, self.cooldown_minutes) * 60

    @property
    def destinations(self) -> list[str]:
        """Where alerts go for the currently selected provider.

        Telegram addresses chat IDs rather than phone numbers, so it reads a
        different variable. Everything else uses ALERT_PHONE_NUMBERS.
        """
        if self.provider == "telegram":
            return self.telegram_chat_ids
        return self.recipients


def _read_settings() -> AlertSettings:
    return AlertSettings(
        enabled=_env_bool("SMS_ALERTS_ENABLED", True),
        provider=_env_str("SMS_PROVIDER", "twilio").lower(),
        recipients=_split_numbers(_env_str("ALERT_PHONE_NUMBERS")),
        cooldown_minutes=_env_int("ALERT_COOLDOWN_MINUTES", 60),
        max_alerts_per_batch=_env_int("MAX_ALERTS_PER_BATCH", 10),
        batch_summary_enabled=_env_bool("BATCH_SUMMARY_ENABLED", True),
        min_confidence=_env_float("ALERT_MIN_CONFIDENCE", 0.0),
        test_token=_env_str("ALERT_TEST_TOKEN"),
        test_cooldown_seconds=_env_int("TEST_ALERT_COOLDOWN_SECONDS", 300),
        twilio_account_sid=_env_str("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=_env_str("TWILIO_AUTH_TOKEN"),
        twilio_phone_number=_env_str("TWILIO_PHONE_NUMBER"),
        fast2sms_api_key=_env_str("FAST2SMS_API_KEY"),
        telegram_bot_token=_env_str("TELEGRAM_BOT_TOKEN"),
        telegram_chat_ids=_split_numbers(_env_str("TELEGRAM_CHAT_IDS")),
    )


_settings_lock = threading.Lock()
_settings: AlertSettings | None = None


def get_settings() -> AlertSettings:
    """Return the cached settings, reading the environment on first use."""
    global _settings
    with _settings_lock:
        if _settings is None:
            _settings = _read_settings()
        return _settings


def reload_settings() -> AlertSettings:
    """Re-read the environment. Used by the test suite; harmless in production."""
    global _settings
    with _settings_lock:
        _settings = _read_settings()
        return _settings


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
class BaseProvider:
    name = "base"

    def __init__(self, settings: AlertSettings) -> None:
        self.settings = settings

    def check_config(self) -> None:
        """Raise MissingCredentialsError when the provider cannot be used."""
        raise NotImplementedError

    def send(self, to_number: str, body: str) -> str:
        """Send one message and return a provider reference id."""
        raise NotImplementedError


class ConsoleProvider(BaseProvider):
    """Writes the message to the log instead of sending it.

    Useful for offline demos and for the automated tests. It is never selected
    by accident: you have to set SMS_PROVIDER=console explicitly.
    """

    name = "console"

    def check_config(self) -> None:
        return None

    def send(self, to_number: str, body: str) -> str:
        logger.info("[SMS] (console provider) message for %s:\n%s", _mask_number(to_number), body)
        return f"console-{int(time.time() * 1000)}"


class TwilioProvider(BaseProvider):
    """Real SMS delivery through Twilio."""

    name = "twilio"

    def check_config(self) -> None:
        missing = [
            key
            for key, value in (
                ("TWILIO_ACCOUNT_SID", self.settings.twilio_account_sid),
                ("TWILIO_AUTH_TOKEN", self.settings.twilio_auth_token),
                ("TWILIO_PHONE_NUMBER", self.settings.twilio_phone_number),
            )
            if not value
        ]
        if missing:
            raise MissingCredentialsError(f"Missing Twilio settings: {', '.join(missing)}")

    def send(self, to_number: str, body: str) -> str:
        self.check_config()

        try:
            from twilio.base.exceptions import TwilioRestException
            from twilio.rest import Client
        except ImportError as exc:
            raise MissingCredentialsError(
                "The 'twilio' package is not installed. Run: pip install twilio"
            ) from exc

        client = Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)

        try:
            message = client.messages.create(
                body=body,
                from_=self.settings.twilio_phone_number,
                to=to_number,
            )
        except TwilioRestException as exc:
            # 21211 invalid 'to', 21212/21606/21612 invalid 'from',
            # 21608 unverified number on a trial account, 21614 not SMS capable.
            if exc.code in {21211, 21212, 21606, 21608, 21610, 21612, 21614}:
                raise InvalidPhoneNumberError(
                    f"Twilio rejected the phone number (code {exc.code}): {scrub(exc.msg)}"
                ) from None
            raise ProviderApiError(f"Twilio API error (code {exc.code}): {scrub(exc.msg)}") from None
        except Exception as exc:  # connection reset, DNS failure, timeout
            # scrub() strips the account SID that Twilio embeds in the request URL.
            raise ProviderNetworkError(f"Could not reach Twilio: {scrub(exc)}") from None

        return str(getattr(message, "sid", "") or "sent")


# The Fast2SMS quick route ('q') is a plain-GSM channel: emoji and other
# non-ASCII characters make it reject the request. Swap them for readable ASCII
# tags rather than dropping them silently.
_ASCII_REPLACEMENTS = {
    "\U0001f6a8": "[ALERT]",
    "\U0001f4ca": "[SUMMARY]",
    "\U0001f4f1": "",
    "✅": "[OK]",
    "⚠️": "[WARNING]",
    "⚠": "[WARNING]",
}


def to_ascii(text: str) -> str:
    """Make a message safe for plain-GSM SMS channels."""
    for symbol, replacement in _ASCII_REPLACEMENTS.items():
        text = text.replace(symbol, replacement)
    return text.encode("ascii", "ignore").decode("ascii").strip()


def _extract_provider_message(payload: Any) -> str:
    """Fast2SMS puts the real reason in 'message', sometimes as a list."""
    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, list):
            return "; ".join(str(item) for item in message)
        if message:
            return str(message)
    return ""


class Fast2SmsProvider(BaseProvider):
    """Optional India-friendly provider. Kept small on purpose.

    Twilio needs DLT sender registration for +91 destinations; Fast2SMS is a
    common workaround for student projects. Enable with SMS_PROVIDER=fast2sms.
    """

    name = "fast2sms"
    endpoint = "https://www.fast2sms.com/dev/bulkV2"

    def check_config(self) -> None:
        if not self.settings.fast2sms_api_key:
            raise MissingCredentialsError("Missing Fast2SMS setting: FAST2SMS_API_KEY")

    def send(self, to_number: str, body: str) -> str:
        self.check_config()

        try:
            import requests
        except ImportError as exc:
            raise MissingCredentialsError(
                "The 'requests' package is not installed. Run: pip install requests"
            ) from exc

        national_number = to_number.replace("+91", "").replace("+", "").strip()
        if not national_number.isdigit() or len(national_number) != 10:
            raise InvalidPhoneNumberError(
                "Fast2SMS needs a 10-digit Indian mobile number without the country code."
            )

        safe_body = to_ascii(body)
        if not safe_body:
            raise ProviderApiError("The message was empty after removing unsupported characters.")

        try:
            response = requests.post(
                self.endpoint,
                headers={"authorization": self.settings.fast2sms_api_key},
                data={
                    "route": "q",
                    "message": safe_body,
                    "numbers": national_number,
                    "flash": "0",
                    "language": "english",
                },
                timeout=15,
            )
        except Exception as exc:
            raise ProviderNetworkError(f"Could not reach Fast2SMS: {scrub(exc)}") from None

        payload: Any = None
        try:
            payload = response.json()
        except ValueError:
            payload = None

        provider_message = _extract_provider_message(payload)

        if response.status_code >= 400:
            # Fast2SMS explains the real problem in the body - surface it,
            # otherwise a bare "HTTP 400" is impossible to debug.
            detail = provider_message or (response.text or "").strip()[:200] or "no detail returned"
            raise ProviderApiError(f"HTTP {response.status_code} from Fast2SMS - {scrub(detail)}")

        if not isinstance(payload, dict) or not payload.get("return", False):
            detail = provider_message or "unknown error"
            raise ProviderApiError(f"Fast2SMS rejected the message - {scrub(detail)}")

        request_id = payload.get("request_id") or "sent"
        return str(request_id)


class TelegramProvider(BaseProvider):
    """Free phone notifications through a Telegram bot.

    No billing, no DLT registration and no character restrictions, so the
    emoji in the alert templates survive. Alerts arrive as ordinary Telegram
    notifications on your phone.

    Setup:
      1. Message @BotFather on Telegram, send /newbot, follow the prompts.
      2. Put the token it gives you in TELEGRAM_BOT_TOKEN.
      3. Send your new bot any message, then run: python get_telegram_chat_id.py
      4. Put the chat id it prints in TELEGRAM_CHAT_IDS.
    """

    name = "telegram"
    api_base = "https://api.telegram.org"

    def check_config(self) -> None:
        missing = []
        if not self.settings.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.settings.telegram_chat_ids:
            missing.append("TELEGRAM_CHAT_IDS")
        if missing:
            raise MissingCredentialsError(f"Missing Telegram settings: {', '.join(missing)}")

    def send(self, to_number: str, body: str) -> str:
        self.check_config()

        try:
            import requests
        except ImportError as exc:
            raise MissingCredentialsError(
                "The 'requests' package is not installed. Run: pip install requests"
            ) from exc

        url = f"{self.api_base}/bot{self.settings.telegram_bot_token}/sendMessage"

        try:
            response = requests.post(
                url,
                json={"chat_id": to_number, "text": body, "disable_web_page_preview": True},
                timeout=15,
            )
        except Exception as exc:
            raise ProviderNetworkError(f"Could not reach Telegram: {scrub(exc)}") from None

        payload: Any = None
        try:
            payload = response.json()
        except ValueError:
            payload = None

        detail = ""
        if isinstance(payload, dict):
            detail = str(payload.get("description") or "")

        if isinstance(payload, dict) and payload.get("ok"):
            result = payload.get("result") or {}
            return str(result.get("message_id") or "sent")

        lowered = detail.lower()
        if "chat not found" in lowered or "chat_id is empty" in lowered:
            raise InvalidPhoneNumberError(
                "Telegram chat not found. Send your bot a message first, then run "
                "get_telegram_chat_id.py to read the correct TELEGRAM_CHAT_IDS value."
            )
        if "unauthorized" in lowered or response.status_code == 401:
            raise MissingCredentialsError(
                "Telegram rejected the bot token. Copy TELEGRAM_BOT_TOKEN again from @BotFather."
            )
        if "bot was blocked" in lowered:
            raise InvalidPhoneNumberError("You have blocked this bot in Telegram. Unblock it and try again.")

        raise ProviderApiError(
            f"HTTP {response.status_code} from Telegram - {scrub(detail or 'no detail returned')}"
        )


class DisabledProvider(BaseProvider):
    name = "disabled"

    def check_config(self) -> None:
        raise MissingCredentialsError("SMS alerting is disabled (SMS_PROVIDER=disabled)")

    def send(self, to_number: str, body: str) -> str:
        raise MissingCredentialsError("SMS alerting is disabled (SMS_PROVIDER=disabled)")


_PROVIDERS: dict[str, type[BaseProvider]] = {
    "twilio": TwilioProvider,
    "fast2sms": Fast2SmsProvider,
    "telegram": TelegramProvider,
    "console": ConsoleProvider,
    "disabled": DisabledProvider,
}


def get_provider(settings: AlertSettings | None = None) -> BaseProvider:
    """Build the provider named by SMS_PROVIDER."""
    settings = settings or get_settings()
    provider_class = _PROVIDERS.get(settings.provider)
    if provider_class is None:
        logger.warning(
            "[SMS] Unknown SMS_PROVIDER '%s'; falling back to 'disabled'. Valid values: %s",
            settings.provider,
            ", ".join(sorted(_PROVIDERS)),
        )
        provider_class = DisabledProvider
    return provider_class(settings)


# --------------------------------------------------------------------------- #
# Message templates
# --------------------------------------------------------------------------- #
def _mask_number(number: str) -> str:
    """Mask a phone number for logging: +919876543210 -> +91******3210."""
    digits = "".join(character for character in number if character.isdigit())
    if len(digits) <= 4:
        return "***"
    return f"{number[:3]}{'*' * 6}{digits[-4:]}"


# Twilio account SIDs look like AC + 32 hex characters.
_SID_PATTERN = re.compile(r"AC[0-9a-fA-F]{32}")
_ACCOUNT_URL_PATTERN = re.compile(r"(/Accounts/)[^/\s]+")

# Telegram bot tokens look like 123456789:AAE...  and appear inside request URLs.
_TELEGRAM_TOKEN_PATTERN = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}")
_TELEGRAM_URL_PATTERN = re.compile(r"(/bot)[^/\s]+")


def scrub(text: Any) -> str:
    """Remove anything secret from a message before logging or returning it.

    Third-party SDKs happily put credentials into their exception text - the
    Twilio request URL, for example, contains the account SID. Every string
    that leaves this module passes through here first.
    """
    message = str(text)
    if not message:
        return message

    settings = _settings  # read the cache directly to avoid recursion
    if settings is not None:
        for secret in (
            settings.twilio_auth_token,
            settings.twilio_account_sid,
            settings.fast2sms_api_key,
            settings.telegram_bot_token,
            settings.test_token,
        ):
            if secret and len(secret) >= 6:
                message = message.replace(secret, "***")
        for number in settings.recipients + settings.telegram_chat_ids + [settings.twilio_phone_number]:
            if number and len(number) >= 6:
                message = message.replace(number, _mask_number(number))

    message = _SID_PATTERN.sub("***", message)
    message = _ACCOUNT_URL_PATTERN.sub(r"\1***", message)
    message = _TELEGRAM_TOKEN_PATTERN.sub("***", message)
    message = _TELEGRAM_URL_PATTERN.sub(r"\1***", message)
    return message


def build_theft_message(meter_id: str | None, confidence: float, timestamp: str, risk: str = "High") -> str:
    return (
        "\U0001f6a8 Electricity Theft Alert\n"
        f"Meter ID: {meter_id or 'N/A'}\n"
        f"Risk: {str(risk).upper()}\n"
        f"Confidence: {float(confidence):.1f}%\n"
        f"Time: {timestamp}\n"
        "Please inspect this meter."
    )


def build_batch_summary_message(total_rows: int, theft_count: int, alerted_count: int, timestamp: str) -> str:
    return (
        "\U0001f4ca Theft Detection Batch Summary\n"
        f"Meters analysed: {total_rows}\n"
        f"Theft detected: {theft_count}\n"
        f"Individual alerts sent: {alerted_count}\n"
        f"Time: {timestamp}\n"
        "Open the dashboard for the full list."
    )


def build_test_message(timestamp: str) -> str:
    return (
        "\u2705 Test Alert\n"
        "Electricity Theft Detection System\n"
        f"Time: {timestamp}\n"
        "SMS notifications are configured correctly."
    )


# --------------------------------------------------------------------------- #
# Core sending
# --------------------------------------------------------------------------- #
def _describe(error: Exception) -> str:
    """Turn an exception into a short, secret-free message for the API/UI."""
    if isinstance(error, MissingCredentialsError):
        message = f"SMS is not configured: {error}"
    elif isinstance(error, InvalidPhoneNumberError):
        message = f"Invalid phone number: {error}"
    elif isinstance(error, ProviderNetworkError):
        message = f"Network failure: {error}"
    elif isinstance(error, ProviderApiError):
        message = f"SMS provider error: {error}"
    else:
        message = f"Unexpected SMS failure: {error}"
    return scrub(message)


def _send_to_all(body: str, settings: AlertSettings) -> dict[str, Any]:
    """Send one message to every configured recipient.

    Returns a summary dict. Never raises.
    """
    if not settings.enabled:
        return {"sent": False, "error": None, "skipped": "alerts_disabled", "recipients": 0}

    destinations = settings.destinations
    if not destinations:
        variable = "TELEGRAM_CHAT_IDS" if settings.provider == "telegram" else "ALERT_PHONE_NUMBERS"
        message = f"SMS is not configured: {variable} is empty"
        logger.error("[SMS] Alert failed: %s", message)
        return {"sent": False, "error": message, "skipped": None, "recipients": 0}

    provider = get_provider(settings)

    try:
        provider.check_config()
    except SmsError as exc:
        message = _describe(exc)
        logger.error("[SMS] Alert failed: %s", message)
        return {"sent": False, "error": message, "skipped": None, "recipients": 0}

    delivered = 0
    failures: list[str] = []

    for number in destinations:
        logger.info("[SMS] Sending alert to %s via %s...", _mask_number(number), provider.name)
        try:
            reference = provider.send(number, body)
            delivered += 1
            logger.info("[SMS] Alert sent successfully (ref %s)", reference)
        except SmsError as exc:
            message = _describe(exc)
            failures.append(message)
            logger.error("[SMS] Alert failed: %s", message)
        except Exception as exc:  # last-resort net: alerting must never bubble up
            message = _describe(exc)
            failures.append(message)
            # Deliberately no traceback: third-party tracebacks can contain
            # credentials. The scrubbed message is logged instead.
            logger.error("[SMS] Alert failed: %s", message)

    return {
        "sent": delivered > 0,
        "error": None if delivered > 0 else (failures[0] if failures else "SMS could not be sent"),
        "skipped": None,
        "recipients": delivered,
        "failures": failures,
    }


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def send_theft_alert(
    meter_id: str | None,
    confidence: float,
    timestamp: str,
    risk: str = "High",
) -> dict[str, Any]:
    """Send a theft alert for one meter, honouring the cooldown window.

    Always returns a dict shaped like:
        {"alert_sent": bool, "alert_error": str | None, "alert_skipped": str | None}
    and never raises, so the caller's prediction response is never at risk.
    """
    try:
        settings = get_settings()
        cooldown_key = str(meter_id) if meter_id else "UNKNOWN_METER"

        if not settings.enabled:
            logger.info("[SMS] Alerting is disabled; skipping meter %s", cooldown_key)
            return _alert_result(False, None, "alerts_disabled")

        if confidence is not None and float(confidence) < settings.min_confidence:
            logger.info(
                "[SMS] Confidence %.1f%% is below ALERT_MIN_CONFIDENCE (%.1f%%); skipping meter %s",
                float(confidence),
                settings.min_confidence,
                cooldown_key,
            )
            return _alert_result(False, None, "below_min_confidence")

        logger.info("[SMS] Theft detected for meter %s", cooldown_key)

        elapsed = seconds_since_last_successful_alert(cooldown_key)
        if elapsed is not None and elapsed < settings.cooldown_seconds:
            remaining_minutes = (settings.cooldown_seconds - elapsed) / 60
            logger.info(
                "[SMS] Cooldown active for meter %s; %.1f minute(s) remaining, no SMS sent",
                cooldown_key,
                remaining_minutes,
            )
            record_alert(
                meter_id=cooldown_key,
                alert_type="theft",
                channel=settings.provider,
                status="cooldown",
                error=None,
                confidence=confidence,
                recipients=0,
            )
            return _alert_result(False, None, "cooldown")

        body = build_theft_message(meter_id, confidence, timestamp, risk=risk)
        outcome = _send_to_all(body, settings)

        record_alert(
            meter_id=cooldown_key,
            alert_type="theft",
            channel=settings.provider,
            status="sent" if outcome["sent"] else "failed",
            error=outcome["error"],
            confidence=confidence,
            recipients=outcome["recipients"],
        )

        return _alert_result(outcome["sent"], outcome["error"], outcome["skipped"])
    except Exception as exc:  # absolute guarantee: alerting cannot break prediction
        message = scrub(f"Unexpected SMS failure: {exc}")
        logger.error("[SMS] Alert failed: %s", message)
        return _alert_result(False, message, None)


def send_batch_summary(total_rows: int, theft_count: int, alerted_count: int, timestamp: str) -> dict[str, Any]:
    """Send one summary SMS after a CSV upload. Never raises."""
    try:
        settings = get_settings()
        if not settings.enabled or not settings.batch_summary_enabled:
            return _alert_result(False, None, "summary_disabled")

        logger.info(
            "[SMS] Sending batch summary: %s rows, %s theft, %s individual alerts",
            total_rows,
            theft_count,
            alerted_count,
        )
        body = build_batch_summary_message(total_rows, theft_count, alerted_count, timestamp)
        outcome = _send_to_all(body, settings)

        record_alert(
            meter_id="__BATCH_SUMMARY__",
            alert_type="batch_summary",
            channel=settings.provider,
            status="sent" if outcome["sent"] else "failed",
            error=outcome["error"],
            confidence=None,
            recipients=outcome["recipients"],
        )
        return _alert_result(outcome["sent"], outcome["error"], outcome["skipped"])
    except Exception as exc:
        message = scrub(f"Unexpected SMS failure: {exc}")
        logger.error("[SMS] Batch summary failed: %s", message)
        return _alert_result(False, message, None)


# In-process guard so /test-alert cannot be hammered.
_last_test_alert_at: float = 0.0
_test_lock = threading.Lock()


def send_test_alert(token: str | None, timestamp: str) -> dict[str, Any]:
    """Send a test SMS. Returns (result dict, http status code) style payload.

    The endpoint is protected two ways:
      1. ALERT_TEST_TOKEN must be set on the server and matched by the caller.
      2. TEST_ALERT_COOLDOWN_SECONDS throttles repeat calls.
    """
    global _last_test_alert_at

    settings = get_settings()

    if not settings.test_token:
        return {
            "success": False,
            "message": "Test endpoint is disabled. Set ALERT_TEST_TOKEN in backend/.env to enable it.",
            "status_code": 503,
        }

    if not token or token != settings.test_token:
        logger.warning("[SMS] Test alert rejected: invalid or missing token")
        return {"success": False, "message": "Invalid or missing alert test token.", "status_code": 401}

    with _test_lock:
        elapsed = time.monotonic() - _last_test_alert_at
        if _last_test_alert_at and elapsed < settings.test_cooldown_seconds:
            wait_seconds = int(settings.test_cooldown_seconds - elapsed)
            logger.info("[SMS] Test alert throttled; %s second(s) remaining", wait_seconds)
            return {
                "success": False,
                "message": f"Test alerts are throttled. Try again in {wait_seconds} second(s).",
                "status_code": 429,
            }
        _last_test_alert_at = time.monotonic()

    logger.info("[SMS] Sending test alert...")
    outcome = _send_to_all(build_test_message(timestamp), settings)

    record_alert(
        meter_id="__TEST__",
        alert_type="test",
        channel=settings.provider,
        status="sent" if outcome["sent"] else "failed",
        error=outcome["error"],
        confidence=None,
        recipients=outcome["recipients"],
    )

    if outcome["sent"]:
        logger.info("[SMS] Test alert sent successfully")
        return {"success": True, "message": "Test SMS sent successfully", "status_code": 200}

    logger.error("[SMS] Test alert failed: %s", outcome["error"])
    return {"success": False, "message": outcome["error"] or "Test SMS failed", "status_code": 502}


def reset_test_throttle() -> None:
    """Clear the /test-alert throttle. Used by the automated tests only."""
    global _last_test_alert_at
    with _test_lock:
        _last_test_alert_at = 0.0


def get_alert_status() -> dict[str, Any]:
    """Report configuration health for the UI.

    Deliberately returns booleans and counts only: no tokens, no SIDs, and no
    phone numbers ever leave the backend.
    """
    settings = get_settings()
    provider = get_provider(settings)

    configured = True
    configuration_error: str | None = None
    try:
        provider.check_config()
    except SmsError as exc:
        configured = False
        configuration_error = scrub(exc)

    return {
        "enabled": settings.enabled,
        "provider": settings.provider,
        "provider_configured": configured,
        "configuration_error": configuration_error,
        "recipients_configured": len(settings.destinations),
        "sender_configured": bool(settings.twilio_phone_number) if settings.provider == "twilio" else True,
        "cooldown_minutes": settings.cooldown_minutes,
        "max_alerts_per_batch": settings.max_alerts_per_batch,
        "batch_summary_enabled": settings.batch_summary_enabled,
        "min_confidence": settings.min_confidence,
        "test_endpoint_enabled": bool(settings.test_token),
        "ready": settings.enabled and configured and bool(settings.destinations),
    }


def _alert_result(sent: bool, error: str | None, skipped: str | None) -> dict[str, Any]:
    return {"alert_sent": bool(sent), "alert_error": error, "alert_skipped": skipped}
