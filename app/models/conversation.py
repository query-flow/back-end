"""
Conversation/clarification session models - MVC2 Pattern
MODEL = Entidade + Lógica de Acesso a Dados
"""
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import JSON, Column, Text
from sqlmodel import SQLModel, Field


class ClarificationSession(SQLModel, table=True):
    """
    MODEL em MVC2 - ClarificationSession

    Stores clarification conversations between user and system.
    Sessions expire after 10 minutes.

    Responsabilidades:
    - Estrutura da tabela
    - Armazenar estado da conversa de clarificação
    """
    __tablename__ = "clarification_sessions"

    id: str = Field(primary_key=True)  # UUID
    org_id: str = Field(foreign_key="orgs.id", index=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    original_question: str  # User's original question
    schema_name: str  # Which schema was being used
    intent_analysis: Dict[str, Any] = Field(sa_column=Column(JSON))  # Store full intent analysis
    created_at: datetime
    expires_at: datetime  # Auto-expire after 10 minutes


class Conversation(SQLModel, table=True):
    """
    MODEL em MVC2 - Conversation

    Stores persistent conversation threads between user and system.
    Each conversation has multiple messages (questions and answers).

    Responsabilidades:
    - Estrutura da tabela de conversas
    - Metadados da conversa (título, timestamps, etc)
    """
    __tablename__ = "conversations"

    id: str = Field(primary_key=True)  # UUID
    org_id: str = Field(foreign_key="orgs.id", index=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    title: str  # Auto-generated from first question
    created_at: datetime
    updated_at: datetime  # Last message timestamp


class ConversationMessage(SQLModel, table=True):
    """
    MODEL em MVC2 - ConversationMessage

    Stores individual messages within a conversation.
    Each message is either a user question or system response.

    Responsabilidades:
    - Estrutura da tabela de mensagens
    - Histórico de perguntas e respostas
    """
    __tablename__ = "conversation_messages"

    id: str = Field(primary_key=True)  # UUID
    conversation_id: str = Field(foreign_key="conversations.id", index=True)
    role: str  # "user" or "assistant"
    content: str = Field(sa_column=Column(Text))  # Question or answer

    # Metadata for assistant responses
    sql_executed: Optional[str] = Field(default=None, sa_column=Column(Text))
    schema_used: Optional[str] = None
    row_count: Optional[int] = None
    duration_ms: Optional[int] = None

    created_at: datetime
