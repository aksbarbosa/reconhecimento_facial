"""
register_from_folder.py

Responsabilidade: Cadastrar pessoas no banco de dados a partir de
fotos colocadas na pasta data/raw/uploads/.

Como usar:
    1. Coloque as fotos em data/raw/uploads/
       O nome do arquivo vira o nome da pessoa:
       - joao.png       → cadastra "joao"
       - maria_silva.png → cadastra "maria_silva"

    2. Rode:
       python3 scripts/register_from_folder.py

    3. Verifique no TablePlus — as pessoas e embeddings estarão no banco.

Fluxo:
    Lê as fotos da pasta uploads/
        → Detecta o rosto em cada foto (InsightFace)
        → Gera o embedding do rosto (vetor de 512 números)
        → Salva a pessoa e o embedding no banco (PostgreSQL)
"""

import sys
import os

# Adiciona a pasta raiz ao path para importar os módulos do projeto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2                                  # OpenCV — leitura das imagens
from app.face.detector import FaceDetector  # Detecta rostos nas fotos
from app.face.embedder import FaceEmbedder  # Gera vetores dos rostos
from app.db.database import test_connection # Testa conexão com o banco
from app.db.models import (                 # Operações no banco
    create_person,
    save_embedding,
    get_all_persons
)

# ── Configurações ──────────────────────────────────────────────────────────────

UPLOADS_DIR   = "data/raw/uploads"       # Pasta onde as fotos devem ser colocadas
PROCESSED_DIR = "data/processed/cropped_faces"  # Onde salvar os rostos recortados

# Extensões de imagem aceitas
EXTENSOES_ACEITAS = (".png", ".jpg", ".jpeg", ".webp")

# ── Inicialização ──────────────────────────────────────────────────────────────

print("=" * 50)
print("  CADASTRO DE PESSOAS — Face Access System")
print("=" * 50)

# 1. Testa a conexão com o banco antes de começar
print("\n🔌 Verificando conexão com o banco...")
if not test_connection():
    print("❌ Não foi possível conectar ao banco. Verifique se o PostgreSQL está rodando.")
    sys.exit(1)

# 2. Verifica se a pasta de uploads existe
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    print(f"\n📁 Pasta criada: {UPLOADS_DIR}")
    print(f"   Coloque as fotos nessa pasta e rode o script novamente.")
    sys.exit(0)

# 3. Lista as fotos na pasta
fotos = [
    f for f in os.listdir(UPLOADS_DIR)
    if f.lower().endswith(EXTENSOES_ACEITAS)
]

if not fotos:
    print(f"\n⚠️  Nenhuma foto encontrada em: {UPLOADS_DIR}")
    print(f"   Coloque fotos .png ou .jpg na pasta e rode novamente.")
    sys.exit(0)

print(f"\n📸 {len(fotos)} foto(s) encontrada(s) em {UPLOADS_DIR}/")

# 4. Carrega os modelos InsightFace
print("\n🤖 Carregando modelo InsightFace (pode demorar na primeira vez)...")
detector = FaceDetector(model_root="models/insightface")
embedder = FaceEmbedder()
print("✅ Modelo carregado!")

# Cria a pasta de rostos processados se não existir
os.makedirs(PROCESSED_DIR, exist_ok=True)

# ── Processamento das fotos ────────────────────────────────────────────────────

print("\n" + "─" * 50)
cadastrados  = 0  # Contador de pessoas cadastradas com sucesso
ignorados    = 0  # Contador de fotos ignoradas (sem rosto ou erro)

for nome_arquivo in fotos:

    # Remove a extensão para usar como nome da pessoa
    # Ex: "joao_silva.png" → "joao_silva"
    nome_pessoa = os.path.splitext(nome_arquivo)[0]
    caminho_foto = os.path.join(UPLOADS_DIR, nome_arquivo)

    print(f"\n📄 Processando: {nome_arquivo}")
    print(f"   Nome da pessoa: {nome_pessoa}")

    # ── Lê a imagem ───────────────────────────────────────────────────────────

    # OpenCV lê a imagem no formato BGR
    imagem_bgr = cv2.imread(caminho_foto)

    if imagem_bgr is None:
        print(f"   ❌ Não foi possível ler a imagem. Pulando.")
        ignorados += 1
        continue

    # Converte para RGB (InsightFace exige RGB)
    imagem_rgb = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2RGB)

    # ── Detecta o rosto na foto ───────────────────────────────────────────────

    result = detector.process_frame(imagem_bgr, imagem_rgb)

    if not result["has_faces"]:
        print(f"   ❌ Nenhum rosto detectado na foto. Tente outra imagem.")
        ignorados += 1
        continue

    # Se houver mais de um rosto, usa o de maior confiança
    face = max(result["faces"], key=lambda f: f.det_score)
    print(f"   ✅ Rosto detectado (confiança: {face.det_score:.0%})")

    # ── Gera o embedding do rosto ─────────────────────────────────────────────

    embedding = embedder.get_embedding(face)

    if not embedder.is_valid(embedding):
        print(f"   ❌ Embedding inválido. Pulando.")
        ignorados += 1
        continue

    # ── Salva o rosto recortado em disco ──────────────────────────────────────

    crop = result["crops"][result["faces"].index(face)]
    caminho_crop = os.path.join(PROCESSED_DIR, nome_arquivo)
    cv2.imwrite(caminho_crop, crop)

    # ── Salva no banco de dados ───────────────────────────────────────────────

    try:
        # Cria a pessoa na tabela persons
        person = create_person(nome_pessoa)

        # Salva o embedding na tabela face_embeddings
        save_embedding(
            person_id=person["id"],
            embedding=embedding,
            image_path=caminho_foto
        )

        print(f"   ✅ Cadastrado no banco! ID: {person['id']}")
        cadastrados += 1

    except Exception as e:
        print(f"   ❌ Erro ao salvar no banco: {e}")
        ignorados += 1

# ── Resumo final ───────────────────────────────────────────────────────────────

print("\n" + "=" * 50)
print(f"  RESUMO")
print(f"  ✅ Cadastrados com sucesso: {cadastrados}")
print(f"  ⚠️  Ignorados:              {ignorados}")
print("=" * 50)

# Lista todas as pessoas cadastradas no banco
print("\n👥 Pessoas no banco:")
pessoas = get_all_persons()
if pessoas:
    for p in pessoas:
        print(f"   ID {p['id']} — {p['name']} (cadastrado em {p['created_at'].strftime('%d/%m/%Y %H:%M')})")
else:
    print("   Nenhuma pessoa cadastrada ainda.")