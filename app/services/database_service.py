"""
Serviço para operações de descoberta e teste de conexões com banco de dados.
"""

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Connection
from typing import List, Dict, Any
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service para testar conexões e listar databases/schemas"""

    @staticmethod
    def test_connection(
        host: str,
        port: int,
        username: str,
        password: str,
        database_name: str = "mysql",
        driver: str = "mysql+pymysql"
    ) -> Dict[str, Any]:
        """
        Testa conexão com o banco de dados.

        Args:
            host: Endereço do servidor MySQL
            port: Porta do servidor
            username: Usuário do banco
            password: Senha do usuário
            database_name: Nome do database (padrão: mysql)
            driver: Driver SQLAlchemy (padrão: mysql+pymysql)

        Returns:
            Dict com status e mensagem

        Raises:
            HTTPException: Se não conseguir conectar
        """
        try:
            # Constrói a URL de conexão
            url = f"{driver}://{username}:{password}@{host}:{port}/{database_name}"

            # Tenta criar engine e conectar
            engine = create_engine(url, pool_pre_ping=True)

            with engine.connect() as conn:
                # Executa query simples para validar conexão
                result = conn.execute(text("SELECT 1 as test"))
                result.fetchone()

            logger.info(f"Conexão bem-sucedida: {username}@{host}:{port}/{database_name}")

            return {
                "status": "connected",
                "message": "Conexão estabelecida com sucesso!",
                "host": host,
                "port": port,
                "username": username
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Falha na conexão: {error_msg}")

            # Mensagens de erro mais amigáveis
            if "Access denied" in error_msg:
                user_msg = "Usuário ou senha incorretos."
            elif "Can't connect" in error_msg or "Connection refused" in error_msg:
                user_msg = f"Não foi possível conectar ao servidor {host}:{port}. Verifique se o MySQL está rodando."
            elif "Unknown database" in error_msg:
                user_msg = f"O banco de dados '{database_name}' não existe."
            else:
                user_msg = f"Erro ao conectar: {error_msg}"

            raise HTTPException(
                status_code=400,
                detail={
                    "status": "failed",
                    "message": user_msg,
                    "technical_error": error_msg
                }
            )

    @staticmethod
    def list_databases(
        host: str,
        port: int,
        username: str,
        password: str,
        driver: str = "mysql+pymysql"
    ) -> List[str]:
        """
        Lista todos os databases disponíveis na conexão.

        Args:
            host: Endereço do servidor MySQL
            port: Porta do servidor
            username: Usuário do banco
            password: Senha do usuário
            driver: Driver SQLAlchemy

        Returns:
            Lista de nomes de databases

        Raises:
            HTTPException: Se não conseguir conectar ou listar
        """
        try:
            # Conecta ao database 'mysql' (sempre existe)
            url = f"{driver}://{username}:{password}@{host}:{port}/mysql"
            engine = create_engine(url, pool_pre_ping=True)

            with engine.connect() as conn:
                # Executa SHOW DATABASES
                result = conn.execute(text("SHOW DATABASES"))
                databases = [row[0] for row in result]

            # Filtra databases de sistema que não são relevantes
            system_dbs = {"information_schema", "performance_schema", "sys"}
            filtered = [db for db in databases if db not in system_dbs]

            logger.info(f"Listados {len(filtered)} databases (excluindo sistema)")

            return filtered

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erro ao listar databases: {error_msg}")
            raise HTTPException(
                status_code=400,
                detail=f"Erro ao listar databases: {error_msg}"
            )

    @staticmethod
    def list_schemas(
        host: str,
        port: int,
        username: str,
        password: str,
        database_name: str,
        driver: str = "mysql+pymysql"
    ) -> List[str]:
        """
        Lista todos os schemas (tabelas) de um database específico.

        Args:
            host: Endereço do servidor MySQL
            port: Porta do servidor
            username: Usuário do banco
            password: Senha do usuário
            database_name: Nome do database para inspecionar
            driver: Driver SQLAlchemy

        Returns:
            Lista de nomes de tabelas/schemas

        Raises:
            HTTPException: Se não conseguir conectar ou listar
        """
        try:
            # Conecta ao database específico
            url = f"{driver}://{username}:{password}@{host}:{port}/{database_name}"
            engine = create_engine(url, pool_pre_ping=True)

            # Usa inspector do SQLAlchemy para listar tabelas
            inspector = inspect(engine)
            tables = inspector.get_table_names()

            logger.info(f"Listadas {len(tables)} tabelas no database '{database_name}'")

            return sorted(tables)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erro ao listar schemas do database '{database_name}': {error_msg}")
            raise HTTPException(
                status_code=400,
                detail=f"Erro ao listar tabelas: {error_msg}"
            )

    @staticmethod
    def get_table_info(
        host: str,
        port: int,
        username: str,
        password: str,
        database_name: str,
        table_name: str,
        driver: str = "mysql+pymysql"
    ) -> Dict[str, Any]:
        """
        Retorna informações detalhadas sobre uma tabela específica.

        Args:
            host: Endereço do servidor MySQL
            port: Porta do servidor
            username: Usuário do banco
            password: Senha do usuário
            database_name: Nome do database
            table_name: Nome da tabela
            driver: Driver SQLAlchemy

        Returns:
            Dict com colunas e metadados da tabela
        """
        try:
            url = f"{driver}://{username}:{password}@{host}:{port}/{database_name}"
            engine = create_engine(url, pool_pre_ping=True)

            inspector = inspect(engine)
            columns = inspector.get_columns(table_name)

            # Formata informações das colunas
            column_info = []
            for col in columns:
                column_info.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "default": str(col.get("default")) if col.get("default") else None
                })

            return {
                "table_name": table_name,
                "database": database_name,
                "columns": column_info,
                "column_count": len(column_info)
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erro ao obter info da tabela '{table_name}': {error_msg}")
            raise HTTPException(
                status_code=400,
                detail=f"Erro ao obter informações da tabela: {error_msg}"
            )
