"""
Natural Language to SQL Query Pipeline - Refactored with Service Layer
"""
import logging
import asyncio
from typing import AsyncGenerator
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.core.database import get_db
from app.core.auth import get_current_user, get_user_org_id
from app.schemas import PerguntaOrg, AuthedUser
from app.dtos import QueryExecutionContext, StreamEvent
from app.repositories import OrgRepository, ClarificationRepository, AuditRepository, ConversationRepository
from app.services import QueryService, EnrichmentService
from app.core.streaming import format_sse

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
    conversation_repo = ConversationRepository(db) if p.conversation_id else None

    query_service = QueryService(
        clarification_repo=clarification_repo,
        audit_repo=audit_repo,
        enrichment_service=enrichment_service,
        conversation_repo=conversation_repo
    )

    # 5. Execute query (all business logic in service)
    result = query_service.execute_query(
        ctx=ctx,
        org_ctx=org_ctx,
        user_id=u.sub,
        conversation_id=p.conversation_id
    )

    return result


@router.post("/perguntar_org_stream")
async def perguntar_org_stream(
    p: PerguntaOrg,
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Streaming endpoint for natural language to SQL queries

    Returns Server-Sent Events (SSE) with progress updates

    Event types:
    - started: Query processing started
    - selecting_schema: Selecting best schema
    - analyzing_intent: Analyzing question intent
    - generating_sql: Generating SQL query
    - executing_sql: Executing SQL on database
    - enriching: Generating insights (if enrich=true)
    - completed: Query completed successfully
    - error: Error occurred
    - done: Final marker (no data)
    """
    # 1. Get user's org_id
    org_id = get_user_org_id(u)

    # 2. Load organization context
    org_repo = OrgRepository(db)
    org_ctx = org_repo.get_org_context(org_id)

    # 3. Build query execution context
    ctx = QueryExecutionContext(
        pergunta=p.pergunta,
        max_linhas=p.max_linhas,
        enrich=p.enrich,
        clarification_id=p.clarification_id,
        clarifications=p.clarifications,
        conversation_history=None
    )

    # 4. Initialize service layer
    clarification_repo = ClarificationRepository(db)
    audit_repo = AuditRepository(db)
    enrichment_service = EnrichmentService()
    conversation_repo = ConversationRepository(db) if p.conversation_id else None

    query_service = QueryService(
        clarification_repo=clarification_repo,
        audit_repo=audit_repo,
        enrichment_service=enrichment_service,
        conversation_repo=conversation_repo
    )

    # 5. Create event queue for streaming
    event_queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()

    def emit_event(event: StreamEvent):
        """Callback to emit events from sync code"""
        asyncio.create_task(event_queue.put(event))

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events"""
        try:
            # Start query execution in background
            loop = asyncio.get_event_loop()

            async def execute_in_thread():
                """Run sync query execution in thread pool"""
                try:
                    result = await loop.run_in_executor(
                        None,
                        lambda: query_service.execute_query(
                            ctx=ctx,
                            org_ctx=org_ctx,
                            event_callback=emit_event,
                            user_id=u.sub,
                            conversation_id=p.conversation_id
                        )
                    )
                    # Signal completion with None
                    await event_queue.put(None)
                    # Store result for final event
                    return result
                except Exception as e:
                    logger.error(f"Query execution error: {e}", exc_info=True)
                    await event_queue.put(StreamEvent(
                        stage="error",
                        progress=0,
                        error=str(e)
                    ))
                    await event_queue.put(None)

            # Start execution task
            execution_task = asyncio.create_task(execute_in_thread())

            # Stream events as they arrive
            while True:
                event = await event_queue.get()

                if event is None:
                    # Execution complete
                    break

                # Send event as SSE
                yield format_sse(event, event_type=event.stage)

            # Wait for execution to complete and get result
            result = await execution_task

            # Send final result event
            if result:
                final_event = StreamEvent(
                    stage="result",
                    progress=100,
                    data=result
                )
                yield format_sse(final_event, event_type="result")

            # Send done marker
            yield "event: done\ndata: {}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            error_event = StreamEvent(
                stage="error",
                progress=0,
                error=str(e)
            )
            yield format_sse(error_event, event_type="error")
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
