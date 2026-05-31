"""
test_pipeline.py

Testa o pipeline completo usando a câmera do Mac:
FrameReader → FaceDetector → FaceEmbedder → FaceMatcher

Exibe a janela com a câmera ao vivo e mostra na tela
se detectou rosto e o embedding gerado.

Como sair: pressione 'q'
"""

import sys
import os

# Adiciona a pasta raiz do projeto ao path para importar os módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from app.camera.frame_reader import FrameReader
from app.face.detector import FaceDetector
from app.face.embedder import FaceEmbedder

# ── Inicializa os módulos ──────────────────────────────────────
print("Iniciando câmera...")
reader   = FrameReader(0)  # 0 = câmera do Mac

if not reader.is_opened():
    print("❌ Câmera não acessível. Verifique as permissões.")
    sys.exit(1)

print(f"✅ Câmera conectada: {reader.get_info()}")
print("Carregando modelo InsightFace (pode demorar na primeira vez)...")

detector = FaceDetector(model_root="models/insightface")
embedder = FaceEmbedder()

print("✅ Modelo carregado! Pressione 'q' para sair.\n")

# ── Loop principal ─────────────────────────────────────────────
while True:

    # 1. Captura o frame
    frame_bgr, frame_rgb = reader.read_frame()
    if frame_bgr is None:
        print("⚠️ Frame não capturado.")
        break

    # 2. Detecta rostos
    result = detector.process_frame(frame_bgr, frame_rgb)

    if result["has_faces"]:
        for i, face in enumerate(result["faces"]):

            # 3. Gera embedding
            embedding = embedder.get_embedding(face)

            # Exibe informações no terminal
            print(
                f"✅ Rosto {i+1} | "
                f"Confiança: {face.det_score:.0%} | "
                f"Embedding válido: {embedder.is_valid(embedding)}"
            )

    # 4. Exibe o frame com retângulos na janela
    cv2.imshow("Pipeline - Pressione Q para sair", result["frame_debug"])

    # Sai ao pressionar 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# ── Encerra ────────────────────────────────────────────────────
reader.release()
cv2.destroyAllWindows()
print("Encerrado.")