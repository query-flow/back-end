"""
Chart generation schemas
"""
from pydantic import BaseModel
from typing import Dict, Any, List, Optional


class GenerateChartRequest(BaseModel):
    """Request to generate chart from data"""
    columns: List[str]
    data: List[List[Any]]  # First few rows
    question: str
    chart_hint: Optional[str] = None  # e.g., "use line chart", "show trend"


class RegenerateChartRequest(BaseModel):
    """Request to regenerate/edit existing chart"""
    current_config: Dict[str, Any]
    columns: List[str]
    data: List[List[Any]]
    edit_instruction: str  # e.g., "make it blue", "change to pie chart"


class ChartConfigResponse(BaseModel):
    """Chart configuration response"""
    type: str  # bar, line, scatter, pie, area
    title: str
    description: str
    config: Dict[str, Any]  # Chart-specific configuration
