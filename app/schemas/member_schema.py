"""
Schemas for member management endpoints
"""
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional


class InviteMemberRequest(BaseModel):
    """Request body for POST /members/invite"""
    email: EmailStr = Field(..., description="Email do membro a ser convidado")
    name: str = Field(..., min_length=1, max_length=120, description="Nome do membro")


class InviteMemberResponse(BaseModel):
    """Response for POST /members/invite"""
    user_id: str
    email: str
    name: str
    status: str
    invite_token: str
    invite_expires: str
    message: str


class MemberInfo(BaseModel):
    """Member information"""
    user_id: str
    name: str
    email: str
    role_in_org: str
    status: str


class ListMembersResponse(BaseModel):
    """Response for GET /members"""
    org_id: str
    org_name: str
    members: List[MemberInfo]


class UpdateMemberRoleRequest(BaseModel):
    """Request body for PUT /members/{user_id}"""
    role_in_org: str = Field(..., description="Nova role: 'org_admin' ou 'member'")


class UpdateMemberRoleResponse(BaseModel):
    """Response for PUT /members/{user_id}"""
    user_id: str
    email: str
    role_in_org: str
    message: str


class RemoveMemberResponse(BaseModel):
    """Response for DELETE /members/{user_id}"""
    user_id: str
    email: str
    message: str
