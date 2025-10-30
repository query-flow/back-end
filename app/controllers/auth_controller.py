"""
Authentication endpoints (JWT-based) - MVC2 Pattern
"""
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_invite_token,
    encrypt_str,
)
from app.models import User, Organization, OrgMember, OrgDbConnection, OrgAllowedSchema

# DTOs (Schemas)
from app.schemas import (
    RegisterRequest,
    RegisterResponse,
    RegisterAdminRequest,
    RegisterAdminResponse,
    LoginRequest,
    LoginResponse,
    AcceptInviteRequest,
    AcceptInviteResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse)
def register(p: RegisterRequest, db: Session = Depends(get_db)):
    """
    Registro de novo admin + criação de organização.

    Fluxo:
    1. Admin cria conta com email + senha
    2. Sistema cria organização automaticamente
    3. Admin é vinculado à org com role='org_admin'
    4. Retorna tokens JWT para acesso imediato
    """
    # Verificar se email já existe
    existing_user = db.exec(
        select(User).where(User.email == p.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email já cadastrado. Use /auth/login para entrar."
        )

    # Verificar se organização já existe
    existing_org = db.exec(
        select(Organization).where(Organization.name == p.org_name)
    ).first()
    if existing_org:
        raise HTTPException(
            status_code=400,
            detail=f"Organização '{p.org_name}' já existe. Escolha outro nome."
        )

    # Criar usuário (admin)
    user_id = str(uuid.uuid4())
    hashed_pw = hash_password(p.password)

    user = User(
        id=user_id,
        name=p.name,
        email=p.email,
        password_hash=hashed_pw,
        status="active",
        role="user",  # Campo legado, não mais usado
        password_changed_at=datetime.utcnow()
    )
    db.add(user)

    # Criar organização
    org_id = str(uuid.uuid4())
    org = Organization(
        id=org_id,
        name=p.org_name,
        status="active"
    )
    db.add(org)

    # Criar conexão de banco de dados
    db_connection = OrgDbConnection(
        org_id=org_id,
        driver="mysql+pymysql",
        host=p.db_host,
        port=p.db_port,
        username=p.db_user,
        password_enc=encrypt_str(p.db_password),
        database_name=p.db_name,
        options_json={}
    )
    db.add(db_connection)

    # Criar schemas permitidos
    for schema_name in p.allowed_schemas:
        allowed_schema = OrgAllowedSchema(
            org_id=org_id,
            schema_name=schema_name
        )
        db.add(allowed_schema)

    # Vincular user como org_admin
    org_member = OrgMember(
        user_id=user_id,
        org_id=org_id,
        role_in_org="org_admin"
    )
    db.add(org_member)

    db.commit()
    db.refresh(user)
    db.refresh(org)

    # Gerar tokens JWT
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})

    return RegisterResponse(
        user_id=user_id,
        email=user.email,
        org_id=org_id,
        org_name=org.name,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/register-admin", response_model=RegisterAdminResponse)
def register_admin(p: RegisterAdminRequest, db: Session = Depends(get_db)):
    """
    Registro de Platform Admin.

    Cria um usuário com role='admin' (acesso total à plataforma).

    ⚠️ ATENÇÃO: Em produção, este endpoint deve ser desabilitado
    ou protegido com autenticação de superadmin.
    """
    # Verificar se email já existe
    existing_user = db.exec(
        select(User).where(User.email == p.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email já cadastrado."
        )

    # Criar Platform Admin
    user_id = str(uuid.uuid4())[:12]
    hashed_pw = hash_password(p.password)

    admin = User(
        id=user_id,
        name=p.name,
        email=p.email,
        password_hash=hashed_pw,
        role="admin",  # ← Platform Admin
        status="active",
        password_changed_at=datetime.utcnow()
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    # Gerar tokens JWT
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})

    return RegisterAdminResponse(
        user_id=user_id,
        name=admin.name,
        email=admin.email,
        role=admin.role,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/login", response_model=LoginResponse)
def login(p: LoginRequest, db: Session = Depends(get_db)):
    """
    Login com email + senha.

    Retorna tokens JWT (access + refresh) se credenciais estiverem corretas.
    """
    # Buscar usuário por email
    user = db.exec(
        select(User).where(User.email == p.email)
    ).first()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Email ou senha incorretos"
        )

    # Verificar se usuário tem senha cadastrada
    if not user.password_hash:
        raise HTTPException(
            status_code=400,
            detail="Usuário sem senha. Aceite o convite primeiro via /auth/accept-invite"
        )

    # Verificar senha
    if not verify_password(p.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Email ou senha incorretos"
        )

    # Verificar status do usuário
    if user.status == "invited":
        raise HTTPException(
            status_code=403,
            detail="Usuário ainda não aceitou o convite. Use /auth/accept-invite"
        )

    if user.status != "active":
        raise HTTPException(
            status_code=403,
            detail=f"Conta está {user.status}. Contate o administrador."
        )

    # Gerar tokens JWT
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    return LoginResponse(
        user_id=user.id,
        email=user.email,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/accept-invite", response_model=AcceptInviteResponse)
def accept_invite(p: AcceptInviteRequest, db: Session = Depends(get_db)):
    """
    Aceitar convite de membro.

    Fluxo:
    1. Membro recebe email com invite_token
    2. Membro acessa este endpoint com token + senha desejada
    3. Sistema valida token e expira
    4. Membro é ativado e pode fazer login
    """
    # Buscar usuário pelo invite_token
    user = db.exec(
        select(User).where(User.invite_token == p.invite_token)
    ).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Token de convite inválido ou já usado"
        )

    # Verificar se token expirou
    if user.invite_expires and user.invite_expires < datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="Token de convite expirado. Solicite um novo convite ao administrador."
        )

    # Verificar se usuário já está ativo
    if user.status == "active" and user.password_hash:
        raise HTTPException(
            status_code=400,
            detail="Convite já foi aceito. Use /auth/login para entrar."
        )

    # Ativar usuário
    user.password_hash = hash_password(p.password)
    user.status = "active"
    user.invite_token = None  # Invalidar token
    user.invite_expires = None
    user.password_changed_at = datetime.utcnow()

    db.commit()
    db.refresh(user)

    # Buscar organização do usuário
    org_link = db.exec(
        select(OrgMember).where(OrgMember.user_id == user.id)
    ).first()
    if not org_link:
        raise HTTPException(
            status_code=500,
            detail="Erro: usuário sem organização vinculada"
        )

    org = db.get(Organization, org_link.org_id)

    # Gerar tokens JWT
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    return AcceptInviteResponse(
        user_id=user.id,
        email=user.email,
        org_id=org.id,
        org_name=org.name,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_access_token(p: RefreshTokenRequest):
    """
    Renovar access token usando refresh token.

    Fluxo:
    1. Cliente envia refresh_token
    2. Sistema valida e gera novo access_token
    3. Refresh token continua válido
    """
    # Decodificar refresh token
    payload = decode_token(p.refresh_token)

    # Verificar tipo do token
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=400,
            detail="Token fornecido não é um refresh token"
        )

    # Extrair user_id
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="Token inválido: subject (sub) ausente"
        )

    # Gerar novo access token
    access_token = create_access_token(data={"sub": user_id})

    return RefreshTokenResponse(
        access_token=access_token,
        token_type="bearer"
    )


