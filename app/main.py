"""
main.py

Ponto de entrada da aplicação (modelo escolar: horários, turmas, alunos).

Usa lifespan (substitui on_event), inicializa o pool de conexões e para a
câmera no shutdown.

Como rodar:
    uvicorn app.main:app --reload --env-file .env
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_health import router as health_router
from app.api.routes_horarios import router as horarios_router
from app.api.routes_turmas import router as turmas_router
from app.api.routes_alunos import router as alunos_router
from app.api.routes_camera import router as camera_router
from app.db.database import test_connection, init_pool, close_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida: startup antes do yield, shutdown depois."""
    logger.info("Iniciando Face Access System...")
    init_pool()

    if not test_connection():
        logger.error("❌ Banco de dados inacessível. Verifique o PostgreSQL.")
    else:
        logger.info("✅ Banco de dados conectado.")

    logger.info("✅ API pronta em http://localhost:8000")
    logger.info("📖 Documentação em http://localhost:8000/docs")

    yield

    logger.info("Encerrando Face Access System...")
    try:
        from app.api.routes_camera import camera_service
        if camera_service.is_running:
            camera_service.stop_camera()
    except Exception as e:
        logger.error(f"Erro ao parar a câmera no shutdown: {e}")
    close_pool()


app = FastAPI(
    title="Face Access System",
    description="Reconhecimento facial escolar com controle de acesso por horário.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro das rotas
app.include_router(health_router)     # GET /health
app.include_router(horarios_router)   # /horarios/...
app.include_router(turmas_router)     # /turmas/...
app.include_router(alunos_router)     # /alunos/...
app.include_router(camera_router)     # /camera/...