"""
Schemas for JWT authentication endpoints
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class RegisterRequest(BaseModel):
    """Request body for POST /register"""
    name: str = Field(..., min_length=1, max_length=120, description="Nome completo do admin")
    email: EmailStr = Field(..., description="Email (será usado no login)")
    password: str = Field(..., min_length=8, description="Senha (mínimo 8 caracteres)")
    org_name: str = Field(..., min_length=1, max_length=120, description="Nome da organização")


class RegisterResponse(BaseModel):
    """Response for POST /register"""
    user_id: str
    email: str
    org_id: str
    org_name: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Request body for POST /login"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Response for POST /login"""
    user_id: str
    email: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AcceptInviteRequest(BaseModel):
    """Request body for POST /accept-invite"""
    invite_token: str = Field(..., description="Token recebido por email")
    password: str = Field(..., min_length=8, description="Senha para a nova conta")


class AcceptInviteResponse(BaseModel):
    """Response for POST /accept-invite"""
    user_id: str
    email: str
    org_id: str
    org_name: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Request body for POST /refresh"""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Response for POST /refresh"""
    access_token: str
    token_type: str = "bearer"


class RegisterAdminRequest(BaseModel):
    """Request body for POST /register-admin"""
    name: str = Field(..., min_length=1, max_length=120, description="Nome do Platform Admin")
    email: EmailStr = Field(..., description="Email (será usado no login)")
    password: str = Field(..., min_length=8, description="Senha (mínimo 8 caracteres)")


class RegisterAdminResponse(BaseModel):
    """Response for POST /register-admin"""
    user_id: str
    name: str
    email: str
    role: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
