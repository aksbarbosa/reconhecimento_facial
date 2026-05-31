"""
routes_camera.py

Responsabilidade: Endpoints para controlar a câmera e receber
notificações de reconhecimento em tempo real via WebSocket.

Endpoints:
    POST /camera/start      → inicia a câmera e o reconhecimento
    POST /camera/stop       → para a câmera
    GET  /camera/status     → status atual da câmera
    GET  /camera/last       → último reconhecimento
    WS   /camera/ws         → WebSocket para notificações em tempo real
"""

import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from app.services.camera_service import CameraService   # Gerencia a câmera

logger = logging.getLogger(__name__)

# Cria o roteador com prefixo /camera
router = APIRouter(prefix="/camera", tags=["Camera"])

# Instância única do CameraService — compartilhada entre todas as rotas
camera_service = CameraService()

# Lista de clientes WebSocket conectados
# Quando um reconhecimento acontece, todos são notificados
websocket_clients: list[WebSocket] = []


async def notify_clients(data: dict):
    """
    Envia uma notificação para todos os clientes WebSocket conectados.

    É chamado pelo RecognitionService via callback quando alguém é reconhecido.
    O frontend Streamlit recebe essa notificação e atualiza a interface.

    :param data: Dicionário com os dados do reconhecimento
    """

    # Converte o dicionário para JSON para enviar pelo WebSocket
    message = json.dumps(data, default=str)

    # Envia para todos os clientes conectados
    disconnected = []
    for client in websocket_clients:
        try:
            await client.send_text(message)
        except Exception:
            # Se o cliente desconectou, marca para remover da lista
            disconnected.append(client)

    # Remove clientes desconectados da lista
    for client in disconnected:
        websocket_clients.remove(client)


@router.post("/start")
async def start_camera(source: int = 0, threshold: float = 0.6):
    """
    Inicia a câmera e o pipeline de reconhecimento em background.

    :param source:    Índice da câmera (0 = Mac) ou URL RTSP (câmera IP)
    :param threshold: Limiar de similaridade (padrão: 0.6 = 60%)
    """

    if camera_service.is_running:
        raise HTTPException(status_code=400, detail="Câmera já está rodando.")

    # Define os callbacks que serão chamados pelo RecognitionService
    # Quando reconhecer alguém, notifica todos os WebSocket conectados
    def on_recognized(result: dict):
        asyncio.create_task(notify_clients({
            "event": "recognized",
            **result
        }))

    def on_unknown(result: dict):
        asyncio.create_task(notify_clients({
            "event": "unknown",
            **result
        }))

    # Inicia a câmera com os callbacks configurados
    success = camera_service.start_camera(
        source=source,
        on_recognized=on_recognized,
        on_unknown=on_unknown,
        threshold=threshold,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Falha ao iniciar a câmera.")

    return {"message": "Câmera iniciada com sucesso.", "source": source}


@router.post("/stop")
def stop_camera():
    """
    Para a câmera e encerra o pipeline de reconhecimento.
    """

    if not camera_service.is_running:
        raise HTTPException(status_code=400, detail="Câmera não está rodando.")

    camera_service.stop_camera()
    return {"message": "Câmera encerrada com sucesso."}


@router.get("/status")
def camera_status():
    """
    Retorna o status atual da câmera e do sistema de reconhecimento.
    """
    return camera_service.get_status()


@router.get("/last")
def last_recognition():
    """
    Retorna o último resultado de reconhecimento.
    Útil para o frontend consultar sem usar WebSocket.
    """
    result = camera_service.last_result

    if not result:
        return {"message": "Nenhum reconhecimento registrado ainda."}

    return result


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket para notificações de reconhecimento em tempo real.

    O frontend conecta aqui e fica "escutando".
    Quando alguém é reconhecido, recebe uma mensagem JSON automaticamente.

    Formato da mensagem recebida:
    {
        "event": "recognized",
        "person_id": 1,
        "person_name": "Filipe",
        "similarity": 0.97,
        "timestamp": "20240101_143200_000000"
    }
    """

    # Aceita a conexão WebSocket
    await websocket.accept()

    # Adiciona o cliente à lista de notificações
    websocket_clients.append(websocket)
    logger.info(f"WebSocket conectado. Total: {len(websocket_clients)} cliente(s).")

    try:
        # Mantém a conexão aberta enquanto o cliente estiver conectado
        while True:
            # Aguarda mensagens do cliente (heartbeat para manter vivo)
            await websocket.receive_text()

    except WebSocketDisconnect:
        # Remove o cliente da lista quando desconectar
        websocket_clients.remove(websocket)
        logger.info(f"WebSocket desconectado. Total: {len(websocket_clients)} cliente(s).")


@router.get("/logs")
def get_logs(limit: int = 100):
    """
    Retorna o histórico de reconhecimentos do banco.

    Usado pelo frontend Streamlit para exibir a página de Histórico.
    O Streamlit não pode importar o módulo app diretamente pois roda
    em processo separado — por isso busca os logs via esta rota da API.

    :param limit: Número máximo de registros a retornar (padrão: 100)
    """
    from app.db.models import get_access_logs  # Importa aqui para evitar import circular

    logs = get_access_logs(limit=limit)
    return {"logs": logs, "total": len(logs)}