"""
engine.py

Responsabilidade: Carregar os modelos InsightFace (detector + embedder)
UMA ÚNICA VEZ e compartilhá-los entre todos os serviços do sistema.

Antes, PersonService, RecognitionService e CameraWorker criavam cada um
sua própria instância do FaceDetector — carregando o modelo buffalo_l
(~500MB) várias vezes na memória. Este módulo centraliza isso em
instâncias únicas (singletons), criadas sob demanda na primeira chamada.

Como o modelo passa a ser compartilhado entre threads (a câmera roda em
background e o cadastro roda na thread da requisição HTTP), o acesso à
INFERÊNCIA é serializado por um lock (infer_lock). Sem isso, duas threads
poderiam chamar o modelo ao mesmo tempo e gerar resultados corrompidos,
já que a inferência do InsightFace não é garantidamente thread-safe.

Uso:
    from app.face.engine import get_detector, get_embedder, infer_lock

    detector = get_detector()
    embedder = get_embedder()

    with infer_lock:                       # serializa o acesso ao modelo
        result = detector.process_frame(frame_bgr, frame_rgb)
"""

import threading

from app.face.detector import FaceDetector
from app.face.embedder import FaceEmbedder

# Instâncias compartilhadas — começam como None e são criadas no primeiro uso
_detector: FaceDetector = None
_embedder: FaceEmbedder = None

# Lock usado apenas durante a criação das instâncias (dupla checagem)
_init_lock = threading.Lock()

# Lock público para serializar a inferência do modelo entre threads.
# Quem for chamar detector.process_frame()/detect() deve fazê-lo dentro de:
#     with infer_lock:
#         ...
infer_lock = threading.Lock()


def get_detector(model_root: str = "models/insightface") -> FaceDetector:
    """
    Retorna a instância única do FaceDetector, criando-a na primeira chamada.

    :param model_root: Pasta dos modelos InsightFace (usado só na criação)
    :return:           Instância compartilhada do FaceDetector
    """
    global _detector
    if _detector is None:
        with _init_lock:
            # Dupla checagem: outra thread pode ter criado enquanto esperávamos o lock
            if _detector is None:
                _detector = FaceDetector(model_root=model_root)
    return _detector


def get_embedder() -> FaceEmbedder:
    """
    Retorna a instância única do FaceEmbedder, criando-a na primeira chamada.

    :return: Instância compartilhada do FaceEmbedder
    """
    global _embedder
    if _embedder is None:
        with _init_lock:
            if _embedder is None:
                _embedder = FaceEmbedder()
    return _embedder