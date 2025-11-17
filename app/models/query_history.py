"""
Query History Model - Track user queries for analytics and personalization
"""
from typing import Optional
from datetime import datetime
from sqlalchemy import Column, Text
from sqlmodel import SQLModel, Field


class QueryHistory(SQLModel, table=True):
    """
    MODEL em MVC2 - QueryHistory

    Stores every query executed by users for:
    - Personalized suggestions
    - Popular query tracking
    - Analytics and insights
    - User behavior analysis

    Responsabilidades:
    - Estrutura da tabela de histórico
    - Metadados de execução de queries
    """
    __tablename__ = "user_query_history"

    id: str = Field(primary_key=True)  # UUID
    user_id: str = Field(foreign_key="users.id", index=True)
    org_id: str = Field(foreign_key="orgs.id", index=True)
    pergunta: str = Field(sa_column=Column(Text))  # Natural language question (TEXT)
    schema_used: Optional[str] = None  # Which schema was queried
    sql_executed: Optional[str] = Field(default=None, sa_column=Column(Text))  # Generated SQL (MEDIUMTEXT)
    row_count: Optional[int] = None  # Number of rows returned
    duration_ms: Optional[int] = None  # Execution time
    conversation_id: Optional[str] = Field(default=None, foreign_key="conversations.id")  # Optional conversation context
    created_at: datetime
