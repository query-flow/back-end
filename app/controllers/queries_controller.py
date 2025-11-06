"""
Natural Language to SQL Query Pipeline - Refactored with Service Layer
"""
import logging
from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.database import get_db
from app.core.auth import get_current_user, get_user_org_id
from app.schemas import PerguntaOrg, AuthedUser
from app.dtos import QueryExecutionContext
from app.repositories import OrgRepository, ClarificationRepository, AuditRepository
from app.services import QueryService, EnrichmentService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Query"])


@router.post("/perguntar_org")
async def perguntar_org(
    p: PerguntaOrg,
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Main endpoint for natural language to SQL queries

    Two flows:
    1. New question → intent analysis → maybe clarification → execute
    2. Clarification response → execute with clarified question

    This controller is now thin - delegates to service layer
    """
    # 1. Get user's org_id
    org_id = get_user_org_id(u)

    # 2. Load organization context (via repository)
    org_repo = OrgRepository(db)
    org_ctx = org_repo.get_org_context(org_id)

    # 3. Build query execution context
    ctx = QueryExecutionContext(
        pergunta=p.pergunta,
        max_linhas=p.max_linhas,
        enrich=p.enrich,
        clarification_id=p.clarification_id,
        clarifications=p.clarifications,
        conversation_history=None  # TODO: add when implementing chat
    )

    # 4. Initialize service layer
    clarification_repo = ClarificationRepository(db)
    audit_repo = AuditRepository(db)
    enrichment_service = EnrichmentService()

    query_service = QueryService(
        clarification_repo=clarification_repo,
        audit_repo=audit_repo,
        enrichment_service=enrichment_service
    )

    # 5. Execute query (all business logic in service)
    result = query_service.execute_query(ctx, org_ctx)

    return result
