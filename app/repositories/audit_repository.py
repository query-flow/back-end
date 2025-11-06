"""
Repository for QueryAudit logs
"""
import logging
from typing import Optional
from sqlmodel import Session
from app.models import QueryAudit
from app.dtos import QueryExecutionContext

logger = logging.getLogger(__name__)


class AuditRepository:
    """Handles QueryAudit logging"""

    def __init__(self, session: Session):
        self.session = session

    def log_query(
        self,
        org_id: str,
        schema_used: str,
        prompt_snip: str,
        sql_text: str,
        row_count: Optional[int] = None,
        duration_ms: Optional[int] = None
    ) -> None:
        """
        Log query execution to audit trail

        Best-effort: does not raise exceptions
        Silently fails if database write errors
        """
        try:
            audit = QueryAudit(
                org_id=org_id,
                schema_used=schema_used,
                prompt_snip=prompt_snip[:500],  # Truncate to 500 chars
                sql_text=sql_text,
                row_count=row_count,
                duration_ms=duration_ms
            )

            self.session.add(audit)
            self.session.commit()

            logger.info(
                f"Audit log: org={org_id}, schema={schema_used}, "
                f"rows={row_count}, duration={duration_ms}ms"
            )

        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")
            # Best-effort: do not raise exception
            # Audit failure should not break user flow

    def log_from_context(self, org_id: str, ctx: QueryExecutionContext) -> None:
        """
        Log query from QueryExecutionContext

        Convenience method for service layer
        """
        if not ctx.sql_executed or not ctx.schema_used:
            logger.debug("Skipping audit log: incomplete context")
            return

        self.log_query(
            org_id=org_id,
            schema_used=ctx.schema_used,
            prompt_snip=ctx.pergunta,
            sql_text=ctx.sql_executed,
            row_count=ctx.row_count,
            duration_ms=ctx.duration_ms
        )
