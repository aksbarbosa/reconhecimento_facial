"""
notify_service.py

Envia um evento de reconhecimento para a Supabase Edge Function,
que valida, salva no banco e dispara o push para o FaceNotify.

Variáveis de ambiente necessárias:
    EDGE_FUNCTION_URL  — URL da função (ex: https://<id>.supabase.co/functions/v1/notify-recognition)
    WEBHOOK_SECRET     — segredo compartilhado validado no header x-webhook-secret
    CAMERA_ID          — identificador da câmera (ex: "cam_001")
    CAMERA_LABEL       — nome legível (ex: "Câmera - Entrada Principal")
    CAMERA_ADDRESS     — endereço (ex: "Rua das Flores, 123")
    CAMERA_CITY        — cidade (ex: "São Paulo")
    CAMERA_STATE       — estado (ex: "SP")
"""

import os
import time
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_EDGE_FUNCTION_URL = os.getenv("EDGE_FUNCTION_URL", "")
_WEBHOOK_SECRET    = os.getenv("WEBHOOK_SECRET", "")
_SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
_COOLDOWN_SECONDS  = int(os.getenv("NOTIFY_COOLDOWN_SECONDS", "30"))

# Armazena o timestamp do último envio por dependent_id
_last_sent: dict[str, float] = {}

_CAMERA_LOCATION = {
    "camera_id":    os.getenv("CAMERA_ID",      "cam_001"),
    "camera_label": os.getenv("CAMERA_LABEL",   "Câmera Principal"),
    "address":      os.getenv("CAMERA_ADDRESS",  ""),
    "city":         os.getenv("CAMERA_CITY",     ""),
    "state":        os.getenv("CAMERA_STATE",    ""),
}


def notify_recognition(resultado: dict) -> None:
    """
    Dispara o webhook de reconhecimento para a Edge Function do Supabase.

    :param resultado: Dicionário com os dados do reconhecimento vindos do CameraWorker.
                      Precisa ter 'supabase_dependent_id', 'aluno_nome' e 'similarity'.
    """
    dependent_id = resultado.get("supabase_dependent_id")
    if not dependent_id:
        logger.debug(
            f"Aluno '{resultado.get('aluno_nome')}' sem supabase_dependent_id — "
            "notificação não enviada."
        )
        return

    camera_id = _CAMERA_LOCATION["camera_id"]
    cooldown_key = (dependent_id, camera_id)

    now = time.monotonic()
    last = _last_sent.get(cooldown_key, 0.0)
    if now - last < _COOLDOWN_SECONDS:
        remaining = int(_COOLDOWN_SECONDS - (now - last))
        logger.debug(
            f"Cooldown ativo para '{resultado.get('aluno_nome')}' em '{camera_id}' — "
            f"próxima notificação em {remaining}s."
        )
        return
    _last_sent[cooldown_key] = now

    if not _EDGE_FUNCTION_URL or not _WEBHOOK_SECRET:
        logger.warning(
            "EDGE_FUNCTION_URL ou WEBHOOK_SECRET não configurados — "
            "notificação não enviada."
        )
        return

    payload = {
        "person_id":   dependent_id,
        "person_name": resultado.get("aluno_nome", ""),
        "location":    _CAMERA_LOCATION,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "confidence":  round(float(resultado.get("similarity", 0)), 4),
    }

    try:
        response = httpx.post(
            _EDGE_FUNCTION_URL,
            headers={
                "x-webhook-secret": _WEBHOOK_SECRET,
                "Authorization": f"Bearer {_SUPABASE_ANON_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )
        if response.status_code == 200:
            logger.info(
                f"Notificação enviada: {resultado.get('aluno_nome')} "
                f"(dependent: {dependent_id})"
            )
        else:
            logger.warning(
                f"Edge Function retornou {response.status_code}: {response.text}"
            )
    except httpx.TimeoutException:
        logger.error("Timeout ao enviar notificação para a Edge Function.")
    except Exception as e:
        logger.error(f"Erro ao enviar notificação: {e}")
