"""
camera_service.py

Responsabilidade: Gerenciar o ciclo de vida da câmera e do CameraWorker.

Mudanças desta versão:
    - Os callbacks (on_recognized/on_unknown) agora são repassados ao
      CameraWorker, que é quem realmente roda o pipeline. Antes eles iam
      para o RecognitionService, que nunca era chamado pelo worker — por
      isso o WebSocket não notificava nada.
    - Os candidatos do banco são carregados aqui (get_all_embeddings) e
      passados ao worker. Não há mais um RecognitionService duplicando o
      pipeline e carregando um segundo modelo na memória.
    - reload_candidates() agora pode ser chamado de fora (ex.: após cadastrar
      uma pessoa) para que o sistema reconheça a pessoa nova sem reiniciar.
"""

import logging
from typing import Optional, Callable

from app.workers.camera_worker import CameraWorker
from app.db.models import get_all_embeddings

logger = logging.getLogger(__name__)


class CameraService:
    """
    Gerencia o ciclo de vida da câmera e do pipeline de reconhecimento.
    Expõe métodos simples para a API iniciar e parar a câmera.
    """

    def __init__(self):
        # Worker que roda o loop de captura em background
        self._worker: Optional[CameraWorker] = None

        # Cache dos candidatos carregados do banco
        self._candidates: list = []

        logger.info("CameraService inicializado.")

    def _load_candidates(self) -> list:
        """Carrega os embeddings cadastrados do banco."""
        try:
            candidates = get_all_embeddings()
            logger.info(f"Candidatos carregados: {len(candidates)} embedding(s).")
            return candidates
        except Exception as e:
            logger.error(f"Erro ao carregar candidatos: {e}")
            return []

    def start_camera(
        self,
        source,
        on_recognized: Optional[Callable] = None,
        on_unknown: Optional[Callable] = None,
        threshold: float = 0.6,
    ) -> bool:
        """
        Inicia a câmera e o pipeline de reconhecimento em background.

        :param source:        Fonte da câmera (0 para Mac, URL RTSP para câmera IP)
        :param on_recognized: Callback disparado quando alguém é reconhecido
        :param on_unknown:    Callback disparado quando rosto desconhecido aparece
        :param threshold:     Limiar de similaridade para reconhecimento
        :return:              True se iniciou com sucesso, False caso contrário
        """
        if self.is_running:
            logger.warning("Câmera já está rodando. Ignorando a chamada.")
            return False

        logger.info(f"Iniciando câmera: {source}")

        # Carrega os cadastros do banco
        self._candidates = self._load_candidates()
        if not self._candidates:
            logger.warning("⚠️ Nenhuma pessoa cadastrada no banco. Ninguém será reconhecido.")

        # Cria e inicia o worker com os callbacks de notificação
        self._worker = CameraWorker(
            camera_source=source,
            candidates=self._candidates,
            threshold=threshold,
            on_recognized=on_recognized,
            on_unknown=on_unknown,
        )
        self._worker.start()

        if not self._worker.is_running:
            logger.error("❌ Falha ao iniciar o CameraWorker.")
            self._worker = None
            return False

        logger.info("✅ Câmera iniciada com sucesso.")
        return True

    def stop_camera(self):
        """Para a câmera e libera todos os recursos."""
        if not self.is_running:
            logger.warning("Câmera não está rodando.")
            return

        logger.info("Encerrando câmera...")
        self._worker.stop()
        self._worker = None
        logger.info("✅ Câmera encerrada.")

    def reload_candidates(self):
        """
        Recarrega os candidatos do banco sem reiniciar a câmera.
        Chamado quando uma nova pessoa é cadastrada durante o uso do sistema.
        """
        self._candidates = self._load_candidates()
        if self._worker:
            self._worker.update_candidates(self._candidates)
        logger.info("Candidatos recarregados.")

    @property
    def is_running(self) -> bool:
        """Indica se a câmera está ativa e capturando frames."""
        return self._worker is not None and self._worker.is_running

    @property
    def last_result(self) -> Optional[dict]:
        """Retorna o último resultado de reconhecimento."""
        if self._worker:
            return self._worker.get_last_result()
        return None

    def get_status(self) -> dict:
        """Retorna o status atual da câmera e do sistema."""
        return {
            "camera_running":    self.is_running,
            "candidates_loaded": len(self._candidates),
            "last_result":       self.last_result,
        }