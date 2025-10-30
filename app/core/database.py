from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, create_engine as sqlmodel_create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Import all models to register them with SQLModel metadata
from app.models import User, Organization, OrgDbConnection, OrgAllowedSchema, BizDocument, QueryAudit, OrgMember

# Create database engine
engine = create_engine(settings.CONFIG_DB_URL, pool_pre_ping=True, future=True)

# Create session factory
SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False, future=True)


def get_db():
    """Dependency for getting database session"""
    with SessionLocal() as session:
        yield session


def init_db():
    """Initialize database tables"""
    SQLModel.metadata.create_all(engine)
