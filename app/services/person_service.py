"""
person_service.py

Responsabilidade: Gerenciar o cadastro de pessoas no sistema.

Este serviço cuida de tudo relacionado a pessoas — cadastrar, listar,
buscar e remover. Também processa a foto enviada, detecta o rosto,
gera o embedding e salva tudo no banco de dados.

Fluxo de cadastro:
    Recebe foto + nome
        → Detecta rosto na foto (FaceDetector)
        → Gera embedding do rosto (FaceEmbedder)
        → Salva pessoa no banco (persons)
        → Salva embedding no banco (face_embeddings)
        → Notifica RecognitionService para recarregar candidatos
"""

import os
import cv2                                      # OpenCV — leitura de imagens
import numpy as np                             # NumPy — manipulação de vetores
import logging                                 # Logs do sistema
from typing import Optional                    # Tipagem

from app.face.detector import FaceDetector     # Detecta rostos nas fotos
from app.face.embedder import FaceEmbedder     # Gera vetores dos rostos
from app.db.models import (
    create_person,              # Cria pessoa no banco
    get_person_by_id,           # Busca pessoa por ID
    get_all_persons,            # Lista todas as pessoas
    delete_person,              # Remove pessoa do banco
    save_embedding,             # Salva embedding no banco
)

# Configura o logger para este módulo
logger = logging.getLogger(__name__)

# Pasta onde as fotos de cadastro são salvas após processamento
PROCESSED_DIR = "data/processed/cropped_faces"


class PersonService:
    """
    Serviço de gerenciamento de pessoas.

    Centraliza toda a lógica de cadastro — desde receber a foto
    até salvar o embedding no banco, pronto para o reconhecimento.
    """

    def __init__(self, model_root: str = "models/insightface"):
        """
        Inicializa o serviço com os módulos de detecção e embedding.

        :param model_root: Pasta dos modelos InsightFace
        """

        # Detecta rostos nas fotos enviadas para cadastro
        self.detector = FaceDetector(model_root=model_root)

        # Gera o vetor de 512 números de cada rosto detectado
        self.embedder = FaceEmbedder()

        # Cria a pasta de rostos processados se não existir
        os.makedirs(PROCESSED_DIR, exist_ok=True)

        logger.info("PersonService inicializado.")

    def register_from_image(self, name: str, image_path: str) -> dict:
        """
        Cadastra uma pessoa a partir de uma imagem em disco.

        Detecta o rosto na imagem, gera o embedding e salva
        tudo no banco de dados em uma única operação.

        :param name:       Nome da pessoa a cadastrar
        :param image_path: Caminho da imagem no disco
        :return:           Dicionário com os dados da pessoa cadastrada
        :raises:           ValueError se não encontrar rosto na imagem
        """

        logger.info(f"Cadastrando pessoa: {name} | Imagem: {image_path}")

        # ── 1. Lê a imagem do disco ────────────────────────────────────────

        # OpenCV lê a imagem no formato BGR
        image_bgr = cv2.imread(image_path)

        if image_bgr is None:
            raise ValueError(f"Não foi possível ler a imagem: {image_path}")

        # Converte para RGB (InsightFace exige RGB)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        # ── 2. Detecta o rosto na imagem ───────────────────────────────────

        result = self.detector.process_frame(image_bgr, image_rgb)

        if not result["has_faces"]:
            raise ValueError(f"Nenhum rosto encontrado na imagem: {image_path}")

        # Se houver múltiplos rostos, usa o de maior confiança
        face = max(result["faces"], key=lambda f: f.det_score)
        face_index = result["faces"].index(face)

        logger.info(f"Rosto detectado com confiança: {face.det_score:.0%}")

        # ── 3. Gera o embedding do rosto ───────────────────────────────────

        embedding = self.embedder.get_embedding(face)

        if not self.embedder.is_valid(embedding):
            raise ValueError("Não foi possível gerar o embedding do rosto.")

        # ── 4. Salva o rosto recortado em disco ────────────────────────────

        # Salva o recorte do rosto na pasta de processados
        crop = result["crops"][face_index]
        crop_filename = f"{name}_{os.path.basename(image_path)}"
        crop_path = os.path.join(PROCESSED_DIR, crop_filename)
        cv2.imwrite(crop_path, crop)

        # ── 5. Salva no banco de dados ─────────────────────────────────────

        # Cria o registro da pessoa na tabela persons
        person = create_person(name)

        # Salva o embedding na tabela face_embeddings
        save_embedding(
            person_id=person["id"],
            embedding=embedding,
            image_path=image_path
        )

        logger.info(f"✅ Pessoa cadastrada: {name} (ID: {person['id']})")

        # Retorna os dados completos do cadastro
        return {
            "person":     person,
            "crop_path":  crop_path,
            "confidence": float(face.det_score),
        }

    def register_from_array(self, name: str, image_bgr: np.ndarray) -> dict:
        """
        Cadastra uma pessoa a partir de um array NumPy (frame da câmera).

        Útil quando a foto vem diretamente da câmera, sem passar pelo disco.

        :param name:      Nome da pessoa
        :param image_bgr: Frame BGR capturado pela câmera
        :return:          Dicionário com os dados da pessoa cadastrada
        :raises:          ValueError se não encontrar rosto na imagem
        """

        # Salva o frame temporariamente para referência no banco
        temp_path = f"data/raw/uploads/{name}_temp.jpg"
        os.makedirs("data/raw/uploads", exist_ok=True)
        cv2.imwrite(temp_path, image_bgr)

        # Reutiliza o método de cadastro por imagem
        return self.register_from_image(name, temp_path)

    def get_person(self, person_id: int) -> Optional[dict]:
        """
        Busca uma pessoa pelo ID.

        :param person_id: ID da pessoa no banco
        :return:          Dados da pessoa ou None se não encontrada
        """
        return get_person_by_id(person_id)

    def list_persons(self) -> list:
        """
        Retorna todas as pessoas cadastradas no banco.

        :return: Lista de dicionários com os dados de cada pessoa
        """
        return get_all_persons()

    def remove_person(self, person_id: int) -> bool:
        """
        Remove uma pessoa e todos os seus embeddings do banco.

        :param person_id: ID da pessoa a remover
        :return:          True se removeu, False se não encontrou
        """
        logger.info(f"Removendo pessoa ID: {person_id}")
        return delete_person(person_id)