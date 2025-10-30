"""
Controllers - MVC2 Pattern
All controllers (routes) organized by layer
"""
from app.controllers.auth_controller import router as auth_router
from app.controllers.admin_controller import router as admin_router
from app.controllers.documents_controller import router as documents_router
from app.controllers.members_controller import router as members_router
from app.controllers.queries_controller import router as queries_router

__all__ = [
    "auth_router",
    "admin_router",
    "documents_router",
    "members_router",
    "queries_router",
]
