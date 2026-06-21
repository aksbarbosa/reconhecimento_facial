"""
camera_worker.py

Responsabilidade: Orquestrar o pipeline de reconhecimento em loop contínuo,
em background, decidindo o acesso de cada aluno pelo horário da turma dele.

Recursos:
    - Modelo compartilhado (app.face.engine) com infer_lock.
    - Callbacks on_recognized / on_unknown (notificação WebSocket).
    - Decisão de acesso por janela de horário (app.utils.shifts.evaluate_access),
      usando inicio/fim que vêm de aluno → turma → horario.

Decisões exibidas/registradas:
    - rosto não reconhecido          → "Rosto não cadastrado"            (negado)
    - reconhecido, sem turma/horário → "Reconhecido, mas sem turma/horário definido" (negado)
    - reconhecido, fora do horário   → "Reconhecido, mas horário não permitido" (negado)
    - reconhecido, dentro do horário → "Acesso liberado"                (liberado)
"""

import time
import threading
import logging
from datetime import datetime
from typing import Callable, Optional

from app.camera.frame_reader import FrameReader
from app.camera.snapshot import Snapshot
from app.face.matcher import FaceMatcher
from app.face.engine import get_detector, get_embedder, infer_lock
from app.utils.shifts import evaluate_access
from app.db.models import save_access_log
from app.services.notify_service import notify_recognition

logger = logging.getLogger(__name__)

# Frames consecutivos sem detectar o aluno para considerá-lo ausente
FRAMES_PARA_SAIR = 10


