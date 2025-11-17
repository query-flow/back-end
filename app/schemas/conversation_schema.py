from pydantic import BaseModel
from typing import Optional, List, Dict, Any
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
    table_data: Optional[Dict[str, Any]] = None  # {columns: [], rows: []}
    insights: Optional[Dict[str, Any]] = None  # {summary: str, chart: {...}}
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    """Full conversation with messages"""
    conversation: ConversationResponse
    messages: List[MessageResponse]


class AskInConversationRequest(BaseModel):
    """Ask a question within an existing conversation"""
    pergunta: str
    max_linhas: int = 10
    enrich: bool = True


class AddMessageRequest(BaseModel):
    """Add a message to an existing conversation (for saving quick mode chats)"""
    role: str  # "user" or "assistant"
    content: str
    sql: Optional[str] = None  # Frontend sends "sql" not "sql_executed"
    table_data: Optional[Dict[str, Any]] = None  # {columns: [], rows: []}
    insights: Optional[Dict[str, Any]] = None  # {summary: str, chart: {...}}
