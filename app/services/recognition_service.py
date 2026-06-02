"""
recognition_service.py

Responsabilidade: Orquestrar o reconhecimento facial de um frame avulso.

Observação importante sobre a arquitetura:
    O pipeline da CÂMERA AO VIVO roda no CameraWorker (workers/camera_worker.py),
    que já faz detecção, matching, presença, log e notificação. Este serviço
    NÃO é mais usado por esse caminho — ele existe para reconhecimento avulso
    (ex.: reconhecer um único frame/foto sob demanda) sem rastreamento de
    presença. Mantê-lo separado evita a duplicação que antes deixava os
    callbacks do WebSocket "mudos".

Esta versão usa o modelo compartilhado (app.face.engine), então não carrega
uma cópia extra do InsightFace, e serializa a inferência com infer_lock.
"""

import logging
import numpy as np
from datetime import datetime
from typing import Callable, Optional

from app.face.matcher import FaceMatcher
from app.face.engine import get_detector, get_embedder, infer_lock
from app.camera.snapshot import Snapshot
from app.db.models import get_all_embeddings, save_access_log

logger = logging.getLogger(__name__)


class RecognitionService:
    """
    Serviço de reconhecimento facial para frames avulsos.
    """

    def __init__(
        self,
        model_root: str = "models/insightface",
        snapshot_dir: str = "data/snapshots",
        unknown_dir: str = "data/raw/camera_frames",
        threshold: float = 0.6,
        on_recognized: Optional[Callable] = None,
        on_unknown: Optional[Callable] = None,
    ):
        # Modelo compartilhado (não carrega cópia extra)
        self.detector = get_detector(model_root=model_root)
        self.embedder = get_embedder()
        self.matcher = FaceMatcher(threshold=threshold)

        self.snapshot = Snapshot(output_dir=snapshot_dir)
        self.snapshot_unknown = Snapshot(output_dir=unknown_dir)

        self.on_recognized = on_recognized
        self.on_unknown = on_unknown

        self._candidates = []
        self.reload_candidates()

        logger.info("RecognitionService inicializado.")

    def reload_candidates(self):
        """Recarrega os candidatos do banco de dados."""
        try:
            self._candidates = get_all_embeddings()
            logger.info(f"Candidatos carregados: {len(self._candidates)} pessoa(s).")
        except Exception as e:
            logger.error(f"Erro ao carregar candidatos: {e}")
            self._candidates = []

    def process_frame(self, frame_bgr: np.ndarray, frame_rgb: np.ndarray) -> list:
        """
        Processa um frame avulso pelo pipeline de reconhecimento.

        :param frame_bgr: Frame em BGR (para salvar em disco)
        :param frame_rgb: Frame em RGB (para o InsightFace)
        :return:          Lista de resultados, um por rosto detectado
        """
        resultados = []

        with infer_lock:
            detection = self.detector.process_frame(frame_bgr, frame_rgb)

        if not detection["has_faces"]:
            return resultados

        logger.info(f"{len(detection['faces'])} rosto(s) detectado(s).")

        for i, face in enumerate(detection["faces"]):
            crop = detection["crops"][i]

            embedding = self.embedder.get_embedding(face)
            if not self.embedder.is_valid(embedding):
                logger.warning(f"Embedding inválido para rosto {i}. Pulando.")
                continue

            match = self.matcher.match(embedding, self._candidates)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

            if match.matched:
                resultado = self._handle_recognized(match, crop, timestamp)
            else:
                resultado = self._handle_unknown(crop, timestamp, match.similarity)

            resultados.append(resultado)

        return resultados

    def _handle_recognized(self, match, crop: np.ndarray, timestamp: str) -> dict:
        """Trata um rosto reconhecido: salva foto, registra log e notifica."""
        logger.info(
            f"✅ Reconhecido: {match.person_name} "
            f"(ID: {match.person_id}, Similaridade: {match.similarity:.0%})"
        )

        filename = f"{match.person_id}_{match.person_name}_{timestamp}.jpg"
        image_path = self.snapshot.save(crop, filename)

        try:
            save_access_log(
                person_id=match.person_id,
                similarity=match.similarity,
                image_path=image_path
            )
        except Exception as e:
            logger.error(f"Erro ao salvar log de acesso: {e}")

        resultado = {
            "status":      "recognized",
            "person_id":   match.person_id,
            "person_name": match.person_name,
            "similarity":  match.similarity,
            "image_path":  image_path,
            "timestamp":   timestamp,
        }

        if self.on_recognized:
            try:
                self.on_recognized(resultado)
            except Exception as e:
                logger.error(f"Erro no callback on_recognized: {e}")

        return resultado

    def _handle_unknown(self, crop: np.ndarray, timestamp: str, similarity: float) -> dict:
        """Trata um rosto desconhecido: salva foto e notifica."""
        logger.info(f"❓ Rosto desconhecido (similaridade: {similarity:.0%})")

        filename = f"unknown_{timestamp}.jpg"
        image_path = self.snapshot_unknown.save(crop, filename)

        resultado = {
            "status":     "unknown",
            "similarity": similarity,
            "image_path": image_path,
            "timestamp":  timestamp,
        }

        if self.on_unknown:
            try:
                self.on_unknown(resultado)
            except Exception as e:
                logger.error(f"Erro no callback on_unknown: {e}")

        return resultado

    def get_candidates_count(self) -> int:
        """Retorna o número de candidatos carregados do banco."""
        return len(self._candidates)