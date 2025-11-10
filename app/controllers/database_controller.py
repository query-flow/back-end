"""
Controller para operações de descoberta e teste de conexões com banco de dados.
"""

from fastapi import APIRouter, HTTPException
from app.schemas.database_schema import (
    TestConnectionRequest,
    TestConnectionResponse,
    ListDatabasesRequest,
    ListDatabasesResponse,
    ListSchemasRequest,
    ListSchemasResponse,
    TableInfoRequest,
    TableInfoResponse
)
from app.services.database_service import DatabaseService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/database", tags=["Database Discovery"])


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(req: TestConnectionRequest):
    """
    Testa conexão com banco de dados MySQL.

    Este endpoint NÃO requer autenticação pois é usado durante o fluxo
    de registro de nova organização.

    **Use case**: Validar credenciais antes de criar organização.

    **Request Body**:
    - host: Endereço do servidor MySQL (ex: localhost, 127.0.0.1)
    - port: Porta do servidor (padrão: 3306)
    - username: Usuário do banco de dados
    - password: Senha do usuário
    - database_name: Nome do database para testar (padrão: mysql)
    - driver: Driver SQLAlchemy (padrão: mysql+pymysql)

    **Response**:
    - status: "connected" se sucesso
    - message: Mensagem descritiva
    - host, port, username: Echo dos dados enviados

    **Errors**:
    - 400: Falha na conexão (credenciais inválidas, servidor inacessível, etc)
    """
    logger.info(f"[test-connection] Testando conexão para {req.username}@{req.host}:{req.port}")

    result = DatabaseService.test_connection(
        host=req.host,
        port=req.port,
        username=req.username,
        password=req.password,
        database_name=req.database_name,
        driver=req.driver
    )

    return TestConnectionResponse(**result)


@router.post("/list-databases", response_model=ListDatabasesResponse)
async def list_databases(req: ListDatabasesRequest):
    """
    Lista todos os databases disponíveis na conexão MySQL.

    Este endpoint NÃO requer autenticação pois é usado durante o fluxo
    de registro de nova organização.

    **Use case**: Permitir que usuário escolha qual database usar após
    testar a conexão com sucesso.

    **Request Body**:
    - host: Endereço do servidor MySQL
    - port: Porta do servidor (padrão: 3306)
    - username: Usuário do banco de dados
    - password: Senha do usuário
    - driver: Driver SQLAlchemy (padrão: mysql+pymysql)

    **Response**:
    - databases: Lista de nomes de databases
    - total: Quantidade de databases encontrados
    - message: Mensagem de sucesso

    **Note**: Databases de sistema (information_schema, performance_schema, sys)
    são filtrados automaticamente.

    **Errors**:
    - 400: Falha ao conectar ou listar databases
    """
    logger.info(f"[list-databases] Listando databases para {req.username}@{req.host}:{req.port}")

    databases = DatabaseService.list_databases(
        host=req.host,
        port=req.port,
        username=req.username,
        password=req.password,
        driver=req.driver
    )

    return ListDatabasesResponse(
        databases=databases,
        total=len(databases),
        message=f"{len(databases)} database(s) encontrado(s)"
    )


@router.post("/list-schemas", response_model=ListSchemasResponse)
async def list_schemas(req: ListSchemasRequest):
    """
    Lista todos os schemas (tabelas) de um database específico.

    Este endpoint NÃO requer autenticação pois é usado durante o fluxo
    de registro de nova organização.

    **Use case**: Permitir que usuário escolha quais tabelas/schemas o sistema
    pode acessar após selecionar o database.

    **Request Body**:
    - host: Endereço do servidor MySQL
    - port: Porta do servidor (padrão: 3306)
    - username: Usuário do banco de dados
    - password: Senha do usuário
    - database_name: Nome do database para inspecionar
    - driver: Driver SQLAlchemy (padrão: mysql+pymysql)

    **Response**:
    - database: Nome do database inspecionado
    - schemas: Lista de nomes de tabelas (ordenada alfabeticamente)
    - total: Quantidade de tabelas encontradas
    - message: Mensagem de sucesso

    **Errors**:
    - 400: Falha ao conectar ou listar schemas
    """
    logger.info(f"[list-schemas] Listando schemas do database '{req.database_name}'")

    schemas = DatabaseService.list_schemas(
        host=req.host,
        port=req.port,
        username=req.username,
        password=req.password,
        database_name=req.database_name,
        driver=req.driver
    )

    return ListSchemasResponse(
        database=req.database_name,
        schemas=schemas,
        total=len(schemas),
        message=f"{len(schemas)} tabela(s) encontrada(s) no database '{req.database_name}'"
    )


@router.post("/table-info", response_model=TableInfoResponse)
async def get_table_info(req: TableInfoRequest):
    """
    Retorna informações detalhadas sobre uma tabela específica.

    Este endpoint NÃO requer autenticação pois é usado durante o fluxo
    de configuração.

    **Use case**: Mostrar preview das colunas de uma tabela antes de
    permitir acesso via queries.

    **Request Body**:
    - host: Endereço do servidor MySQL
    - port: Porta do servidor (padrão: 3306)
    - username: Usuário do banco de dados
    - password: Senha do usuário
    - database_name: Nome do database
    - table_name: Nome da tabela
    - driver: Driver SQLAlchemy (padrão: mysql+pymysql)

    **Response**:
    - table_name: Nome da tabela
    - database: Nome do database
    - columns: Lista de colunas com type, nullable, default
    - column_count: Quantidade de colunas

    **Errors**:
    - 400: Falha ao conectar ou obter informações da tabela
    """
    logger.info(f"[table-info] Obtendo info da tabela '{req.table_name}' no database '{req.database_name}'")

    info = DatabaseService.get_table_info(
        host=req.host,
        port=req.port,
        username=req.username,
        password=req.password,
        database_name=req.database_name,
        table_name=req.table_name,
        driver=req.driver
    )

    return TableInfoResponse(**info)
