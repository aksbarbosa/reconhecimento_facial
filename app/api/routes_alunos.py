"""
routes_alunos.py

Endpoints para gerenciar alunos (as pessoas reconhecidas pela câmera).
Substitui o antigo routes_persons. Todos exigem API Key no header X-API-Key.

Endpoints:
    POST   /alunos/register   → cadastra aluno (nome + turma_id + foto)
    GET    /alunos/           → lista alunos (com turma e horário)
    GET    /alunos/{id}       → busca aluno por ID
    PATCH  /alunos/{id}/turma → muda a turma do aluno
    DELETE /alunos/{id}       → remove aluno e seus embeddings/logs
"""

import os
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from app.services.aluno_service import AlunoService
from app.db.models import (
    get_all_alunos, get_aluno_by_id, delete_aluno,
    update_aluno_turma, update_aluno_dependent_id, get_turma_by_id
)
from app.utils.security import verify_api_key

logger = logging.getLogger(__name__)

UPLOAD_TEMP = "data/raw/uploads"
os.makedirs(UPLOAD_TEMP, exist_ok=True)

EXTENSOES_ACEITAS = {".jpg", ".jpeg", ".png", ".webp"}

router = APIRouter(
    prefix="/alunos",
    tags=["Alunos"],
    dependencies=[Depends(verify_api_key)]
)

aluno_service = AlunoService()


def _reload_camera_candidates():
    """Recarrega candidatos da câmera após cadastro/alteração/remoção."""
    try:
        from app.api.routes_camera import camera_service
        camera_service.reload_candidates()
    except Exception as e:
        logger.warning(f"Não foi possível recarregar candidatos da câmera: {e}")


@router.post("/register")
async def register_aluno(
    nome: str = Form(...),
    turma_id: Optional[int] = Form(None),
    supabase_dependent_id: Optional[str] = Form(None),
    file: UploadFile = File(...)
):
    """Cadastra um aluno a partir de uma foto. Requer X-API-Key."""
    # Valida a turma, se informada
    if turma_id is not None and get_turma_by_id(turma_id) is None:
        raise HTTPException(status_code=400, detail=f"Turma ID {turma_id} não existe.")

    # Sanitiza o nome do arquivo (evita path traversal)
    safe_name = os.path.basename(file.filename or "")
    if not safe_name:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")

    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in EXTENSOES_ACEITAS:
        raise HTTPException(
            status_code=400,
            detail="Formato não suportado. Envie JPG, JPEG, PNG ou WEBP."
        )

    image_path = os.path.join(UPLOAD_TEMP, safe_name)
    contents = await file.read()
    with open(image_path, "wb") as f:
        f.write(contents)

    try:
        result = aluno_service.register_from_image(
            nome, image_path,
            turma_id=turma_id,
            supabase_dependent_id=supabase_dependent_id,
        )
        _reload_camera_candidates()
        return {
            "message":                f"Aluno '{nome}' cadastrado com sucesso!",
            "aluno_id":               result["aluno"]["id"],
            "aluno_nome":             result["aluno"]["nome"],
            "turma_id":               result["aluno"]["turma_id"],
            "supabase_dependent_id":  result["aluno"].get("supabase_dependent_id"),
            "confidence":             f"{result['confidence']:.0%}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@router.get("/")
def list_alunos():
    """Lista todos os alunos cadastrados (com turma e horário)."""
    alunos = get_all_alunos()
    return {"alunos": alunos, "total": len(alunos)}


@router.get("/{aluno_id}")
def get_aluno(aluno_id: int):
    """Busca um aluno pelo ID."""
    aluno = get_aluno_by_id(aluno_id)
    if not aluno:
        raise HTTPException(status_code=404, detail=f"Aluno ID {aluno_id} não encontrado.")
    return aluno


@router.patch("/{aluno_id}/dependent")
def link_dependent(aluno_id: int, supabase_dependent_id: str = Form(...)):
    """Vincula um aluno ao dependente correspondente no Supabase/FaceNotify."""
    updated = update_aluno_dependent_id(aluno_id, supabase_dependent_id)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Aluno ID {aluno_id} não encontrado.")
    _reload_camera_candidates()
    return {"message": f"Aluno ID {aluno_id} vinculado ao dependente {supabase_dependent_id}."}


@router.patch("/{aluno_id}/turma")
def change_turma(aluno_id: int, turma_id: int = Form(...)):
    """Atualiza a turma de um aluno."""
    if get_turma_by_id(turma_id) is None:
        raise HTTPException(status_code=400, detail=f"Turma ID {turma_id} não existe.")

    updated = update_aluno_turma(aluno_id, turma_id)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Aluno ID {aluno_id} não encontrado.")

    _reload_camera_candidates()
    return {"message": f"Turma do aluno ID {aluno_id} atualizada."}


@router.delete("/{aluno_id}")
def remove_aluno(aluno_id: int):
    """Remove um aluno e, em cascata, seus embeddings e logs."""
    try:
        removed = delete_aluno(aluno_id)
    except Exception as e:
        logger.error(f"Erro ao remover aluno ID {aluno_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao remover no banco: {e}")

    if not removed:
        raise HTTPException(status_code=404, detail=f"Aluno ID {aluno_id} não encontrado.")

    _reload_camera_candidates()
    return {"message": f"Aluno ID {aluno_id} removido com sucesso."}