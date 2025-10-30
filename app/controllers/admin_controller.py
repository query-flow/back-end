"""
Admin endpoints - Platform Admin only (JWT-based) - MVC2 Pattern
"""
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import create_engine, text as sqltext
from sqlmodel import Session, select

from app.core.database import get_db
from app.core.security import encrypt_str, decrypt_str
from app.core.auth import require_platform_admin
from app.models import User, Organization, OrgDbConnection, OrgAllowedSchema, BizDocument, OrgMember

from app.schemas import (
    AdminOrgCreate,
    AdminOrgResponse,
    AuthedUser,
)
from app.utils.database import parse_database_url, build_sqlalchemy_url

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/orgs", response_model=AdminOrgResponse)
async def create_org(
    payload: AdminOrgCreate,
    _u: AuthedUser = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """Create a new organization"""
    try:
        parts = parse_database_url(payload.database_url)
        if not parts["username"] or not parts["password"]:
            raise HTTPException(
                status_code=400,
                detail="database_url deve conter usuário e senha."
            )

        org_id = uuid4().hex[:12]

        # Check if org name already exists
        existing = db.exec(
            select(Organization).where(Organization.name == payload.name)
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Já existe uma organização com esse nome."
            )

        # Create organization
        org = Organization(id=org_id, name=payload.name, status="active")
        db.add(org)

        # Create database connection
        db.add(OrgDbConnection(
            org_id=org_id,
            driver=parts["driver"],
            host=parts["host"],
            port=parts["port"],
            username=parts["username"],
            password_enc=encrypt_str(parts["password"]),
            database_name=parts["database_name"],
            options_json=parts["options"]
        ))

        # Add allowed schemas
        for s in payload.allowed_schemas:
            db.add(OrgAllowedSchema(org_id=org_id, schema_name=s))

        # Add documents
        for d in payload.documents:
            db.add(BizDocument(
                org_id=org_id,
                title=d["title"],
                metadata_json=d.get("metadata_json", {})
            ))

        db.commit()
        return AdminOrgResponse(
            org_id=org_id,
            name=payload.name,
            allowed_schemas=payload.allowed_schemas
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orgs/{org_id}", response_model=AdminOrgResponse)
async def get_org(
    org_id: str,
    _u: AuthedUser = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """Get organization details"""
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="org_id não encontrado.")

    schemas = [s.schema_name for s in org.allowed_schemas]
    return AdminOrgResponse(org_id=org.id, name=org.name, allowed_schemas=schemas)


@router.post("/orgs/{org_id}/test-connection")
async def test_connection(
    org_id: str,
    _u: AuthedUser = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """Test database connection for an organization"""
    org = db.get(Organization, org_id)
    if not (org and org.connection):
        raise HTTPException(status_code=404, detail="org_id não encontrado.")

    pwd = decrypt_str(org.connection.password_enc)
    db_url = build_sqlalchemy_url(
        org.connection.driver,
        org.connection.host,
        org.connection.port,
        org.connection.username,
        pwd,
        org.connection.database_name,
        org.connection.options_json
    )

    eng = create_engine(db_url, pool_pre_ping=True, future=True)
    try:
        with eng.connect() as c:
            cur = c.execute(sqltext("SELECT DATABASE()")).scalar()
            one = c.execute(sqltext("SELECT 1")).scalar()
        return {"ok": True, "database_corrente": cur, "select_1": one}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orgs/{org_id}/members")
async def add_member(
    org_id: str,
    user_id: str,
    role_in_org: str = "member",
    _u: AuthedUser = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """Add or update member in organization"""
    org = db.get(Organization, org_id)
    user = db.get(User, user_id)

    if not org:
        raise HTTPException(status_code=404, detail="org não encontrada.")
    if not user:
        raise HTTPException(status_code=404, detail="user não encontrado.")

    # Check if member already exists
    link = db.exec(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == user_id
        )
    ).first()

    if link:
        link.role_in_org = role_in_org
    else:
        db.add(OrgMember(
            user_id=user_id,
            org_id=org_id,
            role_in_org=role_in_org
        ))

    db.commit()
    return {"ok": True, "org_id": org_id, "user_id": user_id, "role_in_org": role_in_org}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    _u: AuthedUser = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """Delete a user"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user não encontrado.")

    db.delete(user)
    db.commit()
    return {"ok": True, "deleted_user_id": user_id}
