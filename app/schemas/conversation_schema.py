from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation"""
    title: Optional[str] = None  # If None, auto-generate from first question


class ConversationResponse(BaseModel):
    """Conversation metadata"""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = None  # Optional, included in list view


class ListConversationsResponse(BaseModel):
    """Response for listing conversations"""
    conversations: List[ConversationResponse]
    total: int


class MessageResponse(BaseModel):
    """Individual message in conversation"""
    id: str
    role: str  # "user" or "assistant"
    content: str
    sql_executed: Optional[str] = None
    schema_used: Optional[str] = None
    row_count: Optional[int] = None
    duration_ms: Optional[int] = None
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    """Full conversation with messages"""
    conversation: ConversationResponse
    messages: List[MessageResponse]


class AskInConversationRequest(BaseModel):
    """Ask a question within an existing conversation"""
    pergunta: str
    max_linhas: int = 100
    enrich: bool = True
