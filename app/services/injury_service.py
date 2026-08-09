"""
Injury tracking - recording, checking in, and turning that into constraints.

WHY
---
An injury was previously a sentence in a chat window. It shaped one workout
plan, fell out of the conversation window six turns later, and was never seen
again by the meal planner, the challenge generator, or next week's training.
Meanwhile the thing that actually matters - whether it is getting better - was
never asked about at all.

This module owns the injury's whole life:

    reported  ->  weekly check-ins  ->  recovered
                       |
                       +-> getting worse -> stop loading it, see a physio

and exposes it as constraints that other services consume, so a hamstring
excludes hip hinges everywhere at once rather than only where someone
remembered to handle it.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database import Injury, InjuryCheckIn

logger = logging.getLogger(__name__)

# Ask again after this long. Frequent enough to track a recovery, rare enough
# not to nag - most soft-tissue injuries change on a weekly timescale.
CHECKIN_INTERVAL_DAYS = 7

# Below this, an injury is effectively resolved and is not worth constraining
# every plan the user generates.
RECOVERED_SEVERITY = 2


def _body_part_key(text: str) -> str:
    """
    Map free text onto a contraindication key when possible.

    Falls back to the raw text: an unmapped injury still gets recorded and
    still reaches the plan generators as a named constraint, it just does not
    get the curated exercise exclusion list.
    """
    try:
        from app.services.contraindications import CONTRAINDICATIONS
    except Exception:
        return (text or "").strip().lower()

    lowered = (text or "").lower()
    # Trigger words first - they are the curated synonyms ("proximal
    # hamstring", "sit bone") and match real phrasing better than the key.
    for key, entry in CONTRAINDICATIONS.items():
        for trigger in getattr(entry, "triggers", []) or []:
            if trigger.lower() in lowered:
                return key
    for key in CONTRAINDICATIONS:
        if key.replace("_", " ") in lowered or key in lowered:
            return key
    return lowered.strip()


def _has_red_flag(text: str) -> bool:
    """Whether a description contains something that needs a person, not a plan."""
    if not text:
        return False
    try:
        from app.services.contraindications import RED_FLAGS
        lowered = text.lower()
        return any(flag in lowered for flag in RED_FLAGS)
    except Exception:
        return False


def record_injury(
    db: Session,
    user_id: int,
    description: str,
    severity: int = 5,
    body_part: Optional[str] = None,
) -> Injury:
    """
    Start tracking an injury, or update the one already being tracked.

    Re-reporting the same body part is treated as an update rather than a
    second injury - people mention a niggle repeatedly, and three duplicate
    "left knee" rows would constrain plans three times over.
    """
    key = body_part or _body_part_key(description)

    existing = (
        db.query(Injury)
        .filter(
            Injury.user_id == user_id,
            Injury.body_part == key,
            Injury.status == "active",
        )
        .first()
    )

    if existing:
        existing.severity = max(0, min(10, int(severity)))
        existing.description = description or existing.description
        existing.last_checked_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        logger.info("Updated existing injury %s for user %s", key, user_id)
        return existing

    # Triage at the moment it is reported, not only on later check-ins.
    # Someone typing "knee gave way and it's swollen" needs to be told that
    # now, not after a week of modified workouts.
    severity = max(0, min(10, int(severity)))
    flagged = _has_red_flag(description) or severity >= 8

    injury = Injury(
        user_id=user_id,
        body_part=key,
        description=description,
        severity=severity,
        status="active",
        needs_attention=flagged,
        started_at=datetime.utcnow(),
        last_checked_at=datetime.utcnow(),
    )
    db.add(injury)
    db.commit()
    db.refresh(injury)
    logger.info("Recorded new injury %s (severity %s) for user %s", key, severity, user_id)
    return injury


def check_in(
    db: Session,
    injury_id: int,
    user_id: int,
    severity: int,
    trend: Optional[str] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Record how an injury is doing and react to it.

    Two automatic consequences, because leaving them to the user defeats the
    purpose of asking:

      * severity at or below RECOVERED_SEVERITY closes the injury, so it stops
        constraining plans the moment it no longer needs to
      * a red-flag note, or pain that is climbing, sets needs_attention, which
        the UI surfaces as "get this looked at" rather than quietly producing
        another modified plan
    """
    injury = (
        db.query(Injury)
        .filter(Injury.id == injury_id, Injury.user_id == user_id)
        .first()
    )
    if not injury:
        return {"success": False, "error": "Injury not found"}

    severity = max(0, min(10, int(severity)))
    previous = injury.severity

    entry = InjuryCheckIn(
        injury_id=injury.id,
        user_id=user_id,
        severity=severity,
        trend=trend or ("better" if severity < previous else "worse" if severity > previous else "same"),
        note=note,
        logged_at=datetime.utcnow(),
    )
    db.add(entry)

    injury.severity = severity
    injury.last_checked_at = datetime.utcnow()

    # Red flags in the note mean this is beyond what an exercise plan should
    # be adjusting around.
    red_flag = False
    if note:
        try:
            from app.services.contraindications import RED_FLAGS
            lowered = note.lower()
            red_flag = any(flag in lowered for flag in RED_FLAGS)
        except Exception:
            red_flag = False

    getting_worse = severity >= previous + 2 and severity >= 6
    injury.needs_attention = bool(red_flag or getting_worse)

    resolved = False
    if severity <= RECOVERED_SEVERITY:
        injury.status = "recovered"
        injury.resolved_at = datetime.utcnow()
        injury.needs_attention = False
        resolved = True

    db.commit()

    return {
        "success": True,
        "resolved": resolved,
        "needs_attention": injury.needs_attention,
        "severity": severity,
        "previous_severity": previous,
        "message": _checkin_message(previous, severity, resolved, injury.needs_attention),
    }


