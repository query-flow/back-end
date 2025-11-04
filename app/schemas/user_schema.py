from typing import Optional
from pydantic import BaseModel, Field


class AuthedUser(BaseModel):
    id: str
    email: str
    org_id: Optional[str] = None


