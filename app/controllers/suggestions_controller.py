"""
Suggestions Controller - Help users discover queries
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.database import get_db
from app.core.auth import get_current_user, get_user_org_id
from app.schemas import AuthedUser
from app.schemas.suggestion_schema import SuggestionsResponse, UserQueryStats
from app.repositories import QueryHistoryRepository
from app.services.suggestion_service import SuggestionService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Suggestions"])


@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(
    schema: Optional[str] = Query(None, description="Schema to get suggestions for"),
    include_personalized: bool = Query(True, description="Include user's popular questions"),
    include_org_popular: bool = Query(True, description="Include organization's popular questions"),
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get query suggestions for user

    Returns multiple types of suggestions:
    - Static: Pre-configured questions for schema
    - Personalized: Based on user's query history
    - Popular: Popular questions in organization

    Use this to help users who don't know what to ask.
    """
    org_id = get_user_org_id(u)
    user_id = u.id

    # Initialize services
    query_history_repo = QueryHistoryRepository(db)
    suggestion_service = SuggestionService(query_history_repo)

    # Layer 1: Static suggestions
    static = []
    if schema:
        static = suggestion_service.get_static_suggestions(schema)

    # Layer 2: Personalized suggestions
    personalized = []
    if include_personalized:
        personalized = suggestion_service.get_personalized_suggestions(
            user_id=user_id,
            limit=5
        )

    # Layer 3: Organization popular questions
    popular = []
    if include_org_popular:
        popular = suggestion_service.get_org_popular_suggestions(
            org_id=org_id,
            schema=schema,
            limit=5
        )

    return SuggestionsResponse(
        static=static,
        personalized=personalized,
        popular=popular,
        schema_name=schema
    )


@router.get("/suggestions/stats", response_model=UserQueryStats)
async def get_user_stats(
    days: int = Query(30, description="Look back period in days"),
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's query statistics

    Returns:
    - Total queries in period
    - Average query duration
    - Most used schema
    """
    user_id = u.id

    query_history_repo = QueryHistoryRepository(db)
    stats = query_history_repo.get_user_query_stats(user_id, days)

    return UserQueryStats(**stats)
