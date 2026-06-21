"""
aluno_service.py

Responsabilidade: Gerenciar o cadastro de alunos.

Substitui o antigo person_service. Usa o modelo compartilhado (engine) com
infer_lock. O cadastro recebe o nome, a foto e a turma do aluno.

Fluxo:
    Recebe foto + nome + turma_id
        → Detecta rosto (FaceDetector)
        → Gera embedding (FaceEmbedder)
        → Salva aluno (com turma) e embedding no banco
"""

import os
import cv2
import numpy as np
import logging
from typing import Optional

from app.face.engine import get_detector, get_embedder, infer_lock
from app.db.models import (
    create_aluno,
    get_aluno_by_id,
    get_all_alunos,
    delete_aluno,
    save_embedding,
)

logger = logging.getLogger(__name__)

PROCESSED_DIR = "data/processed/cropped_faces"


class AlunoService:
    """Serviço de cadastro e gerenciamento de alunos."""

    def __init__(self, model_root: str = "models/insightface"):
        self.detector = get_detector(model_root=model_root)
        self.embedder = get_embedder()
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        logger.info("AlunoService inicializado.")

    def register_from_image(self, nome: str, image_path: str,
                            turma_id: int = None,
                            supabase_dependent_id: str = None) -> dict:
        """
        Cadastra um aluno a partir de uma imagem em disco.

        :param nome:       Nome do aluno
        :param image_path: Caminho da imagem no disco
        :param turma_id:   ID da turma do aluno (pode ser None)
        :return:           Dicionário com os dados do aluno cadastrado
        :raises ValueError: se não encontrar rosto ou o embedding for inválido
        """
        logger.info(
            f"Cadastrando aluno: {nome} | turma: {turma_id} "
            f"| dependent: {supabase_dependent_id} | Imagem: {image_path}"
        )

        image_bgr = cv2.imread(image_path)
        if image_bgr is None:
            raise ValueError(f"Não foi possível ler a imagem: {image_path}")

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        with infer_lock:
            result = self.detector.process_frame(image_bgr, image_rgb)

        if not result["has_faces"]:
            raise ValueError(f"Nenhum rosto encontrado na imagem: {image_path}")

        face = max(result["faces"], key=lambda f: f.det_score)
        face_index = result["faces"].index(face)
        logger.info(f"Rosto detectado com confiança: {face.det_score:.0%}")

        embedding = self.embedder.get_embedding(face)
        if not self.embedder.is_valid(embedding):
            raise ValueError("Não foi possível gerar o embedding do rosto.")

        # Salva o rosto recortado em disco
        crop = result["crops"][face_index]
        crop_filename = f"{nome}_{os.path.basename(image_path)}"
        crop_path = os.path.join(PROCESSED_DIR, crop_filename)
        cv2.imwrite(crop_path, crop)

        aluno = create_aluno(nome, turma_id=turma_id,
                             supabase_dependent_id=supabase_dependent_id)
        save_embedding(
            aluno_id=aluno["id"],
            embedding=embedding,
            image_path=image_path
        )

        logger.info(f"✅ Aluno cadastrado: {nome} (ID: {aluno['id']}, turma: {turma_id})")

        return {
            "aluno":      aluno,
            "crop_path":  crop_path,
            "confidence": float(face.det_score),
        }

    def get_aluno(self, aluno_id: int) -> Optional[dict]:
        """Busca um aluno pelo ID."""
        return get_aluno_by_id(aluno_id)

    def list_alunos(self) -> list:
        """Retorna todos os alunos cadastrados."""
        return get_all_alunos()

    def remove_aluno(self, aluno_id: int) -> bool:
        """Remove um aluno e seus embeddings/logs (cascata)."""
        logger.info(f"Removendo aluno ID: {aluno_id}")
        return delete_aluno(aluno_id)