"""
SQL Executor
Executes read-only SQL queries
"""
from typing import Dict, Any
from sqlalchemy import text as sqltext
from sqlalchemy.engine import Connection


def executar_sql_readonly_on_conn(conn: Connection, sql: str) -> Dict[str, Any]:
    """
    Execute a read-only SQL query and return results as JSON-serializable dict
    """
    rs = conn.execute(sqltext(sql))
    cols = list(rs.keys())
    dados = [dict(zip(cols, row)) for row in rs]
    return {"colunas": cols, "dados": dados}
