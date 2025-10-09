# app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import make_url, Connection
from typing import Dict, Any, List, Optional, Tuple
import re
import os
import httpx
from dotenv import load_dotenv

# ---------- .env ----------
load_dotenv()
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
DISABLE_AZURE_LLM = os.getenv("DISABLE_AZURE_LLM", "0") == "1"  # para debug local

app = FastAPI(title="NL→SQL (MySQL) - Multi-DB")

# ---------- Modelos ----------
class Pergunta(BaseModel):
    database_url: str   # pode vir COM ou SEM schema (ex.: mysql+pymysql://user:pass@host:3306?charset=utf8mb4)
    pergunta: str
    max_linhas: int = 100

# ---------- Utils ----------
_SYSTEM_SCHEMAS = {"information_schema", "mysql", "performance_schema", "sys"}
_TEMP_DB_ORDER = ["information_schema", "mysql"]  # quando URL vem sem DB

def _use_schema(conn: Connection, schema: str) -> None:
    schema_quoted = f"`{schema.replace('`','')}`"
    conn.execute(text(f"USE {schema_quoted}"))

def _tokens(texto: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+", (texto or "").lower())

def _parse_schema_override(pergunta: str) -> Optional[str]:
    padroes = [
        r"(?i)\bno\s+schema\s+([a-zA-Z0-9_]+)\s*:?",
        r"(?i)\bschema\s+([a-zA-Z0-9_]+)\s*:?",
        r"(?i)\buse\s+([a-zA-Z0-9_]+)\b",
        r"(?i)\busar\s+([a-zA-Z0-9_]+)\b",
        r"(?i)\bno\s+banco\s+([a-zA-Z0-9_]+)\b",
    ]
    for rx in padroes:
        m = re.search(rx, pergunta or "")
        if m:
            return m.group(1)
    return None

def _schema_exists_on_conn(conn: Connection, schema: str) -> bool:
    rows = conn.execute(text("SHOW DATABASES")).fetchall()
    dbs = {r[0].lower() for r in rows}
    return schema and schema.lower() in dbs and schema.lower() not in _SYSTEM_SCHEMAS

# ---------- Catálogo multi-DB (tolerante a erros) ----------
def _list_user_databases(conn: Connection) -> List[str]:
    rows = conn.execute(text("SHOW DATABASES")).fetchall()
    return sorted([r[0] for r in rows if r[0] not in _SYSTEM_SCHEMAS])

def _reflect_schema_on_current_conn(conn: Connection) -> Dict[str, Any]:
    """
    Reflexão tolerante a erros por tabela.
    Se uma tabela falhar, ela é registrada em 'errors' e ignorada no resumo.
    """
    insp = inspect(conn)
    tabelas: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    try:
        table_names = insp.get_table_names()
    except Exception as te:
        raise HTTPException(status_code=400, detail=f"Falha ao listar tabelas: {te}")

    for t in table_names:
        try:
            cols = insp.get_columns(t)
            fks = []
            try:
                fks = insp.get_foreign_keys(t) or []
            except Exception as fe:
                errors.append({"table": t, "where": "get_foreign_keys", "error": str(fe)})

            tabelas.append({
                "tabela": t,
                "colunas": [
                    {"nome": c["name"], "tipo": str(c.get("type", "")), "pk": bool(c.get("primary_key", False))}
                    for c in cols
                ],
                "fks": [
                    {"coluna": ", ".join(fk.get("constrained_columns", [])), "ref": fk.get("referred_table")}
                    for fk in fks
                ]
            })
        except Exception as ce:
            errors.append({"table": t, "where": "table_reflection", "error": str(ce)})

    return {"tabelas": tabelas, "errors": errors}

def _catalog_all(conn: Connection, only_db: Optional[str] = None) -> Dict[str, Any]:
    """
    Catálogo multi-DB tolerante a erros e NÃO intrusivo:
    - Varre DBs de usuário; se algo falhar, registra e segue.
    - Restaura o schema original ao final.
    Estrutura:
      {"databases": {db: {"tables": {tabela: {...| "error": msg}}, "error"?: msg}},
       "errors": [...]}
    """
    catalog: Dict[str, Any] = {"databases": {}, "errors": []}
    try:
        current_db = conn.execute(text("SELECT DATABASE()")).scalar()
    except Exception:
        current_db = None

    try:
        dbs = _list_user_databases(conn)
        if only_db:
            dbs = [d for d in dbs if d.lower() == only_db.lower()]

        for db in dbs:
            db_entry: Dict[str, Any] = {"tables": {}}
            catalog["databases"][db] = db_entry
            try:
                _use_schema(conn, db)
                insp = inspect(conn)
                try:
                    table_names = insp.get_table_names()
                except Exception as te:
                    db_entry["error"] = f"Falha ao listar tabelas: {te}"
                    catalog["errors"].append({"db": db, "where": "get_table_names", "error": str(te)})
                    continue

                for t in table_names:
                    try:
                        cols = insp.get_columns(t)
                        pks = {c["name"] for c in cols if c.get("primary_key", False)}
                        try:
                            fks = insp.get_foreign_keys(t) or []
                        except Exception as fe:
                            fks = []
                            catalog["errors"].append({"db": db, "table": t, "where": "get_foreign_keys", "error": str(fe)})

                        db_entry["tables"][t] = {
                            "columns": [
                                {"name": c.get("name"), "type": str(c.get("type", "")), "is_pk": c.get("name") in pks}
                                for c in cols
                            ],
                            "fks": [
                                {
                                    "columns": fk.get("constrained_columns", []),
                                    "referred_table": fk.get("referred_table"),
                                    "referred_schema": db,
                                } for fk in fks
                            ],
                        }
                    except Exception as ce:
                        db_entry["tables"][t] = {"error": str(ce)}
                        catalog["errors"].append({"db": db, "table": t, "where": "table_reflection", "error": str(ce)})
            except Exception as de:
                db_entry["error"] = str(de)
                catalog["errors"].append({"db": db, "where": "db_reflection", "error": str(de)})
                continue
    finally:
        # restaura o schema original (se havia)
        if current_db:
            try:
                _use_schema(conn, current_db)
            except Exception:
                pass

    return catalog

# ---------- Extração de esquema (URL com/sem DB) ----------
def extrair_esquema_direct(database_url_com_db: str) -> Dict[str, Any]:
    engine = create_engine(database_url_com_db, pool_pre_ping=True)
    with engine.connect() as conn:
        return _reflect_schema_on_current_conn(conn)

def extrair_esquema_via_use(database_url_base: str, schema: str) -> Dict[str, Any]:
    base = make_url(database_url_base)
    last_err = None
    for temp_db in _TEMP_DB_ORDER:
        try:
            url_temp = str(base.set(database=temp_db))
            engine = create_engine(url_temp, pool_pre_ping=True)
            with engine.connect() as conn:
                _use_schema(conn, schema)
                return _reflect_schema_on_current_conn(conn)
        except Exception as e:
            last_err = e
            continue
    raise HTTPException(status_code=400, detail=str(last_err))

def listar_schemas_usuario(database_url_base: str) -> List[str]:
    base = make_url(database_url_base)
    last_err = None
    for temp_db in _TEMP_DB_ORDER:
        try:
            url_temp = str(base.set(database=temp_db))
            engine = create_engine(url_temp, pool_pre_ping=True)
            with engine.connect() as conn:
                return _list_user_databases(conn)
        except Exception as e:
            last_err = e
            continue
    raise HTTPException(status_code=400, detail=str(last_err))

def escolher_schema_por_prompt(database_url: str, pergunta: str) -> str:
    override = _parse_schema_override(pergunta)
    schemas = listar_schemas_usuario(database_url)
    if override and any(s.lower() == override.lower() for s in schemas):
        return next(s for s in schemas if s.lower() == override.lower())

    toks = set(_tokens(pergunta))
    matches = [s for s in schemas if s.lower() in toks]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return sorted(matches)[0]
    if any(s.lower() == "sakila" for s in schemas):
        return next(s for s in schemas if s.lower() == "sakila")
    return schemas[0]

def resumir_esquema(esquema: Dict[str, Any], max_chars: int = 4000) -> str:
    linhas: List[str] = []
    for t in esquema["tabelas"]:
        cols = ", ".join([f'{c["nome"]}:{c["tipo"]}' for c in t["colunas"]][:24])
        linhas.append(f'- {t["tabela"]}({cols})')
    texto = "Esquema disponível:\n" + "\n".join(linhas)
    return texto[:max_chars]

# ---------- Prompt / NL→SQL ----------
PROMPT_BASE = """Você é um tradutor NL→SQL. Regras:
- Use apenas tabelas e colunas do esquema.
- Prefira JOINs explícitos por chaves declaradas.
- NUNCA modifique dados (somente SELECT).
- Sempre inclua LIMIT {limit} se não houver.
- Use nomes qualificados quando necessário.
- Dialeto alvo: MySQL.
{esquema}

Pergunta do usuário:
{pergunta}

Responda SOMENTE com o SQL válido (sem explicações)."""

SYSTEM_PROMPT_TEMPLATE = """Você é um tradutor NL→SQL no dialeto {dialeto}. Regras obrigatórias:
- Gere SOMENTE um SELECT SQL válido (sem comentários, sem ```).
- Use apenas tabelas/colunas do esquema fornecido.
- Prefira JOINs com PK/FK explícitas.
- NUNCA modifique dados (sem INSERT/UPDATE/DELETE/DDL).
- Se o usuário não pedir limite explícito, inclua LIMIT {limit}.
- Formate datas e funções para {dialeto} (MySQL).
- Evite CTEs desnecessárias.
"""

def _azure_chat_url() -> str:
    if not (AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT and AZURE_OPENAI_API_KEY):
        raise RuntimeError("Faltam variáveis AZURE_OPENAI_* no .env")
    return f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"

def chamar_llm_azure(prompt_usuario: str, limit: int = 100, dialeto: str = "MySQL") -> str:
    if DISABLE_AZURE_LLM:
        return f"SELECT 1 AS ok LIMIT {limit}"
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(dialeto=dialeto, limit=limit)
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_usuario}
        ],
        "temperature": 0.1,
        "max_tokens": 800,
        "top_p": 0.95
    }
    headers = {"Content-Type": "application/json", "api-key": AZURE_OPENAI_API_KEY}
    url = _azure_chat_url()
    with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Resposta inesperada do Azure OpenAI: {data}") from e
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("sql"):
            content = content[3:].lstrip()
    return content.strip()