class CameraWorker:
    """Pipeline de reconhecimento em thread de background, com acesso por horário."""

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
        on_recognized: Optional[Callable] = None,
        on_unknown: Optional[Callable] = None,
    ):
        self.camera_source  = camera_source
        self.candidates     = candidates
        self.frame_interval = frame_interval
        self.save_unknown   = save_unknown

        self.on_recognized = on_recognized
        self.on_unknown    = on_unknown

        self.frame_reader = FrameReader(camera_source)

        # Modelo compartilhado (carregado uma única vez no engine)
        self.detector = get_detector(model_root=model_root)
        self.embedder = get_embedder()
        self.matcher  = FaceMatcher(threshold=threshold)

        self.snapshot = Snapshot(output_dir=snapshot_dir)
        self.snapshot_unknown = Snapshot(output_dir=frames_dir)

        # Mapa aluno_id → dados de acesso (janela de horário + nomes),
        # montado a partir dos candidatos. Evita carregar o turno no MatchResult.
        self._info_by_aluno = self._build_info_map(candidates)

        # Rastreamento de presença: aluno_id → frames sem detecção
        self._presentes: dict = {}

        self._running = False
        self._thread  = None
        self.last_result = None

    @staticmethod
    def _build_info_map(candidates: list) -> dict:
        """Monta {aluno_id: {inicio, fim, turma_nome, horario_nome, supabase_dependent_id}}."""
        info = {}
        for c in candidates:
            info[c["aluno_id"]] = {
                "inicio":                c.get("inicio"),
                "fim":                   c.get("fim"),
                "turma_nome":            c.get("turma_nome"),
                "horario_nome":          c.get("horario_nome"),
                "supabase_dependent_id": c.get("supabase_dependent_id"),
            }
        return info

    def start(self):
        """Inicia o worker em uma thread de background."""
        if not self.frame_reader.is_opened():
            logger.error(f"Falha ao abrir a câmera: {self.camera_source}")
            return

        logger.info(f"Iniciando CameraWorker | Câmera: {self.camera_source}")
        logger.info(f"Informações da câmera: {self.frame_reader.get_info()}")

        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Encerra o loop de captura e libera os recursos da câmera."""
        logger.info("Encerrando CameraWorker...")
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
        self.frame_reader.release()
        logger.info("CameraWorker encerrado.")

    def _loop(self):
        """Loop principal do worker."""
        logger.info("Loop de captura iniciado.")

        while self._running:

            frame_bgr, frame_rgb = self.frame_reader.read_frame()
            if frame_bgr is None:
                logger.warning("Frame não capturado. Tentando novamente...")
                time.sleep(1)
                continue

            with infer_lock:
                result = self.detector.process_frame(frame_bgr, frame_rgb)

            ids_detectados_neste_frame = set()

            if result["has_faces"]:

                for i, face in enumerate(result["faces"]):
                    crop = result["crops"][i]

                    embedding = self.embedder.get_embedding(face)
                    if embedding is None or not self.embedder.is_valid(embedding):
                        logger.warning(f"Embedding inválido para o rosto {i}. Pulando.")
                        continue

                    match = self.matcher.match(embedding, self.candidates)
                    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                    # ── Decide o acesso pela janela de horário da turma ────
                    info = self._info_by_aluno.get(match.aluno_id, {}) if match.matched else {}
                    inicio = info.get("inicio")
                    fim    = info.get("fim")
                    access = evaluate_access(match.matched, inicio, fim)

                    resultado = {
                        "matched":                match.matched,
                        "aluno_id":               match.aluno_id,
                        "aluno_nome":             match.aluno_nome,
                        "supabase_dependent_id":  info.get("supabase_dependent_id"),
                        "turma_nome":             info.get("turma_nome"),
                        "horario_nome":           info.get("horario_nome"),
                        "similarity":             match.similarity,
                        "status":                 access["status"],
                        "access_granted":         access["access_granted"],
                        "message":                access["message"],
                        "timestamp":              timestamp,
                    }

                    # A tela ao vivo sempre mostra o rosto mais recente
                    self.last_result = resultado

                    if match.matched:
                        ids_detectados_neste_frame.add(match.aluno_id)

                        # Loga/notifica só na NOVA entrada
                        if match.aluno_id not in self._presentes:
                            estado = "LIBERADO" if access["access_granted"] else "NEGADO"
                            logger.info(
                                f"🚪 Nova entrada: {match.aluno_nome} | {estado} "
                                f"({access['message']}, sim: {match.similarity:.0%})"
                            )

                            filename = (
                                f"{match.aluno_id}_{match.aluno_nome}_"
                                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                            )
                            saved_path = self.snapshot.save(crop, filename)
                            resultado["image_path"] = saved_path

                            try:
                                save_access_log(
                                    aluno_id=match.aluno_id,
                                    similarity=match.similarity,
                                    access_granted=access["access_granted"],
                                    image_path=saved_path,
                                )
                            except Exception as e:
                                logger.error(f"Erro ao salvar log: {e}")

                            notify_recognition(resultado)

                            self._presentes[match.aluno_id] = 0
                            self._fire(self.on_recognized, resultado)
                        else:
                            self._presentes[match.aluno_id] = 0
                            logger.debug(f"👤 Presente: {match.aluno_nome}")

                    else:
                        logger.info(f"❓ Desconhecido (similaridade: {match.similarity:.0%})")
                        saved_path = None
                        if self.save_unknown:
                            filename = f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
                            saved_path = self.snapshot_unknown.save(crop, filename)
                        resultado["image_path"] = saved_path
                        self._fire(self.on_unknown, resultado)

            # ── Atualiza o rastreador de presença ──────────────────────────
            for aluno_id in list(self._presentes.keys()):
                if aluno_id not in ids_detectados_neste_frame:
                    self._presentes[aluno_id] += 1
                    if self._presentes[aluno_id] >= FRAMES_PARA_SAIR:
                        logger.info(f"🚶 Saiu do campo: aluno ID {aluno_id}")
                        del self._presentes[aluno_id]

            time.sleep(self.frame_interval)

        logger.info("Loop de captura encerrado.")

    @staticmethod
    def _fire(callback: Optional[Callable], payload: dict):
        """Dispara um callback com proteção contra exceções."""
        if callback is None:
            return
        try:
            callback(payload)
        except Exception as e:
            logger.error(f"Erro ao disparar callback de notificação: {e}")

    def get_last_result(self) -> dict:
        """Retorna o último resultado de reconhecimento."""
        return self.last_result

    def update_candidates(self, new_candidates: list):
        """Atualiza candidatos e o mapa de horários sem reiniciar o worker."""
        self.candidates = new_candidates
        self._info_by_aluno = self._build_info_map(new_candidates)
        logger.info(f"Candidatos atualizados: {len(new_candidates)} aluno(s).")

    @property
    def is_running(self) -> bool:
        """Indica se o worker está ativo e capturando frames."""
        return self._running