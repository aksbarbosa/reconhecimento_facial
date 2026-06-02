"""
database.py

Responsabilidade: Gerenciar a conexão com o banco de dados PostgreSQL.

Mudança importante: agora usamos um POOL de conexões em vez de abrir e
fechar uma conexão nova a cada operação. O frontend faz polling em
/health e /camera/status a cada poucos segundos — abrir/fechar conexão
nessa frequência é caro e desperdiça recursos do Postgres. Com o pool,
as conexões são reaproveitadas.

O acesso ao banco passa a ser feito por um context manager:

    from app.db.database import get_cursor

    # Leitura
    with get_cursor() as cursor:
        cursor.execute("SELECT ...")
        rows = cursor.fetchall()

    # Escrita (commit=True faz o commit ao sair do bloco;
    #          em caso de exceção, faz rollback automático)
    with get_cursor(commit=True) as cursor:
        cursor.execute("INSERT ...")

As credenciais continuam vindo do .env (nunca no código).
"""

import os
import psycopg2
import psycopg2.extras
import psycopg2.pool
from contextlib import contextmanager
from dotenv import load_dotenv  # Lê as variáveis do arquivo .env

# Carrega as variáveis do .env antes de qualquer os.getenv()
load_dotenv()

# ── Configurações do banco — lidas do .env ─────────────────────────────────────

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "127.0.0.1"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME",     "face_access"),
    "user":     os.getenv("DB_USER",     ""),        # Sem padrão — obrigatório no .env
    "password": os.getenv("DB_PASSWORD", ""),        # Sem padrão — obrigatório no .env
}

# ── Pool de conexões ───────────────────────────────────────────────────────────
# Começa como None e é criado sob demanda (lazy). Se o banco estiver fora no
# startup, a criação falha silenciosamente e é tentada de novo no primeiro uso —
# assim a API ainda sobe mesmo com o Postgres temporariamente indisponível.

_pool: psycopg2.pool.ThreadedConnectionPool = None


def init_pool(minconn: int = 1, maxconn: int = 10):
    """
    Cria o pool de conexões, se ainda não existir.
    Chamado no startup da API e também sob demanda por get_pool().

    :return: O pool criado, ou None se o banco estiver inacessível
    """
    global _pool
    if _pool is None:
        try:
            _pool = psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, **DB_CONFIG)
            print("✅ Pool de conexões criado.")
        except Exception as e:
            print(f"❌ Falha ao criar o pool de conexões: {e}")
            _pool = None
    return _pool


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """
    Retorna o pool, tentando criá-lo se ainda não existir.

    :raises RuntimeError: se não conseguir criar o pool (banco fora)
    """
    if _pool is None:
        init_pool()
    if _pool is None:
        raise RuntimeError("Banco de dados indisponível — pool não pôde ser criado.")
    return _pool


def close_pool():
    """Fecha todas as conexões do pool. Chamado no shutdown da API."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        print("Pool de conexões encerrado.")


@contextmanager
def get_cursor(commit: bool = False):
    """
    Context manager que pega uma conexão do pool, entrega um cursor que
    retorna dicionários (RealDictCursor) e devolve a conexão ao pool no fim.

    - commit=False (padrão): para SELECTs.
    - commit=True: faz commit ao sair; em caso de exceção, faz rollback.

    :param commit: Se True, confirma a transação ao final do bloco
    :yield:        Cursor pronto para uso
    """
    pool = get_pool()
    conn = pool.getconn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception:
        # Desfaz qualquer alteração parcial antes de propagar o erro
        conn.rollback()
        raise
    finally:
        cursor.close()
        # Devolve a conexão ao pool em vez de fechá-la de verdade
        pool.putconn(conn)


def test_connection() -> bool:
    """
    Testa se a conexão com o banco está funcionando.
    Chamado na inicialização da API e no endpoint /health.
    """
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            print(f"✅ Banco conectado! {version['version']}")
        return True
    except Exception as e:
        print(f"❌ Falha na conexão: {e}")
        return False