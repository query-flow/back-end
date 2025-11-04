"""
Natural Language to SQL Query Pipeline - MVC2 Pattern
"""
import time
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import create_engine
from sqlmodel import Session, select

from app.core.database import get_db, SessionLocal
from app.core.security import decrypt_str
from app.core.auth import get_current_user, get_user_org_id
from app.models import Organization, OrgAllowedSchema, QueryAudit, ClarificationSession
from app.schemas import PerguntaOrg, AuthedUser
from app.pipeline.llm.sql_pipeline import (
    analyze_intent,
    generate_sql,
    correct_sql,
    build_clarified_question,
    generate_insights,
    pick_schema,
    QueryResult,
    InsightsGenerated,
    generate_chart
)
from app.pipeline.catalog import (
    catalog_for_current_db,
    esquema_resumido,
    get_schema_index_for_org,
    rank_schemas_by_overlap,
)
from app.pipeline.sql_executor import proteger_sql_singledb, executar_sql_readonly_on_conn
from app.utils.database import build_sqlalchemy_url

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Query"])


def collect_biz_context_for_org(org: Organization) -> str:
    """
    Collect business context from organization documents
    """
    if not org.documents:
        return "Sem documentos de negócio cadastrados."

    partes = []
    for d in org.documents:
        md = d.metadata_json or {}
        md_txt = "; ".join(f"{k}: {v}" for k, v in md.items())
        partes.append(f"- {d.title} ({md_txt})" if md_txt else f"- {d.title}")

    return "Documentos de negócio cadastrados:\n" + "\n".join(partes)


