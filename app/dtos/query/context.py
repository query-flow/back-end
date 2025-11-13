"""
Query execution context DTOs
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel
from app.dtos.query.validation import SQLCandidate


class QueryExecutionContext(BaseModel):
    """
    Encapsulates the full context of a query execution
    Passed between service layers
    """
    # Input
    pergunta: str
    max_linhas: int = 100
    enrich: bool = False
    clarification_id: Optional[str] = None
    clarifications: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Dict[str, str]]] = None

    # Execution state
    schema_used: Optional[str] = None
    sql_generated: Optional[str] = None
    sql_executed: Optional[str] = None
    sql_candidates: List[SQLCandidate] = []

    # Results
    colunas: Optional[List[str]] = None
    dados: Optional[List[List]] = None
    row_count: Optional[int] = None
    duration_ms: Optional[int] = None

    # Enrichment
    insights_text: Optional[str] = None
    chart_spec: Optional[Dict[str, Any]] = None  # Interactive chart specification (JSON)

    # Metadata
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class StreamEvent(BaseModel):
    """
    Event emitted during streaming execution
    """
    stage: str  # analyzing_intent, generating_sql, validating, executing, enriching, done
    progress: int  # 0-100
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