def gerar_sql(pergunta: str, esquema_texto: str, limit: int) -> str:
    prompt = PROMPT_BASE.format(esquema=esquema_texto, pergunta=pergunta, limit=limit)
    sql_sugerido = chamar_llm_azure(prompt, limit=limit, dialeto="MySQL")
    return sql_sugerido.strip()

# ---------- Segurança / Validação ----------
SQL_PERIGOSO = re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE|ALTER|DROP|CREATE|TRUNCATE|GRANT|REVOKE)\b", re.IGNORECASE)

def proteger_sql_multidb(sql: str, catalog: Dict[str, Any], default_db: str, max_linhas: int, conn: Connection) -> str:
    """
    - Bloqueia DDL/DML.
    - Valida referências FROM/JOIN no modo multi-DB.
    - Se a tabela não estiver no catálogo, confirma no information_schema.
    """
    if SQL_PERIGOSO.search(sql):
        raise ValueError("SQL com comandos de escrita/DDL não é permitido.")

    # after FROM/JOIN: (db?.table)
    refs = re.findall(
        r'(?:from|join)\s+((?:[`"]?[a-zA-Z0-9_]+[`"]?\.)?[`"]?[a-zA-Z0-9_]+[`"]?)',
        sql, flags=re.IGNORECASE
    )

    def split_ref(r: str) -> Tuple[str, str]:
        r = r.strip('`"')
        parts = r.split(".")
        if len(parts) == 2:
            return parts[0], parts[1]
        return default_db, parts[0]

    # 1) checa no catálogo
    unknown: List[Tuple[str, str]] = []
    dbs = catalog.get("databases", {})
    for r in refs:
        db, tbl = split_ref(r)
        if db not in dbs or tbl not in dbs.get(db, {}).get("tables", {}):
            unknown.append((db, tbl))

    # 2) fallback: confirma no information_schema
    if unknown:
        clauses = []
        params = {}
        for i, (db, tbl) in enumerate(unknown):
            clauses.append(f"(table_schema = :db{i} AND table_name = :tb{i})")
            params[f"db{i}"] = db
            params[f"tb{i}"] = tbl

        q = text(f"""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE {" OR ".join(clauses)}
        """)
        found = {(row[0], row[1]) for row in conn.execute(q, params).fetchall()}

        still_unknown = {(db, tbl) for (db, tbl) in unknown if (db, tbl) not in found}
        if still_unknown:
            raise ValueError(f"Tabelas desconhecidas (multi-DB): { {f'{db}.{tbl}' for db, tbl in still_unknown} }")

    # 3) garante LIMIT
    if re.search(r"\blimit\b", sql, flags=re.IGNORECASE) is None:
        sql += f"\nLIMIT {max_linhas}"
    return sql