@router.post("/perguntar_org")
async def perguntar_org(
    p: PerguntaOrg,
    u: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Main endpoint with clarification support

    Two flows:
    1. New question → check clarity → maybe ask clarification
    2. Clarification response → build clarified question → execute
    """
    try:
        # Get user's org_id
        org_id = get_user_org_id(u)

        # Load org config and business context
        with SessionLocal() as s:
            org = s.get(Organization, org_id)
            if not org:
                raise HTTPException(
                    status_code=404,
                    detail=f"Organização '{org_id}' não encontrada. Verifique se a org existe."
                )
            if not org.connection:
                raise HTTPException(
                    status_code=400,
                    detail=f"Organização '{org_id}' não tem conexão de banco configurada."
                )

            allowed = [x.schema_name for x in org.allowed_schemas]
            if not allowed:
                raise HTTPException(status_code=400, detail="Org sem schemas permitidos.")

            biz_context = collect_biz_context_for_org(org)

            pwd = decrypt_str(org.connection.password_enc)
            base_parts = (
                org.connection.driver,
                org.connection.host,
                org.connection.port,
                org.connection.username,
                pwd,
                org.connection.options_json,
                org.connection.database_name
            )

        # Build schema index for routing
        base_url_default_db = build_sqlalchemy_url(
            base_parts[0], base_parts[1], base_parts[2], base_parts[3], base_parts[4],
            base_parts[6], base_parts[5]
        )

        schema_index = get_schema_index_for_org(org_id, base_url_default_db, allowed)
        ranked = rank_schemas_by_overlap(schema_index, p.pergunta)

        best_by_overlap, top_score = ranked[0]
        top_ties = [s for s, sc in ranked if sc == top_score]

        # Use LLM to pick schema if there's ambiguity
        if top_score == 0 or len(top_ties) > 1:
            picked = pick_schema(allowed, p.pergunta)
            preferred = picked or best_by_overlap
        else:
            preferred = best_by_overlap

        schema_try_order = [preferred] + [s for s in allowed if s != preferred]

        # ========================================
        # FLOW 2: Handle clarification response
        # ========================================

        if p.clarification_id:
            logger.info(f"Processing clarification: {p.clarification_id}")

            # Load session
            session = db.get(ClarificationSession, p.clarification_id)
            if not session or session.expires_at < datetime.utcnow():
                raise HTTPException(400, "Clarification session expired or not found")

            # Build clarified question
            clarified_question = build_clarified_question(
                session.original_question,
                p.clarifications or {}
            )

            # Use the schema from session
            schema = session.schema_name

            # Connect and generate SQL (no intent check)
            db_url = build_sqlalchemy_url(
                base_parts[0], base_parts[1], base_parts[2],
                base_parts[3], base_parts[4], schema, base_parts[5]
            )
            eng = create_engine(db_url, pool_pre_ping=True, future=True)

            with eng.connect() as conn:
                catalog = catalog_for_current_db(conn, db_name=schema)
                esquema_txt = esquema_resumido(catalog)

                # Generate SQL directly (skip intent analysis)
                sql = generate_sql(clarified_question, esquema_txt, p.max_linhas)

                # Protect and execute SQL
                sql_seguro = proteger_sql_singledb(sql, catalog, db_name=schema, max_linhas=p.max_linhas)

                t0 = time.time()
                try:
                    resultado = executar_sql_readonly_on_conn(conn, sql_seguro)
                except Exception as err:
                    # Retry with correction
                    sql2 = correct_sql(sql_seguro, str(err), esquema_txt, p.max_linhas)
                    sql_seguro = proteger_sql_singledb(sql2, catalog, db_name=schema, max_linhas=p.max_linhas)
                    resultado = executar_sql_readonly_on_conn(conn, sql_seguro)

                dur_ms = int((time.time() - t0) * 1000)

            # Audit log
            try:
                with SessionLocal() as s:
                    s.add(QueryAudit(
                        org_id=org_id,
                        schema_used=schema,
                        prompt_snip=clarified_question[:500],
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
                colunas = resultado.get("colunas", [])
                dados_dict = resultado.get("dados", [])
                dados_list = [[row.get(col) for col in colunas] for row in dados_dict]

                # Generate insights using new pipeline
                insights_text = generate_insights(
                    pergunta=clarified_question,
                    colunas=colunas,
                    dados=dados_list,
                    biz_context=biz_context
                )

                # Generate chart
                chart_data = None
                try:
                    query_result = QueryResult(
                        sql=sql_seguro,
                        schema=schema,
                        colunas=colunas,
                        dados=dados_list
                    )
                    chart_data = generate_chart(query_result)
                except Exception as e:
                    logger.warning(f"Chart generation failed: {e}")

                insights_payload = {
                    "summary": insights_text,
                    "chart": {"mime": "image/png", "base64": chart_data} if chart_data else None
                }

            # Cleanup session
            db.delete(session)
            db.commit()

            return {
                "org_id": org_id,
                "schema_usado": schema,
                "sql": sql_seguro,
                "resultado": resultado,
                "insights": insights_payload
            }

        # ========================================
        # FLOW 1: New question with intent check
        # ========================================

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

                    # NEW: Analyze intent first
                    intent = analyze_intent(
                        pergunta=p.pergunta,
                        esquema=esquema_txt,
                        confidence_threshold=0.5  # Só bloqueia quando crítico
                    )

                    # NEW: Check if schema mismatch (data doesn't exist)
                    if intent.schema_mismatch:
                        logger.warning(f"Schema mismatch detected: {intent.missing_data}")
                        return {
                            "status": "schema_error",
                            "message": "Desculpe, esses dados não estão disponíveis no sistema.",
                            "missing_data": intent.missing_data,
                            "suggestions": intent.questions[0]["options"] if intent.questions else [],
                            "confidence": intent.confidence
                        }

                    # NEW: Check if clarification needed
                    if not intent.is_clear:
                        logger.warning(f"Low confidence ({intent.confidence:.2f}), requesting clarification")

                        # Save session
                        session = ClarificationSession(
                            id=str(uuid.uuid4()),
                            org_id=org_id,
                            user_id=u.id,
                            original_question=p.pergunta,
                            schema_name=schema,
                            intent_analysis=intent.dict(),
                            created_at=datetime.utcnow(),
                            expires_at=datetime.utcnow() + timedelta(minutes=10)
                        )
                        db.add(session)
                        db.commit()

                        # Return clarification request (stop here!)
                        return {
                            "status": "needs_clarification",
                            "clarification_id": session.id,
                            "message": "Preciso de mais detalhes para gerar uma consulta precisa:",
                            "questions": intent.questions,
                            "ambiguities": intent.ambiguities,
                            "confidence": intent.confidence
                        }

                    # Intent is clear, generate SQL
                    sql = generate_sql(p.pergunta, esquema_txt, p.max_linhas)

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
                        # Retry with correction using new pipeline
                        sql2 = correct_sql(
                            sql_original=sql_seguro,
                            erro=str(err),
                            esquema=esquema_txt,
                            limit=p.max_linhas
                        )
                        sql_seguro = proteger_sql_singledb(sql2, catalog, db_name=schema, max_linhas=p.max_linhas)
                        resultado = executar_sql_readonly_on_conn(conn, sql_seguro)

                    dur_ms = int((time.time() - t0) * 1000)

                # Audit log (best-effort)
                try:
                    with SessionLocal() as s:
                        s.add(QueryAudit(
                            org_id=org_id,
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
                    colunas = resultado.get("colunas", [])
                    dados_dict = resultado.get("dados", [])
                    dados_list = [[row.get(col) for col in colunas] for row in dados_dict]

                    # Generate insights using new pipeline
                    insights_text = generate_insights(
                        pergunta=p.pergunta,
                        colunas=colunas,
                        dados=dados_list,
                        biz_context=biz_context
                    )

                    # Generate chart
                    chart_data = None
                    try:
                        query_result = QueryResult(
                            sql=sql_seguro,
                            schema=schema,
                            colunas=colunas,
                            dados=dados_list
                        )
                        chart_data = generate_chart(query_result)
                    except Exception as e:
                        logger.warning(f"Chart generation failed: {e}")

                    insights_payload = {
                        "summary": insights_text,
                        "chart": {"mime": "image/png", "base64": chart_data} if chart_data else None
                    }

                return {
                    "org_id": org_id,
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
