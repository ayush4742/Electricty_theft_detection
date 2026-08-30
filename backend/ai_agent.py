"""The AI assistant: a tool-calling agent over the theft-detection database.

HOW IT WORKS
------------
    question -> model picks a tool -> we run it on the real DB -> model reads the
    result -> model either picks another tool or writes the final answer

The model never sees the database directly and is told, firmly, that it may not
state a number it did not receive from a tool. That is what stops it inventing
confident nonsense.

PROVIDERS
---------
    ollama   Local model on the user's own machine (default). Free, offline,
             nothing leaves the laptop - which matters when the data is
             consumer billing records.
    rules    No language model at all: keyword routing straight to a tool, with
             a templated answer. Always available, and used automatically when
             Ollama is not running so a demo never dies on stage.
    disabled Assistant switched off.

Set AI_PROVIDER in backend/.env.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

import agent_tools


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

try:  # pragma: no cover - trivial import guard
    from dotenv import load_dotenv

    load_dotenv(ENV_PATH)
except ImportError:  # pragma: no cover
    logger.warning("[AGENT] python-dotenv is not installed; reading OS environment only")


# Models known to handle function calling well, best first. The first one the
# user actually has installed wins.
PREFERRED_MODELS = [
    "qwen2.5:7b", "qwen2.5", "llama3.1:8b", "llama3.1", "llama3.2",
    "mistral-nemo", "mistral", "firefunction-v2", "command-r",
]

# Kept deliberately short. Every token here is re-read by the model on EVERY
# tool-calling round, and on a small CPU-only model prompt processing is the
# single biggest cost. Trimming this from ~250 tokens to ~90 roughly halves the
# time to first answer on a 3B model.
SYSTEM_PROMPT = """You are the assistant in an electricity theft detection system for a power utility.

Rules:
1. Never state a number, transformer id or meter id unless a tool returned it. Call a tool instead of guessing.
2. Answer in 2-4 short sentences: the direct answer first, then the numbers.
3. Say "flagged for inspection", never "is stealing" - only a field visit confirms theft.
4. Reply in the user's language (English, Hindi or Hinglish)."""

# Keep the model resident in RAM between questions. Ollama unloads after 5
# minutes by default, and reloading a model from disk costs 20-60 seconds on a
# laptop - which is most of what made the first answer time out.
KEEP_ALIVE = "30m"

# Cap how much of a tool result goes back into the prompt. The full result can
# be 6 KB, and every character of it is re-read by the model on the next round.
MAX_TOOL_RESULT_CHARS = 1500


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
def _env_str(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name)
    try:
        return int(float(raw)) if raw else default
    except ValueError:
        logger.warning("[AGENT] %s is not a number ('%s'); using %s", name, raw, default)
        return default


@dataclass(frozen=True)
class AgentSettings:
    provider: str
    ollama_host: str
    ollama_model: str
    max_steps: int
    timeout: int


