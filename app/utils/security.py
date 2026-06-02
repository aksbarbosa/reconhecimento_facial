"""
security.py

Responsabilidade: Autenticação via API Key para proteger os endpoints.

Todos os endpoints da API exigem um header com a chave secreta:
    X-API-Key: sua_chave_aqui

A chave é definida no arquivo .env:
    API_KEY=sua_chave_secreta

Como gerar uma chave segura pelo terminal:
    python3 -c "import secrets; print(secrets.token_hex(32))"

Nota de segurança: a comparação da chave usa secrets.compare_digest(),
que leva o mesmo tempo independentemente de onde os bytes diferem.
Uma comparação comum com '!=' retorna assim que encontra o primeiro byte
diferente, o que permite (em teoria) um ataque de timing para descobrir
a chave byte a byte. compare_digest() elimina essa brecha.
"""

import os
import secrets
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv  # Lê as variáveis do arquivo .env

# Carrega as variáveis do .env
load_dotenv()

# Nome do header que o cliente deve enviar com a chave
# Exemplo: X-API-Key: minha_chave_secreta
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Chave secreta lida do .env
API_KEY = os.getenv("API_KEY", "")


def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    """
    Verifica se a API Key enviada no header é válida.

    Esta função é usada como dependência nos endpoints do FastAPI.
    Se a chave for inválida, retorna erro 403 automaticamente.

    Uso nos endpoints:
        @router.get("/rota", dependencies=[Depends(verify_api_key)])

    :param api_key: Chave enviada no header X-API-Key
    :raises HTTPException: 500 se a chave não estiver configurada no .env
                           403 se a chave for inválida ou ausente
    """

    # Se não há chave configurada no .env, avisa e bloqueia
    if not API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_KEY não configurada no .env"
        )

    # Comparação em tempo constante (resistente a timing attack).
    # compare_digest exige uma string não vazia, por isso checamos antes.
    if not api_key or not secrets.compare_digest(api_key, API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key inválida ou ausente. Envie no header: X-API-Key"
        )