"""
Core dependencies - Authentication and authorization
"""
from typing import Optional
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select

from app.core.database import get_db
from app.core.security import decode_token, sha256_hex
from app.models import User, OrgMember
from app.schemas import AuthedUser

# JWT Security
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> AuthedUser:
    """
    JWT-based authentication dependency.
    Extracts user from JWT token in Authorization header.

    Usage:
        @router.get("/protected")
        def protected_route(user: AuthedUser = Depends(get_current_user)):
            ...
    """
    token = credentials.credentials

    # Decode and validate JWT token
    payload = decode_token(token)

    # Extract user_id from token
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Token inválido: subject (sub) ausente",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Load user from database
    user = db.exec(
        select(User).where(User.id == user_id)
    ).first()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Usuário não encontrado",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Check if user is active
    if user.status != "active":
        raise HTTPException(
            status_code=403,
            detail=f"Usuário está {user.status}, não pode acessar a API",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Return authenticated user info with org_id from first org membership
    org_link = db.exec(
        select(OrgMember).where(OrgMember.user_id == user.id)
    ).first()

    return AuthedUser(
        id=user.id,
        email=user.email,
        role=user.role,
        org_id=org_link.org_id if org_link else None
    )


async def require_org_admin(
    current_user: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AuthedUser:
    """
    Dependency to require organization admin role.
    User must have role_in_org='org_admin' in at least one organization.

    Usage:
        @router.post("/admin/members/invite")
        def invite_member(admin: AuthedUser = Depends(require_org_admin)):
            ...
    """
    # Check if user is org_admin in any organization
    admin_link = db.exec(
        select(OrgMember).where(
            OrgMember.user_id == current_user.id,
            OrgMember.role_in_org == "org_admin"
        )
    ).first()

    if not admin_link:
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a administradores da organização"
        )

    return current_user


def require_org_access(org_id: str, user: AuthedUser, db: Session) -> OrgMember:
    """
    Check if user has access to a specific organization.
    Returns the OrgMember link if access is granted.

    Usage:
        def my_route(org_id: str, user: AuthedUser = Depends(get_current_user), db: Session = Depends(get_db)):
            member = require_org_access(org_id, user, db)
            # Now you have access to member.role_in_org
    """
    link = db.exec(
        select(OrgMember).where(
            OrgMember.user_id == user.id,
            OrgMember.org_id == org_id
        )
    ).first()
    if not link:
        raise HTTPException(
            status_code=403,
            detail="Sem acesso a esta organização"
        )

    return link


def require_org_admin_access(org_id: str, user: AuthedUser, db: Session) -> OrgMember:
    """
    Check if user is an admin of a specific organization.

    Usage:
        def my_route(org_id: str, user: AuthedUser = Depends(get_current_user), db: Session = Depends(get_db)):
            admin_link = require_org_admin_access(org_id, user, db)
            # User is confirmed org_admin
    """
    link = db.exec(
        select(OrgMember).where(
            OrgMember.user_id == user.id,
            OrgMember.org_id == org_id,
            OrgMember.role_in_org == "org_admin"
        )
    ).first()

    if not link:
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a administradores desta organização"
        )

    return link


async def require_platform_admin(
    current_user: AuthedUser = Depends(get_current_user)
) -> AuthedUser:
    """
    Dependency to require Platform Admin role (JWT-based).

    Platform Admin (user.role='admin') has full access to the platform,
    including /admin/* endpoints for managing organizations, users, and infrastructure.

    Difference from Org Admin:
    - Platform Admin: Global access to all organizations and platform management
    - Org Admin: Access only to their specific organization

    Usage:
        @router.post("/admin/orgs")
        def create_org(admin: AuthedUser = Depends(require_platform_admin)):
            # Only Platform Admins can access this
            ...
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a Platform Admins. Use /auth/admin-login para autenticar."
        )

    return current_user


def get_user_org_id(user: AuthedUser) -> str:
    """
    Extract org_id from authenticated user.
    Raises HTTPException if user doesn't belong to any organization.

    Usage:
        def my_route(user: AuthedUser = Depends(get_current_user)):
            org_id = get_user_org_id(user)
            # Use org_id...
    """
    if not user.org_id:
        raise HTTPException(
            status_code=403,
            detail="Usuário não pertence a nenhuma organização"
        )
    return user.org_id
