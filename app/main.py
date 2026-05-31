"""
main.py

Responsabilidade: Ponto de entrada da aplicação.

Este arquivo sobe a API FastAPI, registra todas as rotas,
inicializa os serviços e configura o logging do sistema.

Como rodar:
    uvicorn app.main:app --reload

Endpoints disponíveis:
    GET  /health                  → status do sistema
    POST /persons/register        → cadastrar pessoa
    GET  /persons                 → listar pessoas
    DELETE /persons/{id}          → remover pessoa
    POST /camera/start            → iniciar câmera
    POST /camera/stop             → parar câmera
    GET  /camera/status           → status da câmera
    GET  /camera/last             → último reconhecimento
    WebSocket /ws                 → notificações em tempo real
"""

import logging                              # Configuração de logs
from fastapi import FastAPI                 # Framework da API
from fastapi.middleware.cors import CORSMiddleware  # Permite acesso do frontend

from app.api.routes_health import router as health_router
from app.api.routes_persons import router as persons_router
from app.api.routes_camera import router as camera_router
from app.db.database import test_connection  # Testa conexão com banco na inicialização

# ── Configuração de logs ───────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,                         # Nível mínimo de log (INFO, WARNING, ERROR)
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",  # Formato da mensagem
    datefmt="%Y-%m-%d %H:%M:%S"                # Formato da data
)

logger = logging.getLogger(__name__)

# ── Inicialização da API ───────────────────────────────────────────────────────

# Cria a instância principal do FastAPI
app = FastAPI(
    title="Face Access System",           # Nome da API (aparece no /docs)
    description="Sistema de reconhecimento facial em tempo real.",
    version="1.0.0",
)

# ── CORS — permite que o frontend acesse a API ─────────────────────────────────

# CORS (Cross-Origin Resource Sharing) permite que o Streamlit,
# rodando em outra porta, faça requisições para esta API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Em produção, substitua pelo domínio do frontend
    allow_methods=["*"],       # Permite todos os métodos HTTP (GET, POST, DELETE...)
    allow_headers=["*"],       # Permite todos os headers
)

# ── Registro das rotas ─────────────────────────────────────────────────────────

# Cada router agrupa os endpoints de um módulo
app.include_router(health_router)    # GET /health
app.include_router(persons_router)   # /persons/...
app.include_router(camera_router)    # /camera/...

# ── Eventos de ciclo de vida ───────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """
    Executado automaticamente quando a API sobe.
    Verifica a conexão com o banco antes de aceitar requisições.
    """
    logger.info("Iniciando Face Access System...")

    # Testa a conexão com o banco de dados
    if not test_connection():
        logger.error("❌ Banco de dados inacessível. Verifique o PostgreSQL.")
    else:
        logger.info("✅ Banco de dados conectado.")

    logger.info("✅ API pronta em http://localhost:8000")
    logger.info("📖 Documentação em http://localhost:8000/docs")


@app.on_event("shutdown")
async def shutdown():
    """
    Executado automaticamente quando a API é encerrada.
    Para a câmera e libera os recursos.
    """
    logger.info("Encerrando Face Access System...")