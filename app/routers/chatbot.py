import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_active_user
from app.database import ChatMessage, User, get_db
from app.services.conversation_manager import ConversationManager

logger = logging.getLogger(__name__)
router = APIRouter()

conversation_manager = ConversationManager()


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
            current_user.id, request.query.strip(), db
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
            current_user.id, request.query.strip(), db
        )
        return {"response": str(result.get("response", ""))}
    except Exception as e:
        logger.error("simple_chat error: %s", e, exc_info=True)
        return {"response": "Sorry, I'm having trouble right now. Please try again in a moment."}


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
