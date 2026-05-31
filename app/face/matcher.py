"""
matcher.py

Responsabilidade: Comparar o embedding de um rosto capturado pela câmera
com os embeddings cadastrados no banco de dados, identificando quem é a pessoa.

Um embedding é um vetor de 512 números que representa as características
únicas de um rosto. Rostos da mesma pessoa geram vetores similares.
Este módulo mede essa similaridade e decide se há correspondência.

Fluxo:
    FaceEmbedder (face/embedder.py)
        → entrega o vetor do rosto capturado
    FaceMatcher (este arquivo)
        → compara com todos os vetores cadastrados no banco
        → retorna quem é a pessoa (ou desconhecida)
    RecognitionService (services/recognition_service.py)
        → usa o resultado para registrar o acesso
"""

import numpy as np  # NumPy — cálculos vetoriais para comparação de embeddings
from dataclasses import dataclass  # Para estruturar o resultado da comparação
from typing import Optional  # Para tipagem de valores que podem ser None


@dataclass
class MatchResult:
    """
    Estrutura que representa o resultado de uma comparação de rosto.

    Agrupa todas as informações relevantes sobre a identificação
    de forma organizada para uso nos serviços e API.
    """

    matched: bool             # True se encontrou correspondência no banco
    person_id: Optional[int]  # ID da pessoa no banco (None se não identificada)
    person_name: Optional[str]  # Nome da pessoa (None se não identificada)
    similarity: float         # Similaridade encontrada (0.0 a 1.0)
    threshold: float          # Limiar usado na comparação


class FaceMatcher:
    """
    Compara embeddings de rostos capturados com os cadastrados no banco.

    Usa similaridade por cosseno para medir o quão parecidos dois vetores são.
    Quanto mais próximo de 1.0, mais similar — ou seja, mais provável que
    seja a mesma pessoa.
    """

    def __init__(self, threshold: float = 0.6):
        """
        Inicializa o matcher com o limiar de similaridade.

        :param threshold: Similaridade mínima para considerar uma correspondência.
                          Valores recomendados:
                          - 0.5: permissivo (mais falsos positivos)
                          - 0.6: equilibrado (padrão recomendado)
                          - 0.7: restritivo (mais falsos negativos)
        """

        # Limiar mínimo de similaridade para aceitar uma correspondência
        self.threshold = threshold

    def match(self, embedding: np.ndarray, candidates: list) -> MatchResult:
        """
        Compara um embedding com uma lista de candidatos cadastrados no banco.

        Percorre todos os candidatos, calcula a similaridade com cada um
        e retorna o mais similar — desde que supere o limiar configurado.

        :param embedding:   Vetor do rosto capturado (saída do FaceEmbedder)
        :param candidates:  Lista de dicionários com os cadastros do banco.
                            Cada item deve ter:
                            - "person_id":   ID da pessoa
                            - "person_name": Nome da pessoa
                            - "embedding":   Vetor np.ndarray cadastrado
        :return:            MatchResult com o resultado da comparação
        """

        # Se não há candidatos no banco, retorna não identificado
        if not candidates:
            return MatchResult(
                matched=False,
                person_id=None,
                person_name=None,
                similarity=0.0,
                threshold=self.threshold
            )

        best_similarity = 0.0   # Maior similaridade encontrada até agora
        best_candidate = None   # Candidato com maior similaridade

        # Percorre todos os cadastros do banco comparando com o rosto capturado
        for candidate in candidates:

            # Obtém o vetor cadastrado do candidato
            candidate_embedding = candidate["embedding"]

            # Calcula a similaridade por cosseno entre os dois vetores
            # (produto escalar de vetores normalizados = similaridade por cosseno)
            similarity = self._cosine_similarity(embedding, candidate_embedding)

            # Atualiza o melhor candidato se a similaridade for maior
            if similarity > best_similarity:
                best_similarity = similarity
                best_candidate = candidate

        # Verifica se a melhor similaridade encontrada supera o limiar
        if best_similarity >= self.threshold and best_candidate is not None:

            # Correspondência encontrada — retorna os dados da pessoa
            return MatchResult(
                matched=True,
                person_id=best_candidate["person_id"],
                person_name=best_candidate["person_name"],
                similarity=round(best_similarity, 4),
                threshold=self.threshold
            )

        # Nenhum candidato superou o limiar — rosto não identificado
        return MatchResult(
            matched=False,
            person_id=None,
            person_name=None,
            similarity=round(best_similarity, 4),
            threshold=self.threshold
        )

    def match_batch(self, embeddings: list, candidates: list) -> list:
        """
        Compara uma lista de embeddings com os candidatos do banco.
        Útil quando há múltiplos rostos no mesmo frame.

        :param embeddings:  Lista de vetores (um por rosto detectado no frame)
        :param candidates:  Lista de cadastros do banco
        :return:            Lista de MatchResult (um por embedding)
        """

        # Processa cada rosto individualmente e retorna todos os resultados
        return [self.match(embedding, candidates) for embedding in embeddings]

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calcula a similaridade por cosseno entre dois vetores.

        Mede o ângulo entre dois vetores no espaço de 512 dimensões.
        Vetores paralelos (mesma direção) têm similaridade 1.0.
        Vetores perpendiculares têm similaridade 0.0.

        Se os vetores já estiverem normalizados (como os do FaceEmbedder),
        o cálculo se reduz a um simples produto escalar.

        :param vec1: Primeiro vetor (rosto capturado)
        :param vec2: Segundo vetor (rosto cadastrado)
        :return:     Similaridade entre 0.0 e 1.0
        """

        # Calcula as normas dos vetores para normalização
        norma1 = np.linalg.norm(vec1)
        norma2 = np.linalg.norm(vec2)

        # Evita divisão por zero (caso de vetor nulo)
        if norma1 == 0 or norma2 == 0:
            return 0.0

        # Produto escalar dividido pelo produto das normas = similaridade cosseno
        return float(np.dot(vec1, vec2) / (norma1 * norma2))

    def update_threshold(self, new_threshold: float):
        """
        Atualiza o limiar de similaridade em tempo de execução.
        Permite ajustar a sensibilidade sem reiniciar o sistema.

        :param new_threshold: Novo limiar (deve estar entre 0.0 e 1.0)
        """

        # Valida o intervalo do limiar
        if not 0.0 <= new_threshold <= 1.0:
            raise ValueError(f"Limiar deve estar entre 0.0 e 1.0, recebido: {new_threshold}")

        self.threshold = new_threshold