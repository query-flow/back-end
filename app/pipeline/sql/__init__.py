"""
SQL utilities (catalog, protection, execution)
"""
from app.pipeline.sql.catalog import (
    catalog_for_current_db,
    esquema_resumido,
    get_schema_index_for_org,
    rank_schemas_by_overlap
)
from app.pipeline.sql.protector import proteger_sql_singledb
from app.pipeline.sql.executor import executar_sql_readonly_on_conn

__all__ = [
    "catalog_for_current_db",
    "esquema_resumido",
    "get_schema_index_for_org",
    "rank_schemas_by_overlap",
    "proteger_sql_singledb",
    "executar_sql_readonly_on_conn",
]
