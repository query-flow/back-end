import re
from typing import Dict, Any, Set, Tuple, Optional
from sqlalchemy import text as sqltext
from sqlalchemy.engine import Connection
from fastapi import HTTPException

# Dangerous SQL patterns
SQL_PERIGOSO = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|ALTER|DROP|CREATE|TRUNCATE|GRANT|REVOKE)\b",
    re.I
)


def proteger_sql_singledb(
    sql: str,
    catalog: Dict[str, Any],
    db_name: str,
    max_linhas: int
) -> str:
    """
    Validate and secure SQL query:
    - Block dangerous operations
    - Ensure tables exist in catalog
    - Add LIMIT if missing
    """
    if SQL_PERIGOSO.search(sql):
        raise HTTPException(
            status_code=400,
            detail="SQL com comandos de escrita/DDL não é permitido."
        )

    # Extract table references from FROM and JOIN clauses
    refs = re.findall(
        r'(?:from|join)\s+((?:[`"]?[a-zA-Z0-9_]+[`"]?\.)?[`"]?[a-zA-Z0-9_]+[`"]?)',
        sql,
        flags=re.I
    )

    def split_ref(r: str) -> Tuple[Optional[str], str]:
        r = r.strip('`"')
        parts = r.split(".")
        if len(parts) == 2:
            return parts[0].lower(), parts[1].lower()
        return None, parts[0].lower()

    other_dbs: Set[str] = set()
    tables_used: Set[str] = set()

    for ref in refs:
        db, tb = split_ref(ref)
        if db and db != db_name.lower():
            other_dbs.add(db)
        tables_used.add(tb)

    if other_dbs:
        raise HTTPException(
            status_code=400,
            detail=f"Tabelas desconhecidas (multi-DB não permitido): {other_dbs}"
        )

    known = {k.lower() for k in catalog["tables"].keys()}
    unknown = {t for t in tables_used if t not in known}

    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Tabela(s) não encontrada(s) em {db_name}: {unknown}"
        )

    # Add LIMIT if missing
    if re.search(r"\blimit\b", sql, flags=re.I) is None:
        sql += f"\nLIMIT {max_linhas}"

    # Add semicolon if missing
    if not sql.strip().endswith(";"):
        sql += ";"

    return sql


def executar_sql_readonly_on_conn(conn: Connection, sql: str) -> Dict[str, Any]:
    """
    Execute a read-only SQL query and return results as JSON-serializable dict
    """
    rs = conn.execute(sqltext(sql))
    cols = list(rs.keys())
    dados = [dict(zip(cols, row)) for row in rs]
    return {"colunas": cols, "dados": dados}
