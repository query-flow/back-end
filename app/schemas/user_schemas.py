from typing import Optional
from pydantic import BaseModel, Field


class AuthedUser(BaseModel):
    id: str
    email: str
    role: str


class AdminUserCreate(BaseModel):
    name: str
    email: str
    role: str = Field(..., pattern="^(admin|user)$")
    api_key_plain: str = Field(..., min_length=16)
    org_id: Optional[str] = None
    org_role: Optional[str] = Field(default="member")


class AdminUserResponse(BaseModel):
    user_id: str
    name: str
    email: str
    role: str


class AdminOrgMemberAdd(BaseModel):
    user_id: str
    role_in_org: str = "member"
