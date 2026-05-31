"""
routes_persons.py

Responsabilidade: Endpoints da API para gerenciar pessoas cadastradas.
Todos os endpoints exigem autenticação via API Key no header X-API-Key.

Endpoints:
    POST   /persons/register  → cadastra pessoa a partir de imagem
    GET    /persons/           → lista todas as pessoas
    GET    /persons/{id}       → busca pessoa por ID
    DELETE /persons/{id}       → remove pessoa e seus embeddings
"""

import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from app.services.person_service import PersonService
from app.db.models import get_all_persons, get_person_by_id, delete_person
from app.utils.security import verify_api_key  # Importa a verificação de API Key

UPLOAD_TEMP = "data/raw/uploads"
os.makedirs(UPLOAD_TEMP, exist_ok=True)

# Aplica a verificação de API Key em todos os endpoints deste router
router = APIRouter(
    prefix="/persons",
    tags=["Persons"],
    dependencies=[Depends(verify_api_key)]  # ← exige API Key em todas as rotas
)

person_service = PersonService()


@router.post("/register")
async def register_person(
    name: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Cadastra uma nova pessoa a partir de uma foto enviada.
    Requer header: X-API-Key: sua_chave
    """
    image_path = os.path.join(UPLOAD_TEMP, file.filename)
    contents = await file.read()
    with open(image_path, "wb") as f:
        f.write(contents)

    try:
        result = person_service.register_from_image(name, image_path)
        return {
            "message":     f"Pessoa '{name}' cadastrada com sucesso!",
            "person_id":   result["person"]["id"],
            "person_name": result["person"]["name"],
            "confidence":  f"{result['confidence']:.0%}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@router.get("/")
def list_persons():
    """Lista todas as pessoas cadastradas."""
    persons = get_all_persons()
    return {"persons": persons, "total": len(persons)}


@router.get("/{person_id}")
def get_person(person_id: int):
    """Busca uma pessoa pelo ID."""
    person = get_person_by_id(person_id)
    if not person:
        raise HTTPException(status_code=404, detail=f"Pessoa ID {person_id} não encontrada.")
    return person


@router.delete("/{person_id}")
def remove_person(person_id: int):
    """Remove uma pessoa e todos os seus embeddings."""
    removed = delete_person(person_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Pessoa ID {person_id} não encontrada.")
    return {"message": f"Pessoa ID {person_id} removida com sucesso."}