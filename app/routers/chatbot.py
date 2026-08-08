import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_active_user
from app.database import ChatMessage, User, get_db
from app.services.chat_context import build_and_render, build_chat_context, opening_line
from app.services.conversation_manager import ConversationManager

logger = logging.getLogger(__name__)
router = APIRouter()

conversation_manager = ConversationManager()


def _personalisation(user_id: int, db: Session) -> Optional[str]:
    """
    What this user has actually been doing, for the system prompt.

    Wrapped because the assistant must still answer if this fails - losing
    personalisation is a degraded reply, not a broken one.
    """
    try:
        return build_and_render(user_id, db) or None
    except Exception as e:
        logger.error("Could not build chat personalisation: %s", e, exc_info=True)
        return None


class ChatRequest(BaseModel):
    query: str = Field(..., description="User's natural language message")
    user_id: Optional[int] = Field(None, description="Ignored; identity comes from the auth token")


class ChatResponse(BaseModel):
    success: bool
    # Always a string now. The previous version returned the raw service dict
    # here while saving the formatted text to the database, so the UI and the
    # stored history disagreed.
    response: str
    agent_used: str
    tool_used: Optional[str] = None
    user_context: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AgentInfo(BaseModel):
    name: str
    description: str


class HistoryMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Main chat endpoint.

    One assistant handles the whole conversation, with prior turns replayed to
    the model on every request. It asks its own follow-up questions and calls a
    specialist service only when it has enough information to produce something.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        result = await conversation_manager.handle_query(
            current_user.id,
            request.query.strip(),
            db,
            extra_context=_personalisation(current_user.id, db),
        )
        return ChatResponse(
            success=result.get("success", True),
            response=str(result.get("response", "")),
            agent_used=result.get("agent_used", "nutricoach"),
            tool_used=result.get("tool_used"),
            user_context=result.get("user_context"),
            error=result.get("error"),
        )
    except Exception as e:
        logger.error("Chat endpoint error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Chatbot error")


@router.post("/chat/simple")
async def simple_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Returns just the reply text. This is what the React frontend calls."""
    if not request.query or not request.query.strip():
        return {"response": "Did you mean to send something? I didn't catch that."}

    try:
        result = await conversation_manager.handle_query(
            current_user.id,
            request.query.strip(),
            db,
            extra_context=_personalisation(current_user.id, db),
        )
        return {"response": str(result.get("response", ""))}
    except Exception as e:
        logger.error("simple_chat error: %s", e, exc_info=True)
        return {"response": "Sorry, I'm having trouble right now. Please try again in a moment."}


@router.get("/opener")
async def get_opener(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    A grounded first line plus suggested follow-ups for an empty chat window.

    Computed, not generated: it costs no AI quota, cannot hallucinate, and is
    ready before the screen finishes painting. An empty input box is the least
    inviting thing an assistant can show, and a generic "How can I help?" is
    barely better - this one knows whether they have eaten today.
    """
    try:
        ctx = build_chat_context(current_user.id, db)
        name = current_user.full_name or current_user.username or ""
        return {
            "greeting": opening_line(ctx, name),
            "suggestions": _suggestions(ctx),
        }
    except Exception as e:
        logger.error("opener failed: %s", e, exc_info=True)
        return {
            "greeting": "What can I help with today?",
            "suggestions": ["Plan my meals for today", "Build me a workout plan"],
        }


def _suggestions(ctx) -> List[str]:
    """
    Three next steps drawn from this user's actual situation.

    Ordered by how likely they are to be what the person came for, so the first
    chip is usually the right one.
    """
    out: List[str] = []
    remaining = ctx.calories_remaining

    if ctx.meals_today == 0 and ctx.local_hour >= 10:
        out.append("What should I eat today?")
    elif remaining is not None and remaining > 250:
        out.append(f"Dinner idea under {int(remaining)} kcal")

    if ctx.top_foods:
        out.append(f"A recipe using {ctx.top_foods[0]}")

    if ctx.last_plan_type == "workout":
        out.append("Adjust my workout plan")
    else:
        out.append("Build me a workout plan")

    if ctx.weight_change_kg is not None:
        out.append("Am I on track with my goal?")

    if ctx.typical_budget:
        out.append(f"A week of meals under ₹{int(ctx.typical_budget)} a day")

    # Fall back to the generic set only if nothing personal applied.
    if not out:
        out = ["Plan my meals for today", "Build me a workout plan", "What can you do?"]
    return out[:3]


@router.get("/history", response_model=List[HistoryMessage])
async def get_history(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Full stored conversation, so the UI can restore it after a refresh."""
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.timestamp.desc())
        .limit(min(limit, 200))
        .all()
    )
    rows.reverse()
    return [
        HistoryMessage(
            role=row.role,
            content=row.content or "",
            timestamp=row.timestamp.isoformat() if row.timestamp else None,
        )
        for row in rows
    ]


@router.delete("/history")
async def clear_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Start a fresh conversation - backs a 'New chat' button."""
    try:
        deleted = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_id == current_user.id)
            .delete(synchronize_session=False)
        )
        db.commit()
        return {"success": True, "deleted": deleted}
    except Exception as e:
        db.rollback()
        logger.error("Failed to clear history: %s", e)
        raise HTTPException(status_code=500, detail="Could not clear history")


@router.get("/agents", response_model=List[AgentInfo])
async def get_available_agents():
    """Capabilities the assistant can invoke. Kept for backward compatibility."""
    return [AgentInfo(**a) for a in conversation_manager.get_available_agents()]


@router.get("/health")
async def health_check():
    from app.config.groq_config import groq_config

    return {
        "status": "healthy",
        "service": "chatbot",
        "tools_available": len(conversation_manager.get_available_agents()),
        "groq_keys": groq_config.get_status(),
    }
