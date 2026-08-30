"""API endpoints for the AI assistant.

Own Blueprint, like transformer_routes.py, so routes.py stays untouched.
Registered from app.py via register_agent_routes(app).
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Flask, jsonify, request

import ai_agent


logger = logging.getLogger(__name__)
agent_bp = Blueprint("agent", __name__)

MAX_QUESTION_CHARS = 1000
MAX_HISTORY_TURNS = 12


@agent_bp.get("/agent/status")
def agent_status() -> Any:
    """Which provider is live and which model is loaded.

    Returns provider and model names only - never a key, host credential or
    anything else that should stay on the server.
    """
    try:
        return jsonify(ai_agent.get_status())
    except Exception as exc:
        logger.exception("Agent status check failed")
        return jsonify({"enabled": False, "provider": "error", "message": str(exc)}), 500


@agent_bp.get("/agent/suggestions")
def agent_suggestions() -> Any:
    """Starter questions for the empty chat screen."""
    return jsonify({"suggestions": ai_agent.SUGGESTED_QUESTIONS})


@agent_bp.post("/agent/ask")
def agent_ask() -> Any:
    """Answer one question against the live database."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid input", "message": "Send a JSON body."}), 400

    question = str(payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Invalid input", "message": "'question' is required."}), 400
    if len(question) > MAX_QUESTION_CHARS:
        return jsonify(
            {"error": "Invalid input",
             "message": f"Question is too long (max {MAX_QUESTION_CHARS} characters)."}
        ), 400

    raw_history = payload.get("history")
    history: list[dict[str, str]] = []
    if isinstance(raw_history, list):
        for turn in raw_history[-MAX_HISTORY_TURNS:]:
            if isinstance(turn, dict) and turn.get("role") in {"user", "assistant"}:
                history.append(
                    {"role": turn["role"], "content": str(turn.get("content") or "")[:2000]}
                )

    try:
        result = ai_agent.ask(question, history)
        return jsonify(result)
    except Exception as exc:
        logger.exception("Agent question failed")
        return jsonify({"error": "Agent error", "message": str(exc)}), 500


def register_agent_routes(app: Flask) -> None:
    """Register the assistant blueprint."""
    app.register_blueprint(agent_bp)
