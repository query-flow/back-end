from fastapi import HTTPException, Depends, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import MultipleResultsFound

from app.core.database import get_db
from app.core.security import sha256_hex
from app.models import User, OrgMember
from app.schemas import AuthedUser


def auth_required(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db)
) -> AuthedUser:
    """Dependency to require authentication via API key"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key ausente.")

    try:
        user = db.query(User).filter_by(api_key_sha=sha256_hex(x_api_key)).one_or_none()
    except MultipleResultsFound:
        raise HTTPException(
            status_code=401,
            detail="API Key ambígua (duplicada). Rotacione a chave ou contate o admin."
        )

    if not user:
        raise HTTPException(status_code=401, detail="API Key inválida.")

    return AuthedUser(id=user.id, email=user.email, role=user.role)


def require_admin(user: AuthedUser = Depends(auth_required)) -> AuthedUser:
    """Dependency to require admin role"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a admin.")
    return user


def require_user_or_admin(user: AuthedUser = Depends(auth_required)) -> AuthedUser:
    """Dependency to require user or admin role"""
    if user.role not in ("admin", "user"):
        raise HTTPException(status_code=403, detail="Acesso negado.")
    return user


def require_org_access(org_id: str, user: AuthedUser, db: Session) -> None:
    """Check if user has access to organization"""
    if user.role == "admin":
        return

    link = db.query(OrgMember).filter_by(user_id=user.id, org_id=org_id).first()
    if not link:
        raise HTTPException(status_code=403, detail="Sem acesso a esta organização.")
