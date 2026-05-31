"""
routes_health.py

Responsabilidade: Endpoint de verificação de saúde do sistema.

Expõe um endpoint simples que retorna o status da API e do banco.
Útil para monitoramento e para o frontend verificar se o sistema está ativo.

Endpoint:
    GET /health → retorna status da API e do banco
"""

from fastapi import APIRouter               # Roteador do FastAPI
from app.db.database import test_connection # Testa conexão com o banco

# Cria o roteador — agrupa os endpoints de health
router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """
    Verifica se a API e o banco de dados estão funcionando.

    Retorna:
        status: "ok" se tudo funciona, "degraded" se o banco está fora
        database: True se o banco está acessível
    """

    # Testa a conexão com o banco de dados
    db_ok = test_connection()

    return {
        "status":   "ok" if db_ok else "degraded",  # Status geral do sistema
        "database": db_ok,                            # Status específico do banco
        "version":  "1.0.0",                          # Versão do sistema
    }