def _checkin_message(previous: int, current: int, resolved: bool, attention: bool) -> str:
    if resolved:
        return "Good - marking that as recovered. Your plans will stop working around it."
    if attention:
        return (
            "That sounds like it needs looking at rather than training around. "
            "Worth seeing a physio before loading it again."
        )
    if current < previous:
        return "Heading the right way. Keeping the same restrictions for now."
    if current > previous:
        return "Backing off the load on that for the next few days."
    return "No change - staying cautious with it."


def active_injuries(db: Session, user_id: int) -> List[Injury]:
    return (
        db.query(Injury)
        .filter(Injury.user_id == user_id, Injury.status == "active")
        .order_by(Injury.severity.desc())
        .all()
    )


def due_for_checkin(db: Session, user_id: int) -> Optional[Injury]:
    """The injury most in need of an update, or None if nothing is due."""
    cutoff = datetime.utcnow() - timedelta(days=CHECKIN_INTERVAL_DAYS)
    return (
        db.query(Injury)
        .filter(
            Injury.user_id == user_id,
            Injury.status == "active",
            Injury.last_checked_at <= cutoff,
        )
        .order_by(Injury.last_checked_at.asc())
        .first()
    )


def as_constraints(db: Session, user_id: int) -> List[str]:
    """
    Active injuries as plain-language constraints for the plan generators.

    Each one carries its concrete exercise exclusions where they are known, so
    the generator does not have to reason about anatomy - which is exactly what
    it gets wrong. Severity is included because a 2/10 niggle and an 8/10 tear
    warrant different caution.
    """
    out: List[str] = []
    try:
        from app.services.contraindications import (
            CONTRAINDICATIONS, graded_exclusions, stage_for,
        )
    except Exception:
        return out

    for injury in active_injuries(db, user_id):
        label = injury.description or injury.body_part.replace("_", " ")
        stage = stage_for(injury.severity)
        line = f"{label} (severity {injury.severity}/10, {stage['label']})"
        line += f". {stage['guidance']}"

        entry = CONTRAINDICATIONS.get(injury.body_part)
        if entry:
            # Only what applies at this stage. Listing every exclusion for a
            # 2/10 niggle is how people stop reporting injuries at all.
            avoid = graded_exclusions(entry, injury.severity)
            if avoid:
                line += " Avoid: " + ", ".join(avoid[:16]) + "."
            subs = list(getattr(entry, "substitutions", []) or [])
            if subs:
                line += " Use instead: " + ", ".join(subs[:4]) + "."

        # A one-sided injury leaves a whole working limb. Excluding the
        # movement outright removes training that is both safe and useful -
        # loading the good side maintains strength and has a measurable
        # cross-education effect on the injured one.
        side = _side_of(label)
        if side:
            other = "right" if side == "left" else "left"
            line += (
                f" This is the {side} side only - single-leg and single-arm work "
                f"on the {other} side is fine and worth keeping in."
            )

        if injury.needs_attention:
            line += " Reported as worsening - keep load minimal."
        if not stage["prescribe"]:
            line += (
                " DO NOT prescribe training for this area at all. Say plainly that "
                "it needs assessing first, and train only unaffected areas."
            )

        out.append(line)

    return out


def _side_of(text: str) -> Optional[str]:
    """
    Which side an injury is on.

    Delegates to injury_taxonomy so there is one implementation. Two existed
    and disagreed: this one returned None for "both knees" while the taxonomy
    returned "bilateral", so the same phrase produced different behaviour
    depending on which module handled it.
    """
    try:
        from app.services.injury_taxonomy import _detect_side
        return _detect_side(text)
    except Exception:
        return None

def summary(db: Session, user_id: int) -> Dict[str, Any]:
    """Everything a screen or prompt needs about the user's injuries."""
    injuries = active_injuries(db, user_id)
    due = due_for_checkin(db, user_id)

    items = []
    for injury in injuries:
        history = (
            db.query(InjuryCheckIn)
            .filter(InjuryCheckIn.injury_id == injury.id)
            .order_by(InjuryCheckIn.logged_at.desc())
            .limit(6)
            .all()
        )
        days = (datetime.utcnow() - injury.started_at).days if injury.started_at else 0
        first = history[-1].severity if history else injury.severity
        items.append({
            "id": injury.id,
            "body_part": injury.body_part,
            "label": injury.description or injury.body_part.replace("_", " ").title(),
            "severity": injury.severity,
            "days_since_start": days,
            "needs_attention": bool(injury.needs_attention),
            "checkin_due": bool(due and due.id == injury.id),
            "last_checked_days_ago": (
                (datetime.utcnow() - injury.last_checked_at).days
                if injury.last_checked_at else None
            ),
            # Only meaningful once there is something to compare against.
            "improvement": (first - injury.severity) if len(history) >= 1 else None,
            "history": [
                {"severity": h.severity, "trend": h.trend,
                 "logged_at": h.logged_at.isoformat() if h.logged_at else None}
                for h in reversed(history)
            ],
        })

    return {
        "injuries": items,
        "has_active": bool(items),
        "checkin_due": bool(due),
        "needs_attention": any(i["needs_attention"] for i in items),
    }
