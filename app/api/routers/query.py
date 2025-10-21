import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.core.security import decrypt_str
from app.dependencies.auth import require_user_or_admin, require_org_access
from app.models import Org, QueryAudit
from app.schemas import PerguntaOrg, AuthedUser
from app.services.llm_service import chamar_llm_azure, ask_llm_pick_schema, PROMPT_BASE
from app.services.catalog_service import (
    catalog_for_current_db,
    esquema_resumido,
    get_schema_index_for_org,
    rank_schemas_by_overlap,
)
from app.services.sql_service import proteger_sql_singledb, executar_sql_readonly_on_conn
from app.services.insights_service import (
    collect_biz_context_for_org,
    insights_from_llm,
    make_bar_chart_base64_generic,
)
from app.utils.database_utils import build_sqlalchemy_url

router = APIRouter(tags=["Query"])


@router.post("/perguntar_org")
def perguntar_org(
    p: PerguntaOrg,
    u: AuthedUser = Depends(require_user_or_admin),
    db: Session = Depends(get_db)
):
    """
    Main endpoint: convert natural language to SQL, execute, and optionally generate insights
    """
    try:
        # Check org access
        require_org_access(p.org_id, u, db)

        # Load org config and business context
        with SessionLocal() as s:
            org = s.get(Org, p.org_id)
            if not (org and org.conn):
                raise HTTPException(status_code=404, detail="org_id inválido.")

            allowed = [x.schema_name for x in org.schemas]
            if not allowed:
                raise HTTPException(status_code=400, detail="Org sem schemas permitidos.")

            biz_context = collect_biz_context_for_org(org)

            pwd = decrypt_str(org.conn.password_enc)
            base_parts = (
                org.conn.driver,
                org.conn.host,
                org.conn.port,
                org.conn.username,
                pwd,
                org.conn.options_json,
                org.conn.database_name
            )

        # Build schema index for routing
        base_url_default_db = build_sqlalchemy_url(
            base_parts[0], base_parts[1], base_parts[2], base_parts[3], base_parts[4],
            base_parts[6], base_parts[5]
        )

        schema_index = get_schema_index_for_org(p.org_id, base_url_default_db, allowed)
        ranked = rank_schemas_by_overlap(schema_index, p.pergunta)

        best_by_overlap, top_score = ranked[0]
        top_ties = [s for s, sc in ranked if sc == top_score]

        # Use LLM to pick schema if there's ambiguity
        if top_score == 0 or len(top_ties) > 1:
            picked = ask_llm_pick_schema(allowed, p.pergunta)
            preferred = picked or best_by_overlap
        else:
            preferred = best_by_overlap

        schema_try_order = [preferred] + [s for s in allowed if s != preferred]

        last_err: Optional[str] = None

        # Try executing on schemas in order
        for schema in schema_try_order:
            db_url = build_sqlalchemy_url(
                base_parts[0], base_parts[1], base_parts[2],
                base_parts[3], base_parts[4], schema, base_parts[5]
            )
            eng = create_engine(db_url, pool_pre_ping=True, future=True)

            try:
                with eng.connect() as conn:
                    catalog = catalog_for_current_db(conn, db_name=schema)
                    esquema_txt = esquema_resumido(catalog)
                    prompt = PROMPT_BASE.format(esquema=esquema_txt, pergunta=p.pergunta)
                    sql = chamar_llm_azure(prompt_usuario=prompt, limit=p.max_linhas, dialeto="MySQL")

                    try:
                        sql_seguro = proteger_sql_singledb(sql, catalog, db_name=schema, max_linhas=p.max_linhas)
                    except HTTPException as e:
                        msg = str(e.detail)
                        if "Tabela(s) não encontrada(s)" in msg or "multi-DB" in msg:
                            last_err = f"[{schema}] {msg}"
                            continue
                        raise

                    t0 = time.time()
                    try:
                        resultado = executar_sql_readonly_on_conn(conn, sql_seguro)
                    except Exception as err:
                        # Retry with correction
                        corre = (
                            f"Esquema:\n{esquema_txt}\n\nErro:\n{err}\n\n"
                            f"Corrija (somente SELECT, LIMIT {p.max_linhas} se faltar):\n{sql_seguro}"
                        )
                        sql2 = chamar_llm_azure(corre, limit=p.max_linhas, dialeto="MySQL")
                        sql_seguro = proteger_sql_singledb(sql2, catalog, db_name=schema, max_linhas=p.max_linhas)
                        resultado = executar_sql_readonly_on_conn(conn, sql_seguro)

                    dur_ms = int((time.time() - t0) * 1000)

                # Audit log (best-effort)
                try:
                    with SessionLocal() as s:
                        s.add(QueryAudit(
                            org_id=p.org_id,
                            schema_used=schema,
                            prompt_snip=p.pergunta[:500],
                            sql_text=sql_seguro,
                            row_count=len(resultado["dados"]) if resultado and "dados" in resultado else None,
                            duration_ms=dur_ms
                        ))
                        s.commit()
                except Exception:
                    pass

                # Generate insights if requested
                insights_payload = None
                if p.enrich:
                    summary = insights_from_llm(p.pergunta, resultado, biz_context)
                    chart_b64 = make_bar_chart_base64_generic(resultado)
                    chart = {"mime": "image/png", "base64": chart_b64} if chart_b64 else None
                    insights_payload = {"summary": summary, "chart": chart}

                return {
                    "org_id": p.org_id,
                    "schema_usado": schema,
                    "sql": sql_seguro,
                    "resultado": resultado,
                    "insights": insights_payload
                }

            except HTTPException as e:
                last_err = f"[{schema}] {e.detail}"
                continue
            except Exception as e:
                last_err = f"[{schema}] {e}"
                continue

        raise HTTPException(
            status_code=400,
            detail=last_err or "Falha ao executar em todos os schemas permitidos."
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
