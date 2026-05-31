"""
detector.py

Responsabilidade: Detectar rostos em frames usando InsightFace,
e recortar (crop) a região do rosto usando OpenCV.

Este módulo recebe um frame do FrameReader e:
1. Passa o frame pelo modelo InsightFace para detectar rostos
2. Para cada rosto encontrado, recorta a região com OpenCV
3. Retorna os recortes para o embedder gerar os vetores de reconhecimento

Fluxo:
    FrameReader → entrega frame_rgb
    FaceDetector (este arquivo) → detecta e recorta rostos
    Embedder (face/embedder.py) → gera embedding de cada rosto recortado
"""

import cv2          # OpenCV — para recortar e salvar a região do rosto
import numpy as np  # NumPy — manipulação dos arrays de pixels
import insightface  # InsightFace — modelo de detecção de rostos
from insightface.app import FaceAnalysis  # Interface principal do InsightFace


class FaceDetector:
    """
    Detecta rostos em frames de vídeo usando InsightFace (modelo RetinaFace).

    O InsightFace analisa o frame inteiro e retorna a posição (bounding box)
    de cada rosto encontrado. O OpenCV então recorta essa região.
    """

    def __init__(self, model_root: str = "models/insightface", min_confidence: float = 0.5):
        """
        Inicializa o detector carregando o modelo InsightFace.

        :param model_root:      Pasta onde os modelos serão baixados/lidos
                                (padrão: models/insightface/ do projeto)
        :param min_confidence:  Confiança mínima para considerar um rosto válido
                                (0.0 a 1.0 — padrão: 0.5 = 50%)
        """

        self.min_confidence = min_confidence  # Guarda o limiar de confiança

        # Inicializa o FaceAnalysis do InsightFace
        # - name="buffalo_l": modelo padrão do InsightFace (detecção + embedding)
        # - root: onde os modelos ficam salvos (pasta do projeto)
        self.app = FaceAnalysis(
            name="buffalo_l",
            root=model_root
        )

        # Prepara o modelo para rodar na CPU
        # - ctx_id=0: usa a primeira GPU se disponível; -1 força CPU
        # - det_size: tamanho da imagem de entrada para detecção (640x640 é o padrão)
        self.app.prepare(ctx_id=0, det_size=(640, 640))

    def detect(self, frame_rgb: np.ndarray) -> list:
        """
        Detecta todos os rostos presentes no frame.

        :param frame_rgb: Frame em formato RGB (array NumPy — saída do FrameReader)
        :return: Lista de objetos Face do InsightFace, cada um contendo:
                 - .bbox: coordenadas do rosto [x1, y1, x2, y2]
                 - .det_score: confiança da detecção (0.0 a 1.0)
                 - .embedding: vetor de 512 dimensões do rosto (se modelo completo)
                 - .kps: keypoints (olhos, nariz, boca)
        """

        # Passa o frame pelo modelo InsightFace
        # O modelo retorna uma lista de objetos Face, um por rosto encontrado
        faces = self.app.get(frame_rgb)

        # Filtra apenas os rostos com confiança acima do mínimo configurado
        # Evita falsos positivos (objetos detectados como rosto por engano)
        faces_filtradas = [
            face for face in faces
            if face.det_score >= self.min_confidence
        ]

        return faces_filtradas

    def crop_face(self, frame_bgr: np.ndarray, face) -> np.ndarray:
        """
        Recorta a região do rosto no frame original usando OpenCV.

        Usamos o frame_bgr (formato OpenCV) para salvar corretamente em disco.

        :param frame_bgr: Frame original em BGR (saída do FrameReader)
        :param face:      Objeto Face do InsightFace com as coordenadas do rosto
        :return:          Imagem recortada contendo apenas o rosto (array NumPy BGR)
        """

        # Extrai as coordenadas da bounding box do rosto
        # bbox = [x1, y1, x2, y2] — canto superior esquerdo e inferior direito
        x1, y1, x2, y2 = face.bbox.astype(int)

        # Garante que as coordenadas não saiam dos limites da imagem
        # (pode acontecer quando o rosto está na borda do frame)
        height, width = frame_bgr.shape[:2]  # Dimensões do frame
        x1 = max(0, x1)   # Não pode ser menor que 0
        y1 = max(0, y1)   # Não pode ser menor que 0
        x2 = min(width, x2)    # Não pode ultrapassar a largura
        y2 = min(height, y2)   # Não pode ultrapassar a altura

        # Recorta a região do rosto usando slicing NumPy (via OpenCV)
        # frame[y1:y2, x1:x2] → recorta linhas de y1 a y2 e colunas de x1 a x2
        face_crop = frame_bgr[y1:y2, x1:x2]

        return face_crop

    def draw_boxes(self, frame_bgr: np.ndarray, faces: list) -> np.ndarray:
        """
        Desenha retângulos ao redor dos rostos detectados no frame.
        Útil para debug e visualização em tempo real.

        :param frame_bgr: Frame original em BGR
        :param faces:     Lista de rostos detectados pelo InsightFace
        :return:          Frame com os retângulos desenhados
        """

        # Copia o frame para não modificar o original
        frame_debug = frame_bgr.copy()

        for face in faces:
            # Extrai as coordenadas da bounding box
            x1, y1, x2, y2 = face.bbox.astype(int)

            # Desenha o retângulo ao redor do rosto
            # - cor: (0, 255, 0) = verde no formato BGR
            # - espessura: 2 pixels
            cv2.rectangle(frame_debug, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Exibe a confiança da detecção acima do retângulo
            confidence_text = f"{face.det_score:.2f}"  # Ex: "0.98"
            cv2.putText(
                frame_debug,
                confidence_text,
                (x1, y1 - 10),           # Posição: acima do retângulo
                cv2.FONT_HERSHEY_SIMPLEX, # Fonte padrão do OpenCV
                0.6,                      # Tamanho da fonte
                (0, 255, 0),              # Cor: verde
                2                         # Espessura do texto
            )

        return frame_debug

    def process_frame(self, frame_bgr: np.ndarray, frame_rgb: np.ndarray) -> dict:
        """
        Processa um frame completo: detecta rostos e recorta cada um.

        Este é o método principal que o CameraWorker vai chamar.

        :param frame_bgr: Frame em BGR (para salvar e desenhar)
        :param frame_rgb: Frame em RGB (para o InsightFace detectar)
        :return: Dicionário com:
                 - "faces": lista de objetos Face do InsightFace
                 - "crops": lista de imagens recortadas (uma por rosto)
                 - "frame_debug": frame com retângulos desenhados
                 - "has_faces": True se encontrou ao menos um rosto
        """

        # Detecta os rostos no frame RGB
        faces = self.detect(frame_rgb)

        # Recorta cada rosto encontrado usando o frame BGR
        crops = [self.crop_face(frame_bgr, face) for face in faces]

        # Desenha os retângulos no frame para visualização
        frame_debug = self.draw_boxes(frame_bgr, faces)

        return {
            "faces": faces,               # Objetos Face com bbox, score, embedding
            "crops": crops,               # Imagens recortadas de cada rosto
            "frame_debug": frame_debug,   # Frame com retângulos (para exibir/debug)
            "has_faces": len(faces) > 0,  # True se encontrou ao menos um rosto
        }