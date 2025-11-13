"""
Conversations Controller - Manage persistent conversations
"""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_db
from app.core.auth import get_current_user, get_user_org_id
from app.schemas import (
    AuthedUser,
    PerguntaOrg,
    CreateConversationRequest,
    ConversationResponse,
    ListConversationsResponse,
    MessageResponse,
    ConversationHistoryResponse,
    AskInConversationRequest,
    AddMessageRequest,
)
from app.repositories import (
    OrgRepository,
    ConversationRepository,
    ClarificationRepository,
    AuditRepository,
)
from app.services import QueryService, EnrichmentService
from app.models import ConversationMessage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Conversations"])


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    req: CreateConversationRequest,
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new conversation

    If title not provided, it will be auto-generated from first question
    """
    org_id = get_user_org_id(u)
    user_id = u.id

    conv_repo = ConversationRepository(db)

    # Create conversation with default title (will be updated on first message)
    title = req.title or "Nova Conversa"

    conversation = conv_repo.create_conversation(
        org_id=org_id,
        user_id=user_id,
        title=title
    )

    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )


@router.get("/conversations", response_model=ListConversationsResponse)
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List user's conversations

    Returns conversations ordered by updated_at (most recent first)
    """
    org_id = get_user_org_id(u)
    user_id = u.id

    conv_repo = ConversationRepository(db)

    conversations = conv_repo.list_conversations(
        user_id=user_id,
        org_id=org_id,
        limit=limit,
        offset=offset
    )

    # Count messages for each conversation
    response_conversations = []
    for conv in conversations:
        messages = conv_repo.get_messages(conv.id)
        response_conversations.append(
            ConversationResponse(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=len(messages)
            )
        )

    return ListConversationsResponse(
        conversations=response_conversations,
        total=len(conversations)
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    conversation_id: str,
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get full conversation history with all messages
    """
    user_id = u.id

    conv_repo = ConversationRepository(db)

    # This validates user owns conversation
    conversation = conv_repo.get_conversation(conversation_id, user_id)

    # Get messages
    messages = conv_repo.get_messages(conversation_id)

    message_responses = [
        MessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            sql_executed=msg.sql_executed,
            schema_used=msg.schema_used,
            row_count=msg.row_count,
            duration_ms=msg.duration_ms,
            table_data=msg.table_data,
            insights=msg.insights,
            created_at=msg.created_at
        )
        for msg in messages
    ]

    return ConversationHistoryResponse(
        conversation=ConversationResponse(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=len(messages)
        ),
        messages=message_responses
    )


@router.post("/conversations/{conversation_id}/ask")
async def ask_in_conversation(
    conversation_id: str,
    req: AskInConversationRequest,
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ask a question within an existing conversation

    The system will load conversation history and use it as context
    for better understanding of follow-up questions
    """
    org_id = get_user_org_id(u)
    user_id = u.id

    # Validate conversation exists and user owns it
    conv_repo = ConversationRepository(db)
    conversation = conv_repo.get_conversation(conversation_id, user_id)

    # Load organization context
    org_repo = OrgRepository(db)
    org_ctx = org_repo.get_org_context(org_id)

    # Build query execution context
    from app.dtos import QueryExecutionContext
    ctx = QueryExecutionContext(
        pergunta=req.pergunta,
        max_linhas=req.max_linhas,
        enrich=req.enrich
    )

    # Initialize services
    clarification_repo = ClarificationRepository(db)
    audit_repo = AuditRepository(db)
    enrichment_service = EnrichmentService()

    from app.repositories.query_history_repository import QueryHistoryRepository
    query_history_repo = QueryHistoryRepository(db)

    query_service = QueryService(
        clarification_repo=clarification_repo,
        audit_repo=audit_repo,
        enrichment_service=enrichment_service,
        conversation_repo=conv_repo,
        query_history_repo=query_history_repo
    )

    # Execute query with conversation context
    result = query_service.execute_query(
        ctx=ctx,
        org_ctx=org_ctx,
        user_id=user_id,
        conversation_id=conversation_id
    )

    # Update conversation title if it's the first question
    messages = conv_repo.get_messages(conversation_id)
    if len(messages) <= 2:  # user + assistant message
        # Generate title from first question
        title = req.pergunta[:100]
        if len(req.pergunta) > 100:
            title += "..."

        conversation.title = title
        db.add(conversation)
        db.commit()

    return result


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def add_message_to_conversation(
    conversation_id: str,
    req: AddMessageRequest,
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a message to an existing conversation

    Used for saving quick mode conversations with all their messages
    (including table data and insights)
    """
    user_id = u.id

    conv_repo = ConversationRepository(db)

    # Validate conversation exists and user owns it
    conversation = conv_repo.get_conversation(conversation_id, user_id)

    # Add message with all data
    message = conv_repo.add_message(
        conversation_id=conversation_id,
        role=req.role,
        content=req.content,
        sql_executed=req.sql,  # Frontend sends "sql", backend stores as "sql_executed"
        table_data=req.table_data,
        insights=req.insights
    )

    logger.info(f"Added message {message.id} to conversation {conversation_id}")

    return MessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        sql_executed=message.sql_executed,
        schema_used=message.schema_used,
        row_count=message.row_count,
        duration_ms=message.duration_ms,
        table_data=message.table_data,
        insights=message.insights,
        created_at=message.created_at
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a conversation and all its messages
    """
    user_id = u.id

    conv_repo = ConversationRepository(db)
    conv_repo.delete_conversation(conversation_id, user_id)

    return {"status": "success", "message": "Conversation deleted"}
