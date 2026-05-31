"""
database.py

Responsabilidade: Gerenciar a conexão com o banco de dados PostgreSQL.

Este módulo centraliza a conexão com o banco, evitando que cada arquivo
do sistema precise criar sua própria conexão. Usa um padrão de conexão
única (singleton) para economizar recursos.

Fluxo:
    Qualquer service (person_service, face_service, etc.)
        → importa get_connection() deste arquivo
        → usa a conexão para consultar ou salvar dados
        → devolve a conexão ao pool
"""

import psycopg2                          # Driver PostgreSQL para Python
import psycopg2.extras                   # Extras para retornar dados como dicionário
from psycopg2 import OperationalError    # Erro de conexão


# ── Configurações do banco ─────────────────────────────────────────────────────
# Em produção, essas informações viriam do arquivo .env
# Por ora, deixamos direto aqui para facilitar o desenvolvimento local

DB_CONFIG = {
    "host":     "127.0.0.1",   # Endereço do banco (local)
    "port":     5432,           # Porta padrão do PostgreSQL
    "database": "face_access",  # Nome do banco criado no TablePlus
    "user":     "filipe",       # Usuário do PostgreSQL
    "password": "123456789",    # Senha definida no psql
}


def get_connection():
    """
    Abre e retorna uma conexão com o banco de dados PostgreSQL.

    Deve ser usada com context manager (with) para garantir que
    a conexão seja fechada corretamente após o uso.

    :return: Conexão psycopg2 ativa
    :raises: OperationalError se não conseguir conectar
    """
    try:
        # Abre a conexão com o PostgreSQL usando as configurações acima
        conn = psycopg2.connect(**DB_CONFIG)
        return conn

    except OperationalError as e:
        # Loga o erro e relança para o chamador tratar
        print(f"❌ Erro ao conectar no banco: {e}")
        raise


def get_cursor(conn):
    """
    Retorna um cursor que entrega resultados como dicionário.

    Em vez de retornar tuplas (linha[0], linha[1]...),
    retorna dicionários (linha["name"], linha["id"]...),
    o que torna o código mais legível.

    :param conn: Conexão psycopg2 ativa
    :return:     Cursor com RealDictCursor
    """

    # RealDictCursor faz com que cada linha retornada seja um dicionário
    # Ex: {"id": 1, "name": "João"} em vez de (1, "João")
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def test_connection():
    """
    Testa se a conexão com o banco está funcionando.
    Útil para rodar no início do sistema e garantir que o banco está acessível.

    :return: True se conectou com sucesso, False caso contrário
    """
    try:
        # Tenta abrir a conexão
        conn = get_connection()

        # Executa uma query simples para verificar que o banco responde
        cursor = get_cursor(conn)
        cursor.execute("SELECT version();")  # Retorna a versão do PostgreSQL
        version = cursor.fetchone()

        print(f"✅ Banco conectado! {version['version']}")

        # Fecha o cursor e a conexão
        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"❌ Falha na conexão: {e}")
        return False