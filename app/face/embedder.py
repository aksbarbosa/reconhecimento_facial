"""
embedder.py

Responsabilidade: Gerar embeddings (vetores numéricos) de rostos detectados.

Um embedding é uma representação matemática do rosto — um vetor de 512 números
que captura as características únicas de cada pessoa (distância entre olhos,
formato do nariz, contorno do rosto, etc).

Rostos da mesma pessoa geram vetores parecidos.
Rostos de pessoas diferentes geram vetores distantes.

Esse vetor é o que o Matcher (face/matcher.py) vai comparar com o banco de dados
para identificar quem é a pessoa.

Fluxo:
    FaceDetector (face/detector.py)
        → entrega o objeto Face com rosto detectado
    FaceEmbedder (este arquivo)
        → extrai o vetor de 512 dimensões do rosto
    Matcher (face/matcher.py)
        → compara o vetor com os cadastrados no banco
"""

import numpy as np  # NumPy — manipulação dos vetores numéricos


class FaceEmbedder:
    """
    Extrai embeddings de rostos usando o modelo InsightFace.

    O InsightFace já calcula o embedding automaticamente durante a detecção
    (quando usamos o modelo buffalo_l no detector). Este módulo organiza
    e normaliza esses vetores para uso no Matcher.
    """

    def __init__(self, embedding_size: int = 512):
        """
        Inicializa o embedder.

        :param embedding_size: Tamanho do vetor gerado pelo modelo
                               (512 é o padrão do InsightFace buffalo_l)
        """

        # Tamanho esperado do vetor de embedding
        self.embedding_size = embedding_size

    def get_embedding(self, face) -> np.ndarray:
        """
        Extrai o embedding de um rosto já detectado pelo InsightFace.

        O InsightFace calcula o embedding durante a detecção e o armazena
        no atributo .embedding do objeto Face. Este método acessa esse vetor
        e o normaliza para garantir comparações precisas.

        :param face:   Objeto Face do InsightFace (saída do FaceDetector)
        :return:       Vetor normalizado de 512 dimensões (array NumPy float32)
                       ou None se o embedding não estiver disponível
        """

        # Verifica se o InsightFace gerou o embedding durante a detecção
        # (pode não estar disponível se o modelo usado for apenas de detecção)
        if face.embedding is None:
            return None

        # Obtém o vetor de embedding gerado pelo InsightFace
        embedding = face.embedding  # Array NumPy de 512 floats

        # Normaliza o vetor para comprimento 1 (norma L2)
        # Isso garante que a comparação entre vetores seja baseada
        # apenas na direção (características do rosto), não na magnitude
        embedding = self._normalize(embedding)

        return embedding

    def get_embeddings_batch(self, faces: list) -> list:
        """
        Extrai embeddings de uma lista de rostos de uma vez.
        Útil quando há múltiplos rostos no mesmo frame.

        :param faces: Lista de objetos Face do InsightFace
        :return:      Lista de vetores normalizados (None para rostos sem embedding)
        """

        # Processa cada rosto da lista individualmente
        embeddings = [self.get_embedding(face) for face in faces]

        return embeddings

    def _normalize(self, embedding: np.ndarray) -> np.ndarray:
        """
        Normaliza o vetor de embedding para comprimento 1 (norma L2).

        Vetores normalizados permitem usar similaridade por cosseno,
        que é mais precisa para comparação de rostos do que distância euclidiana.

        :param embedding: Vetor bruto do InsightFace
        :return:          Vetor normalizado com comprimento 1
        """

        # Calcula a norma L2 do vetor (raiz da soma dos quadrados)
        norma = np.linalg.norm(embedding)

        # Evita divisão por zero (caso improvável de vetor nulo)
        if norma == 0:
            return embedding

        # Divide cada elemento pela norma, resultando em vetor de comprimento 1
        return embedding / norma

    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calcula a similaridade entre dois embeddings usando cosseno.

        Resultado:
            1.0  → rostos idênticos (mesma pessoa, mesma foto)
            > 0.6 → provavelmente a mesma pessoa
            < 0.4 → pessoas diferentes

        :param embedding1: Vetor do rosto capturado pela câmera
        :param embedding2: Vetor do rosto cadastrado no banco
        :return:           Similaridade entre 0.0 e 1.0
        """

        # Similaridade por cosseno = produto escalar de dois vetores normalizados
        # Como ambos já estão normalizados, basta o produto escalar (dot product)
        return float(np.dot(embedding1, embedding2))

    def is_valid(self, embedding) -> bool:
        """
        Verifica se um embedding é válido para uso no Matcher.

        :param embedding: Vetor a ser validado
        :return:          True se válido, False caso contrário
        """

        # Deve ser um array NumPy
        if not isinstance(embedding, np.ndarray):
            return False

        # Deve ter o tamanho correto (512 para buffalo_l)
        if embedding.shape[0] != self.embedding_size:
            return False

        # Não deve conter valores inválidos (NaN ou infinito)
        if np.any(np.isnan(embedding)) or np.any(np.isinf(embedding)):
            return False

        return True