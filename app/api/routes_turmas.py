"""
routes_turmas.py

Endpoints para gerenciar turmas. Cada turma é vinculada a um horário (turno).
Todos exigem API Key no header X-API-Key.

Endpoints:
    GET    /turmas/        → lista turmas (com horário)
    POST   /turmas/        → cria turma (nome, serie_nivel, horario_id, ano_letivo)
    DELETE /turmas/{id}    → remove turma (alunos ficam sem turma)
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Form, Depends
from app.db.models import create_turma, get_all_turmas, delete_turma, get_horario_by_id
from app.utils.security import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/turmas",
    tags=["Turmas"],
    dependencies=[Depends(verify_api_key)]
)


def _reload_camera_candidates():
    """Recarrega candidatos da câmera após mudança que afete o acesso."""
    try:
        from app.api.routes_camera import camera_service
        camera_service.reload_candidates()
    except Exception as e:
        logger.warning(f"Não foi possível recarregar candidatos da câmera: {e}")


@router.get("/")
def list_turmas():
    """Lista todas as turmas, com nome e período do horário."""
    turmas = get_all_turmas()
    return {"turmas": turmas, "total": len(turmas)}


@router.post("/")
def add_turma(
    nome: str = Form(...),
    serie_nivel: Optional[str] = Form(None),
    horario_id: Optional[int] = Form(None),
    ano_letivo: Optional[int] = Form(None),
):
    """Cria uma turma vinculada a um horário."""
    # Valida o horário, se informado
    if horario_id is not None and get_horario_by_id(horario_id) is None:
        raise HTTPException(status_code=400, detail=f"Horário ID {horario_id} não existe.")

    try:
        turma = create_turma(nome, serie_nivel, horario_id, ano_letivo)
        _reload_camera_candidates()
        return {"message": f"Turma '{nome}' criada.", "turma": turma}
    except Exception as e:
        logger.error(f"Erro ao criar turma: {e}")
        raise HTTPException(status_code=400, detail=f"Erro ao criar turma: {e}")


@router.delete("/{turma_id}")
def remove_turma(turma_id: int):
    """Remove uma turma. Os alunos dela ficam sem turma (acesso negado)."""
    try:
        removed = delete_turma(turma_id)
    except Exception as e:
        logger.error(f"Erro ao remover turma {turma_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao remover turma: {e}")

    if not removed:
        raise HTTPException(status_code=404, detail=f"Turma ID {turma_id} não encontrada.")

    _reload_camera_candidates()
    return {"message": f"Turma ID {turma_id} removida."}