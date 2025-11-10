"""
Service for query execution orchestration
Encapsulates the full query execution pipeline
"""
import time
import logging
from typing import Optional, Dict, Any, Tuple, Callable
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection

from app.dtos import (
    OrgContext,
    QueryExecutionContext,
    IntentAnalysisResult,
    StreamEvent,
)
from app.repositories.clarification_repository import ClarificationRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.conversation_repository import ConversationRepository
from app.services.enrichment_service import EnrichmentService
from app.pipeline.stages import (
    analyze_intent,
    generate_sql,
    correct_sql,
    build_clarified_question,
    pick_schema,
)
from app.pipeline.sql import (
    catalog_for_current_db,
    esquema_resumido,
    get_schema_index_for_org,
    rank_schemas_by_overlap,
    proteger_sql_singledb,
    executar_sql_readonly_on_conn,
)

logger = logging.getLogger(__name__)


class QueryService:
    """
    Orchestrates query execution pipeline
    Handles intent analysis, SQL generation, execution, and enrichment
    """

    def __init__(
        self,
        clarification_repo: ClarificationRepository,
        audit_repo: AuditRepository,
        enrichment_service: EnrichmentService,
        conversation_repo: Optional[ConversationRepository] = None
    ):
        self.clarification_repo = clarification_repo
        self.audit_repo = audit_repo
        self.enrichment_service = enrichment_service
        self.conversation_repo = conversation_repo

    def execute_query(
        self,
        ctx: QueryExecutionContext,
        org_ctx: OrgContext,
        event_callback: Optional[Callable[[StreamEvent], None]] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for query execution

        Handles three flows:
        1. New question → intent analysis → maybe clarification
        2. Clarification response → build clarified question → execute
        3. Conversation → load history → execute with context

        Args:
            ctx: Query execution context
            org_ctx: Organization context
            event_callback: Optional callback to emit progress events
            user_id: User ID (for conversation tracking)
            conversation_id: Optional conversation ID for context

        Returns:
            Response dict with results or clarification request
        """
        ctx.started_at = datetime.utcnow()

        # Load conversation history if conversation_id provided
        if conversation_id and self.conversation_repo:
            try:
                history = self.conversation_repo.get_conversation_history_for_llm(
                    conversation_id,
                    max_messages=10
                )
                ctx.conversation_history = history
                logger.info(f"Loaded {len(history)} messages from conversation {conversation_id}")
            except Exception as e:
                logger.warning(f"Failed to load conversation history: {e}")

        # Emit start event
        if event_callback:
            event_callback(StreamEvent(
                stage="started",
                progress=0,
                message="Iniciando processamento da consulta"
            ))

        try:
            # Flow 2: Clarification response
            if ctx.clarification_id:
                result = self._execute_clarification(ctx, org_ctx, event_callback)
            else:
                # Flow 1 & 3: New question with intent check (with or without history)
                result = self._execute_new_question(ctx, org_ctx, event_callback)

            # Save to conversation if conversation_id provided
            if conversation_id and self.conversation_repo and user_id:
                self._save_to_conversation(
                    conversation_id=conversation_id,
                    ctx=ctx,
                    result=result
                )

            return result

        finally:
            ctx.completed_at = datetime.utcnow()

    def _execute_new_question(
        self,
        ctx: QueryExecutionContext,
        org_ctx: OrgContext,
        event_callback: Optional[Callable[[StreamEvent], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute new question with intent analysis

        Flow:
        1. Select best schema
        2. Analyze intent
        3. If clear → generate SQL → execute
        4. If unclear → save clarification session → return questions
        5. If schema mismatch → return error with suggestions
        """
        # Emit schema selection event
        if event_callback:
            event_callback(StreamEvent(
                stage="selecting_schema",
                progress=10,
                message="Selecionando melhor schema"
            ))

        # Select schema
        schema_order = self._select_schema_order(ctx, org_ctx)

        # Try executing on schemas in order
        last_error: Optional[str] = None

        for schema in schema_order:
            try:
                result = self._execute_on_schema(ctx, org_ctx, schema, event_callback)

                # Success! Log audit and return
                self.audit_repo.log_from_context(org_ctx.org_id, ctx)

                # Emit completion event
                if event_callback:
                    event_callback(StreamEvent(
                        stage="completed",
                        progress=100,
                        message="Consulta executada com sucesso"
                    ))

                return result

            except HTTPException as e:
                last_error = f"[{schema}] {e.detail}"
                logger.warning(f"Failed on schema {schema}: {e.detail}")
                continue
            except Exception as e:
                last_error = f"[{schema}] {str(e)}"
                logger.warning(f"Failed on schema {schema}: {e}")
                continue

        # All schemas failed
        raise HTTPException(
            status_code=400,
            detail=last_error or "Falha ao executar em todos os schemas permitidos."
        )

    def _execute_clarification(
        self,
        ctx: QueryExecutionContext,
        org_ctx: OrgContext,
        event_callback: Optional[Callable[[StreamEvent], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute clarification response

        Flow:
        1. Load clarification session
        2. Build clarified question
        3. Generate SQL (skip intent analysis)
        4. Execute SQL
        5. Enrich if requested
        6. Delete clarification session
        """
        # Load session
        session = self.clarification_repo.get_session(ctx.clarification_id)

        # Emit clarification processing event
        if event_callback:
            event_callback(StreamEvent(
                stage="processing_clarification",
                progress=20,
                message="Processando respostas de clarificação"
            ))

        # Build clarified question
        clarified_question = build_clarified_question(
            session.original_question,
            ctx.clarifications or {}
        )

        # Use schema from session
        schema = session.schema_name
        ctx.schema_used = schema

        # Connect and execute
        db_url = org_ctx.build_sqlalchemy_url(schema)
        eng = create_engine(db_url, pool_pre_ping=True, future=True)

        with eng.connect() as conn:
            # Get schema
            catalog = catalog_for_current_db(conn, db_name=schema)
            esquema_txt = esquema_resumido(catalog)

            # Emit SQL generation event
            if event_callback:
                event_callback(StreamEvent(
                    stage="generating_sql",
                    progress=40,
                    message="Gerando consulta SQL"
                ))

            # Generate SQL (skip intent analysis)
            ctx.pergunta = clarified_question
            sql = generate_sql(clarified_question, esquema_txt, ctx.max_linhas)
            ctx.sql_generated = sql

            # Emit execution event
            if event_callback:
                event_callback(StreamEvent(
                    stage="executing_sql",
                    progress=60,
                    message="Executando consulta no banco de dados",
                    data={"sql": sql}
                ))

            # Execute with retry
            self._execute_sql_with_retry(conn, sql, esquema_txt, catalog, schema, ctx)

        # Enrich if requested
        if ctx.enrich:
            # Emit enrichment event
            if event_callback:
                event_callback(StreamEvent(
                    stage="enriching",
                    progress=80,
                    message="Gerando insights e gráficos"
                ))

            self.enrichment_service.enrich_results(ctx, org_ctx)

        # Clean up session
        self.clarification_repo.delete_session(ctx.clarification_id)

        # Log audit
        self.audit_repo.log_from_context(org_ctx.org_id, ctx)

        # Emit completion event
        if event_callback:
            event_callback(StreamEvent(
                stage="completed",
                progress=100,
                message="Consulta executada com sucesso"
            ))

        # Build response
        return self._build_response(org_ctx.org_id, ctx)

    def _execute_on_schema(
        self,
        ctx: QueryExecutionContext,
        org_ctx: OrgContext,
        schema: str,
        event_callback: Optional[Callable[[StreamEvent], None]] = None
    ) -> Dict[str, Any]:
        """
        Try executing query on a specific schema

        Returns:
            Response dict if successful
        Raises:
            HTTPException if fails (to try next schema)
        """
        ctx.schema_used = schema

        # Connect
        db_url = org_ctx.build_sqlalchemy_url(schema)
        eng = create_engine(db_url, pool_pre_ping=True, future=True)

        with eng.connect() as conn:
            # Get schema
            catalog = catalog_for_current_db(conn, db_name=schema)
            esquema_txt = esquema_resumido(catalog)

            # Emit intent analysis event
            if event_callback:
                event_callback(StreamEvent(
                    stage="analyzing_intent",
                    progress=20,
                    message="Analisando intenção da pergunta"
                ))

            # Analyze intent
            intent = analyze_intent(
                pergunta=ctx.pergunta,
                esquema=esquema_txt,
                confidence_threshold=0.5
            )

            # Check schema mismatch
            if intent.schema_mismatch:
                logger.warning(f"Schema mismatch: {intent.missing_data}")
                return {
                    "status": "schema_error",
                    "message": "Desculpe, esses dados não estão disponíveis no sistema.",
                    "missing_data": intent.missing_data,
                    "suggestions": intent.questions[0]["options"] if intent.questions else [],
                    "confidence": intent.confidence
                }

            # Check if clarification needed
            if not intent.is_clear:
                logger.warning(f"Low confidence ({intent.confidence:.2f}), requesting clarification")
                return self._request_clarification(intent, schema, ctx, org_ctx)

            # Emit SQL generation event
            if event_callback:
                event_callback(StreamEvent(
                    stage="generating_sql",
                    progress=40,
                    message="Gerando consulta SQL"
                ))

            # Intent is clear, generate SQL
            sql = generate_sql(ctx.pergunta, esquema_txt, ctx.max_linhas)
            ctx.sql_generated = sql

            # Emit execution event
            if event_callback:
                event_callback(StreamEvent(
                    stage="executing_sql",
                    progress=60,
                    message="Executando consulta no banco de dados",
                    data={"sql": sql}
                ))

            # Execute with retry
            self._execute_sql_with_retry(conn, sql, esquema_txt, catalog, schema, ctx)

        # Enrich if requested
        if ctx.enrich:
            # Emit enrichment event
            if event_callback:
                event_callback(StreamEvent(
                    stage="enriching",
                    progress=80,
                    message="Gerando insights e gráficos"
                ))

            self.enrichment_service.enrich_results(ctx, org_ctx)

        # Build response
        return self._build_response(org_ctx.org_id, ctx)

    def _execute_sql_with_retry(
        self,
        conn: Connection,
        sql: str,
        esquema_txt: str,
        catalog: Dict,
        schema: str,
        ctx: QueryExecutionContext
    ) -> None:
        """
        Execute SQL with retry on error

        Modifies ctx in place with results
        """
        # Protect SQL
        try:
            sql_seguro = proteger_sql_singledb(sql, catalog, db_name=schema, max_linhas=ctx.max_linhas)
        except HTTPException as e:
            msg = str(e.detail)
            if "Tabela(s) não encontrada(s)" in msg or "multi-DB" in msg:
                raise  # Let caller try next schema
            raise

        # Execute
        t0 = time.time()

        try:
            resultado = executar_sql_readonly_on_conn(conn, sql_seguro)
        except Exception as err:
            # Retry with correction
            logger.warning(f"SQL error, attempting correction: {err}")
            sql2 = correct_sql(
                sql_original=sql_seguro,
                erro=str(err),
                esquema=esquema_txt,
                limit=ctx.max_linhas
            )
            sql_seguro = proteger_sql_singledb(sql2, catalog, db_name=schema, max_linhas=ctx.max_linhas)
            resultado = executar_sql_readonly_on_conn(conn, sql_seguro)

        ctx.duration_ms = int((time.time() - t0) * 1000)
        ctx.sql_executed = sql_seguro

        # Parse results
        ctx.colunas = resultado.get("colunas", [])
        dados_dict = resultado.get("dados", [])
        ctx.dados = [[row.get(col) for col in ctx.colunas] for row in dados_dict]
        ctx.row_count = len(ctx.dados)

        logger.info(f"SQL executed: {sql_seguro}")
        logger.info(f"SQL executed successfully: {ctx.row_count} rows in {ctx.duration_ms}ms")

    def _request_clarification(
        self,
        intent: Any,
        schema: str,
        ctx: QueryExecutionContext,
        org_ctx: OrgContext
    ) -> Dict[str, Any]:
        """
        Save clarification session and return questions to user
        """
        intent_result = IntentAnalysisResult(
            confidence=intent.confidence,
            is_clear=intent.is_clear,
            schema_mismatch=intent.schema_mismatch,
            ambiguities=intent.ambiguities,
            questions=intent.questions,
            missing_data=intent.missing_data,
            analyzed_at=datetime.utcnow(),
            schema_used=schema
        )

        session = self.clarification_repo.create_session(
            org_id=org_ctx.org_id,
            user_id="",  # TODO: get from ctx
            original_question=ctx.pergunta,
            schema_name=schema,
            intent_analysis=intent_result
        )

        return {
            "status": "needs_clarification",
            "clarification_id": session.id,
            "message": "Preciso de mais detalhes para gerar uma consulta precisa:",
            "questions": intent.questions,
            "ambiguities": intent.ambiguities,
            "confidence": intent.confidence
        }

    def _select_schema_order(
        self,
        ctx: QueryExecutionContext,
        org_ctx: OrgContext
    ) -> list[str]:
        """
        Select order to try schemas

        Uses overlap ranking + LLM tie-breaking
        """
        # Build schema index
        base_url = org_ctx.build_sqlalchemy_url(org_ctx.database_name)
        schema_index = get_schema_index_for_org(
            org_ctx.org_id,
            base_url,
            org_ctx.allowed_schemas
        )

        # Rank by overlap
        ranked = rank_schemas_by_overlap(schema_index, ctx.pergunta)
        best_by_overlap, top_score = ranked[0]
        top_ties = [s for s, sc in ranked if sc == top_score]

        # Use LLM to pick if ambiguous
        if top_score == 0 or len(top_ties) > 1:
            picked = pick_schema(org_ctx.allowed_schemas, ctx.pergunta)
            preferred = picked or best_by_overlap
        else:
            preferred = best_by_overlap

        # Return order: preferred first, then others
        return [preferred] + [s for s in org_ctx.allowed_schemas if s != preferred]

    def _build_response(self, org_id: str, ctx: QueryExecutionContext) -> Dict[str, Any]:
        """
        Build final response dict

        Standardized format:
        {
            "status": "success",
            "sql": "SELECT ...",
            "columns": ["col1", "col2"],
            "rows": [[val1, val2], ...],
            "insights": "text summary" or {"summary": "...", "chart": {...}},
            "metadata": {
                "org_id": "uuid",
                "row_count": 10,
                "duration_ms": 45,
                "schema_used": "sakila"
            }
        }
        """
        response = {
            "status": "success",
            "sql": ctx.sql_executed,
            "columns": ctx.colunas or [],
            "rows": ctx.dados or [],
            "metadata": {
                "org_id": org_id,
                "row_count": ctx.row_count or (len(ctx.dados) if ctx.dados else 0),
                "duration_ms": ctx.duration_ms,
                "schema_used": ctx.schema_used
            }
        }

        # Add insights if available
        if ctx.insights_text or ctx.chart_base64:
            response["insights"] = {
                "summary": ctx.insights_text,
                "chart": {
                    "mime": "image/png",
                    "base64": ctx.chart_base64
                } if ctx.chart_base64 else None
            }
        else:
            response["insights"] = None

        return response

    def _save_to_conversation(
        self,
        conversation_id: str,
        ctx: QueryExecutionContext,
        result: Dict[str, Any]
    ) -> None:
        """
        Save user question and assistant response to conversation

        Args:
            conversation_id: Conversation ID
            ctx: Query execution context
            result: Query result dict
        """
        try:
            # Save user message
            self.conversation_repo.add_message(
                conversation_id=conversation_id,
                role="user",
                content=ctx.pergunta
            )

            # Format assistant response
            if result.get("status") == "success" and result.get("resultado"):
                assistant_content = f"Executei a consulta: {ctx.sql_executed or ctx.sql_generated}\n\n"
                assistant_content += f"Resultado: {ctx.row_count or len(ctx.dados or [])} linhas retornadas"

                if ctx.insights_text:
                    assistant_content += f"\n\n{ctx.insights_text}"

                # Save assistant message
                self.conversation_repo.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assistant_content,
                    sql_executed=ctx.sql_executed or ctx.sql_generated,
                    schema_used=ctx.schema_used,
                    row_count=ctx.row_count or (len(ctx.dados) if ctx.dados else None),
                    duration_ms=ctx.duration_ms
                )

                logger.info(f"Saved messages to conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Failed to save to conversation: {e}", exc_info=True)
