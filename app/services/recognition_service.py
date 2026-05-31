"""
recognition_service.py

Responsabilidade: Orquestrar o reconhecimento facial completo.

Este é o serviço central do sistema — ele recebe o frame da câmera,
passa pelo pipeline de detecção e identificação, salva o log no banco
quando alguém é reconhecido, e notifica o frontend em tempo real.

Fluxo:
    CameraWorker chama process_frame()
        → Detecta rostos (FaceDetector)
        → Gera embeddings (FaceEmbedder)
        → Compara com banco (FaceMatcher)
        → Salva log (access_logs)
        → Notifica frontend (callback)
"""

import os
import cv2                                      # OpenCV — salvar imagens
import numpy as np                             # NumPy — manipulação de vetores
import logging                                 # Logs do sistema
from datetime import datetime                  # Timestamp dos eventos
from typing import Callable, Optional          # Tipagem

from app.face.detector import FaceDetector     # Detecta rostos nos frames
from app.face.embedder import FaceEmbedder     # Gera vetores dos rostos
from app.face.matcher import FaceMatcher       # Compara vetores com o banco
from app.camera.snapshot import Snapshot       # Salva imagens em disco
from app.db.models import (
    get_all_embeddings,    # Busca todos os candidatos do banco
    save_access_log        # Salva o log de acesso
)

# Configura o logger para este módulo
logger = logging.getLogger(__name__)


