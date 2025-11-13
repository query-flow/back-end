"""
Repository for Query History data access
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select, func
from app.models.query_history import QueryHistory

logger = logging.getLogger(__name__)


class QueryHistoryRepository:
    """Handles QueryHistory CRUD operations and analytics"""

    def __init__(self, session: Session):
        self.session = session

    def save_query(
        self,
        user_id: str,
        org_id: str,
        pergunta: str,
        schema_used: Optional[str] = None,
        sql_executed: Optional[str] = None,
        row_count: Optional[int] = None,
        duration_ms: Optional[int] = None,
        conversation_id: Optional[str] = None
    ) -> QueryHistory:
        """
        Save query to history

        Args:
            user_id: User ID
            org_id: Organization ID
            pergunta: Natural language question
            schema_used: Schema queried
            sql_executed: Generated SQL
            row_count: Number of rows returned
            duration_ms: Execution time
            conversation_id: Optional conversation context

        Returns:
            Created QueryHistory
        """
        history = QueryHistory(
            id=str(uuid.uuid4()),
            user_id=user_id,
            org_id=org_id,
            pergunta=pergunta,
            schema_used=schema_used,
            sql_executed=sql_executed,
            row_count=row_count,
            duration_ms=duration_ms,
            conversation_id=conversation_id,
            created_at=datetime.utcnow()
        )

        self.session.add(history)
        self.session.commit()
        self.session.refresh(history)

        logger.info(f"Saved query history {history.id} for user {user_id}")

        return history

    def get_user_recent_queries(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[QueryHistory]:
        """
        Get user's recent queries

        Args:
            user_id: User ID
            limit: Max queries to return

        Returns:
            List of recent queries ordered by created_at desc
        """
        statement = (
            select(QueryHistory)
            .where(QueryHistory.user_id == user_id)
            .order_by(QueryHistory.created_at.desc())
            .limit(limit)
        )

        queries = self.session.exec(statement).all()

        return list(queries)

    def get_user_popular_questions(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get user's most frequent questions

        Args:
            user_id: User ID
            days: Look back period in days
            limit: Max questions to return

        Returns:
            List of dicts with {pergunta, count, last_asked}
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        count_col = func.count(QueryHistory.id).label("count")

        statement = (
            select(
                QueryHistory.pergunta,
                count_col,
                func.max(QueryHistory.created_at).label("last_asked")
            )
            .where(QueryHistory.user_id == user_id)
            .where(QueryHistory.created_at >= cutoff)
            .group_by(QueryHistory.pergunta)
            .order_by(count_col.desc())
            .limit(limit)
        )

        results = self.session.exec(statement).all()

        return [
            {
                "pergunta": row.pergunta,
                "count": row.count,
                "last_asked": row.last_asked
            }
            for row in results
        ]

    def get_org_popular_questions(
        self,
        org_id: str,
        schema: Optional[str] = None,
        days: int = 30,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get organization's most frequent questions

        Useful for showing "other users also asked" suggestions

        Args:
            org_id: Organization ID
            schema: Optional filter by schema
            days: Look back period in days
            limit: Max questions to return

        Returns:
            List of dicts with {pergunta, count, user_count}
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        count_col = func.count(QueryHistory.id).label("count")

        statement = (
            select(
                QueryHistory.pergunta,
                count_col,
                func.count(func.distinct(QueryHistory.user_id)).label("user_count")
            )
            .where(QueryHistory.org_id == org_id)
            .where(QueryHistory.created_at >= cutoff)
        )

        if schema:
            statement = statement.where(QueryHistory.schema_used == schema)

        statement = (
            statement
            .group_by(QueryHistory.pergunta)
            .order_by(count_col.desc())
            .limit(limit)
        )

        results = self.session.exec(statement).all()

        return [
            {
                "pergunta": row.pergunta,
                "count": row.count,
                "user_count": row.user_count
            }
            for row in results
        ]

    def get_user_query_stats(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get user query statistics

        Args:
            user_id: User ID
            days: Look back period in days

        Returns:
            Dict with stats: total_queries, avg_duration_ms, most_used_schema
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Total queries
        total_statement = (
            select(func.count(QueryHistory.id))
            .where(QueryHistory.user_id == user_id)
            .where(QueryHistory.created_at >= cutoff)
        )
        total = self.session.exec(total_statement).one()

        # Average duration
        avg_statement = (
            select(func.avg(QueryHistory.duration_ms))
            .where(QueryHistory.user_id == user_id)
            .where(QueryHistory.created_at >= cutoff)
            .where(QueryHistory.duration_ms.is_not(None))
        )
        avg_duration = self.session.exec(avg_statement).one() or 0

        # Most used schema
        schema_count_col = func.count(QueryHistory.id).label("count")

        schema_statement = (
            select(
                QueryHistory.schema_used,
                schema_count_col
            )
            .where(QueryHistory.user_id == user_id)
            .where(QueryHistory.created_at >= cutoff)
            .where(QueryHistory.schema_used.is_not(None))
            .group_by(QueryHistory.schema_used)
            .order_by(schema_count_col.desc())
            .limit(1)
        )

        schema_result = self.session.exec(schema_statement).first()
        most_used_schema = schema_result.schema_used if schema_result else None

        return {
            "total_queries": total,
            "avg_duration_ms": int(avg_duration),
            "most_used_schema": most_used_schema
        }
