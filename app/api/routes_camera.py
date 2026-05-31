"""
routes_camera.py

Responsabilidade: Endpoints para controlar a câmera e receber
notificações de reconhecimento em tempo real via WebSocket.
Todos os endpoints HTTP exigem autenticação via API Key.

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
from app.utils.security import verify_api_key  # Verificação de API Key

logger = logging.getLogger(__name__)

# Aplica API Key em todos os endpoints HTTP (não no WebSocket)
router = APIRouter(
    prefix="/camera",
    tags=["Camera"],
    dependencies=[Depends(verify_api_key)]  # ← exige API Key em todas as rotas HTTP
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
        websocket_clients.remove(client)


@router.post("/start")
async def start_camera(source: int = 0, threshold: float = 0.6):
    """Inicia a câmera e o pipeline de reconhecimento."""
    if camera_service.is_running:
        raise HTTPException(status_code=400, detail="Câmera já está rodando.")

    def on_recognized(result: dict):
        asyncio.create_task(notify_clients({"event": "recognized", **result}))

    def on_unknown(result: dict):
        asyncio.create_task(notify_clients({"event": "unknown", **result}))

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


# WebSocket não usa API Key pois o protocolo WS não suporta headers facilmente
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
        websocket_clients.remove(websocket)
        logger.info(f"WebSocket desconectado. Total: {len(websocket_clients)} cliente(s).")