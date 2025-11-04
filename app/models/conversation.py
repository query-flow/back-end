"""
Conversation/clarification session models - MVC2 Pattern
MODEL = Entidade + Lógica de Acesso a Dados
"""
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import JSON, Column
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
