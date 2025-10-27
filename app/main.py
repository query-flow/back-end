from uuid import uuid4
from fastapi import FastAPI

from app.core.config import settings
from app.core.database import init_db, SessionLocal
from app.core.security import sha256_hex
from app.models import User
from app.api.routers import (
    admin_router,
    query_router,
    documents_router,
    auth_router,
    members_router,
)

# Create FastAPI app
app = FastAPI(title=settings.APP_TITLE)


@app.on_event("startup")
def startup():
    """
    Initialize database and seed superadmin if configured
    """
    # Create all tables
    init_db()

    # Seed superadmin from environment variables
    if settings.SUPERADMIN_EMAIL and settings.SUPERADMIN_API_KEY:
        with SessionLocal() as s:
            exists = s.query(User).filter_by(email=settings.SUPERADMIN_EMAIL).one_or_none()
            if not exists:
                s.add(User(
                    id=uuid4().hex[:12],
                    name=settings.SUPERADMIN_NAME or "Super Admin",
                    email=settings.SUPERADMIN_EMAIL,
                    role="admin",
                    api_key_sha=sha256_hex(settings.SUPERADMIN_API_KEY)
                ))
                s.commit()


# Include routers
app.include_router(auth_router)  # JWT authentication endpoints (public)
app.include_router(members_router)  # Member management (admin only)
app.include_router(admin_router)
app.include_router(query_router)
app.include_router(documents_router)


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "NL→SQL Multi-Org API",
        "docs": "/docs",
        "version": "2.0-refactored"
    }
