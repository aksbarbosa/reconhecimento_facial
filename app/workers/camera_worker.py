"""
camera_worker.py

Responsabilidade: Orquestrar o pipeline completo de reconhecimento facial
em loop contínuo, rodando em background enquanto o sistema estiver ativo.

Sistema de presença:
    - Salva no banco apenas quando a pessoa APARECE pela primeira vez
    - Ignora frames subsequentes enquanto a pessoa estiver presente
    - Só volta a salvar quando a pessoa DESAPARECER e REAPARECER
    - Usa um contador de ausência para evitar falsos saídas (piscar, virar rosto)

Fluxo:
    CameraWorker
        → FrameReader     → captura frame
        → FaceDetector    → detecta rostos
        → FaceEmbedder    → gera embeddings
        → FaceMatcher     → identifica pessoas
        → PresenceTracker → controla quem está presente
        → Snapshot        → salva foto se for nova entrada
        → save_access_log → salva no banco se for nova entrada
"""

import time
import threading
import logging
from datetime import datetime

from app.camera.frame_reader import FrameReader
from app.camera.snapshot import Snapshot
from app.face.detector import FaceDetector
from app.face.embedder import FaceEmbedder
from app.face.matcher import FaceMatcher
from app.db.models import save_access_log

logger = logging.getLogger(__name__)

# Número de frames consecutivos sem detectar a pessoa para considerá-la ausente
# Com frame_interval=0.1s, 10 frames = 1 segundo de ausência antes de resetar
FRAMES_PARA_SAIR = 10


