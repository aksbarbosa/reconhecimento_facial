"""
routes_horarios.py

Endpoints para gerenciar horários (turnos com nome e período).
Todos exigem API Key no header X-API-Key.

Endpoints:
    GET    /horarios/        → lista horários
    POST   /horarios/        → cria horário (nome, inicio, fim)
    DELETE /horarios/{id}    → remove horário (bloqueado se houver turmas usando)
"""

import logging
from fastapi import APIRouter, HTTPException, Form, Depends
from app.db.models import create_horario, get_all_horarios, delete_horario
from app.utils.security import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/horarios",
    tags=["Horarios"],
    dependencies=[Depends(verify_api_key)]
)


@router.get("/")
def list_horarios():
    """Lista todos os horários cadastrados."""
    horarios = get_all_horarios()
    return {"horarios": horarios, "total": len(horarios)}


@router.post("/")
def add_horario(nome: str = Form(...), inicio: str = Form(...), fim: str = Form(...)):
    """
    Cria um horário. inicio/fim no formato HH:MM (ex: 07:00, 12:20).
    """
    try:
        horario = create_horario(nome, inicio, fim)
        return {"message": f"Horário '{nome}' criado.", "horario": horario}
    except Exception as e:
        logger.error(f"Erro ao criar horário: {e}")
        raise HTTPException(status_code=400, detail=f"Erro ao criar horário: {e}")


@router.delete("/{horario_id}")
def remove_horario(horario_id: int):
    """Remove um horário (o banco bloqueia se houver turmas vinculadas)."""
    try:
        removed = delete_horario(horario_id)
    except Exception as e:
        # Geralmente erro de FK: horário em uso por alguma turma
        logger.error(f"Erro ao remover horário {horario_id}: {e}")
        raise HTTPException(
            status_code=400,
            detail="Não é possível remover: há turmas usando este horário."
        )

    if not removed:
        raise HTTPException(status_code=404, detail=f"Horário ID {horario_id} não encontrado.")
    return {"message": f"Horário ID {horario_id} removido."}