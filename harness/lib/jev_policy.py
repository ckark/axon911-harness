"""Confidence thresholds and policy actions for Jev decisions."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

HIGH_NOUL = 0.85
LOW_NOUL = 0.15
MID_NOUL = 0.5  # boundary between weak signal and actionable classification
CHOICE_CONFIDENCE = 0.7

VERDICT_PASS = {"PASS", "PASS WITH CONCERNS"}
VERDICT_BLOCK = {"CHANGES REQUIRED", "BLOCK"}


def noul_yes(probability: Optional[float], *, high: float = HIGH_NOUL) -> bool:
    return probability is not None and probability >= high


def noul_no(probability: Optional[float], *, low: float = LOW_NOUL) -> bool:
    return probability is not None and probability <= low


def inconclusive_decision(
    *,
    decision: str = "fallback",
    fallback_reason: str,
    mode: str = "shadow",
    **extra: Any,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "decision": decision,
        "policy_action": "fallback",
        "fallback_reason": fallback_reason,
        "mode": mode,
        "confidence": None,
    }
    payload.update(extra)
    return payload


def command_policy(
    *,
    destructive: Optional[float],
    readonly: Optional[float],
    reversible: Optional[float],
) -> Dict[str, Any]:
    if destructive is not None and destructive >= HIGH_NOUL:
        return {
            "decision": "deny",
            "policy_action": "deny",
            "fallback_reason": "",
            "mode": "live",
            "confidence": destructive,
        }
    if readonly is not None and readonly >= HIGH_NOUL:
        return {
            "decision": "allow",
            "policy_action": "allow",
            "fallback_reason": "",
            "mode": "live",
            "confidence": readonly,
        }
    if reversible is not None and reversible >= HIGH_NOUL:
        return {
            "decision": "ask",
            "policy_action": "ask",
            "fallback_reason": "",
            "mode": "live",
            "confidence": reversible,
        }
    return inconclusive_decision(
        fallback_reason="command-risk-uncertain",
        mode="shadow",
        destructive=destructive,
        readonly=readonly,
        reversible=reversible,
    )