@router.post("/admin-login", response_model=LoginResponse)
def admin_login(p: LoginRequest, db: Session = Depends(get_db)):
    """
    Login exclusivo para Platform Admins (role='admin').

    Diferença de Org Admin:
    - Platform Admin (role='admin'): Acesso total à plataforma
    - Org Admin (role_in_org='org_admin'): Acesso apenas à sua organização
    """
    # Buscar usuário por email
    user = db.exec(
        select(User).where(User.email == p.email)
    ).first()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Email ou senha incorretos"
        )

    # Verificar se usuário tem senha cadastrada
    if not user.password_hash:
        raise HTTPException(
            status_code=400,
            detail="Usuário sem senha cadastrada"
        )

    # Verificar senha
    if not verify_password(p.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Email ou senha incorretos"
        )

    # Verificar se é Platform Admin
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a Platform Admins. Use /auth/login para Org Admins."
        )

    # Verificar status
    if user.status != "active":
        raise HTTPException(
            status_code=403,
            detail=f"Usuário com status '{user.status}' não pode fazer login"
        )

    # Gerar tokens JWT
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    return LoginResponse(
        user_id=user.id,
        email=user.email,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )

@router.get("/debug/me")
async def debug_current_user(
    u=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    DEBUG: Ver informações do usuário autenticado e sua organização.
    Útil para verificar se o JWT tem org_id populado.
    """
    from app.core.auth import get_current_user
    from app.models import OrgMember

    # Buscar OrgMember
    org_link = db.exec(
        select(OrgMember).where(OrgMember.user_id == u.id)
    ).first()

    return {
        "user_id": u.id,
        "email": u.email,
        "role": u.role,
        "org_id_in_token": u.org_id,
        "org_member_exists": bool(org_link),
        "org_member_org_id": org_link.org_id if org_link else None,
        "org_member_role": org_link.role_in_org if org_link else None
    }
