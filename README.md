# Face Access System

Sistema de reconhecimento facial em tempo real com controle de acesso por horário, construído com Python, FastAPI, InsightFace e PostgreSQL. Integrado ao app mobile **FaceNotify** para envio de notificações push quando um rosto é identificado pela câmera.

---

## Visão Geral

```
Câmera (local ou IP)
        │
        ▼
CameraWorker (background thread)
        │
   ┌────┴────┐
   │         │
   ▼         ▼
Reconhecido  Desconhecido
   │
   ├── Verifica horário da turma
   ├── Salva em access_logs (PostgreSQL)
   └── notify_service.py
              │
              ▼
   Supabase Edge Function
              │
              ├── Salva em recognition_events
              └── FCM v1 API → FaceNotify (push)
```

---

## Tecnologias

| Componente | Tecnologia |
|---|---|
| Reconhecimento facial | InsightFace (buffalo_l — RetinaFace + ArcFace) |
| Captura de vídeo | OpenCV |
| Inferência | ONNX Runtime |
| API REST | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Banco de dados local | PostgreSQL |
| Notificações | Supabase Edge Function + Firebase FCM v1 |

---

## Estrutura do Projeto

```
reconhecimento_facial/
├── app/
│   ├── camera/
│   │   ├── frame_reader.py        ← captura frames (local ou RTSP)
│   │   ├── ip_camera.py           ← monta URL RTSP
│   │   └── snapshot.py            ← salva frames em disco
│   ├── face/
│   │   ├── detector.py            ← detecta rostos (InsightFace)
│   │   ├── embedder.py            ← gera vetores de 512 dimensões
│   │   ├── matcher.py             ← compara vetores (similaridade cosseno)
│   │   ├── aligner.py             ← alinha rostos
│   │   └── quality.py             ← verifica qualidade da imagem
│   ├── services/
│   │   ├── recognition_service.py ← orquestra o reconhecimento
│   │   ├── person_service.py      ← gerencia cadastros
│   │   ├── face_service.py        ← gerencia rostos
│   │   ├── camera_service.py      ← gerencia câmeras
│   │   └── notify_service.py      ← envia eventos para o FaceNotify
│   ├── workers/
│   │   └── camera_worker.py       ← loop contínuo em background
│   └── db/
│       ├── database.py
│       ├── models.py
│       └── schemas.py
├── docs/
│   └── arquitetura.md             ← pipeline completo e modelo de dados
├── documentacao.md                ← referência dos módulos Python
├── scripts/
│   ├── init_db.sql
│   ├── test_camera_mac.py
│   └── test_camera.py
├── supabase/
│   └── functions/
│       └── notify-recognition/
│           └── index.ts           ← Edge Function (FCM v1 API)
├── .env.example
└── requirements.txt
```

---

## Instalação

### Requisitos

- Python 3.9+
- PostgreSQL 15+ (Mac: via Homebrew)
- Conta no Supabase (para integração com FaceNotify)
- Projeto Firebase com FCM habilitado (para push)

### 1. Clone o repositório

```bash
git clone https://github.com/aksbarbosa/reconhecimento_facial.git
cd reconhecimento_facial
```

### 2. Ambiente virtual

```bash
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 3. Dependências Python

```bash
pip install -r requirements.txt
```

Ou manualmente:
```bash
pip install opencv-python insightface onnxruntime numpy \
            fastapi uvicorn psycopg2-binary python-multipart \
            python-dotenv streamlit requests pandas httpx
```

### 4. PostgreSQL

```bash
brew install postgresql@15      # Mac
brew services start postgresql@15
psql postgres -c "CREATE DATABASE face_access;"
psql -d face_access -f scripts/init_db.sql
```

### 5. Variáveis de ambiente

```bash
cp .env.example .env
# edite o .env com suas credenciais
```

Conteúdo do `.env`:

```env
# Banco de dados
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=face_access
DB_USER=seu_usuario
DB_PASSWORD=suasenha

# API local
API_KEY=gere_com_python3_-c_"import_secrets;print(secrets.token_hex(32))"

# Integração FaceNotify
EDGE_FUNCTION_URL=https://<projeto>.supabase.co/functions/v1/notify-recognition
WEBHOOK_SECRET=mesmo_valor_configurado_na_edge_function
SUPABASE_ANON_KEY=sua_anon_key_do_supabase

# Câmera
CAMERA_ID=cam_001
CAMERA_LABEL=Câmera - Entrada Principal
CAMERA_ADDRESS=Rua das Flores, 123
CAMERA_CITY=São Paulo
CAMERA_STATE=SP

# Cooldown entre notificações da mesma pessoa na mesma câmera (segundos)
NOTIFY_COOLDOWN_SECONDS=30
```

### 6. Permissão de câmera (Mac)

```
Configurações do Sistema → Privacidade e Segurança → Câmera → ✅ Terminal
```

---

## Subir o Sistema

Dois terminais na raiz do projeto:

```bash
# Terminal 1 — API
uvicorn app.main:app --reload --env-file .env

# Terminal 2 — Frontend
streamlit run frontend/streamlit_app.py
```

- Frontend: `http://localhost:8501`
- API + docs: `http://localhost:8000/docs`

---

## Como Usar

A ordem de cadastro importa — cada nível depende do anterior:

1. **Horários** → crie os turnos (Matutino, Vespertino, Noturno)
2. **Turmas** → vincule cada turma a um horário e ano letivo
3. **Alunos** → cadastre com foto; o sistema gera o embedding automaticamente
4. **Câmera** → ligue na página "Câmera Ao Vivo" e veja o reconhecimento em tempo real

Ao reconhecer um rosto dentro do horário da turma, o sistema:
- Exibe o banner de acesso liberado na tela
- Salva o evento no PostgreSQL local
- Envia notificação push para o responsável via FaceNotify

---

## Integração com FaceNotify

App mobile: **https://github.com/aksbarbosa/facenotify**

Veja `docs/arquitetura.md` para o pipeline completo e o README do FaceNotify para a configuração do app mobile.

O arquivo `app/services/notify_service.py` é responsável por enviar cada reconhecimento para a Supabase Edge Function. Ele aplica um **cooldown de 30 segundos por pessoa por câmera** para evitar notificações duplicadas.

Variáveis de ambiente necessárias para a integração:

| Variável | Descrição |
|---|---|
| `EDGE_FUNCTION_URL` | URL da Edge Function no Supabase |
| `WEBHOOK_SECRET` | Segredo compartilhado com a Edge Function |
| `SUPABASE_ANON_KEY` | Chave anon do projeto Supabase |
| `NOTIFY_COOLDOWN_SECONDS` | Intervalo mínimo entre notificações (padrão: 30) |

---

## Segurança

- Credenciais no `.env` — nunca no código
- `.env` e `data/` estão no `.gitignore`
- API local protegida por `X-API-Key` em todos os endpoints
- Edge Function valida `x-webhook-secret` antes de qualquer operação
- `service_role_key` do Supabase fica exclusivamente na Edge Function

---

## Documentação Adicional

| Arquivo | Conteúdo |
|---|---|
| `docs/arquitetura.md` | Pipeline de visão, modelo de dados, regra de acesso |
| `documentacao.md` | Referência detalhada dos módulos Python |
| `supabase/functions/notify-recognition/index.ts` | Edge Function completa |