# ---------- Execução ----------
def executar_sql_readonly_on_conn(conn: Connection, sql: str) -> Dict[str, Any]:
    rs = conn.execute(text(sql))
    cols = list(rs.keys())
    dados = [dict(zip(cols, row)) for row in rs]
    return {"colunas": cols, "dados": dados}

def executar_sql_readonly_direct(database_url_com_db: str, sql: str) -> Dict[str, Any]:
    engine = create_engine(database_url_com_db, pool_pre_ping=True)
    with engine.connect() as conn:
        return executar_sql_readonly_on_conn(conn, sql)

# ---------- Endpoints ----------
@app.post("/perguntar")
def perguntar(p: Pergunta):
    try:
        url = make_url(p.database_url)

        # ===== Caminho 1: URL já vem com DB (p.ex. /xtremo) — com override via prompt =====
        if url.database:
            engine = create_engine(p.database_url, pool_pre_ping=True)
            with engine.connect() as conn:
                override = _parse_schema_override(p.pergunta)
                if override and override.lower() != url.database.lower():
                    if not _schema_exists_on_conn(conn, override):
                        raise HTTPException(status_code=400, detail=f"Schema '{override}' não existe neste servidor MySQL.")
                    _use_schema(conn, override)
                    schema_final = override
                    modo = "direto_com_db_override_use"
                else:
                    schema_final = url.database
                    _use_schema(conn, schema_final)  # garante
                    modo = "direto_com_db"

                # catálogo de TODOS os DBs (permite referencias db.tabela)
                catalog = _catalog_all(conn)

                # 🔒 garante schema correto após catalogar
                _use_schema(conn, schema_final)

                # reflection/resumo no schema em uso (tolerante)
                esquema = _reflect_schema_on_current_conn(conn)
                esquema_txt = resumir_esquema(esquema)

                # LLM → SQL
                sql = gerar_sql(p.pergunta, esquema_txt, p.max_linhas)

                # guard-rails multi-DB (com fallback no information_schema)
                sql_seguro = proteger_sql_multidb(sql, catalog, default_db=schema_final, max_linhas=p.max_linhas, conn=conn)

                # execução (com 1 correção automática)
                try:
                    resultado = executar_sql_readonly_on_conn(conn, sql_seguro)
                except Exception as err:
                    corre_prompt = f"Esquema:\n{esquema_txt}\n\nErro:\n{err}\n\nCorrija o SQL (somente SELECT, LIMIT {p.max_linhas} se faltar):\n{sql_seguro}"
                    sql_corrigido = chamar_llm_azure(corre_prompt, limit=p.max_linhas, dialeto="MySQL").strip()
                    sql_seguro = proteger_sql_multidb(sql_corrigido, catalog, default_db=schema_final, max_linhas=p.max_linhas, conn=conn)
                    _use_schema(conn, schema_final)
                    resultado = executar_sql_readonly_on_conn(conn, sql_seguro)

                return {"schema_usado": schema_final, "modo_conexao": modo, "sql": sql_seguro, "resultado": resultado}

        # ===== Caminho 2: URL sem DB — conecta em neutro, dá USE <schema> =====
        else:
            base = make_url(p.database_url)
            last_err = None
            for temp_db in _TEMP_DB_ORDER:
                try:
                    url_temp = str(base.set(database=temp_db))
                    engine = create_engine(url_temp, pool_pre_ping=True)
                    with engine.connect() as conn:
                        schema_escolhido = escolher_schema_por_prompt(p.database_url, p.pergunta)
                        _use_schema(conn, schema_escolhido)

                        # catálogo multi-DB
                        catalog = _catalog_all(conn)

                        # 🔒 garante schema correto após catalogar
                        _use_schema(conn, schema_escolhido)

                        # reflection/resumo no schema escolhido (tolerante)
                        esquema = _reflect_schema_on_current_conn(conn)
                        esquema_txt = resumir_esquema(esquema)

                        # LLM → SQL
                        sql = gerar_sql(p.pergunta, esquema_txt, p.max_linhas)

                        # guard-rails multi-DB (com fallback no information_schema)
                        sql_seguro = proteger_sql_multidb(sql, catalog, default_db=schema_escolhido, max_linhas=p.max_linhas, conn=conn)

                        # execução (com 1 correção automática)
                        try:
                            resultado = executar_sql_readonly_on_conn(conn, sql_seguro)
                        except Exception as err:
                            corre_prompt = f"Esquema:\n{esquema_txt}\n\nErro:\n{err}\n\nCorrija o SQL (somente SELECT, LIMIT {p.max_linhas} se faltar):\n{sql_seguro}"
                            sql_corrigido = chamar_llm_azure(corre_prompt, limit=p.max_linhas, dialeto="MySQL").strip()
                            sql_seguro = proteger_sql_multidb(sql_corrigido, catalog, default_db=schema_escolhido, max_linhas=p.max_linhas, conn=conn)
                            _use_schema(conn, schema_escolhido)
                            resultado = executar_sql_readonly_on_conn(conn, sql_seguro)

                        return {"schema_usado": schema_escolhido, "modo_conexao": f"sem_db_com_use({temp_db})", "sql": sql_seguro, "resultado": resultado}
                except Exception as e:
                    last_err = e
                    continue
            raise HTTPException(status_code=400, detail=str(last_err))

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------- Diagnóstico ----------
@app.post("/_debug_connect")
def _debug_connect(p: Pergunta):
    try:
        engine = create_engine(p.database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            current = conn.execute(text("SELECT DATABASE()")).scalar()
            dbs = [r[0] for r in conn.execute(text("SHOW DATABASES"))]
            one = conn.execute(text("SELECT 1")).scalar()
        return {"ok": True, "database_corrente": current, "databases": dbs, "select_1": one}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/_catalog")
def post_catalog(p: Pergunta):
    """
    Gera catálogo multi-DB tolerante a erros.
    Body JSON:
      { "database_url": "...", "pergunta": "ping" }
    Opcional: limitar a um DB citando no prompt: "schema X:" (apenas filtro do catálogo).
    """
    try:
        # 1) tenta usar a URL como está
        try:
            engine = create_engine(p.database_url, pool_pre_ping=True)
            with engine.connect() as conn:
                only_db = _parse_schema_override(p.pergunta)
                return _catalog_all(conn, only_db=only_db)
        except Exception as first_err:
            # 2) se falhou (ex.: URL sem DB), tenta via DBs neutros
            try:
                url = make_url(p.database_url)
            except Exception:
                raise HTTPException(status_code=400, detail=f"URL inválida: {first_err}")

            last_err = first_err
            for temp_db in _TEMP_DB_ORDER:
                try:
                    url_temp = str(url.set(database=temp_db))
                    engine = create_engine(url_temp, pool_pre_ping=True)
                    with engine.connect() as conn:
                        only_db = _parse_schema_override(p.pergunta)
                        return _catalog_all(conn, only_db=only_db)
                except Exception as e:
                    last_err = e
                    continue
            raise HTTPException(status_code=400, detail=str(last_err))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