def get_settings() -> AgentSettings:
    provider = _env_str("AI_PROVIDER", "ollama").lower()
    if provider not in {"ollama", "rules", "disabled"}:
        logger.warning("[AGENT] unknown AI_PROVIDER '%s'; falling back to 'ollama'", provider)
        provider = "ollama"
    return AgentSettings(
        provider=provider,
        ollama_host=_env_str("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
        ollama_model=_env_str("OLLAMA_MODEL", ""),
        # 3 rounds is enough for pick-tool then answer, with one spare. Every
        # extra round is another full prompt re-read on a slow local model.
        max_steps=max(1, min(8, _env_int("AGENT_MAX_STEPS", 3))),
        # Generous, because a small model on CPU genuinely takes this long the
        # first time. The rules engine still answers instantly if it is exceeded.
        timeout=max(5, min(900, _env_int("AGENT_TIMEOUT_SECONDS", 300))),
    )


# --------------------------------------------------------------------------- #
# Ollama
# --------------------------------------------------------------------------- #
def list_ollama_models(settings: AgentSettings) -> list[str]:
    """Model names installed locally. Empty list means Ollama is not reachable."""
    try:
        response = requests.get(f"{settings.ollama_host}/api/tags", timeout=4)
        response.raise_for_status()
        return [model.get("name", "") for model in response.json().get("models", [])]
    except Exception as exc:
        logger.info("[AGENT] Ollama not reachable at %s (%s)", settings.ollama_host, exc)
        return []


def pick_model(settings: AgentSettings, available: list[str]) -> str | None:
    """Choose which local model to drive the agent with."""
    if not available:
        return None

    # An explicit OLLAMA_MODEL wins if it is actually installed.
    if settings.ollama_model:
        for name in available:
            if name == settings.ollama_model or name.startswith(f"{settings.ollama_model}:"):
                return name
        logger.warning(
            "[AGENT] OLLAMA_MODEL='%s' is not installed. Installed: %s",
            settings.ollama_model, ", ".join(available),
        )

    for preferred in PREFERRED_MODELS:
        for name in available:
            if name == preferred or name.startswith(f"{preferred}:"):
                return name

    # Nothing recognised - use whatever is there and hope it supports tools.
    # If it does not, _run_ollama falls back to the rules engine anyway.
    return available[0]


# model name -> "loading" | "ready". Lets the UI say "model is loading" instead
# of leaving the user staring at a spinner for the first minute.
_warm_state: dict[str, str] = {}


def warm_model(settings: AgentSettings, model: str) -> None:
    """Load the model into RAM in the background so the first question is fast.

    Ollama only pulls a model off disk when it is first used, which on a laptop
    takes 20-60 seconds. Doing that lazily meant the user's very first question
    paid the whole cost and often timed out. Instead we fire a one-token request
    the moment the UI asks for status - by the time anyone has read the page and
    typed a question, the model is resident.

    Runs in a daemon thread and swallows every error: warming is an
    optimisation, never a reason for a request to fail.
    """
    if model in _warm_state:
        return
    _warm_state[model] = "loading"

    def _warm() -> None:
        try:
            requests.post(
                f"{settings.ollama_host}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "keep_alive": KEEP_ALIVE,
                    "options": {"num_predict": 1},
                },
                timeout=settings.timeout,
            )
            _warm_state[model] = "ready"
            logger.info("[AGENT] model '%s' warmed and resident for %s", model, KEEP_ALIVE)
        except Exception as exc:
            logger.info("[AGENT] warm-up of '%s' did not finish (%s)", model, exc)
            _warm_state.pop(model, None)

    threading.Thread(target=_warm, daemon=True, name=f"warm-{model}").start()


def _tool_content(result: dict[str, Any]) -> str:
    """Serialise a tool result for the model, small enough to stay fast.

    Long lists are the only thing that ever blows the budget, so those are
    shortened by dropping trailing items rather than by cutting the JSON in
    half. The model is told how many were dropped, so it can say "showing 5 of
    40" instead of silently presenting a truncated list as the whole answer.
    """
    text = json.dumps(result, default=str)
    if len(text) <= MAX_TOOL_RESULT_CHARS:
        return text

    trimmed = dict(result)
    for key, value in result.items():
        if isinstance(value, list) and len(value) > 3:
            trimmed[key] = value[:3]
            trimmed[f"{key}_note"] = f"showing first 3 of {len(value)}"
    text = json.dumps(trimmed, default=str)

    if len(text) > MAX_TOOL_RESULT_CHARS:
        text = text[:MAX_TOOL_RESULT_CHARS] + ' ...(result truncated)"}'
    return text


