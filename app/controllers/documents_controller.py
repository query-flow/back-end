"""
Document management endpoints - MVC2 Pattern
CONTROLLER = Coordena Model e View
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from sqlmodel import Session, select

from app.core.database import get_db
from app.core.auth import get_current_user, get_user_org_id
from app.models import Organization, BizDocument
from app.utils.documents import extract_text_from_upload, summarize_business_metadata
from app.schemas import AuthedUser

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", response_model=dict)
async def create_document(
    titulo: str,
    conteudo: str,
    tipo: str = "data_dictionary",
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    CONTROLLER: Create a business document with manual metadata

    MVC2 Flow:
    1. Controller recebe requisição
    2. Controller valida acesso
    3. Controller chama MODEL para criar documento
    4. Controller retorna VIEW (JSON response)
    """
    # Get user's org_id
    org_id = get_user_org_id(u)

    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="org não encontrada.")

    # CONTROLLER chama MODEL diretamente (sem Service)
    doc = BizDocument.create(
        db=db,
        org_id=org_id,
        title=titulo,
        metadata_json={
            "content": conteudo,
            "type": tipo
        }
    )

    return {"ok": True, "doc_id": doc.id, "org_id": org_id}


@router.get("", response_model=dict)
async def list_documents(
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    CONTROLLER: List all business documents for user's organization
    """
    # Get user's org_id
    org_id = get_user_org_id(u)

    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="org não encontrada.")

    # CONTROLLER chama MODEL diretamente
    docs = BizDocument.list_by_org(db=db, org_id=org_id)

    return {
        "org_id": org_id,
        "documents": [
            {"id": d.id, "title": d.title, "metadata_json": d.metadata_json}
            for d in docs
        ]
    }


@router.post("/extract", response_model=dict)
async def extract_document(
    title: str = Form(...),
    file: UploadFile = File(...),
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    CONTROLLER: Upload and extract metadata from a business document (PDF, DOCX, TXT)
    """
    # Get user's org_id
    org_id = get_user_org_id(u)

    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="org não encontrada.")

    raw_text = extract_text_from_upload(file)
    meta = summarize_business_metadata(raw_text)

    # CONTROLLER chama MODEL diretamente
    doc = BizDocument.create(
        db=db,
        org_id=org_id,
        title=title,
        metadata_json={
            "content": raw_text,
            "type": "business_document",
            "meta": meta
        }
    )

    return {
        "ok": True,
        "doc_id": doc.id,
        "org_id": org_id,
        "title": title,
        "meta_preview": meta
    }


@router.delete("/{doc_id}", response_model=dict)
async def delete_document(
    doc_id: int,
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    CONTROLLER: Delete a document
    """
    # Get user's org_id
    org_id = get_user_org_id(u)

    # CONTROLLER chama MODEL para buscar
    doc = BizDocument.get_by_id(db=db, doc_id=doc_id)
    if not doc or doc.org_id != org_id:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    # CONTROLLER chama MODEL para deletar
    doc.delete(db=db)

    return {"ok": True, "deleted_doc_id": doc_id}