class RecognitionService:
    """
    Serviço central de reconhecimento facial.

    Conecta o pipeline de visão computacional (câmera → detecção → embedding → matching)
    com o banco de dados e o frontend, disparando eventos quando alguém é identificado.
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
        """
        Inicializa o serviço com todos os módulos necessários.

        :param model_root:      Pasta dos modelos InsightFace
        :param snapshot_dir:    Pasta para salvar fotos de pessoas identificadas
        :param unknown_dir:     Pasta para salvar fotos de pessoas desconhecidas
        :param threshold:       Limiar de similaridade para reconhecimento (padrão: 0.6)
        :param on_recognized:   Callback chamado quando alguém é reconhecido
                                Assinatura: on_recognized(result: dict)
        :param on_unknown:      Callback chamado quando rosto desconhecido é detectado
                                Assinatura: on_unknown(result: dict)
        """

        # ── Módulos do pipeline ────────────────────────────────────────────

        # Detecta rostos nos frames via InsightFace
        self.detector = FaceDetector(model_root=model_root)

        # Gera embeddings (vetores de 512 números) dos rostos
        self.embedder = FaceEmbedder()

        # Compara embeddings com os cadastros do banco
        self.matcher = FaceMatcher(threshold=threshold)

        # Salva imagens de rostos identificados em disco
        self.snapshot = Snapshot(output_dir=snapshot_dir)

        # Salva imagens de rostos desconhecidos em disco
        self.snapshot_unknown = Snapshot(output_dir=unknown_dir)

        # ── Callbacks ─────────────────────────────────────────────────────

        # Função chamada quando uma pessoa é reconhecida
        # O frontend pode passar um callback aqui para atualizar a interface
        self.on_recognized = on_recognized

        # Função chamada quando um rosto desconhecido é detectado
        self.on_unknown = on_unknown

        # ── Estado interno ─────────────────────────────────────────────────

        # Cache dos candidatos do banco — atualizado periodicamente
        # para evitar consultas ao banco a cada frame
        self._candidates = []

        # Carrega os candidatos do banco ao inicializar
        self.reload_candidates()

        logger.info("RecognitionService inicializado.")

    def reload_candidates(self):
        """
        Recarrega os candidatos do banco de dados.

        Deve ser chamado quando uma nova pessoa for cadastrada,
        para que o sistema passe a reconhecê-la imediatamente.
        """
        try:
            # Busca todos os embeddings cadastrados no banco
            self._candidates = get_all_embeddings()
            logger.info(f"Candidatos carregados: {len(self._candidates)} pessoa(s).")
        except Exception as e:
            logger.error(f"Erro ao carregar candidatos: {e}")
            self._candidates = []

    def process_frame(self, frame_bgr: np.ndarray, frame_rgb: np.ndarray) -> list:
        """
        Processa um frame completo pelo pipeline de reconhecimento.

        Este é o método principal chamado pelo CameraWorker a cada frame.

        :param frame_bgr: Frame em BGR (formato OpenCV — para salvar em disco)
        :param frame_rgb: Frame em RGB (formato InsightFace — para detectar rostos)
        :return:          Lista de resultados, um por rosto detectado no frame
        """

        resultados = []

        # ── 1. Detecta rostos no frame ─────────────────────────────────────

        detection = self.detector.process_frame(frame_bgr, frame_rgb)

        # Se não há rostos, retorna lista vazia
        if not detection["has_faces"]:
            return resultados

        logger.info(f"{len(detection['faces'])} rosto(s) detectado(s).")

        # ── 2. Processa cada rosto detectado ───────────────────────────────

        for i, face in enumerate(detection["faces"]):

            # Obtém o recorte do rosto (imagem BGR com apenas o rosto)
            crop = detection["crops"][i]

            # ── 3. Gera o embedding do rosto ───────────────────────────────

            embedding = self.embedder.get_embedding(face)

            # Pula rostos com embedding inválido
            if not self.embedder.is_valid(embedding):
                logger.warning(f"Embedding inválido para rosto {i}. Pulando.")
                continue

            # ── 4. Compara com o banco de dados ────────────────────────────

            match = self.matcher.match(embedding, self._candidates)

            # Gera timestamp para nomear arquivos e registrar o evento
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

            # ── 5. Trata o resultado ───────────────────────────────────────

            if match.matched:
                resultado = self._handle_recognized(match, crop, timestamp)
            else:
                resultado = self._handle_unknown(crop, timestamp, match.similarity)

            resultados.append(resultado)

        return resultados

    def _handle_recognized(self, match, crop: np.ndarray, timestamp: str) -> dict:
        """
        Trata um rosto reconhecido:
        - Salva a foto em data/snapshots/
        - Registra o acesso no banco (access_logs)
        - Dispara o callback on_recognized para o frontend

        :param match:     Resultado do FaceMatcher com dados da pessoa
        :param crop:      Imagem recortada do rosto (BGR)
        :param timestamp: Timestamp do evento
        :return:          Dicionário com os dados do reconhecimento
        """

        logger.info(
            f"✅ Reconhecido: {match.person_name} "
            f"(ID: {match.person_id}, Similaridade: {match.similarity:.0%})"
        )

        # Salva a foto do rosto identificado em disco
        filename = f"{match.person_id}_{match.person_name}_{timestamp}.jpg"
        image_path = self.snapshot.save(crop, filename)

        # Salva o log de acesso no banco de dados
        try:
            save_access_log(
                person_id=match.person_id,
                similarity=match.similarity,
                image_path=image_path
            )
        except Exception as e:
            logger.error(f"Erro ao salvar log de acesso: {e}")

        # Monta o resultado do reconhecimento
        resultado = {
            "status":      "recognized",
            "person_id":   match.person_id,
            "person_name": match.person_name,
            "similarity":  match.similarity,
            "image_path":  image_path,
            "timestamp":   timestamp,
        }

        # Dispara o callback para o frontend (se configurado)
        # O frontend usa isso para atualizar a interface em tempo real
        if self.on_recognized:
            self.on_recognized(resultado)

        return resultado

    def _handle_unknown(self, crop: np.ndarray, timestamp: str, similarity: float) -> dict:
        """
        Trata um rosto desconhecido:
        - Salva a foto em data/raw/camera_frames/
        - Dispara o callback on_unknown para o frontend

        :param crop:       Imagem recortada do rosto (BGR)
        :param timestamp:  Timestamp do evento
        :param similarity: Maior similaridade encontrada (abaixo do limiar)
        :return:           Dicionário com os dados do evento
        """

        logger.info(f"❓ Rosto desconhecido (similaridade: {similarity:.0%})")

        # Salva a foto do rosto desconhecido em disco para análise posterior
        filename = f"unknown_{timestamp}.jpg"
        image_path = self.snapshot_unknown.save(crop, filename)

        # Monta o resultado
        resultado = {
            "status":     "unknown",
            "similarity": similarity,
            "image_path": image_path,
            "timestamp":  timestamp,
        }

        # Dispara o callback para o frontend (se configurado)
        if self.on_unknown:
            self.on_unknown(resultado)

        return resultado

    def get_candidates_count(self) -> int:
        """
        Retorna o número de candidatos carregados do banco.
        Útil para verificar se o sistema tem pessoas cadastradas.
        """
        return len(self._candidates)