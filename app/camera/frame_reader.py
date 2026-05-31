"""
frame_reader.py

Responsabilidade: Capturar frames contínuos de uma câmera (IP ou local) usando OpenCV.

Este módulo é a "porta de entrada" do vídeo no sistema. Ele abre a conexão
com a câmera e disponibiliza frames individuais para o restante do pipeline.

Fluxo:
    FrameReader (este arquivo)
        → captura o frame bruto da câmera
        → entrega para o FaceDetector (face/detector.py)
        → que decide se salva ou descarta
"""

import cv2  # OpenCV — biblioteca de visão computacional


class FrameReader:
    """
    Abre a conexão com a câmera e lê frames um a um via OpenCV.

    Funciona tanto com câmera local (índice 0) quanto câmera IP (URL RTSP).
    """

    def __init__(self, source):
        """
        Inicializa a conexão com a câmera.

        :param source: Índice da câmera local (ex: 0) ou URL RTSP da câmera IP
                       Exemplos:
                           0                              → câmera do Mac
                           "rtsp://admin:senha@192.168.1.100:554/stream" → câmera IP
        """

        # Abre o stream de vídeo — funciona para câmera local e câmera IP
        self.cap = cv2.VideoCapture(source)

        # Guarda a fonte para uso em logs
        self.source = source

        # Reduz o buffer interno para 1 frame, minimizando o delay do stream
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def is_opened(self) -> bool:
        """
        Verifica se a câmera foi aberta com sucesso.

        :return: True se a câmera está acessível, False caso contrário
        """
        return self.cap.isOpened()

    def get_info(self) -> dict:
        """
        Retorna informações técnicas do stream capturado pelo OpenCV.
        Útil para debug e logs.

        :return: Dicionário com largura, altura e FPS da câmera
        """
        return {
            # Largura do frame em pixels
            "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),

            # Altura do frame em pixels
            "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),

            # Frames por segundo configurados na câmera
            "fps": self.cap.get(cv2.CAP_PROP_FPS),
        }

    def read_frame(self):
        """
        Lê e retorna o próximo frame do stream de vídeo.

        O OpenCV retorna os frames no formato BGR (Blue, Green, Red),
        que é diferente do RGB padrão. O InsightFace espera RGB,
        então a conversão é feita aqui antes de entregar o frame.

        :return: Tupla (frame_bgr, frame_rgb) ou (None, None) se falhar
                 - frame_bgr: frame original do OpenCV (para salvar em disco)
                 - frame_rgb: frame convertido para RGB (para o detector de rostos)
        """

        # cap.read() retorna:
        # - ret: True se o frame foi capturado com sucesso
        # - frame: array NumPy com os pixels da imagem (altura x largura x 3 canais)
        ret, frame_bgr = self.cap.read()

        # Se a leitura falhou (câmera desconectada, fim do stream, etc.)
        if not ret:
            return None, None

        # Converte BGR (padrão OpenCV) para RGB (padrão InsightFace e maioria dos modelos)
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # Retorna os dois formatos:
        # - BGR para salvar imagens corretamente com cv2.imwrite()
        # - RGB para passar ao detector de rostos
        return frame_bgr, frame_rgb

    def release(self):
        """
        Libera os recursos da câmera e encerra a conexão.
        Deve ser chamado ao finalizar o uso para evitar vazamento de recursos.
        """
        self.cap.release()  # Fecha o stream e libera memória do OpenCV

    def __repr__(self) -> str:
        """Representação legível para logs."""
        info = self.get_info()
        return f"<FrameReader source={self.source} {info['width']}x{info['height']} @ {info['fps']}fps>"