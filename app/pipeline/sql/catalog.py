import re
import time
from typing import Dict, Any, List, Set
from sqlalchemy import text as sqltext, bindparam
from sqlalchemy.engine import Connection


# Schema index cache
_SCHEMA_INDEX_CACHE: Dict[str, Dict[str, Set[str]]] = {}
_SCHEMA_INDEX_TTL: Dict[str, float] = {}


def catalog_for_current_db(conn: Connection, db_name: str) -> Dict[str, Any]:
    """
    Reflect database catalog (tables, columns, PKs, FKs) for a given database
    """
    tables: Dict[str, Any] = {}

    # Get columns
    cols = conn.execute(
        sqltext("""
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_KEY
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :db
            ORDER BY TABLE_NAME, ORDINAL_POSITION
        """),
        {"db": db_name}
    ).mappings()

    for row in cols:
        t = row["TABLE_NAME"]
        tables.setdefault(t, {"columns": [], "pks": set(), "fks": []})
        tables[t]["columns"].append({
            "name": row["COLUMN_NAME"],
            "type": row["DATA_TYPE"]
        })
        if row["COLUMN_KEY"] == "PRI":
            tables[t]["pks"].add(row["COLUMN_NAME"])

    # Get foreign keys
    fks = conn.execute(
        sqltext("""
            SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = :db AND REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY TABLE_NAME, COLUMN_NAME
        """),
        {"db": db_name}
    ).mappings()

    for row in fks:
        t = row["TABLE_NAME"]
        tables.setdefault(t, {"columns": [], "pks": set(), "fks": []})
        tables[t]["fks"].append({
            "col": row["COLUMN_NAME"],
            "ref_table": row["REFERENCED_TABLE_NAME"],
            "ref_col": row["REFERENCED_COLUMN_NAME"]
        })

    return {"db": db_name, "tables": tables}


def esquema_resumido(catalog: Dict[str, Any], max_chars: int = 4000) -> str:
    """
    Generate a summarized schema description for LLM context
    Includes columns, types, and foreign key relationships
    """
    linhas: List[str] = []
    for t, meta in catalog["tables"].items():
        # Format columns (limit to 24 to avoid token overflow)
        cols = ", ".join([f'{c["name"]}:{c["type"]}' for c in meta["columns"]][:24])

        # Add foreign keys info if present
        fk_info = ""
        if meta.get("fks"):
            fks = [f'{fk["col"]}→{fk["ref_table"]}.{fk["ref_col"]}' for fk in meta["fks"][:5]]
            fk_info = f' [FK: {", ".join(fks)}]'

        linhas.append(f"- {t}({cols}){fk_info}")

    texto = "Esquema disponível:\n" + "\n".join(linhas)
    return texto[:max_chars]


def normalize_tokens(*parts: str) -> Set[str]:
    """
    Normalize strings into lowercase tokens for schema matching
    """
    toks: Set[str] = set()
    for p in parts:
        for t in re.findall(r"[a-zA-Z0-9_]+", (p or "").lower()):
            toks.add(t)
    return toks


def build_schema_index(conn: Connection, allowed_schemas: List[str]) -> Dict[str, Set[str]]:
    """
    Build an inverted index of tokens (table/column names) per schema
    """
    rows = conn.execute(
        sqltext("""
            SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA IN :schemas
        """).bindparams(bindparam("schemas", expanding=True)),
        {"schemas": allowed_schemas}
    ).fetchall()

    index: Dict[str, Set[str]] = {s: set() for s in allowed_schemas}
    for schema, table, col in rows:
        index[schema].add((table or "").lower())
        index[schema].add((col or "").lower())

    return index


def get_schema_index_for_org(
    org_id: str,
    base_db_url_with_default: str,
    allowed: List[str]
) -> Dict[str, Set[str]]:
    """
    Get or build schema index for an organization with caching
    """
    from sqlalchemy import create_engine
    from app.core.config import settings

    now = time.time()
    if (
        org_id in _SCHEMA_INDEX_CACHE
        and (now - _SCHEMA_INDEX_TTL.get(org_id, 0) < settings.SCHEMA_INDEX_MAX_AGE)
    ):
        return _SCHEMA_INDEX_CACHE[org_id]

    eng = create_engine(base_db_url_with_default, pool_pre_ping=True, future=True)
    with eng.connect() as conn:
        idx = build_schema_index(conn, allowed)

    _SCHEMA_INDEX_CACHE[org_id] = idx
    _SCHEMA_INDEX_TTL[org_id] = now

    return idx


def rank_schemas_by_overlap(
    schema_index: Dict[str, Set[str]],
    pergunta: str
) -> List[tuple[str, int]]:
    """
    Rank schemas by token overlap with the question
    """
    q_toks = normalize_tokens(pergunta)
    scored: List[tuple[str, int]] = []

    for schema, tokens in schema_index.items():
        score = len(q_toks & tokens)
        scored.append((schema, score))

    scored.sort(key=lambda x: (-x[1], x[0].lower()))
    return scored
