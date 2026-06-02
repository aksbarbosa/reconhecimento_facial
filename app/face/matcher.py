"""
matcher.py

Responsabilidade: Comparar o embedding de um rosto capturado pela câmera
com os embeddings cadastrados no banco, identificando qual aluno é.

Usa similaridade por cosseno entre vetores de 512 dimensões. Quanto mais
próximo de 1.0, mais similar — mais provável ser a mesma pessoa.

Cada candidato (vindo de models.get_all_embeddings) carrega, além do
embedding, a identidade do aluno e a janela de horário da turma dele.
O matcher só identifica QUEM é; a decisão de acesso por horário é feita
depois, no CameraWorker, usando os campos inicio/fim do candidato.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class MatchResult:
    """Resultado de uma comparação de rosto."""
    matched: bool                  # True se encontrou correspondência
    aluno_id: Optional[int]        # ID do aluno (None se não identificado)
    aluno_nome: Optional[str]      # Nome do aluno (None se não identificado)
    similarity: float              # Similaridade encontrada (0.0 a 1.0)
    threshold: float               # Limiar usado na comparação


class FaceMatcher:
    """Compara embeddings de rostos capturados com os cadastrados no banco."""

    def __init__(self, threshold: float = 0.6):
        """
        :param threshold: Similaridade mínima para aceitar uma correspondência.
                          0.5 permissivo, 0.6 equilibrado, 0.7 restritivo.
        """
        self.threshold = threshold

    def match(self, embedding: np.ndarray, candidates: list) -> MatchResult:
        """
        Compara um embedding com a lista de candidatos do banco e retorna
        o mais similar, desde que supere o limiar.

        :param embedding:  Vetor do rosto capturado
        :param candidates: Lista de dicts com "aluno_id", "aluno_nome", "embedding"
        :return:           MatchResult
        """
        if not candidates:
            return MatchResult(False, None, None, 0.0, self.threshold)

        best_similarity = 0.0
        best_candidate = None

        for candidate in candidates:
            candidate_embedding = candidate["embedding"]
            similarity = self._cosine_similarity(embedding, candidate_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_candidate = candidate

        if best_similarity >= self.threshold and best_candidate is not None:
            return MatchResult(
                matched=True,
                aluno_id=best_candidate["aluno_id"],
                aluno_nome=best_candidate["aluno_nome"],
                similarity=round(best_similarity, 4),
                threshold=self.threshold
            )

        return MatchResult(
            matched=False,
            aluno_id=None,
            aluno_nome=None,
            similarity=round(best_similarity, 4),
            threshold=self.threshold
        )

    def match_batch(self, embeddings: list, candidates: list) -> list:
        """Compara vários embeddings (vários rostos no mesmo frame)."""
        return [self.match(embedding, candidates) for embedding in embeddings]

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Similaridade por cosseno entre dois vetores (0.0 a 1.0)."""
        norma1 = np.linalg.norm(vec1)
        norma2 = np.linalg.norm(vec2)
        if norma1 == 0 or norma2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norma1 * norma2))

    def update_threshold(self, new_threshold: float):
        """Atualiza o limiar de similaridade em tempo de execução."""
        if not 0.0 <= new_threshold <= 1.0:
            raise ValueError(f"Limiar deve estar entre 0.0 e 1.0, recebido: {new_threshold}")
        self.threshold = new_threshold