from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class SuggestionSource(BaseModel):
    """Source of suggestion (for transparency)"""
    type: str  # "static", "personalized", "contextual", "popular"
    reason: Optional[str] = None  # Why this was suggested


class QuestionSuggestion(BaseModel):
    """A suggested question"""
    question: str
    source: SuggestionSource
    metadata: Optional[Dict[str, Any]] = None  # Extra info (frequency, last_asked, etc)


class SuggestionsResponse(BaseModel):
    """Response with multiple suggestion types"""
    static: List[str] = []  # Pre-configured questions for schema
    personalized: List[QuestionSuggestion] = []  # Based on user history
    contextual: List[str] = []  # Based on current result
    popular: List[QuestionSuggestion] = []  # Popular in organization
    schema_name: Optional[str] = None  # Which schema these apply to


class UserQueryStats(BaseModel):
    """User query statistics"""
    total_queries: int
    avg_duration_ms: int
    most_used_schema: Optional[str] = None
