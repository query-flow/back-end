from typing import List, Dict, Any
from pydantic import BaseModel, Field


class AdminOrgCreate(BaseModel):
    name: str = Field(..., examples=["Empresa X"])
    database_url: str = Field(..., description="SQLAlchemy URL com DB (schema) obrigatório")
    allowed_schemas: List[str] = Field(..., min_items=1)
    documents: List[Dict[str, Any]] = Field(default_factory=list)


class AdminOrgResponse(BaseModel):
    org_id: str
    name: str
    allowed_schemas: List[str]
