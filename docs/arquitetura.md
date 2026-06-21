# Face Access System — Arquitetura e Pipeline

---

## Sumário

1. [Modelo de Dados](#modelo-de-dados)
2. [Regra de Acesso](#regra-de-acesso)
3. [Pipeline de Visão](#pipeline-de-visão)
4. [Arquitetura Completa](#arquitetura-completa)
5. [Integração FaceNotify](#integração-facenotify)
6. [API — Endpoints](#api--endpoints)
7. [Banco de Dados PostgreSQL](#banco-de-dados-postgresql)
8. [Segurança](#segurança)
9. [Solução de Problemas](#solução-de-problemas)

---

## Modelo de Dados

A estrutura segue uma hierarquia. Cada nível depende do anterior:

```
horarios → turmas → alunos → face_embeddings
                        └──→ access_logs
```

- **horarios** — turno com nome e período (hora início/fim). Ex: Matutino 07:00–12:20.
- **turmas** — vinculadas a um horário e a um ano letivo. Ex: "3º Ano A", 2026.
- **alunos** — cada aluno pertence a uma turma. É a pessoa reconhecida pela câmera.
- **face_embeddings** — vetor de 512 números gerado a partir da foto do aluno.
- **access_logs** — histórico de cada reconhecimento com o resultado de acesso.

A decisão de acesso percorre: `aluno → turma → horario (início, fim)`.

---

## Regra de Acesso

| Situação | Resultado |
|---|---|
| Rosto não reconhecido | ⛔ Negado — não cadastrado |
| Reconhecido, sem turma ou horário | ⛔ Negado — configuração incompleta |
| Reconhecido, fora do horário da turma | ⛔ Negado — fora do horário permitido |
| Reconhecido, dentro do horário da turma | ✅ Liberado |

Os limites são **inclusivos**: turno 07:00–12:20 libera exatamente às 07:00 e às 12:20.

---

## Pipeline de Visão

```
┌──────────────────────────────────────────────────────────┐
│                     CameraWorker                          │
│                                                           │
│  FrameReader ──→ frame_bgr + frame_rgb                    │
│                          │                                │
│                  FaceDetector                             │
│                     has_faces?                            │
│                    /         \                            │
│                  NÃO         SIM                          │
│               descarta    FaceEmbedder                    │
│                          vetor 512D                       │
│                              │                            │
│                         FaceMatcher                       │
│                        similarity ≥ 0.6?                  │
│                       /              \                    │
│                     NÃO             SIM                   │
│              salva em            avalia horário           │
│          camera_frames/          da turma                 │
│           (unknown)             /        \                │
│                             fora       dentro             │
│                           NEGADO      LIBERADO            │
│                               \        /                  │
│                          salva em access_logs             │
│                                  │                        │
│                         notify_service.py                 │
│                      (se reconhecido e tem                │
│                       supabase_dependent_id)              │
└──────────────────────────────────────────────────────────┘
```

### Decisão de salvamento de imagens

| Situação | Destino |
|---|---|
| Frame sem rosto | Descartado na memória |
| Rosto identificado | `data/snapshots/` |
| Rosto desconhecido | `data/raw/camera_frames/` |

---

## Arquitetura Completa

```
┌──────────────────────────────────────────────────────────┐
│                  FRONTEND (Streamlit :8501)               │
│   Horários │ Turmas │ Cadastrar Aluno │ Câmera │ Histórico│
└─────────────────────────┬────────────────────────────────┘
                          │ HTTP + X-API-Key
                          ▼
┌──────────────────────────────────────────────────────────┐
│                    API (FastAPI :8000)                    │
│      /horarios  /turmas  /alunos  /camera  /health        │
└──────────┬───────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│           PIPELINE DE VISÃO (background thread)           │
│   FrameReader → FaceDetector → FaceEmbedder → FaceMatcher │
│                                      ↓                    │
│                        avaliação de acesso por horário    │
│                                      ↓                    │
│                            notify_service.py              │
└──────────┬───────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
┌──────────────────┐         ┌────────────────────────────┐
│    PostgreSQL     │         │   Supabase Edge Function   │
│  (banco local)   │         │   notify-recognition       │
│                  │         │                            │
│  horarios        │         │  1. valida webhook secret  │
│  turmas          │         │  2. salva recognition_event│
│  alunos          │         │  3. busca fcm_tokens       │
│  face_embeddings │         │  4. envia via FCM v1 API   │
│  access_logs     │         └──────────────┬─────────────┘
└──────────────────┘                        │
                                            ▼
                                   FCM (Firebase)
                                            │
                                            ▼
                                    FaceNotify (mobile)
                                   push + Realtime
```

O modelo InsightFace é carregado **uma única vez** e compartilhado entre cadastro e câmera, com inferência serializada por lock para ser thread-safe.

---

## Integração FaceNotify

Quando um rosto é reconhecido, `notify_service.py` envia um POST para a Supabase Edge Function:

```
notify_service.py
        │
        ├── Verifica supabase_dependent_id (aluno precisa ter esse ID cadastrado)
        ├── Aplica cooldown: 30s por (dependent_id, camera_id)
        └── POST https://<projeto>.supabase.co/functions/v1/notify-recognition
                Headers:
                  x-webhook-secret: <WEBHOOK_SECRET>
                  Authorization: Bearer <SUPABASE_ANON_KEY>
                Body:
                  person_id, person_name, location, timestamp, confidence
```

A Edge Function (`supabase/functions/notify-recognition/index.ts`):
1. Valida `x-webhook-secret`
2. Busca o `profile_id` (responsável) pelo `dependent_id`
3. Salva o evento em `recognition_events` (Supabase Postgres)
4. Busca todos os `fcm_tokens` do responsável
5. Gera um JWT OAuth2 usando a service account do Firebase
6. Envia push via **FCM v1 API** (`/messages:send`)

O FaceNotify recebe o evento por duas vias simultâneas:
- **Push FCM** — notificação mesmo com o app fechado
- **Supabase Realtime** — atualiza a lista em tempo real com o app aberto

### Cooldown

O cooldown é aplicado **por par (dependent_id, camera_id)**, em memória no processo Python. Isso significa que a mesma pessoa pode gerar notificações em câmeras diferentes sem esperar o cooldown, mas não gera duplicatas na mesma câmera.

```
Variável: NOTIFY_COOLDOWN_SECONDS (padrão: 30)
```

---

## API — Endpoints

Documentação interativa em `http://localhost:8000/docs`. Todos os endpoints exigem `X-API-Key`.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Status da API e do banco |
| GET | `/horarios/` | Lista horários |
| POST | `/horarios/` | Cria horário |
| DELETE | `/horarios/{id}` | Remove (bloqueado se houver turmas) |
| GET | `/turmas/` | Lista turmas |
| POST | `/turmas/` | Cria turma |
| DELETE | `/turmas/{id}` | Remove turma |
| POST | `/alunos/register` | Cadastra aluno com foto |
| GET | `/alunos/` | Lista alunos |
| PATCH | `/alunos/{id}/turma` | Muda turma de um aluno |
| DELETE | `/alunos/{id}` | Remove aluno e seus dados |
| POST | `/camera/start` | Inicia a câmera |
| POST | `/camera/stop` | Para a câmera |
| GET | `/camera/status` | Status da câmera |
| GET | `/camera/last` | Último reconhecimento |
| GET | `/camera/logs` | Histórico de acessos |
| WS | `/camera/ws` | Notificações em tempo real |

---

## Banco de Dados PostgreSQL

### Comportamento na exclusão

| Você apaga | O que acontece com os dependentes |
|---|---|
| Horário | Bloqueado se houver turmas usando (RESTRICT) |
| Turma | Alunos ficam sem turma (SET NULL) → acesso negado |
| Aluno | Embeddings e logs apagados junto (CASCADE) |

### Consultas úteis

```bash
psql -d face_access -c "SELECT * FROM horarios;"
psql -d face_access -c "SELECT id, nome, turma_id FROM alunos;"
psql -d face_access -c "SELECT * FROM access_logs ORDER BY created_at DESC LIMIT 20;"
```

> Evite `SELECT *` em `face_embeddings` — a coluna de embedding é binária.

---

## Segurança

- Credenciais no `.env` — nunca no código. `.env` está no `.gitignore`.
- API local protegida por `X-API-Key` (comparação em tempo constante).
- Edge Function valida `x-webhook-secret` antes de qualquer operação.
- `service_role_key` do Supabase fica exclusivamente na Edge Function (env var segura).
- `FIREBASE_PRIVATE_KEY` armazenada como base64 puro nos secrets da Edge Function.
- Não commitar: `.env`, `data/` (fotos), `models/` (modelos ~500MB).

---

## Solução de Problemas

### Tabelas já existem no banco

```bash
psql -d face_access -c "DROP TABLE IF EXISTS access_logs, face_embeddings, alunos, turmas, horarios CASCADE;"
psql -d face_access -f scripts/init_db.sql
```

### Aluno reconhecido mas sem notificação no FaceNotify

Verifique se o aluno tem `supabase_dependent_id` cadastrado. Sem esse campo, `notify_service.py` ignora o reconhecimento. Verifique também se `EDGE_FUNCTION_URL`, `WEBHOOK_SECRET` e `SUPABASE_ANON_KEY` estão no `.env`.

### Aluno reconhecido mas sempre negado

Verifique se ele tem turma e se a turma tem horário. Aluno sem turma cai em "sem turma/horário definido".

### Câmera IP não conecta

- Mac e câmera na mesma rede
- Teste: `ping <IP_da_câmera>`
- URLs RTSP por fabricante:

| Marca | URL |
|---|---|
| Hikvision | `rtsp://user:pass@IP:554/Streaming/Channels/101` |
| Dahua / Intelbras | `rtsp://user:pass@IP:554/cam/realmonitor?channel=1` |
| Genérica | `rtsp://user:pass@IP:554/stream1` |

### InsightFace demora na primeira execução

Normal — baixa o modelo `buffalo_l` (~500MB). Fica em cache em `models/insightface/` nas próximas execuções.
