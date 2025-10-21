from .admin import router as admin_router
from .query import router as query_router
from .bootstrap import router as bootstrap_router
from .documents import router as documents_router
from .debug import router as debug_router

__all__ = [
    "admin_router",
    "query_router",
    "bootstrap_router",
    "documents_router",
    "debug_router",
]
