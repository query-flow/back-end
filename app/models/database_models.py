from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Integer, Text, ForeignKey, JSON, UniqueConstraint, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active")

    # Relationships
    conn: Mapped["OrgDbConnection"] = relationship(
        back_populates="org", uselist=False, cascade="all, delete-orphan"
    )
    schemas: Mapped[List["OrgAllowedSchema"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )
    docs: Mapped[List["BizDocument"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )
    members: Mapped[List["OrgMember"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )


class OrgDbConnection(Base):
    __tablename__ = "org_db_connections"

    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("orgs.id"), primary_key=True)
    driver: Mapped[str] = mapped_column(String(40))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=3306)
    username: Mapped[str] = mapped_column(String(255))
    password_enc: Mapped[str] = mapped_column(Text)
    database_name: Mapped[str] = mapped_column(String(255))
    options_json: Mapped[dict] = mapped_column(JSON, default={})

    # Relationships
    org: Mapped[Org] = relationship(back_populates="conn")


class OrgAllowedSchema(Base):
    __tablename__ = "org_allowed_schemas"

    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("orgs.id"), primary_key=True)
    schema_name: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Relationships
    org: Mapped[Org] = relationship(back_populates="schemas")


class BizDocument(Base):
    __tablename__ = "biz_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("orgs.id"))
    title: Mapped[str] = mapped_column(String(255))
    metadata_json: Mapped[dict] = mapped_column(JSON, default={})

    # Relationships
    org: Mapped[Org] = relationship(back_populates="docs")


class QueryAudit(Base):
    __tablename__ = "query_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String(36))
    schema_used: Mapped[str] = mapped_column(String(255))
    prompt_snip: Mapped[str] = mapped_column(String(500))
    sql_text: Mapped[str] = mapped_column(Text)
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("api_key_sha", name="uq_users_api_key_sha"),
        UniqueConstraint("invite_token", name="uq_users_invite_token"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    role: Mapped[str] = mapped_column(String(10))  # 'admin' | 'user' (deprecated, use org_members.role_in_org)

    # JWT Authentication
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")  # active, inactive, invited
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Invitation system
    invite_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    invite_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Legacy (will be removed in future migration)
    api_key_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # sha256 of API key (deprecated)

    # Relationships
    org_links: Mapped[List["OrgMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class OrgMember(Base):
    __tablename__ = "org_members"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("orgs.id"), primary_key=True)
    role_in_org: Mapped[str] = mapped_column(String(20), default="member")

    # Relationships
    user: Mapped[User] = relationship(back_populates="org_links")
    org: Mapped[Org] = relationship(back_populates="members")
