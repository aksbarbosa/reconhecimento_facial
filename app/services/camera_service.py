"""
camera_service.py

Responsabilidade: Gerenciar o ciclo de vida da câmera e do CameraWorker.

Este serviço controla quando a câmera é ligada e desligada,
e conecta o CameraWorker ao RecognitionService para que o
reconhecimento aconteça automaticamente em background.

Fluxo:
    API chama start_camera()
        → CameraService inicia o CameraWorker
        → CameraWorker captura frames em background
        → Cada frame vai para o RecognitionService
        → RecognitionService identifica e salva logs
"""

import logging                                          # Logs do sistema
from typing import Optional, Callable                  # Tipagem

from app.camera.frame_reader import FrameReader        # Captura frames
from app.workers.camera_worker import CameraWorker     # Loop em background
from app.services.recognition_service import RecognitionService  # Reconhecimento

# Configura o logger para este módulo
logger = logging.getLogger(__name__)


class CameraService:
    """
    Gerencia o ciclo de vida da câmera e do pipeline de reconhecimento.

    Expõe métodos simples para a API iniciar e parar a câmera,
    sem que a API precise conhecer os detalhes do CameraWorker.
    """

    def __init__(self):
        """
        Inicializa o serviço sem iniciar a câmera.
        A câmera só é iniciada quando start_camera() for chamado.
        """

        # Worker que roda o loop de captura em background
        # Começa como None — só é criado quando a câmera for iniciada
        self._worker: Optional[CameraWorker] = None

        # Serviço de reconhecimento — processa cada frame capturado
        self._recognition: Optional[RecognitionService] = None

        logger.info("CameraService inicializado.")

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

        # Verifica se a câmera já está rodando
        if self.is_running:
            logger.warning("Câmera já está rodando. Ignore a chamada.")
            return False

        logger.info(f"Iniciando câmera: {source}")

        # ── Inicializa o RecognitionService com os callbacks ───────────────

        # Os callbacks são funções passadas pelo frontend via WebSocket
        # Quando o reconhecimento acontece, o frontend é notificado
        self._recognition = RecognitionService(
            threshold=threshold,
            on_recognized=on_recognized,
            on_unknown=on_unknown,
        )

        # Verifica se há pessoas cadastradas antes de iniciar
        if self._recognition.get_candidates_count() == 0:
            logger.warning("⚠️ Nenhuma pessoa cadastrada no banco. O sistema não reconhecerá ninguém.")

        # ── Inicializa o CameraWorker ──────────────────────────────────────

        # O CameraWorker recebe o RecognitionService como processador de frames
        # A cada frame capturado, chama recognition_service.process_frame()
        self._worker = CameraWorker(
            camera_source=source,
            candidates=self._recognition._candidates,
            threshold=threshold,
        )

        # Substitui o processamento padrão do worker pelo RecognitionService
        # O worker vai chamar process_frame() do RecognitionService em vez do próprio
        self._worker._recognition_service = self._recognition

        # Inicia o worker em background (thread separada)
        self._worker.start()

        if not self._worker.is_running:
            logger.error("❌ Falha ao iniciar o CameraWorker.")
            return False

        logger.info("✅ Câmera iniciada com sucesso.")
        return True

    def stop_camera(self):
        """
        Para a câmera e encerra o pipeline de reconhecimento.
        Libera todos os recursos (câmera, memória, thread).
        """

        if not self.is_running:
            logger.warning("Câmera não está rodando.")
            return

        logger.info("Encerrando câmera...")

        # Para o worker — encerra a thread e libera a câmera
        self._worker.stop()
        self._worker = None
        self._recognition = None

        logger.info("✅ Câmera encerrada.")

    def reload_candidates(self):
        """
        Recarrega os candidatos do banco sem reiniciar a câmera.
        Chamado quando uma nova pessoa é cadastrada durante o uso do sistema.
        """

        if self._recognition:
            self._recognition.reload_candidates()

            # Atualiza também a lista do worker
            if self._worker:
                self._worker.update_candidates(self._recognition._candidates)

            logger.info("Candidatos recarregados.")

    @property
    def is_running(self) -> bool:
        """
        Indica se a câmera está ativa e capturando frames.

        :return: True se o worker está rodando, False caso contrário
        """
        return self._worker is not None and self._worker.is_running

    @property
    def last_result(self) -> Optional[dict]:
        """
        Retorna o último resultado de reconhecimento.
        Usado pela API para consultar o estado mais recente.

        :return: Dicionário com o último reconhecimento ou None
        """
        if self._worker:
            return self._worker.get_last_result()
        return None

    def get_status(self) -> dict:
        """
        Retorna o status atual da câmera e do sistema.
        Usado pelo endpoint /health da API.

        :return: Dicionário com informações do estado atual
        """
        return {
            "camera_running":    self.is_running,
            "candidates_loaded": self._recognition.get_candidates_count() if self._recognition else 0,
            "last_result":       self.last_result,
        }