class CameraWorker:
    """
    Orquestra o pipeline completo de reconhecimento facial em loop contínuo.
    Roda em uma thread separada (background) para não bloquear a API.

    Usa um sistema de rastreamento de presença para salvar no banco
    apenas quando uma pessoa aparece — não a cada frame detectado.
    """

    def __init__(
        self,
        camera_source,
        candidates: list,
        model_root: str = "models/insightface",
        snapshot_dir: str = "data/snapshots",
        frames_dir: str = "data/raw/camera_frames",
        threshold: float = 0.6,
        frame_interval: float = 0.1,
        save_unknown: bool = True,
    ):
        """
        Inicializa o worker com todos os módulos do pipeline.

        :param camera_source:  Índice da câmera local (0) ou URL RTSP da câmera IP
        :param candidates:     Lista de cadastros do banco para comparação
        :param model_root:     Pasta dos modelos InsightFace
        :param snapshot_dir:   Pasta para salvar snapshots de rostos identificados
        :param frames_dir:     Pasta para salvar frames de rostos desconhecidos
        :param threshold:      Limiar de similaridade para identificação (padrão: 0.6)
        :param frame_interval: Intervalo em segundos entre cada frame processado
        :param save_unknown:   Se True, salva imagens de rostos não identificados
        """

        self.camera_source  = camera_source
        self.candidates     = candidates
        self.frame_interval = frame_interval
        self.save_unknown   = save_unknown

        # Captura frames da câmera via OpenCV
        self.frame_reader = FrameReader(camera_source)

        # Detecta rostos nos frames via InsightFace
        self.detector = FaceDetector(model_root=model_root)

        # Gera embeddings (vetores) dos rostos detectados
        self.embedder = FaceEmbedder()

        # Compara embeddings com os cadastros do banco
        self.matcher = FaceMatcher(threshold=threshold)

        # Salva imagens de rostos identificados em disco
        self.snapshot = Snapshot(output_dir=snapshot_dir)

        # Salva imagens de rostos desconhecidos em disco
        self.snapshot_unknown = Snapshot(output_dir=frames_dir)

        # ── Sistema de rastreamento de presença ────────────────────────────
        #
        # Dicionário que rastreia quem está presente no momento.
        # Chave: person_id
        # Valor: número de frames consecutivos sem detectar a pessoa
        #
        # Exemplo:
        #   {1: 0}  → Filipe está presente, 0 frames sem detectar
        #   {1: 5}  → Filipe não foi detectado nos últimos 5 frames
        #   {}      → ninguém presente no momento
        self._presentes: dict = {}

        # Controle da thread
        self._running = False
        self._thread  = None

        # Último resultado de reconhecimento (para a API consultar)
        self.last_result = None

    def start(self):
        """
        Inicia o worker em uma thread de background.
        """

        if not self.frame_reader.is_opened():
            logger.error(f"Falha ao abrir a câmera: {self.camera_source}")
            return

        logger.info(f"Iniciando CameraWorker | Câmera: {self.camera_source}")
        logger.info(f"Informações da câmera: {self.frame_reader.get_info()}")

        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """
        Encerra o loop de captura e libera os recursos da câmera.
        """

        logger.info("Encerrando CameraWorker...")

        self._running = False

        if self._thread is not None:
            self._thread.join(timeout=5)

        self.frame_reader.release()
        logger.info("CameraWorker encerrado.")

    def _loop(self):
        """
        Loop principal do worker.

        A cada iteração:
            1. Captura um frame da câmera
            2. Detecta rostos no frame
            3. Para cada rosto reconhecido: verifica se é nova entrada
            4. Atualiza o rastreador de presença
            5. Aguarda o intervalo configurado
        """

        logger.info("Loop de captura iniciado.")

        while self._running:

            # ── 1. Captura o frame ─────────────────────────────────────────

            frame_bgr, frame_rgb = self.frame_reader.read_frame()

            if frame_bgr is None:
                logger.warning("Frame não capturado. Tentando novamente...")
                time.sleep(1)
                continue

            # ── 2. Detecta rostos no frame ─────────────────────────────────

            result = self.detector.process_frame(frame_bgr, frame_rgb)

            # IDs das pessoas detectadas neste frame
            # Usado para atualizar o rastreador de presença ao final
            ids_detectados_neste_frame = set()

            if result["has_faces"]:

                # ── 3. Processa cada rosto detectado ───────────────────────

                for i, face in enumerate(result["faces"]):

                    crop = result["crops"][i]

                    # Gera o embedding do rosto
                    embedding = self.embedder.get_embedding(face)

                    if embedding is None or not self.embedder.is_valid(embedding):
                        logger.warning(f"Embedding inválido para o rosto {i}. Pulando.")
                        continue

                    # Compara com o banco de dados
                    match = self.matcher.match(embedding, self.candidates)

                    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                    if match.matched:

                        # Marca esta pessoa como detectada neste frame
                        ids_detectados_neste_frame.add(match.person_id)

                        # ── Verifica se é nova entrada ─────────────────────
                        #
                        # A pessoa é considerada "nova entrada" se:
                        #   1. Não estava na lista de presentes (chegou agora)
                        #   2. Estava na lista mas o contador zerou (voltou após sair)
                        #
                        # Só salva no banco em caso de nova entrada
                        if match.person_id not in self._presentes:

                            logger.info(
                                f"🚪 Nova entrada: {match.person_name} "
                                f"(Similaridade: {match.similarity:.0%})"
                            )

                            # Salva a foto do rosto identificado
                            filename = (
                                f"{match.person_id}_{match.person_name}_"
                                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                            )
                            saved_path = self.snapshot.save(crop, filename)

                            # Salva o log no banco — só acontece na entrada
                            try:
                                save_access_log(
                                    person_id=match.person_id,
                                    similarity=match.similarity,
                                    image_path=saved_path
                                )
                            except Exception as e:
                                logger.error(f"Erro ao salvar log: {e}")

                            # Adiciona à lista de presentes com contador zerado
                            # 0 = acabou de ser detectado, nenhum frame de ausência
                            self._presentes[match.person_id] = 0

                        else:
                            # Pessoa já estava presente — reseta o contador de ausência
                            # pois foi detectada neste frame
                            self._presentes[match.person_id] = 0
                            logger.debug(f"👤 Presente: {match.person_name}")

                        # Atualiza o último resultado para a API
                        self.last_result = {
                            "matched":     match.matched,
                            "person_id":   match.person_id,
                            "person_name": match.person_name,
                            "similarity":  match.similarity,
                            "timestamp":   timestamp,
                        }

                    else:
                        # Rosto desconhecido
                        logger.info(f"❓ Desconhecido (similaridade: {match.similarity:.0%})")

                        if self.save_unknown:
                            filename = f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
                            self.snapshot_unknown.save(crop, filename)

            # ── 4. Atualiza o rastreador de presença ───────────────────────
            #
            # Para cada pessoa que estava presente mas NÃO foi detectada
            # neste frame, incrementa o contador de ausência.
            # Quando o contador atingir FRAMES_PARA_SAIR, remove da lista.

            for person_id in list(self._presentes.keys()):

                if person_id not in ids_detectados_neste_frame:

                    # Incrementa o contador de frames sem detectar esta pessoa
                    self._presentes[person_id] += 1

                    if self._presentes[person_id] >= FRAMES_PARA_SAIR:
                        # Pessoa ausente por frames suficientes — considera que saiu
                        logger.info(
                            f"🚶 Saiu do campo: pessoa ID {person_id} "
                            f"(ausente por {FRAMES_PARA_SAIR} frames)"
                        )
                        # Remove da lista — próxima detecção será nova entrada
                        del self._presentes[person_id]

            # ── 5. Aguarda antes do próximo frame ──────────────────────────

            time.sleep(self.frame_interval)

        logger.info("Loop de captura encerrado.")

    def get_last_result(self) -> dict:
        """Retorna o último resultado de reconhecimento."""
        return self.last_result

    def update_candidates(self, new_candidates: list):
        """
        Atualiza a lista de candidatos sem reiniciar o worker.
        Chamado quando uma nova pessoa é cadastrada durante o uso.
        """
        self.candidates = new_candidates
        logger.info(f"Candidatos atualizados: {len(new_candidates)} pessoa(s).")

    @property
    def is_running(self) -> bool:
        """Indica se o worker está ativo e capturando frames."""
        return self._running