from uuid import uuid4
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import create_engine, text as sqltext
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import sha256_hex, encrypt_str, decrypt_str
from app.dependencies.auth import require_platform_admin
from app.models import Org, OrgDbConnection, OrgAllowedSchema, BizDocument, User, OrgMember
from app.schemas import (
    AdminOrgCreate,
    AdminOrgResponse,
    AdminUserCreate,
    AdminUserResponse,
    AdminOrgMemberAdd,
    AuthedUser,
)
from app.utils.database_utils import parse_database_url, build_sqlalchemy_url

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/orgs", response_model=AdminOrgResponse)
async def create_org(payload: AdminOrgCreate, _u: AuthedUser = Depends(require_platform_admin), db: Session = Depends(get_db)):
    """Create a new organization"""
    try:
        parts = parse_database_url(payload.database_url)
        if not parts["username"] or not parts["password"]:
            raise HTTPException(status_code=400, detail="database_url deve conter usuário e senha.")

        org_id = uuid4().hex[:12]

        if db.query(Org).filter(Org.name == payload.name).first():
            raise HTTPException(status_code=400, detail="Já existe uma organização com esse nome.")

        org = Org(id=org_id, name=payload.name, status="active")
        db.add(org)

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

        for s in payload.allowed_schemas:
            db.add(OrgAllowedSchema(org_id=org_id, schema_name=s))

        for d in payload.documents:
            db.add(BizDocument(
                org_id=org_id,
                title=d["title"],
                metadata_json=d.get("metadata_json", {})
            ))

        db.commit()
        return AdminOrgResponse(org_id=org_id, name=payload.name, allowed_schemas=payload.allowed_schemas)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orgs/{org_id}", response_model=AdminOrgResponse)
async def get_org(org_id: str, _u: AuthedUser = Depends(require_platform_admin), db: Session = Depends(get_db)):
    """Get organization details"""
    org = db.get(Org, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="org_id não encontrado.")

    schemas = [s.schema_name for s in org.schemas]
    return AdminOrgResponse(org_id=org.id, name=org.name, allowed_schemas=schemas)


@router.post("/orgs/{org_id}/test-connection")
async def test_connection(org_id: str, _u: AuthedUser = Depends(require_platform_admin), db: Session = Depends(get_db)):
    """Test database connection for an organization"""
    org = db.get(Org, org_id)
    if not (org and org.conn):
        raise HTTPException(status_code=404, detail="org_id não encontrado.")

    pwd = decrypt_str(org.conn.password_enc)
    db_url = build_sqlalchemy_url(
        org.conn.driver, org.conn.host, org.conn.port,
        org.conn.username, pwd, org.conn.database_name, org.conn.options_json
    )

    eng = create_engine(db_url, pool_pre_ping=True, future=True)
    try:
        with eng.connect() as c:
            cur = c.execute(sqltext("SELECT DATABASE()")).scalar()
            one = c.execute(sqltext("SELECT 1")).scalar()
        return {"ok": True, "database_corrente": cur, "select_1": one}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users", response_model=AdminUserResponse)
async def create_user(payload: AdminUserCreate, _u: AuthedUser = Depends(require_platform_admin), db: Session = Depends(get_db)):
    """Create a new user"""
    if db.query(User).filter_by(email=payload.email).one_or_none():
        raise HTTPException(status_code=400, detail="Email já cadastrado.")

    if db.query(User).filter_by(api_key_sha=sha256_hex(payload.api_key_plain)).one_or_none():
        raise HTTPException(status_code=400, detail="API key já está em uso. Gere uma diferente.")

    user = User(
        id=uuid4().hex[:12],
        name=payload.name,
        email=payload.email,
        role=payload.role,
        api_key_sha=sha256_hex(payload.api_key_plain),
    )
    db.add(user)

    # Auto-link to org if specified
    if payload.org_id:
        org = db.get(Org, payload.org_id)
        if not org:
            raise HTTPException(status_code=404, detail="org_id para vincular não encontrada.")
        db.add(OrgMember(user_id=user.id, org_id=payload.org_id, role_in_org=payload.org_role or "member"))

    db.commit()
    return AdminUserResponse(user_id=user.id, name=user.name, email=user.email, role=user.role)


@router.post("/orgs/{org_id}/members")
async def add_member(org_id: str, payload: AdminOrgMemberAdd, _u: AuthedUser = Depends(require_platform_admin), db: Session = Depends(get_db)):
    """Add or update member in organization"""
    org = db.get(Org, org_id)
    user = db.get(User, payload.user_id)

    if not org:
        raise HTTPException(status_code=404, detail="org não encontrada.")
    if not user:
        raise HTTPException(status_code=404, detail="user não encontrado.")

    link = db.query(OrgMember).filter_by(org_id=org_id, user_id=user.id).one_or_none()
    if link:
        link.role_in_org = payload.role_in_org
    else:
        db.add(OrgMember(user_id=user.id, org_id=org_id, role_in_org=payload.role_in_org))

    db.commit()
    return {"ok": True, "org_id": org_id, "user_id": user.id, "role_in_org": payload.role_in_org}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, _u: AuthedUser = Depends(require_platform_admin), db: Session = Depends(get_db)):
    """Delete a user"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user não encontrado.")

    db.delete(user)
    db.commit()
    return {"ok": True, "deleted_user_id": user_id}
