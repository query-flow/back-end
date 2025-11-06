"""
Intent analysis DTOs
"""
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel


class IntentAnalysisResult(BaseModel):
    """
    Wrapper for IntentAnalysis with additional metadata
    """
    confidence: float
    is_clear: bool
    schema_mismatch: bool
    ambiguities: List[str]
    questions: List[Dict]
    missing_data: List[str] = []

    # Metadata
    analyzed_at: Optional[datetime] = None
    schema_used: Optional[str] = None
