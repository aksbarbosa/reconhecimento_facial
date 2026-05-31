"""
routes_persons.py

Responsabilidade: Endpoints da API para gerenciar pessoas cadastradas.

Expõe rotas HTTP para cadastrar, listar e remover pessoas.
O frontend Streamlit e qualquer cliente HTTP podem usar esses endpoints.

Endpoints:
    POST   /persons/register  → cadastra pessoa a partir de imagem
    GET    /persons            → lista todas as pessoas
    GET    /persons/{id}       → busca pessoa por ID
    DELETE /persons/{id}       → remove pessoa e seus embeddings
"""

import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from app.services.person_service import PersonService   # Lógica de cadastro
from app.db.models import get_all_persons, get_person_by_id, delete_person

# Pasta temporária para salvar uploads antes de processar
UPLOAD_TEMP = "data/raw/uploads"
os.makedirs(UPLOAD_TEMP, exist_ok=True)

# Cria o roteador com prefixo /persons
router = APIRouter(prefix="/persons", tags=["Persons"])

# Instância do serviço de pessoas — compartilhada entre todas as requisições
person_service = PersonService()


@router.post("/register")
async def register_person(
    name: str = Form(...),           # Nome da pessoa (campo do formulário)
    file: UploadFile = File(...)     # Foto da pessoa (upload de arquivo)
):
    """
    Cadastra uma nova pessoa a partir de uma foto enviada.

    - Salva a foto em data/raw/uploads/
    - Detecta o rosto na foto
    - Gera o embedding do rosto
    - Salva pessoa e embedding no banco

    Retorna os dados da pessoa cadastrada.
    """

    # Salva o arquivo enviado em disco temporariamente
    image_path = os.path.join(UPLOAD_TEMP, file.filename)

    # Lê o conteúdo do arquivo enviado e salva em disco
    contents = await file.read()
    with open(image_path, "wb") as f:
        f.write(contents)

    try:
        # Processa a imagem e cadastra no banco via PersonService
        result = person_service.register_from_image(name, image_path)

        return {
            "message":    f"Pessoa '{name}' cadastrada com sucesso!",
            "person_id":  result["person"]["id"],
            "person_name": result["person"]["name"],
            "confidence": f"{result['confidence']:.0%}",
        }

    except ValueError as e:
        # ValueError é lançado quando não há rosto na imagem
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@router.get("/")
def list_persons():
    """
    Lista todas as pessoas cadastradas no banco.

    Retorna uma lista com id, nome e data de cadastro de cada pessoa.
    """
    persons = get_all_persons()
    return {"persons": persons, "total": len(persons)}


@router.get("/{person_id}")
def get_person(person_id: int):
    """
    Busca uma pessoa específica pelo ID.

    Retorna os dados da pessoa ou 404 se não encontrada.
    """
    person = get_person_by_id(person_id)

    if not person:
        raise HTTPException(status_code=404, detail=f"Pessoa ID {person_id} não encontrada.")

    return person


@router.delete("/{person_id}")
def remove_person(person_id: int):
    """
    Remove uma pessoa e todos os seus embeddings do banco.

    O ON DELETE CASCADE na tabela face_embeddings garante que
    os embeddings são removidos automaticamente junto com a pessoa.
    """
    removed = delete_person(person_id)

    if not removed:
        raise HTTPException(status_code=404, detail=f"Pessoa ID {person_id} não encontrada.")

    return {"message": f"Pessoa ID {person_id} removida com sucesso."}