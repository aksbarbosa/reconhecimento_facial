"""
routes_camera.py

Responsabilidade: Endpoints para controlar a câmera e receber
notificações de reconhecimento em tempo real via WebSocket.
Todos os endpoints HTTP exigem autenticação via API Key.

Correção de tempo real:
    Os callbacks on_recognized/on_unknown são chamados de DENTRO da thread
    do CameraWorker, onde NÃO existe event loop do asyncio. Por isso não dá
    para usar asyncio.create_task() ali — usamos run_coroutine_threadsafe(),
    que agenda a corrotina no event loop principal (capturado no /start).

Endpoints:
    POST /camera/start  → inicia a câmera
    POST /camera/stop   → para a câmera
    GET  /camera/status → status atual
    GET  /camera/last   → último reconhecimento
    GET  /camera/logs   → histórico de acessos
    WS   /camera/ws     → WebSocket em tempo real
"""

import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from app.services.camera_service import CameraService
from app.utils.security import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/camera",
    tags=["Camera"],
    dependencies=[Depends(verify_api_key)]  # exige API Key em todas as rotas HTTP
)

camera_service = CameraService()
websocket_clients: list[WebSocket] = []


async def notify_clients(data: dict):
    """Envia notificação para todos os clientes WebSocket conectados."""
    message = json.dumps(data, default=str)
    disconnected = []
    for client in websocket_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.append(client)
    for client in disconnected:
        if client in websocket_clients:
            websocket_clients.remove(client)


@router.post("/start")
async def start_camera(source: int = 0, threshold: float = 0.6):
    """Inicia a câmera e o pipeline de reconhecimento."""
    if camera_service.is_running:
        raise HTTPException(status_code=400, detail="Câmera já está rodando.")

    # Captura o event loop principal AQUI (este endpoint roda no loop).
    # Os callbacks abaixo rodam na thread do worker e usam esse loop para
    # agendar a notificação de forma thread-safe.
    loop = asyncio.get_running_loop()

    def on_recognized(result: dict):
        asyncio.run_coroutine_threadsafe(
            notify_clients({"event": "recognized", **result}), loop
        )

    def on_unknown(result: dict):
        asyncio.run_coroutine_threadsafe(
            notify_clients({"event": "unknown", **result}), loop
        )

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
    """Para a câmera e encerra o pipeline."""
    if not camera_service.is_running:
        raise HTTPException(status_code=400, detail="Câmera não está rodando.")
    camera_service.stop_camera()
    return {"message": "Câmera encerrada com sucesso."}


@router.get("/status")
def camera_status():
    """Retorna o status atual da câmera."""
    return camera_service.get_status()


@router.get("/last")
def last_recognition():
    """Retorna o último resultado de reconhecimento."""
    result = camera_service.last_result
    if not result:
        return {"message": "Nenhum reconhecimento registrado ainda."}
    return result


@router.get("/logs")
def get_logs(limit: int = 100):
    """Retorna o histórico de reconhecimentos do banco."""
    from app.db.models import get_access_logs
    logs = get_access_logs(limit=limit)
    return {"logs": logs, "total": len(logs)}


# WebSocket não usa API Key pois o protocolo WS não suporta headers facilmente.
# Para produção, use um token de autenticação na URL: /camera/ws?token=xxx
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para notificações em tempo real."""
    await websocket.accept()
    websocket_clients.append(websocket)
    logger.info(f"WebSocket conectado. Total: {len(websocket_clients)} cliente(s).")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)
        logger.info(f"WebSocket desconectado. Total: {len(websocket_clients)} cliente(s).")