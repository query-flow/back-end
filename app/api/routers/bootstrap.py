from uuid import uuid4
from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import sha256_hex, encrypt_str
from app.models import Org, OrgDbConnection, OrgAllowedSchema, User, OrgMember
from app.schemas import PublicBootstrapOrg, PublicBootstrapResponse
from app.utils.database_utils import parse_database_url

router = APIRouter(prefix="/public", tags=["Bootstrap"])


@router.post("/bootstrap_org", response_model=PublicBootstrapResponse)
def bootstrap_org(p: PublicBootstrapOrg):
    """
    Public endpoint for self-service organization and admin user creation
    """
    if len(p.admin_api_key) < 16:
        raise HTTPException(status_code=400, detail="admin_api_key deve ter pelo menos 16 caracteres.")

    if not p.allowed_schemas:
        raise HTTPException(status_code=400, detail="allowed_schemas não pode ser vazio.")

    parts = parse_database_url(p.database_url)
    if not parts["username"] or not parts["password"]:
        raise HTTPException(status_code=400, detail="database_url deve conter usuário e senha.")

    org_id = uuid4().hex[:12]
    admin_id = uuid4().hex[:12]

    try:
        with SessionLocal() as s:
            if s.query(Org).filter(Org.name == p.org_name).first():
                raise HTTPException(status_code=400, detail="Já existe uma organização com esse nome.")

            if s.query(User).filter(User.email == p.admin_email).first():
                raise HTTPException(status_code=400, detail="Já existe um usuário com esse e-mail.")

            if s.query(User).filter(User.api_key_sha == sha256_hex(p.admin_api_key)).first():
                raise HTTPException(status_code=400, detail="API key já está em uso. Informe outra.")

            org = Org(id=org_id, name=p.org_name, status="active")
            s.add(org)

            s.add(OrgDbConnection(
                org_id=org_id,
                driver=parts["driver"],
                host=parts["host"],
                port=parts["port"],
                username=parts["username"],
                password_enc=encrypt_str(parts["password"]),
                database_name=parts["database_name"],
                options_json=parts["options"]
            ))

            for sch in p.allowed_schemas:
                s.add(OrgAllowedSchema(org_id=org_id, schema_name=sch))

            admin_user = User(
                id=admin_id,
                name=p.admin_name,
                email=p.admin_email,
                role="admin",
                api_key_sha=sha256_hex(p.admin_api_key),
            )
            s.add(admin_user)
            s.add(OrgMember(user_id=admin_id, org_id=org_id, role_in_org="admin_org"))

            s.commit()

        return PublicBootstrapResponse(
            org_id=org_id,
            admin_user_id=admin_id,
            admin_email=p.admin_email
        )

    except IntegrityError as ie:
        raise HTTPException(
            status_code=400,
            detail=f"Violação de integridade no banco de configuração: {str(ie.orig)}"
        ) from ie
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Falha no bootstrap: {e}")
