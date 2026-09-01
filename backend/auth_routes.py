"""Authentication endpoints.

Own Blueprint, so no existing route file is touched and no existing API
contract changes. The detection endpoints keep working exactly as before.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any

from flask import Blueprint, Flask, g, jsonify, request

import auth_store


logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


def _bearer() -> str:
    header = request.headers.get("Authorization", "")
    return header[7:].strip() if header.lower().startswith("bearer ") else ""


def require_auth(view):
    """Guard a route. Available for future use — no existing route uses it yet,
    because retrofitting it onto all 29 endpoints is a separate change with real
    breakage risk. Authentication currently gates the user interface."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        user = auth_store.user_for_token(_bearer())
        if user is None:
            return jsonify({"error": "Unauthorised", "message": "Sign in to continue."}), 401
        g.user = user
        return view(*args, **kwargs)

    return wrapper


@auth_bp.post("/auth/signup")
def signup() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        result = auth_store.signup(
            payload.get("full_name"), payload.get("email"), payload.get("password")
        )
        return jsonify(result), 201
    except auth_store.AuthError as exc:
        return jsonify({"error": "Sign up failed", "message": str(exc)}), exc.status
    except Exception as exc:
        logger.exception("Sign up failed")
        return jsonify({"error": "Sign up failed", "message": str(exc)}), 500


@auth_bp.post("/auth/login")
def login() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        result = auth_store.login(
            payload.get("email"), payload.get("password"), bool(payload.get("remember"))
        )
        return jsonify(result)
    except auth_store.AuthError as exc:
        return jsonify({"error": "Sign in failed", "message": str(exc)}), exc.status
    except Exception as exc:
        logger.exception("Sign in failed")
        return jsonify({"error": "Sign in failed", "message": str(exc)}), 500


@auth_bp.post("/auth/logout")
def logout() -> Any:
    auth_store.logout(_bearer())
    # Always 200: signing out must succeed even if the token had already expired.
    return jsonify({"message": "Signed out."})


@auth_bp.get("/auth/me")
def me() -> Any:
    user = auth_store.user_for_token(_bearer())
    if user is None:
        return jsonify({"error": "Unauthorised", "message": "Not signed in."}), 401
    return jsonify({"user": user})


@auth_bp.get("/auth/status")
def status() -> Any:
    """Whether accounts exist yet. Lets the sign-in screen say 'create the first
    account' instead of showing an empty login form on a fresh install."""
    return jsonify({"enabled": True, "accounts": auth_store.account_count()})


def register_auth_routes(app: Flask) -> None:
    auth_store.init_auth_tables()
    app.register_blueprint(auth_bp)
