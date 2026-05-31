"""
ip_camera.py

Responsabilidade: Representar uma câmera IP no sistema.
Este módulo encapsula as informações de conexão de uma câmera IP,
montando a URL RTSP a partir das credenciais e endereço fornecidos.
A URL gerada é usada pelo FrameReader para capturar os frames de vídeo.
"""

class IPCamera:
    """
    Classe que representa uma câmera IP.
    Recebe as credenciais e monta a URL de conexão no protocolo RTSP.
    """

    def __init__(self, ip: str, user: str, password: str, port: int = 554, stream_path: str = "stream"):
        """
        Inicializa a câmera com as informações de conexão.

        :param ip:          Endereço IP da câmera na rede (ex: 192.168.1.100)
        :param user:        Usuário de acesso à câmera (ex: admin)
        :param password:    Senha de acesso à câmera
        :param port:        Porta RTSP da câmera (padrão: 554)
        :param stream_path: Caminho do stream na câmera (padrão: stream)
        """

        # Monta a URL RTSP no formato padrão:
        # rtsp://usuario:senha@ip:porta/caminho_do_stream
        self.url = f"rtsp://{user}:{password}@{ip}:{port}/{stream_path}"

        # Guarda o IP separadamente para uso em logs e identificação
        self.ip = ip

    def get_url(self) -> str:
        """
        Retorna a URL RTSP completa para conexão com a câmera.
        """
        return self.url

    def __repr__(self) -> str:
        """
        Representação legível da câmera (oculta a senha por segurança).
        """
        # Exibe o IP mas não expõe a senha nos logs
        return f"<IPCamera ip={self.ip}>"