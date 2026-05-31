# Face Access System — Documentação Completa

Sistema de reconhecimento facial em tempo real usando OpenCV, InsightFace,
FastAPI e PostgreSQL. Captura frames de câmera, detecta rostos, identifica
pessoas cadastradas e notifica o frontend em tempo real.

---

## Sumário

1. [Visão Geral](#visão-geral)
2. [Arquitetura](#arquitetura)
3. [Estrutura de Arquivos](#estrutura-de-arquivos)
4. [Instalação](#instalação)
5. [Como Usar o Sistema](#como-usar-o-sistema)
6. [Como Cada Arquivo se Conecta](#como-cada-arquivo-se-conecta)
7. [Banco de Dados](#banco-de-dados)
8. [Sistema de Presença](#sistema-de-presença)
9. [API — Endpoints](#api--endpoints)
10. [Configurações](#configurações)
11. [Solução de Problemas](#solução-de-problemas)

---

## Visão Geral

O sistema funciona em dois modos:

**Modo Cadastro** — você envia uma foto ou tira uma pela câmera.
O sistema detecta o rosto, gera o vetor matemático (embedding) e salva no banco.

**Modo Reconhecimento** — a câmera fica ligada em loop contínuo.
Quando um rosto aparece, o sistema compara com os cadastros do banco.
Se reconhecer, salva o log e exibe no histórico. Só salva novamente
quando a pessoa sair do campo da câmera e voltar.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND (Streamlit)                        │
│  Cadastrar Pessoa | Câmera Ao Vivo | Histórico | Pessoas        │
└──────────────────┬──────────────────────────┬───────────────────┘
                   │ HTTP (REST)              │ Auto-atualização
                   ▼                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                       API (FastAPI)                             │
│  /health  /persons  /camera/start  /camera/stop  /camera/logs  │
└────┬──────────────┬───────────────────────────────────────────┘
     │              │
     ▼              ▼
PersonService   CameraService
cadastra        liga/desliga
pessoas         a câmera
     │              │
     ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PIPELINE DE VISÃO                             │
│  FrameReader → FaceDetector → FaceEmbedder → FaceMatcher       │
│                                    ↓                            │
│                           PresenceTracker                       │
│                    (salva só na entrada)                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BANCO DE DADOS (PostgreSQL)                    │
│       persons | face_embeddings | access_logs                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Estrutura de Arquivos

```
face_access_system/
│
├── app/
│   ├── main.py                    ← Sobe a API FastAPI
│   │
│   ├── api/
│   │   ├── routes_health.py       ← GET /health
│   │   ├── routes_persons.py      ← POST/GET/DELETE /persons
│   │   └── routes_camera.py       ← POST/GET /camera + /logs
│   │
│   ├── camera/
│   │   ├── frame_reader.py        ← Captura frames via OpenCV
│   │   ├── ip_camera.py           ← Monta URL RTSP da câmera IP
│   │   └── snapshot.py            ← Salva frames em disco
│   │
│   ├── face/
│   │   ├── detector.py            ← Detecta rostos (InsightFace)
│   │   ├── embedder.py            ← Gera vetores de 512 números
│   │   └── matcher.py             ← Compara vetores com o banco
│   │
│   ├── services/
│   │   ├── recognition_service.py ← Orquestra o reconhecimento
│   │   ├── person_service.py      ← Gerencia cadastro de pessoas
│   │   └── camera_service.py      ← Gerencia ciclo de vida da câmera
│   │
│   ├── workers/
│   │   └── camera_worker.py       ← Loop contínuo + rastreamento de presença
│   │
│   └── db/
│       ├── database.py            ← Conexão com PostgreSQL
│       └── models.py              ← Operações no banco (CRUD)
│
├── data/
│   ├── raw/uploads/               ← Fotos enviadas para cadastro
│   ├── raw/camera_frames/         ← Rostos desconhecidos salvos
│   ├── processed/cropped_faces/   ← Rostos recortados no cadastro
│   └── snapshots/                 ← Fotos salvas no reconhecimento
│
├── models/
│   └── insightface/               ← Modelos InsightFace (buffalo_l)
│
├── frontend/
│   ├── streamlit_app.py           ← Página inicial
│   └── pages/
│       ├── 1_Cadastrar_Pessoa.py  ← Cadastro via upload ou câmera
│       ├── 2_Camera_Ao_Vivo.py    ← Controle e monitoramento
│       ├── 3_Historico.py         ← Histórico de acessos
│       └── 4_Pessoas_Cadastradas.py ← Gerenciar pessoas
│
└── scripts/
    ├── test_camera_mac.py         ← Testa câmera do Mac
    ├── test_pipeline.py           ← Testa pipeline ao vivo
    ├── tirar_foto.py              ← Tira foto pela câmera
    └── register_from_folder.py    ← Cadastra pessoas em lote
```

---

## Instalação

### Requisitos

- Python 3.9 ou superior
- Mac, Linux ou Windows
- PostgreSQL instalado via Homebrew

### Passo a passo

**1. Instalar dependências Python**
```bash
pip3 install opencv-python insightface onnxruntime numpy \
             fastapi uvicorn psycopg2-binary python-multipart \
             streamlit requests pandas --break-system-packages
```

**2. Instalar e iniciar o PostgreSQL**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**3. Criar o banco de dados**
```bash
psql postgres
```
```sql
CREATE DATABASE face_access;
ALTER USER filipe WITH PASSWORD 'suasenha';
GRANT ALL PRIVILEGES ON DATABASE face_access TO filipe;
\q
```

**4. Criar as tabelas**

No TablePlus ou psql, execute:
```sql
CREATE TABLE persons (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE face_embeddings (
    id         SERIAL PRIMARY KEY,
    person_id  INTEGER REFERENCES persons(id) ON DELETE CASCADE,
    embedding  BYTEA NOT NULL,
    image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE access_logs (
    id         SERIAL PRIMARY KEY,
    person_id  INTEGER REFERENCES persons(id),
    similarity FLOAT,
    image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**5. Configurar a conexão com o banco**

Edite `app/db/database.py`:
```python
DB_CONFIG = {
    "host":     "127.0.0.1",
    "port":     5432,
    "database": "face_access",
    "user":     "filipe",       # seu usuário
    "password": "suasenha",     # sua senha
}
```

**6. Permissão de câmera no Mac**
```
Configurações do Sistema → Privacidade e Segurança → Câmera → ✅ Terminal
```

---

## Como Usar o Sistema

### 1. Iniciar os serviços

Abra **dois terminais** na pasta do projeto:

**Terminal 1 — API:**
```bash
uvicorn app.main:app --reload
```

**Terminal 2 — Frontend:**
```bash
streamlit run frontend/streamlit_app.py
```

Acesse o frontend em: `http://localhost:8501`

---

### 2. Cadastrar uma pessoa

Clique em **Cadastrar Pessoa** no menu lateral.

**Opção A — Upload de foto:**
- Selecione a aba **📁 Upload de Foto**
- Digite o nome da pessoa
- Clique em **Escolher arquivo** e selecione uma foto
- Clique em **✅ Cadastrar Pessoa**

**Opção B — Tirar foto pela câmera:**
- Selecione a aba **📷 Tirar Foto**
- Digite o nome da pessoa
- Permita o acesso à câmera no navegador
- Clique em **Take Photo**
- Clique em **✅ Cadastrar Pessoa**

**Dicas para uma boa foto:**
- Rosto centralizado e bem iluminado
- Fundo neutro
- Apenas um rosto na foto
- Foto nítida, sem borrão

---

### 3. Ligar a câmera

Clique em **Câmera Ao Vivo** no menu lateral e clique em **▶️ Ligar Câmera**.

O sistema vai:
- Conectar à câmera do Mac (índice 0)
- Carregar todos os cadastros do banco
- Iniciar o loop de reconhecimento em background

Quando reconhecer alguém, aparece:
```
🟢 Câmera ativa | 2 pessoa(s) cadastrada(s)
Pessoa: Filipe | Confiança: 78% | Horário: 30/05/2026 10:25:35
```

---

### 4. Ver o histórico

Clique em **Histórico** no menu lateral.

Exibe uma tabela com todos os acessos registrados:

| ID | Pessoa | Confiança | Data/Hora |
|---|---|---|---|
| 1 | Filipe | 78% | 30/05/2026 10:25:35 |
| 2 | Maria | 92% | 30/05/2026 11:10:02 |

Clique em **🔄 Atualizar** para ver os registros mais recentes.

---

### 5. Gerenciar pessoas

Clique em **Pessoas Cadastradas** no menu lateral.

Exibe todas as pessoas cadastradas com ID, nome e data de cadastro.
Para remover uma pessoa, selecione no menu e clique em **🗑️ Remover**.

> ⚠️ Remover uma pessoa apaga também todos os seus embeddings e não pode ser desfeito.

---

### 6. Desligar a câmera

Na página **Câmera Ao Vivo**, clique em **⏹️ Desligar Câmera**.

---

### 7. Parar os serviços

Em cada terminal, pressione `Ctrl + C`.

---

## Como Cada Arquivo se Conecta

### Pipeline de visão

```
frame_reader.py
    Abre a câmera e captura frames.
    Entrega frame_bgr (para salvar) e frame_rgb (para detectar).
        ↓
detector.py
    Recebe frame_rgb e passa pelo InsightFace.
    Detecta rostos e recorta cada um com OpenCV.
    Entrega lista de objetos Face + imagens recortadas.
        ↓
embedder.py
    Recebe cada objeto Face.
    Extrai o vetor de 512 números gerado pelo InsightFace.
    Normaliza o vetor para comparações precisas.
    Entrega array NumPy de 512 floats.
        ↓
matcher.py
    Recebe o vetor do rosto capturado.
    Compara com todos os vetores do banco via similaridade cosseno.
    Entrega MatchResult (matched, person_name, similarity).
        ↓
camera_worker.py
    Orquestra tudo em loop contínuo.
    Controla o rastreamento de presença.
    Salva no banco apenas na entrada.
```

---

## Banco de Dados

### Tabelas

```
persons           → quem está cadastrado no sistema
face_embeddings   → vetores dos rostos de cada pessoa
access_logs       → histórico de cada vez que alguém foi reconhecido
```

### Como o embedding é salvo

O vetor de 512 números é serializado para bytes antes de salvar:

```python
# Salvar — array → bytes
embedding_bytes = embedding.astype(np.float32).tobytes()

# Ler — bytes → array
embedding_array = np.frombuffer(bytes_do_banco, dtype=np.float32)
```

### Visualizar no TablePlus

Abra o TablePlus e conecte com:
```
Host:     127.0.0.1
Port:     5432
User:     filipe
Password: suasenha
Database: face_access
```

---

## Sistema de Presença

O sistema salva no banco **apenas quando a pessoa aparece** — não a cada frame.

```
Frame 1:  Filipe detectado → não estava → SALVA no banco
Frame 2:  Filipe detectado → já presente → ignora
Frame 3:  Filipe detectado → já presente → ignora
Frames 4-13: Filipe não detectado → contador de ausência sobe
Frame 14: Contador atingiu 10 → Filipe considerado ausente
Frame 15: Filipe detectado → não estava → SALVA no banco
```

### Por que 10 frames?

Com `frame_interval=0.1s`, 10 frames = 1 segundo de ausência.
Evita falsos saídas quando a pessoa pisca ou vira o rosto por um momento.

### Ajustar a sensibilidade

Em `app/workers/camera_worker.py`:
```python
FRAMES_PARA_SAIR = 10   # 1 segundo  — mais sensível
FRAMES_PARA_SAIR = 30   # 3 segundos — padrão recomendado
FRAMES_PARA_SAIR = 50   # 5 segundos — menos sensível
```

---

## API — Endpoints

Documentação interativa disponível em: `http://localhost:8000/docs`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Status da API e do banco |
| POST | `/persons/register` | Cadastra pessoa (multipart/form-data) |
| GET | `/persons/` | Lista todas as pessoas |
| GET | `/persons/{id}` | Busca pessoa por ID |
| DELETE | `/persons/{id}` | Remove pessoa e embeddings |
| POST | `/camera/start` | Inicia a câmera |
| POST | `/camera/stop` | Para a câmera |
| GET | `/camera/status` | Status atual da câmera |
| GET | `/camera/last` | Último reconhecimento |
| GET | `/camera/logs` | Histórico de acessos |
| WS | `/camera/ws` | WebSocket em tempo real |

---

## Configurações

### Limiar de similaridade (threshold)

Controla o quão rigoroso é o reconhecimento:

| Valor | Comportamento |
|---|---|
| `0.5` | Permissivo — mais falsos positivos |
| `0.6` | Equilibrado — recomendado para uso geral |
| `0.7` | Restritivo — mais falsos negativos |

Para ajustar, mude ao ligar a câmera:
```
POST /camera/start?threshold=0.7
```

### Câmera IP

Para usar uma câmera IP em vez da câmera do Mac:
```
POST /camera/start?source=rtsp://user:senha@192.168.1.100:554/stream
```

URLs por fabricante:

| Marca | URL |
|---|---|
| Hikvision | `rtsp://user:pass@IP:554/Streaming/Channels/101` |
| Dahua | `rtsp://user:pass@IP:554/cam/realmonitor?channel=1` |
| Intelbras | `rtsp://user:pass@IP:554/cam/realmonitor?channel=1` |

---

## Solução de Problemas

### API não sobe
```bash
# Verifique se o PostgreSQL está rodando
brew services list

# Inicie se necessário
brew services start postgresql@15
```

### Câmera não abre no terminal
```
Configurações do Sistema → Privacidade e Segurança → Câmera → ✅ Terminal
```

### Câmera não abre no navegador (página de cadastro)
Clique no cadeado na barra de endereço e permita o acesso à câmera.

### Pessoa não é reconhecida
- Verifique se foi cadastrada em **Pessoas Cadastradas**
- Tente diminuir o threshold: `POST /camera/start?threshold=0.5`
- Certifique-se de boa iluminação na câmera

### Histórico não aparece
- Verifique se a câmera está ligada na página **Câmera Ao Vivo**
- Confirme que há pessoas cadastradas no banco
- Acesse `http://localhost:8000/camera/logs` para verificar os dados

### InsightFace demora na primeira execução
Normal — está baixando o modelo `buffalo_l` (~500MB).
Depois fica em cache em `models/insightface/`.

---

## Segurança

### 1. Credenciais no .env

As credenciais do banco e a API Key nunca ficam escritas no código.
Ficam no arquivo `.env` que é ignorado pelo Git.

**Configurar:**
```bash
cp .env.example .env
# Edite o .env com suas credenciais reais
```

**Gerar uma API Key segura:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Cole o resultado no `.env`:
```
API_KEY=a1b2c3d4e5f6...
```

---

### 2. API Key

Todos os endpoints da API exigem autenticação via header `X-API-Key`.
Sem a chave correta, a API retorna erro **403 Forbidden**.

**Exemplo de requisição autenticada:**
```bash
curl -H "X-API-Key: sua_chave" http://localhost:8000/persons/
```

O frontend lê a chave automaticamente do `.env` e a envia em todas as requisições.

**Como funciona:**
```
Cliente envia → X-API-Key: sua_chave
API verifica  → chave correta? → permite
               → chave errada? → 403 Forbidden
```

---

### 3. O que nunca commitar no GitHub

```
❌ .env                  → credenciais reais
❌ data/                 → fotos de pessoas
❌ models/               → modelos InsightFace (muito grandes)
```

Todos já estão no `.gitignore`.

---

### 4. Instalar dependência de segurança

```bash
pip3 install python-dotenv --break-system-packages
```

**Por que?** O `python-dotenv` é a biblioteca que lê o arquivo `.env`
e carrega as variáveis para o sistema. Sem ela, `load_dotenv()` não funciona.