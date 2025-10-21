from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import create_engine, text as sqltext
from sqlalchemy.engine import make_url

from app.core.config import settings, DOTENV_PATH
from app.dependencies.auth import require_admin
from app.schemas import PerguntaDireta, AuthedUser

router = APIRouter(tags=["Debug"])


@router.post("/_debug_connect")
def debug_connect(p: PerguntaDireta, _u: AuthedUser = Depends(require_admin)):
    """
    Debug endpoint to test direct database connection
    """
    u = make_url(p.database_url)
    if not u.database:
        raise HTTPException(status_code=400, detail="Passe uma database_url com DB/schema.")

    eng = create_engine(p.database_url, pool_pre_ping=True, future=True)
    try:
        with eng.connect() as c:
            dbn = c.execute(sqltext("SELECT DATABASE()")).scalar()
            dbs = [r[0] for r in c.execute(sqltext("SHOW DATABASES"))]
            one = c.execute(sqltext("SELECT 1")).scalar()
        return {"ok": True, "database_corrente": dbn, "databases": dbs, "select_1": one}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/_env")
def get_env(_u: AuthedUser = Depends(require_admin)):
    """
    Debug endpoint to check environment configuration
    """
    return {
        "loaded_dotenv_from": str(DOTENV_PATH),
        "DISABLE_AZURE_LLM": settings.DISABLE_AZURE_LLM,
        "AZURE_OPENAI_ENDPOINT_set": bool(settings.AZURE_OPENAI_ENDPOINT),
        "AZURE_OPENAI_DEPLOYMENT_set": bool(settings.AZURE_OPENAI_DEPLOYMENT),
        "AZURE_OPENAI_API_KEY_set": bool(settings.AZURE_OPENAI_API_KEY),
        "AZURE_OPENAI_API_VERSION": settings.AZURE_OPENAI_API_VERSION,
    }
