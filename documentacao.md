# Face Access System — Documentação

Sistema de reconhecimento facial em tempo real usando OpenCV e InsightFace.
Captura frames de câmera (local ou IP), detecta rostos, gera vetores de identificação
e compara com pessoas cadastradas no banco de dados.

---

## Sumário

1. [Visão Geral](#visão-geral)
2. [Estrutura do Projeto](#estrutura-do-projeto)
3. [Instalação](#instalação)
4. [Arquivos Implementados](#arquivos-implementados)
5. [Pipeline de Reconhecimento](#pipeline-de-reconhecimento)
6. [Guia de Uso](#guia-de-uso)
7. [Configurações](#configurações)
8. [Onde os Dados São Salvos](#onde-os-dados-são-salvos)
9. [Solução de Problemas](#solução-de-problemas)

---

## Visão Geral

O sistema captura frames de vídeo em tempo real, detecta rostos usando o modelo
InsightFace (RetinaFace + ArcFace), gera um vetor matemático de cada rosto e
compara com os cadastros do banco de dados para identificar pessoas.

```
Câmera → Frame → Detecção → Embedding → Comparação → Identificação
```

### Tecnologias utilizadas

| Tecnologia | Função |
|---|---|
| **OpenCV** | Captura de vídeo, manipulação e salvamento de imagens |
| **InsightFace** | Detecção de rostos e geração de embeddings |
| **ONNX Runtime** | Motor de inferência dos modelos InsightFace |
| **NumPy** | Operações matemáticas nos vetores de embedding |
| **FastAPI** | API REST para integração com frontend |
| **Streamlit** | Interface web para uso do sistema |

---

## Estrutura do Projeto

```
face_access_system/
│
├── app/
│   ├── camera/
│   │   ├── frame_reader.py       ← Captura frames da câmera via OpenCV
│   │   ├── ip_camera.py          ← Monta a URL RTSP da câmera IP
│   │   └── snapshot.py           ← Salva frames em disco via OpenCV
│   │
│   ├── face/
│   │   ├── detector.py           ← Detecta rostos usando InsightFace
│   │   ├── embedder.py           ← Gera vetores de 512 dimensões
│   │   ├── matcher.py            ← Compara vetores com o banco
│   │   ├── aligner.py            ← Alinha rostos detectados
│   │   └── quality.py            ← Verifica qualidade da imagem
│   │
│   ├── services/
│   │   ├── recognition_service.py ← Orquestra o reconhecimento
│   │   ├── person_service.py      ← Gerencia cadastros de pessoas
│   │   ├── face_service.py        ← Gerencia rostos cadastrados
│   │   └── camera_service.py      ← Gerencia câmeras
│   │
│   ├── workers/
│   │   └── camera_worker.py      ← Loop contínuo em background
│   │
│   └── db/
│       ├── database.py           ← Conexão com banco de dados
│       ├── models.py             ← Modelos das tabelas
│       └── schemas.py            ← Schemas de validação
│
├── data/
│   ├── raw/
│   │   ├── uploads/              ← Imagens enviadas manualmente
│   │   └── camera_frames/        ← Frames de rostos desconhecidos
│   ├── processed/
│   │   ├── aligned_faces/        ← Rostos alinhados
│   │   └── cropped_faces/        ← Rostos recortados
│   └── snapshots/                ← Fotos de rostos identificados
│
├── models/
│   ├── insightface/              ← Modelos InsightFace (buffalo_l)
│   └── retinaface/               ← Modelos RetinaFace
│
└── scripts/
    ├── test_camera_mac.py        ← Testa câmera do Mac
    └── test_camera.py            ← Testa câmera IP
```

---

## Instalação

### Requisitos

- Python 3.9 ou superior
- Mac, Linux ou Windows
- Câmera local ou câmera IP na mesma rede

### Passo a passo

**1. Clone o repositório**
```bash
git clone https://github.com/seu-usuario/face_access_system.git
cd face_access_system
```

**2. Crie o ambiente virtual (recomendado)**
```bash
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows
```

**3. Instale as dependências**
```bash
pip install opencv-python
pip install insightface
pip install onnxruntime
pip install numpy
```

Ou instale tudo de uma vez via requirements.txt:
```bash
pip install -r requirements.txt
```

**4. Permissão de câmera no Mac**

Na primeira execução, o Mac pedirá permissão para acessar a câmera.
Se negar sem querer, vá em:

```
Configurações do Sistema → Privacidade e Segurança → Câmera → ✅ Terminal
```

---

## Arquivos Implementados

### `app/camera/frame_reader.py`

Responsável por abrir a conexão com a câmera e capturar frames continuamente
via OpenCV. Funciona tanto com câmera local (índice `0`) quanto câmera IP (URL RTSP).

Entrega dois formatos do mesmo frame:
- **BGR** — formato padrão do OpenCV, usado para salvar imagens em disco
- **RGB** — formato esperado pelo InsightFace para detecção de rostos

```python
from app.camera.frame_reader import FrameReader

reader = FrameReader(0)  # 0 = câmera do Mac
frame_bgr, frame_rgb = reader.read_frame()
reader.release()
```

---

### `app/face/detector.py`

Detecta rostos em frames usando InsightFace (modelo `buffalo_l` com RetinaFace).
Para cada rosto encontrado, recorta a região usando OpenCV e filtra detecções
com confiança abaixo do limiar configurado (padrão: 50%).

```python
from app.face.detector import FaceDetector

detector = FaceDetector(model_root="models/insightface", min_confidence=0.5)
result = detector.process_frame(frame_bgr, frame_rgb)

if result["has_faces"]:
    print(f"{len(result['faces'])} rosto(s) detectado(s)")
    crops = result["crops"]        # Imagens recortadas
    frame_debug = result["frame_debug"]  # Frame com retângulos
```

---

### `app/face/embedder.py`

Extrai o embedding (vetor de 512 números) de cada rosto detectado pelo InsightFace.
Normaliza o vetor para garantir comparações precisas por similaridade de cosseno.

```python
from app.face.embedder import FaceEmbedder

embedder = FaceEmbedder()
embedding = embedder.get_embedding(face)  # face = objeto Face do InsightFace

# Verifica se é válido antes de usar
if embedder.is_valid(embedding):
    print(f"Vetor gerado: {embedding.shape}")  # (512,)
```

---

### `app/face/matcher.py`

Compara o embedding de um rosto capturado com todos os cadastros do banco.
Usa similaridade por cosseno e retorna o candidato mais similar desde que
supere o limiar configurado (padrão: 60%).

```python
from app.face.matcher import FaceMatcher

matcher = FaceMatcher(threshold=0.6)

candidates = [
    {"person_id": 1, "person_name": "João", "embedding": vetor_joao},
    {"person_id": 2, "person_name": "Maria", "embedding": vetor_maria},
]

result = matcher.match(embedding, candidates)

if result.matched:
    print(f"Identificado: {result.person_name} ({result.similarity:.0%})")
else:
    print(f"Desconhecido (similaridade: {result.similarity:.0%})")
```

---

### `app/workers/camera_worker.py`

Orquestra o pipeline completo em loop contínuo, rodando em uma thread separada
(background) para não bloquear a API ou o frontend.

```python
from app.workers.camera_worker import CameraWorker

worker = CameraWorker(
    camera_source=0,           # 0 = câmera do Mac, ou URL RTSP
    candidates=candidates,     # Lista de cadastros do banco
    threshold=0.6,             # Limiar de similaridade
    save_unknown=True          # Salvar rostos desconhecidos?
)

worker.start()   # Inicia em background

# ... sistema rodando ...

worker.stop()    # Encerra e libera a câmera
```

---

## Pipeline de Reconhecimento

```
┌─────────────────────────────────────────────────────────────┐
│                      CameraWorker                           │
│                                                             │
│  FrameReader → frame_bgr + frame_rgb                        │
│       ↓                                                     │
│  FaceDetector → has_faces? → NÃO → descarta, próximo frame  │
│       ↓ SIM                                                 │
│  FaceEmbedder → vetor de 512 números                        │
│       ↓                                                     │
│  FaceMatcher → similaridade ≥ 0.6?                          │
│       ├── SIM → salva em data/snapshots/ + loga             │
│       └── NÃO → salva em data/raw/camera_frames/ (unknown)  │
└─────────────────────────────────────────────────────────────┘
```

### Decisão de salvamento

| Situação | O que acontece |
|---|---|
| Frame sem rosto | Descartado na memória, nada salvo |
| Rosto identificado (≥ 60%) | Salvo em `data/snapshots/` |
| Rosto desconhecido (< 60%) | Salvo em `data/raw/camera_frames/` |
| Snapshot manual via API | Salvo em `data/snapshots/` independente |

---

## Guia de Uso

### Testar a câmera do Mac

```bash
python3 scripts/test_camera_mac.py
```

Uma janela abrirá mostrando o vídeo da câmera. Pressione `q` para sair.

---

### Testar uma câmera IP

Edite o arquivo `scripts/test_camera.py` com os dados da sua câmera:

```python
IP       = "192.168.1.100"   # IP da câmera na rede
USER     = "admin"            # Usuário
PASSWORD = "senha"            # Senha
PORT     = 554                # Porta RTSP (padrão)
```

Depois rode:
```bash
python3 scripts/test_camera.py
```

### URLs RTSP por fabricante

| Marca | URL padrão |
|---|---|
| Hikvision | `rtsp://user:pass@IP:554/Streaming/Channels/101` |
| Dahua | `rtsp://user:pass@IP:554/cam/realmonitor?channel=1` |
| Intelbras | `rtsp://user:pass@IP:554/cam/realmonitor?channel=1` |
| Genérica | `rtsp://user:pass@IP:554/stream1` |

---

### Usar o pipeline completo

```python
from app.camera.frame_reader import FrameReader
from app.face.detector import FaceDetector
from app.face.embedder import FaceEmbedder
from app.face.matcher import FaceMatcher

# Candidatos cadastrados no banco
candidates = [
    {"person_id": 1, "person_name": "João", "embedding": vetor_joao},
]

# Inicializa os módulos
reader   = FrameReader(0)
detector = FaceDetector()
embedder = FaceEmbedder()
matcher  = FaceMatcher(threshold=0.6)

# Captura e processa um frame
frame_bgr, frame_rgb = reader.read_frame()
result = detector.process_frame(frame_bgr, frame_rgb)

if result["has_faces"]:
    for face in result["faces"]:
        embedding = embedder.get_embedding(face)
        match = matcher.match(embedding, candidates)
        print(match.person_name if match.matched else "Desconhecido")

reader.release()
```

---

### Usar o worker em background

```python
from app.workers.camera_worker import CameraWorker

worker = CameraWorker(
    camera_source=0,
    candidates=candidates,
    threshold=0.6,
    frame_interval=0.1,   # 10 frames por segundo
    save_unknown=True
)

worker.start()

# Consulta o último resultado a qualquer momento
resultado = worker.get_last_result()
print(resultado)

worker.stop()
```

---

## Configurações

### Limiar de similaridade (`threshold`)

Controla o quão rigoroso é o reconhecimento:

| Valor | Comportamento |
|---|---|
| `0.5` | Permissivo — mais falsos positivos |
| `0.6` | Equilibrado — recomendado para uso geral |
| `0.7` | Restritivo — mais falsos negativos |

### Intervalo entre frames (`frame_interval`)

Controla a taxa de processamento e o consumo de CPU:

| Valor | Taxa aproximada | Uso de CPU |
|---|---|---|
| `0.033` | ~30 fps | Alto |
| `0.1` | ~10 fps | Médio (padrão) |
| `0.5` | ~2 fps | Baixo |

### Salvar rostos desconhecidos (`save_unknown`)

- `True` — salva imagens de rostos não identificados em `data/raw/camera_frames/`
- `False` — descarta rostos desconhecidos (economia de disco)

---

## Onde os Dados São Salvos

```
data/
├── raw/
│   ├── uploads/              ← Imagens enviadas manualmente pela API
│   └── camera_frames/        ← Rostos desconhecidos capturados pela câmera
│                               Nome: unknown_20240101_120000_000000.jpg
│
├── processed/
│   ├── aligned_faces/        ← Rostos alinhados pelo aligner.py
│   └── cropped_faces/        ← Rostos recortados pelo detector.py
│
└── snapshots/                ← Rostos identificados pelo matcher
                                Nome: 1_João_20240101_120000_000000.jpg
```

---

## Solução de Problemas

### `zsh: command not found: pip`

Use `pip3` ou instale com a flag de sistema:
```bash
pip3 install opencv-python
# ou
pip3 install opencv-python --break-system-packages
```

### `error: externally-managed-environment`

Use um ambiente virtual:
```bash
python3 -m venv venv
source venv/bin/activate
pip install opencv-python
```

### `OpenCV: not authorized to capture video`

Permissão de câmera negada no Mac. Vá em:
```
Configurações do Sistema → Privacidade e Segurança → Câmera → ✅ Terminal
```
Depois feche e reabra o terminal.

### Câmera IP não conecta

Verifique:
- Mac e câmera estão na **mesma rede Wi-Fi**
- IP correto (consulte o app da câmera ou o roteador)
- Usuário e senha corretos
- Porta correta (padrão RTSP: `554`)
- Tente fazer ping no IP: `ping 192.168.1.100`

### InsightFace não detecta rostos

- Verifique se a iluminação está adequada
- Reduza o `min_confidence` para `0.3` para ser mais permissivo
- Certifique-se de que o frame está em **RGB** (não BGR) ao passar para o detector
- O modelo `buffalo_l` é baixado automaticamente na primeira execução (~500MB)
