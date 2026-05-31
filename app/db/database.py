"""
database.py

Responsabilidade: Gerenciar a conexão com o banco de dados PostgreSQL.

As credenciais são lidas do arquivo .env em vez de ficarem escritas
diretamente no código — isso evita expor senhas no GitHub.

Como configurar:
    1. Copie .env.example para .env
    2. Preencha com suas credenciais reais
    3. Nunca commite o .env no GitHub (já está no .gitignore)
"""

import os
import psycopg2
import psycopg2.extras
from psycopg2 import OperationalError
from dotenv import load_dotenv  # Lê as variáveis do arquivo .env

# Carrega as variáveis do arquivo .env para o os.environ
# Deve ser chamado antes de qualquer os.getenv()
load_dotenv()

# ── Configurações do banco — lidas do .env ─────────────────────────────────────
# os.getenv("VARIAVEL", "valor_padrao") — usa o valor padrão se não encontrar no .env

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "127.0.0.1"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME",     "face_access"),
    "user":     os.getenv("DB_USER",     ""),        # Sem padrão — obrigatório no .env
    "password": os.getenv("DB_PASSWORD", ""),        # Sem padrão — obrigatório no .env
}


def get_connection():
    """
    Abre e retorna uma conexão com o banco de dados PostgreSQL.

    :return: Conexão psycopg2 ativa
    :raises: OperationalError se não conseguir conectar
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except OperationalError as e:
        print(f"❌ Erro ao conectar no banco: {e}")
        raise


def get_cursor(conn):
    """
    Retorna um cursor que entrega resultados como dicionário.
    Em vez de tuplas (linha[0], linha[1]), retorna {"id": 1, "name": "João"}.
    """
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def test_connection():
    """
    Testa se a conexão com o banco está funcionando.
    Chamado na inicialização da API para garantir que o banco está acessível.
    """
    try:
        conn = get_connection()
        cursor = get_cursor(conn)
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Banco conectado! {version['version']}")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Falha na conexão: {e}")
        return False