def _parse_tool_calls(message: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Pull tool calls out of an Ollama response message."""
    calls = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        name = function.get("name")
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        if name:
            calls.append((name, arguments if isinstance(arguments, dict) else {}))
    return calls


def _run_ollama(question: str, history: list[dict[str, str]], settings: AgentSettings,
                model: str) -> dict[str, Any]:
    """One agent turn: let the model call tools until it has an answer."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history[-6:]:
        role = turn.get("role")
        content = str(turn.get("content") or "")[:2000]
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})

    tools_used: list[dict[str, Any]] = []

    for step in range(settings.max_steps):
        response = requests.post(
            f"{settings.ollama_host}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "tools": agent_tools.get_tool_schemas(),
                "stream": False,
                "keep_alive": KEEP_ALIVE,
                "options": {
                    "temperature": 0.2,
                    # The answer is 2-4 sentences, so there is no reason to let
                    # a slow local model ramble for 2000 tokens.
                    "num_predict": 400,
                },
            },
            timeout=settings.timeout,
        )
        response.raise_for_status()
        message = response.json().get("message") or {}
        calls = _parse_tool_calls(message)

        if not calls:
            answer = str(message.get("content") or "").strip()
            if not answer:
                raise RuntimeError("model returned an empty answer")
            return {
                "answer": answer,
                "tools_used": tools_used,
                "steps": step + 1,
                "grounded": bool(tools_used),
            }

        messages.append(
            {
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": message.get("tool_calls"),
            }
        )

        for name, arguments in calls:
            result = agent_tools.run_tool(name, arguments)
            tools_used.append({"tool": name, "arguments": arguments})
            logger.info("[AGENT] step %s called %s(%s)", step + 1, name, arguments)
            messages.append({"role": "tool", "name": name, "content": _tool_content(result)})

    # Ran out of steps. Answer from whatever the tools returned rather than
    # leaving the user with nothing.
    return {
        "answer": (
            "I gathered the data but could not finish composing an answer in the step "
            "budget. Here is what the tools returned: "
            + ", ".join(call["tool"] for call in tools_used)
            + ". Try asking something more specific."
        ),
        "tools_used": tools_used,
        "steps": settings.max_steps,
        "grounded": bool(tools_used),
    }


# --------------------------------------------------------------------------- #
# Rules engine - the no-LLM fallback
#
# Not a toy. It routes on keywords, runs the same real tools, and formats the
# result. When Ollama is not running this is what answers, so a live demo never
# depends on a model being loaded.
# --------------------------------------------------------------------------- #
def _rupees(value: Any) -> str:
    amount = float(value or 0)
    if amount >= 10_000_000:
        return f"Rs {amount / 10_000_000:.2f} crore"
    if amount >= 100_000:
        return f"Rs {amount / 100_000:.2f} lakh"
    return f"Rs {amount:,.0f}"


def _route(question: str) -> tuple[str, dict[str, Any]]:
    """Pick a tool from the wording of the question."""
    text = question.lower()

    transformer_match = re.search(r"\bdt[-\s]?(\d{1,3})\b", text)
    if transformer_match:
        return "transformer_detail", {"transformer_id": f"DT-{int(transformer_match.group(1)):03d}"}

    meter_match = re.search(r"\b([0-9a-f]{20,})\b", question, re.IGNORECASE)
    if meter_match:
        return "meter_lookup", {"meter_id": meter_match.group(1)}
    meter_match = re.search(r"\b(MTR\d{4,})\b", question, re.IGNORECASE)
    if meter_match:
        return "meter_lookup", {"meter_id": meter_match.group(1).upper()}

    if any(word in text for word in ("what is", "what are", "explain", "why", "kya hai", "kyun",
                                     "samjha", "meaning", "define", "how does")):
        return "explain_concept", {"topic": question}

    if any(word in text for word in ("alert", "sms", "notification", "telegram")):
        return "alert_summary", {}

    if any(word in text for word in ("model", "prediction", "accuracy", "how many predict",
                                     "kitne predict", "flag rate")):
        return "prediction_stats", {}

    # "Which is worst / where do we inspect" questions. Whether the answer is a
    # list of transformers or a list of meters depends on which noun the user
    # actually used - checking the superlative first and the noun second is what
    # keeps "kaunsa transformer sabse zyada kharab hai" out of the meter branch.
    superlative = any(
        word in text
        for word in ("worst", "highest", "most", "top", "biggest", "critical", "priority",
                     "inspect", "check first", "sabse", "zyada", "kharab", "problem")
    )
    asks_which = any(word in text for word in ("which", "what", "who", "kaun", "konsa", "kaunsa"))

    about_meter = any(word in text for word in ("meter", "consumer", "customer", "household",
                                                "ghar", "user"))
    about_transformer = any(word in text for word in ("transformer", "dt-", " dt ", "feeder",
                                                      "area", "zone", "cluster"))

    if about_meter and not about_transformer and (superlative or asks_which):
        return "high_priority_meters", {"limit": 5}

    if about_transformer and (superlative or asks_which):
        return "worst_transformers", {"limit": 5}

    if any(word in text for word in ("who is steal", "chori kaun", "steal")) and about_meter:
        return "high_priority_meters", {"limit": 5}

    if superlative:
        # Ambiguous, so answer at the transformer level - it is the level a
        # utility acts on first, and the reply names the meters underneath.
        return "worst_transformers", {"limit": 5}

    return "network_overview", {}


