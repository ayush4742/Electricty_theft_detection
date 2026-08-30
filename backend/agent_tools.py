"""Tools the AI assistant is allowed to call.

WHY TOOLS INSTEAD OF STUFFING DATA INTO THE PROMPT
--------------------------------------------------
A language model does not know anything about this utility. If we simply ask it
"which transformer is worst?", it will invent a plausible-sounding answer -
confident, well-written, and completely made up. That is the single most common
way an "AI feature" in a student project becomes worse than useless.

So the model is never allowed to state a number from memory. It gets a list of
functions, decides which one answers the question, and we run that function
against the real SQLite database. The model's only job is to pick the right
tool and phrase the result in plain language. Every figure it prints came out of
a query.

Each tool below has:
  * a JSON schema, so the model knows what it does and what arguments it takes
  * a plain Python implementation that hits the real database

Adding a new capability means adding one function and one schema entry - the
agent loop itself never changes.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import energy_balance
import transformer_db
from database import get_alert_counts, get_dashboard_stats, get_prediction_history


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Domain knowledge
#
# Curated, checkable explanations. Kept here rather than left to the model so
# the definitions stay consistent and correct every time they are asked for.
# --------------------------------------------------------------------------- #
KNOWLEDGE: dict[str, str] = {
    "energy balance": (
        "Energy balance compares the energy a distribution transformer SUPPLIES with the "
        "energy BILLED to all the consumer meters connected under it. The difference is "
        "distribution loss. It works because energy is conserved: whatever left the "
        "transformer either reached a billed meter, was lost as heat in the wires, or was "
        "taken without being metered."
    ),
    "technical loss": (
        "Technical loss is energy lost to physics rather than to people: resistive heating "
        "in conductors (I squared R), transformer core and winding losses, and losses in "
        "joints. It cannot be eliminated, only reduced with thicker conductors, shorter LT "
        "lines and better load balancing. In a healthy Indian LT network it is roughly "
        "4-8 percent. This system treats 8 percent as the normal ceiling."
    ),
    "commercial loss": (
        "Commercial loss is energy that physically reached someone but was never billed: "
        "meter tampering, bypassed or stopped meters, direct hooking onto the LT line, "
        "unmetered connections, and billing or meter-reading errors. Unlike technical loss "
        "it is a people problem, and it is what this project tries to find."
    ),
    "at&c losses": (
        "AT&C stands for Aggregate Technical and Commercial losses - the headline number "
        "Indian DISCOMs are judged on. It combines energy lost in the network with energy "
        "that was billed but never collected, so it captures both theft and poor revenue "
        "recovery in one figure."
    ),
    "distribution transformer": (
        "A distribution transformer (DT) steps 11 kV down to 415/230 V for consumers. "
        "Typically 50 to 200 households sit under one DT. Because it is the point where a "
        "cluster of consumers can be measured together, it is the natural place to run an "
        "energy balance."
    ),
    "persistence": (
        "Persistence means a transformer is only escalated when its loss stays high across "
        "most days of the window, not just one or two. A single bad day is usually a "
        "missing meter reading, an estimated bill, or a communication failure - not theft. "
        "This system requires the loss to breach the limit on at least 60 percent of the "
        "days analysed before calling a transformer CRITICAL. It is the main reason the "
        "alert list stays short enough for a real inspection team to act on."
    ),
    "theft detection methods": (
        "Utilities detect theft three ways, and a good system uses all three. First, "
        "consumption analytics: a model looks for meters whose usage pattern breaks - sudden "
        "sustained drops, night-time flatlines, consumption that does not match connected "
        "load. Second, energy balance at the transformer, which proves energy is actually "
        "missing from a cluster. Third, field inspection, which confirms or clears the case. "
        "Analytics alone produces too many false alarms; balance alone cannot say which "
        "household is responsible."
    ),
    "class imbalance": (
        "Only about 1 to 5 percent of consumers steal, so a model that predicts 'Normal' for "
        "everyone still scores 95+ percent accuracy while catching nothing. Accuracy is "
        "therefore a meaningless metric here. Use precision at K (of the top 100 flagged, "
        "how many were genuine), recall, and PR-AUC instead, and weigh them against the cost "
        "of an inspection versus the revenue recovered."
    ),
    "precision at k": (
        "Precision at K asks: of the K meters we actually sent an inspector to, how many "
        "turned out to be theft? It is the metric that matters operationally, because an "
        "inspection team has a fixed capacity per day. A model with lower overall recall but "
        "higher precision at 100 is more useful than the reverse."
    ),
    "shap": (
        "SHAP explains an individual prediction by attributing it across the input features - "
        "which readings pushed this meter towards 'Theft' and by how much. It matters here "
        "because accusing a consumer of theft is a legal action: the inspector needs to see "
        "the reason, not just a score."
    ),
    "priority score": (
        "The priority score blends two independent signals. The ML model gives a per-meter "
        "confidence from its consumption pattern. The energy balance gives a per-transformer "
        "score from how much energy is actually unaccounted for. Each contributes half. A "
        "meter the model dislikes, sitting under a transformer that is provably losing "
        "energy, is a far stronger case than either signal alone - and a model hit under a "
        "perfectly balanced transformer is likely a false positive worth deprioritising."
    ),
    "false positive": (
        "A false positive is a meter flagged as theft that turns out to be innocent. They are "
        "expensive: a wasted inspection visit, and an accusation against a paying customer. "
        "Common innocent causes are a house left vacant, a genuine change in occupancy, "
        "seasonal usage, a faulty meter, or an estimated reading. Persistence checks and the "
        "transformer cross-check exist to cut them down."
    ),
}


# --------------------------------------------------------------------------- #
# Tool implementations - every one of these reads the real database
# --------------------------------------------------------------------------- #
def network_overview(days: int = 30) -> dict[str, Any]:
    """Headline health of the whole distribution network."""
    kpis = energy_balance.get_network_kpis(days)
    return {
        "transformers_monitored": kpis["total_transformers"],
        "consumer_meters": kpis["total_meters"],
        "critical_transformers": kpis["critical_count"],
        "watch_transformers": kpis["watch_count"],
        "normal_transformers": kpis["normal_count"],
        "average_loss_percent": kpis["avg_loss_pct"],
        "technical_loss_limit_percent": kpis["technical_loss_threshold"],
        "units_unaccounted": kpis["total_loss_units"],
        "estimated_monthly_revenue_loss_rupees": kpis["estimated_monthly_revenue_loss"],
        "transformers_getting_worse": kpis["worsening_count"],
        "days_analysed": kpis["days_analysed"],
    }


def worst_transformers(limit: int = 5, days: int = 30) -> dict[str, Any]:
    """The transformers with the highest unaccounted energy - the inspection queue."""
    limit = max(1, min(25, int(limit or 5)))
    rows = energy_balance.get_network_summary(days)[:limit]
    return {
        "count": len(rows),
        "transformers": [
            {
                "transformer_id": row["transformer_id"],
                "area": row["area"],
                "loss_percent": row["loss_pct"],
                "status": row["status"],
                "days_above_limit": f"{row['days_above_threshold']}/{row['days_monitored']}",
                "persistent": row["persistent"],
                "trend": row["trend"],
                "meters": row["meter_count"],
                "monthly_revenue_loss_rupees": row["estimated_monthly_revenue_loss"],
            }
            for row in rows
        ],
    }


def transformer_detail(transformer_id: str, days: int = 30) -> dict[str, Any]:
    """Everything known about one transformer, including its flagged meters."""
    transformer_id = str(transformer_id or "").strip().upper()
    summary = energy_balance.get_transformer_summary(transformer_id, days)
    if summary is None:
        known = [row["transformer_id"] for row in transformer_db.list_transformers()]
        return {
            "error": f"No transformer with id '{transformer_id}'.",
            "known_transformer_ids": known[:30],
        }

    flagged = []
    for meter in transformer_db.get_flagged_meters_for_transformer(transformer_id):
        confidence = float(meter.get("confidence") or 0.0)
        if confidence > 1.0:
            confidence = confidence / 100.0
        scored = energy_balance.combined_priority(
            confidence, summary["loss_pct"], summary["persistent"]
        )
        flagged.append(
            {
                "meter_id": meter["meter_id"],
                "model_says": meter["prediction"],
                "priority": scored["priority"],
                "priority_score": scored["priority_score"],
            }
        )
    flagged.sort(key=lambda row: row["priority_score"], reverse=True)

    return {
        "transformer_id": summary["transformer_id"],
        "name": summary["name"],
        "area": summary["area"],
        "capacity_kva": summary["capacity_kva"],
        "status": summary["status"],
        "loss_percent": summary["loss_pct"],
        "units_supplied": summary["energy_supplied"],
        "units_billed": summary["energy_billed"],
        "units_unaccounted": summary["loss_units"],
        "days_above_limit": f"{summary['days_above_threshold']}/{summary['days_monitored']}",
        "persistent": summary["persistent"],
        "trend": summary["trend"],
        "total_meters": summary["meter_count"],
        "monthly_revenue_loss_rupees": summary["estimated_monthly_revenue_loss"],
        "high_priority_meters": [m for m in flagged if m["priority"] == "HIGH"][:10],
        "flagged_meter_count": len(flagged),
    }


def high_priority_meters(limit: int = 10, days: int = 30) -> dict[str, Any]:
    """Meters worth inspecting first, across the whole network.

    Ranked by the combined score, so a meter only reaches the top when the model
    AND the energy balance both point at it.
    """
    limit = max(1, min(50, int(limit or 10)))
    results: list[dict[str, Any]] = []

    for summary in energy_balance.get_network_summary(days):
        if summary["status"] == "NORMAL":
            continue  # nothing missing here, so no case to make
        for meter in transformer_db.get_flagged_meters_for_transformer(summary["transformer_id"]):
            if str(meter.get("prediction", "")).lower() != "theft":
                continue
            confidence = float(meter.get("confidence") or 0.0)
            if confidence > 1.0:
                confidence = confidence / 100.0
            scored = energy_balance.combined_priority(
                confidence, summary["loss_pct"], summary["persistent"]
            )
            results.append(
                {
                    "meter_id": meter["meter_id"],
                    "transformer_id": summary["transformer_id"],
                    "area": summary["area"],
                    "transformer_loss_percent": summary["loss_pct"],
                    "model_confidence_percent": round(confidence * 100, 1),
                    "priority": scored["priority"],
                    "priority_score": scored["priority_score"],
                }
            )

    results.sort(key=lambda row: row["priority_score"], reverse=True)
    return {"count": len(results), "showing": min(limit, len(results)), "meters": results[:limit]}


def meter_lookup(meter_id: str, days: int = 30) -> dict[str, Any]:
    """Everything known about one consumer meter."""
    meter_id = str(meter_id or "").strip()
    mapping = transformer_db.get_meter_transformer_map()
    transformer_id = mapping.get(meter_id)

    latest = None
    for row in get_prediction_history(limit=1000):
        if str(row.get("meter_id")) == meter_id:
            latest = row
            break

    if transformer_id is None and latest is None:
        return {"error": f"No meter with id '{meter_id}' in the network or the prediction history."}

    result: dict[str, Any] = {"meter_id": meter_id}

    if latest is not None:
        result["model_prediction"] = latest.get("prediction")
        result["model_confidence"] = latest.get("confidence")
        result["risk"] = latest.get("risk")
        result["predicted_at"] = latest.get("timestamp")
    else:
        result["model_prediction"] = "not yet analysed by the model"

    if transformer_id:
        summary = energy_balance.get_transformer_summary(transformer_id, days)
        result["transformer_id"] = transformer_id
        if summary:
            result["transformer_area"] = summary["area"]
            result["transformer_loss_percent"] = summary["loss_pct"]
            result["transformer_status"] = summary["status"]
            if latest is not None:
                confidence = float(latest.get("confidence") or 0.0)
                if confidence > 1.0:
                    confidence = confidence / 100.0
                result.update(
                    energy_balance.combined_priority(
                        confidence, summary["loss_pct"], summary["persistent"]
                    )
                )
    else:
        result["transformer_id"] = "not mapped to a transformer yet"

    return result


def prediction_stats() -> dict[str, Any]:
    """How many predictions the model has made and what it found."""
    stats = get_dashboard_stats()
    total = stats["total_predictions"]
    theft = stats["theft_predictions"]
    return {
        "total_predictions": total,
        "theft_predictions": theft,
        "normal_predictions": stats["normal_predictions"],
        "theft_rate_percent": round(theft / total * 100, 2) if total else 0.0,
        "latest_prediction": stats["latest_prediction"],
    }


def alert_summary() -> dict[str, Any]:
    """How many theft alerts have gone out."""
    counts = get_alert_counts()
    return {
        "alerts_sent": counts.get("sent", 0),
        "alerts_failed": counts.get("failed", 0),
        "alerts_suppressed_by_cooldown": counts.get("cooldown", 0),
    }


def explain_concept(topic: str) -> dict[str, Any]:
    """Explain a domain term. Definitions are curated, not generated."""
    query = str(topic or "").strip().lower()

    if query in KNOWLEDGE:
        return {"topic": query, "explanation": KNOWLEDGE[query]}

    for key, text in KNOWLEDGE.items():
        if key in query or query in key:
            return {"topic": key, "explanation": text}

    # Loose word overlap, so "what causes losses in the wires" finds
    # "technical loss" without an exact phrase match.
    words = {word for word in query.replace("?", " ").split() if len(word) > 3}
    best_key, best_hits = None, 0
    for key, text in KNOWLEDGE.items():
        hits = sum(1 for word in words if word in key or word in text.lower())
        if hits > best_hits:
            best_key, best_hits = key, hits

    if best_key and best_hits >= 2:
        return {"topic": best_key, "explanation": KNOWLEDGE[best_key]}

    return {
        "topic": query,
        "explanation": None,
        "note": "No curated explanation for this topic. Answer from general knowledge and say so.",
        "available_topics": sorted(KNOWLEDGE.keys()),
    }


# --------------------------------------------------------------------------- #
# Registry: schema for the model + implementation for us
# --------------------------------------------------------------------------- #
TOOLS: dict[str, dict[str, Any]] = {
    "network_overview": {
        "fn": network_overview,
        "description": (
            "Overall health of the distribution network: how many transformers are "
            "critical, the average loss percentage, units unaccounted for, and the "
            "estimated monthly revenue loss. Use for broad questions like 'how is the "
            "network doing' or 'how much are we losing'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days to analyse, default 30"}
            },
        },
    },
    "worst_transformers": {
        "fn": worst_transformers,
        "description": (
            "The transformers with the highest energy loss, worst first. Use for 'which "
            "transformer has the most theft', 'where should we inspect', 'show me the "
            "worst areas'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "How many to return, default 5"},
                "days": {"type": "integer", "description": "Days to analyse, default 30"},
            },
        },
    },
    "transformer_detail": {
        "fn": transformer_detail,
        "description": (
            "Full detail for ONE transformer by its id, for example 'DT-015': loss, "
            "status, trend, and the high-priority meters under it. Use whenever the "
            "question names a specific transformer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "transformer_id": {"type": "string", "description": "Transformer id, e.g. DT-015"},
                "days": {"type": "integer", "description": "Days to analyse, default 30"},
            },
            "required": ["transformer_id"],
        },
    },
    "high_priority_meters": {
        "fn": high_priority_meters,
        "description": (
            "Individual consumer meters that should be inspected first across the whole "
            "network, ranked by model confidence combined with their transformer's energy "
            "loss. Use for 'which meters should we check', 'who is stealing'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "How many to return, default 10"},
                "days": {"type": "integer", "description": "Days to analyse, default 30"},
            },
        },
    },
    "meter_lookup": {
        "fn": meter_lookup,
        "description": (
            "Everything known about one consumer meter by its id: what the model said, "
            "which transformer feeds it, and its combined priority. Use whenever the "
            "question names a specific meter id."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "meter_id": {"type": "string", "description": "The consumer meter id"},
            },
            "required": ["meter_id"],
        },
    },
    "prediction_stats": {
        "fn": prediction_stats,
        "description": (
            "How many predictions the ML model has made, how many were theft, and the "
            "theft rate. Use for 'how many meters has the model checked', 'how many "
            "thefts found'."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    "alert_summary": {
        "fn": alert_summary,
        "description": "How many theft alerts were sent, failed, or suppressed by the cooldown.",
        "parameters": {"type": "object", "properties": {}},
    },
    "explain_concept": {
        "fn": explain_concept,
        "description": (
            "Explain an electricity-distribution or machine-learning concept used in this "
            "system: energy balance, technical loss, commercial loss, AT&C losses, "
            "persistence, priority score, SHAP, class imbalance, precision at K, false "
            "positives, theft detection methods. Use for 'what is', 'why', 'how does X "
            "work' questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The concept to explain"},
            },
            "required": ["topic"],
        },
    },
}


def get_tool_schemas() -> list[dict[str, Any]]:
    """Tool definitions in the OpenAI / Ollama function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": spec["description"],
                "parameters": spec["parameters"],
            },
        }
        for name, spec in TOOLS.items()
    ]


def run_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Execute one tool by name. Never raises - the agent must survive a bad call."""
    spec = TOOLS.get(name)
    if spec is None:
        return {"error": f"Unknown tool '{name}'.", "available_tools": sorted(TOOLS.keys())}

    arguments = arguments or {}
    if not isinstance(arguments, dict):
        return {"error": f"Tool '{name}' expected an object of arguments."}

    # Drop anything the model hallucinated that the function does not accept.
    allowed = set(spec["parameters"].get("properties", {}).keys())
    cleaned = {key: value for key, value in arguments.items() if key in allowed}

    try:
        fn: Callable[..., dict[str, Any]] = spec["fn"]
        return fn(**cleaned)
    except TypeError as exc:
        return {"error": f"Tool '{name}' called with wrong arguments: {exc}"}
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Agent tool '%s' failed", name)
        return {"error": f"Tool '{name}' failed: {exc}"}
