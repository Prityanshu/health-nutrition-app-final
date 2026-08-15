"""
Saved plans: persistence, retrieval and PDF export.

Generated plans used to live only in the browser's memory, so closing the app -
or backgrounding it on a phone - threw them away. Everything a specialist
produces is now written here, which is what makes "close the app between sets
and come back to it" work, and what lets the PDF be built server-side.
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_active_user
from app.database import SavedPlan, User, get_db
from app.services.plan_pdf import PLAN_META, build_plan_pdf

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_TYPES = set(PLAN_META.keys())


class PlanSaveRequest(BaseModel):
    plan_type: str = Field(..., description="workout | budget_meal_plan | regional | weekly_meal_plan | recipe")
    content: str = Field(..., min_length=1)
    title: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


class PlanResponse(BaseModel):
    id: int
    plan_type: str
    title: Optional[str]
    content: str
    params: Optional[Dict[str, Any]] = None
    is_current: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


def _to_response(plan: SavedPlan) -> dict:
    parsed = None
    if plan.params:
        try:
            parsed = json.loads(plan.params)
        except json.JSONDecodeError:
            parsed = None
    return {
        "id": plan.id,
        "plan_type": plan.plan_type,
        "title": plan.title,
        "content": plan.content,
        "params": parsed,
        "is_current": plan.is_current,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }


def _validate_type(plan_type: str):
    if plan_type not in VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown plan type '{plan_type}'. Expected one of: {', '.join(sorted(VALID_TYPES))}",
        )


@router.post("/", response_model=PlanResponse)
async def save_plan(
    request: PlanSaveRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Save a generated plan and make it the current one for its type.

    Previous plans of the same type are kept but demoted, so history survives
    while there is exactly one plan to restore on next open.
    """
    _validate_type(request.plan_type)

    db.query(SavedPlan).filter(
        SavedPlan.user_id == current_user.id,
        SavedPlan.plan_type == request.plan_type,
        SavedPlan.is_current == True,  # noqa: E712
    ).update({"is_current": False}, synchronize_session=False)

    plan = SavedPlan(
        user_id=current_user.id,
        plan_type=request.plan_type,
        title=request.title or PLAN_META[request.plan_type]["title"],
        content=request.content,
        params=json.dumps(request.params) if request.params else None,
        is_current=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _to_response(plan)


@router.get("/current")
async def get_current_plans(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Every current plan, keyed by type.

    The specialist pages call this on mount so a plan generated yesterday is
    still on screen today.
    """
    plans = (
        db.query(SavedPlan)
        .filter(SavedPlan.user_id == current_user.id, SavedPlan.is_current == True)  # noqa: E712
        .order_by(SavedPlan.updated_at.desc())
        .all()
    )
    return {p.plan_type: _to_response(p) for p in plans}


@router.get("/current/{plan_type}")
async def get_current_plan(
    plan_type: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """The current plan of one type, or null if there isn't one."""
    _validate_type(plan_type)
    plan = (
        db.query(SavedPlan)
        .filter(
            SavedPlan.user_id == current_user.id,
            SavedPlan.plan_type == plan_type,
            SavedPlan.is_current == True,  # noqa: E712
        )
        .order_by(SavedPlan.updated_at.desc())
        .first()
    )
    return _to_response(plan) if plan else None


@router.get("/history")
async def list_plans(
    plan_type: Optional[str] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Past plans, newest first."""
    q = db.query(SavedPlan).filter(SavedPlan.user_id == current_user.id)
    if plan_type:
        _validate_type(plan_type)
        q = q.filter(SavedPlan.plan_type == plan_type)
    plans = q.order_by(SavedPlan.created_at.desc()).limit(min(limit, 100)).all()
    # Summaries only - the full text would make this response large.
    return [
        {
            "id": p.id,
            "plan_type": p.plan_type,
            "title": p.title,
            "is_current": p.is_current,
            "created_at": p.created_at,
            "preview": (p.content or "")[:180],
        }
        for p in plans
    ]


@router.delete("/{plan_id}")
async def delete_plan(
    plan_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    plan = (
        db.query(SavedPlan)
        .filter(SavedPlan.id == plan_id, SavedPlan.user_id == current_user.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    db.delete(plan)
    db.commit()
    return {"success": True, "deleted": plan_id}


def _safe_filename(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "plan").strip().lower()).strip("-")
    return slug or "plan"


def _build_pdf_for(plan: SavedPlan, user: User) -> tuple:
    """Shared by the download and email endpoints so both produce the same file."""
    meta = PLAN_META.get(plan.plan_type, PLAN_META["workout"])

    pairs = []
    if plan.params:
        try:
            params = json.loads(plan.params)
            label_map = {
                "fitness_goal": "Goal", "activity_level": "Level", "equipment": "Equipment",
                "time_per_day": "Per session", "budget_per_day": "Daily budget",
                "calorie_target": "Calories", "target_calories": "Calories",
                "meals_per_day": "Meals/day", "cuisine_region": "Cuisine",
                "region_or_cuisine": "Cuisine", "meal_type": "Meal",
                "time_constraint": "Time",
            }
            for key, label in label_map.items():
                value = params.get(key)
                if value not in (None, "", [], {}):
                    if key == "time_per_day":
                        value = f"{value} min"
                    if key == "budget_per_day":
                        value = f"Rs {value}"
                    pairs.append((label, str(value).replace("_", " ").title()
                                  if isinstance(value, str) else value))
                if len(pairs) >= 4:
                    break
        except json.JSONDecodeError:
            pass

    pdf = build_plan_pdf(
        title=plan.title or meta["title"],
        content=plan.content,
        plan_type=plan.plan_type,
        owner_name=user.full_name or user.username or "",
        created_at=plan.created_at,
        meta_pairs=pairs,
        disclaimer=meta.get("disclaimer"),
    )
    date = (plan.created_at or datetime.utcnow()).strftime("%Y-%m-%d")
    return pdf, f"{meta['filename']}-{date}.pdf", meta


class EmailPlanRequest(BaseModel):
    # Defaults to the account's own address, which is the common case.
    # Any other address is allowed so a plan can be shared with a friend,
    # trainer or dietitian.
    to_email: Optional[str] = None
    # Optional personal message, shown above the attachment.
    note: Optional[str] = Field(None, max_length=500)


@router.post("/{plan_id}/email")
async def email_plan(
    plan_id: int,
    request: EmailPlanRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Email one plan as a PDF attachment.

    The PDF is built in memory and attached directly - it is never written to
    disk, so there are no temporary files to clean up or leak between users.
    """
    from app.services.email_service import (
        EMAIL_ENABLED, check_rate_limit, is_valid_email, plan_email_body,
        record_send, send_email,
    )

    if not EMAIL_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Email is not configured on the server. Set BREVO_API_KEY and EMAIL_USER.",
        )

    # Checked before doing any work - building a PDF for a request that will be
    # rejected is wasted effort.
    allowed, limit_message = check_rate_limit(current_user.id)
    if not allowed:
        raise HTTPException(status_code=429, detail=limit_message)

    plan = (
        db.query(SavedPlan)
        .filter(SavedPlan.id == plan_id, SavedPlan.user_id == current_user.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    recipient = (request.to_email or current_user.email or "").strip()
    if not is_valid_email(recipient):
        raise HTTPException(status_code=400, detail="A valid email address is required.")

    is_self = recipient.lower() == (current_user.email or "").lower()

    try:
        pdf, filename, meta = _build_pdf_for(plan, current_user)
    except RuntimeError as e:  # reportlab missing
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("PDF build failed while emailing plan %s: %s", plan_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not build the PDF to send.")

    title = plan.title or meta["title"]
    sender_name = current_user.full_name or current_user.username or ""
    text_body, html_body = plan_email_body(
        title, sender_name, plan.plan_type, is_self=is_self, note=request.note,
    )

    subject = (
        f"{title} — Kayosha" if is_self
        else f"{sender_name or 'Someone'} shared a {plan.plan_type.replace('_', ' ')} with you"
    )

    # SMTP is blocking and takes a few seconds; keep it off the event loop.
    result = await asyncio.to_thread(
        send_email,
        to_email=recipient,
        subject=subject,
        body=text_body,
        html_body=html_body,
        attachment=(filename, pdf, "pdf"),
        # Replies should reach the user who shared the plan, not the service
        # mailbox, which nobody reads.
        reply_to=current_user.email,
    )

    if not result.success:
        raise HTTPException(status_code=502, detail=result.message)

    record_send(current_user.id)
    return {"success": True, "message": result.message, "to": recipient, "was_self": is_self}


@router.get("/email/status")
async def email_status(current_user: User = Depends(get_current_active_user)):
    """Whether email is available, so the UI can hide the button if not."""
    from app.services.email_service import status
    info = status()
    info["default_recipient"] = current_user.email
    return info


@router.get("/{plan_id}/pdf")
async def download_plan_pdf(
    plan_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Download one specific plan as a PDF.

    Scoped to a single plan id so each can be downloaded independently rather
    than getting everything in one file.
    """
    plan = (
        db.query(SavedPlan)
        .filter(SavedPlan.id == plan_id, SavedPlan.user_id == current_user.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    meta = PLAN_META.get(plan.plan_type, PLAN_META["workout"])

    # Surface the inputs that produced the plan, so the PDF is self-explanatory
    # months later.
    pairs = []
    if plan.params:
        try:
            params = json.loads(plan.params)
            label_map = {
                "fitness_goal": "Goal", "activity_level": "Level", "equipment": "Equipment",
                "time_per_day": "Per session", "budget_per_day": "Daily budget",
                "calorie_target": "Calories", "target_calories": "Calories",
                "meals_per_day": "Meals/day", "cuisine_region": "Cuisine",
                "region_or_cuisine": "Cuisine", "meal_type": "Meal",
                "time_constraint": "Time",
            }
            for key, label in label_map.items():
                value = params.get(key)
                if value not in (None, "", [], {}):
                    if key == "time_per_day":
                        value = f"{value} min"
                    if key in ("budget_per_day",):
                        value = f"Rs {value}"
                    pairs.append((label, str(value).replace("_", " ").title()
                                  if isinstance(value, str) else value))
                if len(pairs) >= 4:
                    break
        except json.JSONDecodeError:
            pass

    try:
        pdf = build_plan_pdf(
            title=plan.title or meta["title"],
            content=plan.content,
            plan_type=plan.plan_type,
            owner_name=current_user.full_name or current_user.username or "",
            created_at=plan.created_at,
            meta_pairs=pairs,
            disclaimer=meta.get("disclaimer"),
        )
    except Exception as e:
        logger.error("PDF generation failed for plan %s: %s", plan_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not build the PDF")

    date = (plan.created_at or datetime.utcnow()).strftime("%Y-%m-%d")
    filename = f"{meta['filename']}-{date}.pdf"

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf)),
        },
    )
