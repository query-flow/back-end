"""
Chart Generation Controller
Endpoints for creating and editing charts using LLM
"""
import logging
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.schemas import (
    AuthedUser,
    GenerateChartRequest,
    RegenerateChartRequest,
    ChartConfigResponse,
)
from app.services.chart_service import ChartService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Charts"])


@router.post("/generate-chart", response_model=ChartConfigResponse)
async def generate_chart(
    req: GenerateChartRequest,
    u: AuthedUser = Depends(get_current_user)
):
    """
    Generate chart configuration from query results using LLM

    The LLM analyzes the data structure and chooses the best visualization.

    Example request:
    {
        "columns": ["month", "revenue"],
        "data": [["Jan", 1000], ["Feb", 1500], ...],
        "question": "Show revenue by month",
        "chart_hint": "use line chart"  // optional
    }

    Returns chart configuration with D3.js spec.
    """
    chart_service = ChartService()

    config = chart_service.generate_chart_config(
        columns=req.columns,
        data=req.data,
        question=req.question,
        chart_hint=req.chart_hint
    )

    return ChartConfigResponse(**config)


@router.post("/regenerate-chart", response_model=ChartConfigResponse)
async def regenerate_chart(
    req: RegenerateChartRequest,
    u: AuthedUser = Depends(get_current_user)
):
    """
    Regenerate chart based on natural language edit instruction

    User can say things like:
    - "Make it blue"
    - "Change to pie chart"
    - "Add a legend"
    - "Show as area chart"

    Example request:
    {
        "current_config": {...},  // Current chart config
        "columns": ["month", "revenue"],
        "data": [[...]],
        "edit_instruction": "change to line chart and make it blue"
    }

    Returns updated chart configuration.
    """
    chart_service = ChartService()

    updated_config = chart_service.regenerate_chart(
        current_config=req.current_config,
        columns=req.columns,
        data=req.data,
        edit_instruction=req.edit_instruction
    )

    return ChartConfigResponse(**updated_config)
