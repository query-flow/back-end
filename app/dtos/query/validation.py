"""
SQL validation DTOs
"""
from typing import Optional, List
from pydantic import BaseModel


class SQLCandidate(BaseModel):
    """
    Represents a SQL candidate with metadata
    Used in self-consistency voting
    """
    sql: str
    temperature: float
    confidence: Optional[float] = None
    validation_passed: bool = False
    errors: List[str] = []


class ValidationResult(BaseModel):
    """
    Result of semantic SQL validation
    """
    is_valid: bool
    must_include: List[str] = []  # Tables/columns that should be present
    must_not: List[str] = []      # Patterns to avoid (DELETE, DROP, etc)
    suggestions: List[str] = []   # Suggestions for improvement
    confidence: float = 0.0