def _format(tool: str, data: dict[str, Any]) -> str:
    """Turn a tool result into a readable answer without a language model."""
    if data.get("error"):
        return str(data["error"])

    if tool == "network_overview":
        return (
            f"The network has {data['transformers_monitored']} transformers covering "
            f"{data['consumer_meters']:,} meters. {data['critical_transformers']} are critical and "
            f"{data['watch_transformers']} are on the watch list. Average loss is "
            f"{data['average_loss_percent']}% against a {data['technical_loss_limit_percent']}% "
            f"technical limit, which is about {_rupees(data['estimated_monthly_revenue_loss_rupees'])} "
            f"a month of unbilled energy."
        )

    if tool == "worst_transformers":
        rows = data.get("transformers") or []
        if not rows:
            return "No transformer data yet. Run seed_transformers.py in the backend folder."
        top = rows[0]
        lines = [
            f"{top['transformer_id']} in {top['area']} is the worst: {top['loss_percent']}% loss, "
            f"over the limit on {top['days_above_limit']} days, costing about "
            f"{_rupees(top['monthly_revenue_loss_rupees'])} a month."
        ]
        if len(rows) > 1:
            others = ", ".join(f"{r['transformer_id']} ({r['loss_percent']}%)" for r in rows[1:])
            lines.append(f"Next worst: {others}.")
        return " ".join(lines)

    if tool == "transformer_detail":
        base = (
            f"{data['transformer_id']} ({data['area']}) is {data['status']} with "
            f"{data['loss_percent']}% loss. It supplied {data['units_supplied']:,.0f} units but only "
            f"{data['units_billed']:,.0f} were billed, leaving {data['units_unaccounted']:,.0f} "
            f"unaccounted across {data['total_meters']} meters. It breached the limit on "
            f"{data['days_above_limit']} days and the trend is {data['trend']}."
        )
        high = data.get("high_priority_meters") or []
        if high:
            base += (
                f" {len(high)} meters here are high priority for inspection, starting with "
                f"{high[0]['meter_id']}."
            )
        return base

    if tool == "high_priority_meters":
        rows = data.get("meters") or []
        if not rows:
            return (
                "No high-priority meters right now. That happens when the flagged meters sit under "
                "transformers whose energy balance is healthy, which usually means they are false "
                "positives."
            )
        top = rows[0]
        listed = ", ".join(f"{r['meter_id'][:12]} ({r['priority']})" for r in rows[:5])
        return (
            f"{data['count']} meters are worth inspecting. Top of the list is {top['meter_id']} on "
            f"{top['transformer_id']} in {top['area']}: the model is {top['model_confidence_percent']}% "
            f"confident and that transformer is losing {top['transformer_loss_percent']}%. "
            f"Full shortlist: {listed}."
        )

    if tool == "meter_lookup":
        parts = [f"Meter {data['meter_id']}: the model says {data.get('model_prediction')}"]
        if data.get("model_confidence") is not None:
            parts.append(f" at {data['model_confidence']}% confidence")
        if data.get("transformer_id"):
            parts.append(f", fed by {data['transformer_id']}")
        if data.get("transformer_loss_percent") is not None:
            parts.append(
                f" which is losing {data['transformer_loss_percent']}% "
                f"({data.get('transformer_status')})"
            )
        if data.get("priority"):
            parts.append(f". Combined priority: {data['priority']} ({data['priority_score']})")
        return "".join(parts) + "."

    if tool == "prediction_stats":
        return (
            f"The model has scored {data['total_predictions']} meters. "
            f"{data['theft_predictions']} were flagged as theft and {data['normal_predictions']} as "
            f"normal - a flag rate of {data['theft_rate_percent']}%."
        )

    if tool == "alert_summary":
        return (
            f"{data['alerts_sent']} alerts were sent, {data['alerts_failed']} failed, and "
            f"{data['alerts_suppressed_by_cooldown']} were suppressed by the cooldown to avoid "
            f"texting the same meter repeatedly."
        )

    if tool == "explain_concept":
        if data.get("explanation"):
            return data["explanation"]
        topics = ", ".join(data.get("available_topics") or [])
        return (
            "I do not have a curated explanation for that. I can explain any of these: "
            f"{topics}."
        )

    return json.dumps(data, default=str)[:1500]


