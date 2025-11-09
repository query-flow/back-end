"""
Repository for Conversation data access
"""
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import HTTPException
from sqlmodel import Session, select
from app.models import Conversation, ConversationMessage

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Handles Conversation and ConversationMessage CRUD operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_conversation(
        self,
        org_id: str,
        user_id: str,
        title: str
    ) -> Conversation:
        """
        Create a new conversation

        Args:
            org_id: Organization ID
            user_id: User ID
            title: Conversation title (auto-generated from first question)

        Returns:
            Created Conversation
        """
        now = datetime.utcnow()
        conversation = Conversation(
            id=str(uuid.uuid4()),
            org_id=org_id,
            user_id=user_id,
            title=title,
            created_at=now,
            updated_at=now
        )

        self.session.add(conversation)
        self.session.commit()
        self.session.refresh(conversation)

        logger.info(f"Created conversation {conversation.id} for user {user_id}")

        return conversation

    def get_conversation(self, conversation_id: str, user_id: str) -> Conversation:
        """
        Get conversation by ID

        Validates that user owns the conversation

        Raises:
            HTTPException: If conversation not found or unauthorized
        """
        conversation = self.session.get(Conversation, conversation_id)

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found"
            )

        if conversation.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to access this conversation"
            )

        return conversation

    def list_conversations(
        self,
        user_id: str,
        org_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Conversation]:
        """
        List user's conversations

        Args:
            user_id: User ID
            org_id: Organization ID
            limit: Max conversations to return
            offset: Pagination offset

        Returns:
            List of conversations ordered by updated_at desc
        """
        statement = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .where(Conversation.org_id == org_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )

        conversations = self.session.exec(statement).all()

        logger.info(f"Listed {len(conversations)} conversations for user {user_id}")

        return list(conversations)

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        sql_executed: Optional[str] = None,
        schema_used: Optional[str] = None,
        row_count: Optional[int] = None,
        duration_ms: Optional[int] = None
    ) -> ConversationMessage:
        """
        Add message to conversation

        Args:
            conversation_id: Conversation ID
            role: "user" or "assistant"
            content: Message content (question or answer)
            sql_executed: SQL query (for assistant messages)
            schema_used: Schema name (for assistant messages)
            row_count: Number of rows returned (for assistant messages)
            duration_ms: Query duration (for assistant messages)

        Returns:
            Created message
        """
        message = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            sql_executed=sql_executed,
            schema_used=schema_used,
            row_count=row_count,
            duration_ms=duration_ms,
            created_at=datetime.utcnow()
        )

        self.session.add(message)

        # Update conversation updated_at
        conversation = self.session.get(Conversation, conversation_id)
        if conversation:
            conversation.updated_at = datetime.utcnow()

        self.session.commit()
        self.session.refresh(message)

        logger.info(f"Added {role} message to conversation {conversation_id}")

        return message

    def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[ConversationMessage]:
        """
        Get conversation messages

        Args:
            conversation_id: Conversation ID
            limit: Max messages to return (None = all)

        Returns:
            List of messages ordered by created_at asc
        """
        statement = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.asc())
        )

        if limit:
            statement = statement.limit(limit)

        messages = self.session.exec(statement).all()

        return list(messages)

    def get_conversation_history_for_llm(
        self,
        conversation_id: str,
        max_messages: int = 10
    ) -> List[Dict[str, str]]:
        """
        Get conversation history formatted for LLM context

        Returns last N messages formatted as:
        [
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "answer"}
        ]

        Args:
            conversation_id: Conversation ID
            max_messages: Maximum messages to include

        Returns:
            List of message dicts for LLM
        """
        messages = self.get_messages(conversation_id)

        # Take last N messages
        recent_messages = messages[-max_messages:] if len(messages) > max_messages else messages

        # Format for LLM
        history = []
        for msg in recent_messages:
            history.append({
                "role": msg.role,
                "content": msg.content
            })

        return history

    def delete_conversation(self, conversation_id: str, user_id: str) -> None:
        """
        Delete conversation and all its messages

        Args:
            conversation_id: Conversation ID
            user_id: User ID (for authorization)

        Raises:
            HTTPException: If not authorized
        """
        conversation = self.get_conversation(conversation_id, user_id)

        # Delete messages first (CASCADE should handle this, but being explicit)
        statement = select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id
        )
        messages = self.session.exec(statement).all()
        for msg in messages:
            self.session.delete(msg)

        # Delete conversation
        self.session.delete(conversation)
        self.session.commit()

        logger.info(f"Deleted conversation {conversation_id}")
