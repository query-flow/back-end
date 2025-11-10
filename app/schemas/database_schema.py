"""
Schemas (DTOs) para operações de descoberta de banco de dados.
"""

from sqlmodel import SQLModel
from typing import List, Optional


class TestConnectionRequest(SQLModel):
    """Request para testar conexão com banco de dados"""
    host: str
    port: int = 3306
    username: str
    password: str
    database_name: str = "mysql"
    driver: str = "mysql+pymysql"


class TestConnectionResponse(SQLModel):
    """Response do teste de conexão"""
    status: str  # "connected" | "failed"
    message: str
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None


class ListDatabasesRequest(SQLModel):
    """Request para listar databases disponíveis"""
    host: str
    port: int = 3306
    username: str
    password: str
    driver: str = "mysql+pymysql"


class ListDatabasesResponse(SQLModel):
    """Response com lista de databases"""
    databases: List[str]
    total: int
    message: str = "Databases listados com sucesso"


class ListSchemasRequest(SQLModel):
    """Request para listar schemas/tabelas de um database"""
    host: str
    port: int = 3306
    username: str
    password: str
    database_name: str
    driver: str = "mysql+pymysql"


class ListSchemasResponse(SQLModel):
    """Response com lista de schemas/tabelas"""
    database: str
    schemas: List[str]
    total: int
    message: str = "Schemas listados com sucesso"


class TableInfoRequest(SQLModel):
    """Request para obter informações de uma tabela específica"""
    host: str
    port: int = 3306
    username: str
    password: str
    database_name: str
    table_name: str
    driver: str = "mysql+pymysql"


class ColumnInfo(SQLModel):
    """Informações de uma coluna"""
    name: str
    type: str
    nullable: bool
    default: Optional[str] = None


class TableInfoResponse(SQLModel):
    """Response com informações detalhadas de uma tabela"""
    table_name: str
    database: str
    columns: List[ColumnInfo]
    column_count: int
