"""
Repository for Organization data access
Encapsulates logic for loading org context
"""
import logging
from typing import Optional
from fastapi import HTTPException
from sqlmodel import Session
from app.models import Organization
from app.core.security import decrypt_str
from app.dtos import OrgContext

logger = logging.getLogger(__name__)


class OrgRepository:
    """Handles Organization data access"""

    def __init__(self, session: Session):
        self.session = session

    def get_org_context(self, org_id: str) -> OrgContext:
        """
        Load full organization context for query execution

        Raises:
            HTTPException: If org not found or missing connection
        """
        # Load organization
        org = self.session.get(Organization, org_id)
        if not org:
            raise HTTPException(
                status_code=404,
                detail=f"Organização '{org_id}' não encontrada. Verifique se a org existe."
            )

        # Validate connection
        if not org.connection:
            raise HTTPException(
                status_code=400,
                detail=f"Organização '{org_id}' não tem conexão de banco configurada."
            )

        # Get allowed schemas
        allowed_schemas = [x.schema_name for x in org.allowed_schemas]
        if not allowed_schemas:
            raise HTTPException(
                status_code=400,
                detail="Organização sem schemas permitidos."
            )

        # Collect business context from documents
        biz_context = self._collect_biz_context(org)

        # Decrypt password
        pwd = decrypt_str(org.connection.password_enc)

        # Build OrgContext DTO
        return OrgContext(
            org_id=org.id,
            org_name=org.name,
            driver=org.connection.driver,
            host=org.connection.host,
            port=org.connection.port,
            username=org.connection.username,
            password=pwd,
            database_name=org.connection.database_name,
            options_json=org.connection.options_json,
            allowed_schemas=allowed_schemas,
            biz_context=biz_context
        )

    def _collect_biz_context(self, org: Organization) -> str:
        """
        Collect business context from organization documents

        Returns:
            Formatted string with document titles and metadata
        """
        if not org.documents:
            return "Sem documentos de negócio cadastrados."

        partes = []
        for d in org.documents:
            md = d.metadata_json or {}
            md_txt = "; ".join(f"{k}: {v}" for k, v in md.items())
            partes.append(f"- {d.title} ({md_txt})" if md_txt else f"- {d.title}")

        return "Documentos de negócio cadastrados:\n" + "\n".join(partes)

    def validate_schema_access(self, org_id: str, schema_name: str) -> bool:
        """
        Check if org has access to a specific schema

        Returns:
            True if allowed, False otherwise
        """
        org = self.session.get(Organization, org_id)
        if not org:
            return False

        allowed = [x.schema_name for x in org.allowed_schemas]
        return schema_name in allowed