def _run_rules(question: str) -> dict[str, Any]:
    tool, arguments = _route(question)
    data = agent_tools.run_tool(tool, arguments)
    return {
        "answer": _format(tool, data),
        "tools_used": [{"tool": tool, "arguments": arguments}],
        "steps": 1,
        "grounded": True,
    }


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #
def get_status() -> dict[str, Any]:
    """What the assistant can currently do. Safe to expose to the browser -
    no credentials, only provider names and model names."""
    settings = get_settings()

    if settings.provider == "disabled":
        return {
            "enabled": False, "provider": "disabled", "model": None,
            "message": "The assistant is switched off (AI_PROVIDER=disabled in backend/.env).",
        }

    if settings.provider == "rules":
        return {
            "enabled": True, "provider": "rules", "model": None,
            "message": "Running on the built-in rules engine. Answers come straight from the database.",
        }

    available = list_ollama_models(settings)
    model = pick_model(settings, available)
    if model:
        # Start loading it now, while the user is still reading the page.
        warm_model(settings, model)
        ready = _warm_state.get(model) == "ready"
        return {
            "enabled": True, "provider": "ollama", "model": model,
            "installed_models": available,
            "model_ready": ready,
            "message": (
                f"Local model '{model}' via Ollama. Nothing leaves this machine."
                if ready
                else f"Loading '{model}' into memory. The first answer may take a minute."
            ),
        }

    return {
        "enabled": True, "provider": "rules", "model": None,
        "fallback_reason": f"Ollama is not reachable at {settings.ollama_host}.",
        "message": (
            "Ollama is not running, so the built-in rules engine is answering. Answers are still "
            "read from the real database. Start Ollama and pull a model "
            "(ollama pull qwen2.5) for full natural-language answers."
        ),
    }


def ask(question: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Answer one question. Never raises - always returns something usable."""
    question = str(question or "").strip()
    if not question:
        return {"answer": "Ask me something about the network, a transformer, or a meter.",
                "provider": "none", "tools_used": [], "grounded": False}

    settings = get_settings()

    if settings.provider == "disabled":
        return {
            "answer": "The assistant is switched off. Set AI_PROVIDER=ollama or rules in backend/.env.",
            "provider": "disabled", "tools_used": [], "grounded": False,
        }

    if settings.provider == "ollama":
        model = pick_model(settings, list_ollama_models(settings))
        if model:
            try:
                result = _run_ollama(question, history or [], settings, model)
                result.update({"provider": "ollama", "model": model})
                return result
            except Exception as exc:
                # A missing model, a model without tool support, a timeout - none
                # of these should leave the user staring at an error.
                logger.warning("[AGENT] Ollama failed (%s); using the rules engine", exc)
                result = _run_rules(question)
                result.update(
                    {"provider": "rules", "model": None,
                     "fallback_reason": f"Ollama failed: {exc}"}
                )
                return result

        result = _run_rules(question)
        result.update(
            {"provider": "rules", "model": None,
             "fallback_reason": f"Ollama is not reachable at {settings.ollama_host}."}
        )
        return result

    result = _run_rules(question)
    result.update({"provider": "rules", "model": None})
    return result


SUGGESTED_QUESTIONS = [
    "How is the network doing overall?",
    "Which transformer has the highest loss?",
    "Tell me about DT-015",
    "Which meters should we inspect first?",
    "What is energy balance and why does it matter?",
    "Why do we check persistence instead of a single day?",
    "How many meters has the model checked so far?",
    "What is the difference between technical and commercial loss?",
]
