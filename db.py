"""
Módulo para gerenciamento de conexão com banco de dados PostgreSQL.
"""

from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from dotenv import load_dotenv
from psycopg2 import connect
from os import getenv


load_dotenv()

connection_pool = None

DB_CONFIG = {
    'host': getenv('DB_HOST', 'localhost'),
    'port': getenv('DB_PORT', '5432'),
    'database': getenv('DB_NAME', 'postgres'),
    'user': getenv('DB_USER', 'postgres'),
    'password': getenv('DB_PASS', ''),
}


def create_connection_pool(min_conn = 1, max_conn = 10):
    """
    Cria um pool de conexões com o banco de dados.
    
    Args:
        min_conn: Número mínimo de conexões no pool
        max_conn: Número máximo de conexões no pool
    """
    global connection_pool
    try:
        connection_pool = ThreadedConnectionPool(
            min_conn,
            max_conn,
            **DB_CONFIG
        )
        print(f"Pool de conexões criado com sucesso ({min_conn}-{max_conn} conexões)")
    except Exception as e:
        print(f"Erro ao criar pool de conexões: {e}")
        raise


def get_connection():
    """
    Obtém uma conexão do pool ou cria uma nova conexão.
    
    Returns:
        psycopg2.connection: Objeto de conexão com o banco de dados
    """
    if connection_pool:
        return connection_pool.getconn()
    else:
        return connect(**DB_CONFIG)


def return_connection(conn):
    """
    Retorna uma conexão ao pool.
    
    Args:
        conn: Objeto de conexão a ser retornado ao pool
    """
    if connection_pool:
        connection_pool.putconn(conn)
    else:
        conn.close()


@contextmanager
def get_db_connection():
    """
    Context manager para gerenciar conexões com o banco de dados.
    Garante que a conexão seja fechada corretamente após o uso.
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tabela")
            result = cursor.fetchall()
    """
    conn = None
    try:
        conn = get_connection()
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Erro na operação do banco de dados: {e}")
        raise
    finally:
        if conn:
            return_connection(conn)


def test_connection():
    """
    Testa a conexão com o banco de dados.
    
    Returns:
        bool: True se a conexão foi bem-sucedida, False caso contrário
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            print(f"Conexão bem-sucedida! Versão do PostgreSQL: {version[0]}")
            return True
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return False


def execute_query(query, params = None, fetch = True):
    """
    Executa uma query SELECT e retorna os resultados.
    
    Args:
        query: Query SQL a ser executada
        params: Parâmetros para a query (tupla)
        fetch: Se True, retorna os resultados; se False, apenas executa
        
    Returns:
        List[Dict[str, Any]]: Lista de dicionários com os resultados
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            if fetch:
                return cursor.fetchall()
            return []


def execute_update(query, params = None):
    """
    Executa uma query INSERT, UPDATE ou DELETE.
    
    Args:
        query: Query SQL a ser executada
        params: Parâmetros para a query (tupla)
        
    Returns:
        int: Número de linhas afetadas
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount


def execute_many(query, params_list):
    """
    Executa uma query múltiplas vezes com diferentes parâmetros.
    Útil para inserções em lote.
    
    Args:
        query: Query SQL a ser executada
        params_list: Lista de tuplas com parâmetros
        
    Returns:
        int: Número total de linhas afetadas
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount


def close_pool():
    """
    Fecha o pool de conexões.
    """
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
        connection_pool = None
        print("Pool de conexões fechado")
