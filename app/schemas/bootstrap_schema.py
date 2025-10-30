from typing import List
from pydantic import BaseModel


class PublicBootstrapOrg(BaseModel):
    org_name: str
    database_url: str
    allowed_schemas: List[str]
    admin_name: str
    admin_email: str
    admin_api_key: str


class PublicBootstrapResponse(BaseModel):
    org_id: str
    admin_user_id: str
    admin_email: str
