"""
snapshot.py

Responsabilidade: Salvar um frame capturado como imagem em disco.
Este módulo recebe um frame (array NumPy do OpenCV) e o persiste
no diretório de snapshots (data/snapshots/), permitindo auditoria,
debug ou uso posterior no pipeline de reconhecimento facial.

Fluxo:
  FrameReader → captura o frame
  Snapshot (este arquivo) → salva o frame em disco como imagem .jpg
"""

import cv2      # OpenCV para salvar a imagem em disco
import os       # Para verificar e criar diretórios automaticamente


class Snapshot:
    """
    Responsável por persistir frames de vídeo como arquivos de imagem.
    Usado para debug, auditoria ou para alimentar o pipeline de cadastro facial.
    """

    def __init__(self, output_dir: str = "data/snapshots"):
        """
        Inicializa o Snapshot com o diretório onde as imagens serão salvas.

        :param output_dir: Caminho da pasta de destino (padrão: data/snapshots)
        """

        # Guarda o diretório de destino para uso no método save()
        self.output_dir = output_dir

        # Cria o diretório caso ele não exista ainda
        # exist_ok=True evita erro se a pasta já existir
        os.makedirs(self.output_dir, exist_ok=True)

    def save(self, frame, filename: str) -> str:
        """
        Salva um frame como arquivo de imagem no diretório configurado.

        :param frame:    Frame capturado (array NumPy BGR do OpenCV)
        :param filename: Nome do arquivo (ex: "snapshot_001.jpg")
        :return:         Caminho completo do arquivo salvo
        """

        # Monta o caminho completo do arquivo: pasta + nome do arquivo
        filepath = os.path.join(self.output_dir, filename)

        # cv2.imwrite() salva o array NumPy como imagem no disco
        # Suporta .jpg, .png, .bmp, etc. (detectado pela extensão do filename)
        success = cv2.imwrite(filepath, frame)

        # Se a escrita falhou (disco cheio, permissão negada, etc.), lança erro
        if not success:
            raise IOError(f"Falha ao salvar snapshot em: {filepath}")

        # Retorna o caminho do arquivo salvo (útil para logar ou referenciar depois)
        return filepath
