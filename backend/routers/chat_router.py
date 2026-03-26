"""Chat API router - conversational query endpoint."""

from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest, ChatResponse
from services.llm_service import process_query

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a natural language query against the business dataset."""
    try:
        result = process_query(
            user_message=request.message,
            conversation_history=request.conversation_history,
        )
        return ChatResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}",
        )


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "Dodge FDE Query System"}
