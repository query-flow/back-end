from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.models import Base

# Create database engine
engine = create_engine(settings.CONFIG_DB_URL, pool_pre_ping=True, future=True)

# Create session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    """Dependency for getting database session"""
    with SessionLocal() as session:
        yield session


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(engine)
