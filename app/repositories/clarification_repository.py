"""
Repository for ClarificationSession data access
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException
from sqlmodel import Session
from app.models import ClarificationSession
from app.dtos import IntentAnalysisResult

logger = logging.getLogger(__name__)


class ClarificationRepository:
    """Handles ClarificationSession CRUD operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_session(
        self,
        org_id: str,
        user_id: str,
        original_question: str,
        schema_name: str,
        intent_analysis: IntentAnalysisResult,
        ttl_minutes: int = 10
    ) -> ClarificationSession:
        """
        Create a new clarification session

        Args:
            org_id: Organization ID
            user_id: User ID
            original_question: Original user question
            schema_name: Schema that was analyzed
            intent_analysis: Result of intent analysis
            ttl_minutes: Time to live in minutes (default: 10)

        Returns:
            Created ClarificationSession
        """
        session = ClarificationSession(
            id=str(uuid.uuid4()),
            org_id=org_id,
            user_id=user_id,
            original_question=original_question,
            schema_name=schema_name,
            intent_analysis=intent_analysis.dict(),
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes)
        )

        self.session.add(session)
        self.session.commit()
        self.session.refresh(session)

        logger.info(f"Created clarification session {session.id} (expires in {ttl_minutes} min)")

        return session

    def get_session(self, clarification_id: str) -> ClarificationSession:
        """
        Get clarification session by ID

        Raises:
            HTTPException: If session not found or expired
        """
        session = self.session.get(ClarificationSession, clarification_id)

        if not session:
            raise HTTPException(
                status_code=400,
                detail="Clarification session not found"
            )

        if session.expires_at < datetime.utcnow():
            # Clean up expired session
            self.session.delete(session)
            self.session.commit()
            raise HTTPException(
                status_code=400,
                detail="Clarification session expired"
            )

        logger.info(f"Retrieved clarification session {clarification_id}")

        return session

    def delete_session(self, clarification_id: str) -> None:
        """
        Delete clarification session

        Idempotent: does not raise if session not found
        """
        session = self.session.get(ClarificationSession, clarification_id)
        if session:
            self.session.delete(session)
            self.session.commit()
            logger.info(f"Deleted clarification session {clarification_id}")

    def cleanup_expired_sessions(self, older_than_minutes: int = 30) -> int:
        """
        Clean up expired sessions

        Args:
            older_than_minutes: Delete sessions older than this (default: 30)

        Returns:
            Number of sessions deleted
        """
        cutoff = datetime.utcnow() - timedelta(minutes=older_than_minutes)

        from sqlmodel import select
        statement = select(ClarificationSession).where(
            ClarificationSession.created_at < cutoff
        )
        expired = self.session.exec(statement).all()

        count = len(expired)
        for s in expired:
            self.session.delete(s)

        if count > 0:
            self.session.commit()
            logger.info(f"Cleaned up {count} expired clarification sessions")

        return count
