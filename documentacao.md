# Face Access System — Referência dos Módulos

Documentação técnica dos módulos Python que compõem o pipeline de visão computacional.

---

## Sumário

1. [frame_reader.py](#frame_readerpy)
2. [detector.py](#detectorpy)
3. [embedder.py](#embedderpy)
4. [matcher.py](#matcherpy)
5. [camera_worker.py](#camera_workerpy)
6. [notify_service.py](#notify_servicepy)
7. [Pipeline completo](#pipeline-completo)
8. [Configurações](#configurações)
9. [Onde os dados são salvos](#onde-os-dados-são-salvos)
10. [Solução de problemas](#solução-de-problemas)

---

## frame_reader.py

`app/camera/frame_reader.py`

Abre a conexão com a câmera via OpenCV e captura frames continuamente. Funciona com câmera local (índice `0`) ou câmera IP (URL RTSP).

Entrega dois formatos do mesmo frame:
- **BGR** — padrão OpenCV, usado para salvar imagens em disco
- **RGB** — formato esperado pelo InsightFace

```python
from app.camera.frame_reader import FrameReader

reader = FrameReader(0)               # câmera local
# reader = FrameReader("rtsp://...")  # câmera IP

frame_bgr, frame_rgb = reader.read_frame()
reader.release()
```

---

## detector.py

`app/face/detector.py`

Detecta rostos em frames usando InsightFace (modelo `buffalo_l` com RetinaFace). Recorta cada rosto detectado e filtra detecções abaixo do limiar de confiança configurado (padrão: 50%).

```python
from app.face.detector import FaceDetector

detector = FaceDetector(model_root="models/insightface", min_confidence=0.5)
result = detector.process_frame(frame_bgr, frame_rgb)

if result["has_faces"]:
    crops      = result["crops"]        # imagens recortadas
    faces      = result["faces"]        # objetos Face do InsightFace
    frame_debug= result["frame_debug"]  # frame com retângulos desenhados
```

---

## embedder.py

`app/face/embedder.py`

Extrai o embedding (vetor de 512 dimensões) de cada rosto. Normaliza o vetor para garantir comparações precisas por similaridade de cosseno.

```python
from app.face.embedder import FaceEmbedder

embedder = FaceEmbedder()
embedding = embedder.get_embedding(face)   # face = objeto Face do InsightFace

if embedder.is_valid(embedding):
    print(embedding.shape)   # (512,)
```

---

## matcher.py

`app/face/matcher.py`

Compara o embedding de um rosto capturado com todos os cadastros. Usa similaridade por cosseno e retorna o candidato mais similar, desde que supere o limiar configurado (padrão: 60%).

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
    print(f"Desconhecido — similaridade mais alta: {result.similarity:.0%}")
```

---

## camera_worker.py

`app/workers/camera_worker.py`

Orquestra o pipeline completo em loop contínuo, rodando em uma thread separada para não bloquear a API ou o frontend.

```python
from app.workers.camera_worker import CameraWorker

worker = CameraWorker(
    camera_source=0,        # 0 = câmera local, ou URL RTSP
    candidates=candidates,  # lista de cadastros do banco
    threshold=0.6,          # limiar de similaridade
    frame_interval=0.1,     # intervalo entre frames (~10fps)
    save_unknown=True,      # salvar rostos desconhecidos?
)

worker.start()

resultado = worker.get_last_result()   # consulta o último resultado
print(resultado)

worker.stop()
```

O worker dispara callbacks `on_recognized` e `on_unknown` para o WebSocket `/camera/ws`, atualizando o frontend em tempo real.

---

## notify_service.py

`app/services/notify_service.py`

Envia cada reconhecimento para a Supabase Edge Function, que salva o evento no banco e dispara o push para o responsável via FCM.

O serviço aplica um **cooldown por (dependent_id, camera_id)**: a mesma pessoa na mesma câmera só gera uma notificação a cada `NOTIFY_COOLDOWN_SECONDS` segundos (padrão: 30).

```python
from app.services.notify_service import notify_recognition

# resultado vem do CameraWorker após um reconhecimento
notify_recognition({
    "supabase_dependent_id": "uuid-do-dependente",
    "aluno_nome": "João Silva",
    "similarity": 0.92,
})
```

### Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `EDGE_FUNCTION_URL` | URL da Edge Function no Supabase |
| `WEBHOOK_SECRET` | Segredo compartilhado com a Edge Function |
| `SUPABASE_ANON_KEY` | Chave anon do Supabase (Authorization header) |
| `CAMERA_ID` | ID da câmera (ex: `cam_001`) |
| `CAMERA_LABEL` | Nome legível (ex: `Câmera - Entrada`) |
| `CAMERA_ADDRESS` | Endereço físico |
| `CAMERA_CITY` | Cidade |
| `CAMERA_STATE` | Estado (ex: `SP`) |
| `NOTIFY_COOLDOWN_SECONDS` | Cooldown em segundos (padrão: `30`) |

O aluno precisa ter `supabase_dependent_id` cadastrado no PostgreSQL local. Sem esse campo, o serviço ignora o reconhecimento e registra um aviso no log.

---

## Pipeline Completo

```python
from app.camera.frame_reader import FrameReader
from app.face.detector import FaceDetector
from app.face.embedder import FaceEmbedder
from app.face.matcher import FaceMatcher

candidates = [
    {"person_id": 1, "person_name": "João", "embedding": vetor_joao},
]

reader   = FrameReader(0)
detector = FaceDetector()
embedder = FaceEmbedder()
matcher  = FaceMatcher(threshold=0.6)

frame_bgr, frame_rgb = reader.read_frame()
result = detector.process_frame(frame_bgr, frame_rgb)

if result["has_faces"]:
    for face in result["faces"]:
        embedding = embedder.get_embedding(face)
        match = matcher.match(embedding, candidates)
        if match.matched:
            print(f"{match.person_name} — {match.similarity:.0%}")
        else:
            print("Desconhecido")

reader.release()
```

---

## Configurações

### Limiar de similaridade (`threshold`)

| Valor | Comportamento |
|---|---|
| `0.5` | Permissivo — mais falsos positivos |
| `0.6` | Equilibrado — recomendado |
| `0.7` | Restritivo — mais falsos negativos |

### Intervalo entre frames (`frame_interval`)

| Valor | Taxa aproximada | CPU |
|---|---|---|
| `0.033` | ~30 fps | Alto |
| `0.1` | ~10 fps | Médio (padrão) |
| `0.5` | ~2 fps | Baixo |

### Salvar desconhecidos (`save_unknown`)

- `True` — salva em `data/raw/camera_frames/` (padrão)
- `False` — descarta (economia de disco)

---

## Onde os Dados São Salvos

```
data/
├── raw/
│   ├── uploads/              ← imagens enviadas manualmente pela API
│   └── camera_frames/        ← rostos desconhecidos capturados
│                               nome: unknown_20240101_120000_000000.jpg
├── processed/
│   ├── aligned_faces/        ← rostos alinhados pelo aligner.py
│   └── cropped_faces/        ← rostos recortados pelo detector.py
└── snapshots/                ← rostos identificados
                                nome: 1_João_20240101_120000_000000.jpg
```

---

## Solução de Problemas

### `pip: command not found`

```bash
pip3 install opencv-python   # ou com --break-system-packages no Mac sem venv
```

### `error: externally-managed-environment`

Use um ambiente virtual:
```bash
python3 -m venv venv && source venv/bin/activate
```

### `OpenCV: not authorized to capture video`

```
Configurações do Sistema → Privacidade e Segurança → Câmera → ✅ Terminal
```

### InsightFace não detecta rostos

- Verifique iluminação e qualidade da imagem
- Reduza `min_confidence` para `0.3`
- Certifique-se de que o frame está em **RGB** ao passar para o detector
- O modelo `buffalo_l` (~500MB) é baixado automaticamente na primeira execução

### Notificação não chega no FaceNotify

1. Verifique se `EDGE_FUNCTION_URL`, `WEBHOOK_SECRET` e `SUPABASE_ANON_KEY` estão no `.env`
2. Verifique se o aluno tem `supabase_dependent_id` cadastrado
3. Veja os logs do `notify_service`: mensagens `INFO` indicam envio bem-sucedido, `WARNING` e `ERROR` indicam falha
4. Verifique os logs da Edge Function no painel do Supabase
