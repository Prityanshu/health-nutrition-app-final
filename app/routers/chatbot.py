import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.database import get_db, User
from app.auth import get_current_active_user
from app.services.chatbot_manager import ChatbotManager

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize chatbot manager
chatbot_manager = ChatbotManager()

class ChatRequest(BaseModel):
    query: str = Field(..., description="User's natural language query")
    user_id: Optional[int] = Field(None, description="User ID (optional if using auth)")

class ChatResponse(BaseModel):
    success: bool
    response: Dict[str, Any]
    agent_used: str
    user_context: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class AgentInfo(BaseModel):
    name: str
    description: str

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Main chatbot endpoint that routes user queries to appropriate agents.
    
    The chatbot intelligently detects which agent should handle the query based on:
    - Keywords in the user's message
    - User's profile and preferences from database
    - Context from previous interactions
    """
    try:
        # Use authenticated user's ID
        user_id = current_user.id
        
        # Handle the query
        result = await chatbot_manager.handle_query(
            user_id=user_id,
            user_query=request.query,
            db=db
        )
        
        if result["success"]:
            return ChatResponse(
                success=True,
                response=result["response"],
                agent_used=result["agent_used"],
                user_context=result.get("user_context")
            )
        else:
            return ChatResponse(
                success=False,
                response={},
                agent_used=result.get("agent_used", "unknown"),
                error=result.get("error", "Unknown error occurred")
            )
            
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chatbot error: {str(e)}")

@router.get("/agents", response_model=list[AgentInfo])
async def get_available_agents():
    """
    Get list of available agents and their descriptions.
    """
    try:
        agents = chatbot_manager.get_available_agents()
        return [AgentInfo(name=agent["name"], description=agent["description"]) for agent in agents]
    except Exception as e:
        logger.error(f"Error getting agents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting agents: {str(e)}")

@router.get("/health")
async def health_check():
    """
    Health check endpoint for the chatbot service.
    """
    return {
        "status": "healthy",
        "service": "chatbot",
        "agents_available": len(chatbot_manager.agents)
    }

@router.post("/chat/simple")
async def simple_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Simplified chat endpoint that returns just the response text.
    """
    try:
        result = await chatbot_manager.handle_query(
            user_id=current_user.id,
            user_query=request.query,
            db=db
        )
        
        if result["success"]:
            # Extract the main response from the agent result
            agent_response = result["response"]
            if isinstance(agent_response, dict):
                if "data" in agent_response:
                    return {"response": agent_response["data"]}
                elif "message" in agent_response:
                    return {"response": agent_response["message"]}
                else:
                    return {"response": str(agent_response)}
            else:
                return {"response": str(agent_response)}
        else:
            return {"response": f"Sorry, I encountered an error: {result.get('error', 'Unknown error')}"}
            
    except Exception as e:
        logger.error(f"Error in simple_chat: {str(e)}")
        return {"response": f"Sorry, I'm having trouble processing your request. Please try again."}
