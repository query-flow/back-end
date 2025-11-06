"""
Organization context DTO
"""
from typing import Optional, List, Dict
from pydantic import BaseModel


class OrgContext(BaseModel):
    """
    Encapsulates organization context for query execution
    Reduces coupling and primitive obsession
    """
    org_id: str
    org_name: str

    # Database connection
    driver: str
    host: str
    port: int
    username: str
    password: str  # Decrypted
    database_name: str
    options_json: Optional[Dict] = None

    # Schema access
    allowed_schemas: List[str]

    # Business context
    biz_context: str

    def build_sqlalchemy_url(self, schema: str) -> str:
        """Build SQLAlchemy URL for a specific schema"""
        from app.utils.database import build_sqlalchemy_url
        return build_sqlalchemy_url(
            self.driver, self.host, self.port,
            self.username, self.password,
            schema, self.options_json
        )
