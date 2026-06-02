# Face Access System — Guia de Uso

Sistema de reconhecimento facial escolar em tempo real. Captura frames de câmera,
detecta o rosto de alunos cadastrados e **libera ou nega o acesso conforme o
horário da turma** de cada aluno. Usa OpenCV, InsightFace, FastAPI e PostgreSQL.

---

## Sumário

1. [Visão Geral](#visão-geral)
2. [Modelo de Dados](#modelo-de-dados)
3. [Regra de Acesso](#regra-de-acesso)
4. [Instalação](#instalação)
5. [Subir o Sistema](#subir-o-sistema)
6. [Como Usar (passo a passo)](#como-usar-passo-a-passo)
7. [Arquitetura e Pipeline](#arquitetura-e-pipeline)
8. [API — Endpoints](#api--endpoints)
9. [Banco de Dados](#banco-de-dados)
10. [Segurança](#segurança)
11. [Solução de Problemas](#solução-de-problemas)

---

## Visão Geral

O sistema funciona em dois modos.

**Modo Cadastro** — você cadastra horários, turmas e alunos. Ao cadastrar um
aluno, envia uma foto; o sistema detecta o rosto, gera o vetor matemático
(embedding) e salva no banco, vinculando o aluno a uma turma.

**Modo Reconhecimento** — a câmera fica ligada em loop. Quando um rosto aparece,
o sistema compara com os cadastros. Se reconhece o aluno, verifica se o horário
atual está dentro da janela do turno da turma dele e decide o acesso. Cada entrada
é registrada no histórico, com o resultado (liberado ou negado). Só registra de
novo quando o aluno sai do campo da câmera e volta.

---

## Modelo de Dados

A estrutura segue uma hierarquia. Cada nível depende do anterior:

```
horarios  →  turmas  →  alunos  →  face_embeddings
(turno +      (3º Ano A,  (a pessoa     (vetor do rosto)
 período)      vinculada    reconhecida,
               a um horário)  vinculada    alunos  →  access_logs
                              a uma turma)             (histórico de acessos)
```

- **horarios** — cada horário é um turno com nome e período (hora de início e fim). Ex: Matutino, 07:00–12:20.
- **turmas** — cada turma pertence a um horário e a um ano letivo. Ex: "3º Ano A", turno Matutino, 2026.
- **alunos** — cada aluno pertence a uma turma. É a pessoa reconhecida pela câmera.
- **face_embeddings** — o vetor de 512 números gerado pela foto do aluno.
- **access_logs** — o registro de cada reconhecimento, com o resultado de acesso.

O acesso de um aluno é decidido percorrendo essa cadeia:
`aluno → turma → horario (início, fim)`.

---

## Regra de Acesso

Ao reconhecer um rosto, o sistema avalia quatro situações:

| Situação | Resultado | Mensagem exibida |
|---|---|---|
| Rosto não reconhecido | ⛔ Negado | Rosto não cadastrado |
| Reconhecido, sem turma/horário | ⛔ Negado | Reconhecido, mas sem turma/horário definido |
| Reconhecido, fora do horário da turma | ⛔ Negado | Reconhecido, mas horário não permitido |
| Reconhecido, dentro do horário da turma | ✅ Liberado | Acesso liberado |

Os limites do horário são **inclusivos**: um turno de 07:00 às 12:20 libera o
acesso exatamente às 07:00 e às 12:20.

---

## Instalação

### Requisitos

- Python 3.9 ou superior
- Mac, Linux ou Windows
- PostgreSQL (no Mac, via Homebrew)

### Passo a passo

**1. Instalar dependências Python**
```bash
pip3 install opencv-python insightface onnxruntime numpy \
             fastapi uvicorn psycopg2-binary python-multipart python-dotenv \
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
\q
```

**4. Criar as tabelas**

A partir da raiz do projeto:
```bash
psql -U seu_usuario -d face_access -f scripts/init_db.sql
```

Você deve ver cinco `CREATE TABLE` e a mensagem "Banco criado com sucesso".
O script já insere os três turnos padrão (Matutino, Vespertino, Noturno).

> Se aparecer `NOTICE: ... already exists, skipping`, é sinal de que existem
> tabelas antigas no banco. Veja [Solução de Problemas](#solução-de-problemas).

**5. Configurar o `.env`**
```bash
cp .env.example .env
# edite o .env com suas credenciais
```

O `.env` precisa conter:
```
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=face_access
DB_USER=seu_usuario
DB_PASSWORD=suasenha
API_KEY=cole_aqui_uma_chave_gerada
```

Gere uma API Key segura:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**6. Permissão de câmera no Mac**
```
Configurações do Sistema → Privacidade e Segurança → Câmera → ✅ Terminal
```

---

## Subir o Sistema

Dois terminais na raiz do projeto.

**Terminal 1 — API:**
```bash
uvicorn app.main:app --reload --env-file .env
```

**Terminal 2 — Frontend:**
```bash
streamlit run frontend/streamlit_app.py
```

Acesse o frontend em `http://localhost:8501` e a documentação da API em
`http://localhost:8000/docs`.

---

## Como Usar (passo a passo)

A ordem importa, porque cada cadastro depende do anterior.

### 1. Criar um horário

Na página **🕒 Horários**, defina um turno com nome, hora de início e hora de fim.
Os três turnos padrão (Matutino, Vespertino, Noturno) já vêm cadastrados — você
pode usá-los ou criar outros.

### 2. Criar uma turma

Na página **🏫 Turmas**, preencha:
- **Nome** (ex: "3º Ano A")
- **Série / Nível** (ex: "3º Ano")
- **Turno** — escolhido da lista de horários
- **Ano Letivo** (ex: 2026)

### 3. Cadastrar um aluno

Na página **📸 Cadastrar Aluno**, digite o nome, escolha a **turma** e envie uma
foto (upload ou câmera). O sistema detecta o rosto e salva o embedding.

Dicas para a foto: rosto centralizado, boa iluminação, fundo neutro, apenas um
rosto, foto nítida.

### 4. Ligar a câmera

Na página **🎥 Câmera Ao Vivo**, clique em **▶️ Ligar Câmera**. Ao reconhecer um
aluno, aparece o banner grande de acesso:

```
✅ ACESSO LIBERADO        ou        ⛔ ACESSO NEGADO
Acesso liberado                      Reconhecido, mas horário não permitido
Aluno: Filipe | Turma: 3º Ano A | Turno: Matutino | Confiança: 78%
```

### 5. Ver o histórico

Na página **📋 Histórico**, veja todos os reconhecimentos com aluno, turma, turno,
confiança e o resultado (Liberado/Negado).

### 6. Gerenciar alunos

Na página **👥 Alunos Cadastrados**, veja todos os alunos com sua turma, mude a
turma de um aluno, ou remova um aluno (apaga também seus embeddings e histórico).

---

## Arquitetura e Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│                   FRONTEND (Streamlit)                        │
│  Horários | Turmas | Cadastrar Aluno | Câmera | Histórico     │
└───────────────────────┬───────────────────────────────────────┘
                        │ HTTP (REST) + API Key
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                       API (FastAPI)                           │
│  /horarios  /turmas  /alunos  /camera  /health                │
└───────────┬──────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────┐
│                  PIPELINE DE VISÃO (background)               │
│  FrameReader → FaceDetector → FaceEmbedder → FaceMatcher      │
│                                    ↓                          │
│                       avaliação de acesso por horário         │
│                       (aluno → turma → horário)               │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                BANCO DE DADOS (PostgreSQL)                    │
│   horarios | turmas | alunos | face_embeddings | access_logs  │
└──────────────────────────────────────────────────────────────┘
```

O modelo InsightFace é carregado **uma única vez** (em `app/face/engine.py`) e
compartilhado entre o cadastro e a câmera, com a inferência serializada por um
lock para ser segura entre threads.

Notificações em tempo real saem por callbacks (`on_recognized`/`on_unknown`)
que o `CameraWorker` dispara para o WebSocket `/camera/ws`.

---

## API — Endpoints

Documentação interativa em `http://localhost:8000/docs`. Todos os endpoints HTTP
exigem o header `X-API-Key`.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Status da API e do banco |
| GET | `/horarios/` | Lista horários |
| POST | `/horarios/` | Cria horário (nome, inicio, fim) |
| DELETE | `/horarios/{id}` | Remove horário (bloqueado se houver turmas) |
| GET | `/turmas/` | Lista turmas (com horário) |
| POST | `/turmas/` | Cria turma (nome, serie_nivel, horario_id, ano_letivo) |
| DELETE | `/turmas/{id}` | Remove turma (alunos ficam sem turma) |
| POST | `/alunos/register` | Cadastra aluno (nome, turma_id, foto) |
| GET | `/alunos/` | Lista alunos (com turma e horário) |
| GET | `/alunos/{id}` | Busca aluno por ID |
| PATCH | `/alunos/{id}/turma` | Muda a turma de um aluno |
| DELETE | `/alunos/{id}` | Remove aluno e seus embeddings/logs |
| POST | `/camera/start` | Inicia a câmera |
| POST | `/camera/stop` | Para a câmera |
| GET | `/camera/status` | Status da câmera |
| GET | `/camera/last` | Último reconhecimento (com decisão de acesso) |
| GET | `/camera/logs` | Histórico de acessos |
| WS | `/camera/ws` | Notificações em tempo real |

---

## Banco de Dados

### Tabelas

```
horarios         → turnos com nome e período (inicio, fim)
turmas           → turmas vinculadas a um horário e a um ano letivo
alunos           → alunos vinculados a uma turma
face_embeddings  → vetores dos rostos de cada aluno
access_logs      → histórico de reconhecimentos, com resultado de acesso
```

### Comportamento na exclusão

| Você apaga | O que acontece com os dependentes |
|---|---|
| Horário | Bloqueado se houver turmas usando (RESTRICT) |
| Turma | Alunos ficam sem turma (SET NULL) → passam a ter acesso negado |
| Aluno | Embeddings e logs são apagados junto (CASCADE) |

### Ver os dados no terminal

```bash
psql -U seu_usuario -d face_access -c "SELECT * FROM horarios;"
psql -U seu_usuario -d face_access -c "SELECT id, nome, turma_id FROM alunos;"
psql -U seu_usuario -d face_access -c "SELECT * FROM turmas;"
```

Evite `SELECT *` em `face_embeddings` — a coluna de embedding é binária e enche
a tela. Selecione só `id, aluno_id, image_path, created_at`.

---

## Segurança

- **Credenciais no `.env`** — banco e API Key nunca ficam no código. O `.env`
  está no `.gitignore`.
- **API Key** — todos os endpoints HTTP exigem o header `X-API-Key`. A comparação
  da chave é feita em tempo constante (resistente a timing attack).
- **Upload** — o nome do arquivo enviado é sanitizado e a extensão validada no
  servidor (evita path traversal).
- **Não commitar** no GitHub: `.env`, `data/` (fotos), `models/` (modelos grandes).

---

## Solução de Problemas

### `NOTICE: relation "..." already exists, skipping` ao criar o banco

Existem tabelas antigas no banco. Como o `init_db.sql` usa
`CREATE TABLE IF NOT EXISTS`, ele pula as que já existem — deixando o banco
misturado. Se não há dados a preservar, zere tudo e recrie:

```bash
psql -U seu_usuario -d face_access -c "DROP TABLE IF EXISTS access_logs, face_embeddings, alunos, turmas, horarios, persons CASCADE;"
psql -U seu_usuario -d face_access -f scripts/init_db.sql
```

Na segunda vez você deve ver cinco `CREATE TABLE` **sem** nenhum NOTICE.

### `role "..." does not exist`

O usuário do `-U` não existe no Postgres. Use o usuário do seu `.env`
(`grep DB_USER .env`). No Mac com Homebrew, costuma ser o seu login.

### Aluno reconhecido mas sempre negado

Verifique se ele tem turma e se a turma tem horário. Aluno sem turma, ou turma
sem horário, cai em "Reconhecido, mas sem turma/horário definido". Confira a
turma na página **Alunos Cadastrados** e o turno na página **Turmas**.

### Acesso negado por horário inesperadamente

O turno da turma do aluno não bate com a hora atual. Para testar o "liberado"
fora do horário real, cadastre/atribua o aluno a uma turma cujo turno cubra o
momento do teste.

### Câmera não abre no terminal

```
Configurações do Sistema → Privacidade e Segurança → Câmera → ✅ Terminal
```

### InsightFace demora na primeira execução

Normal — está baixando o modelo `buffalo_l` (~500MB). Depois fica em cache em
`models/insightface/`.

### API offline no frontend

Confirme que o uvicorn está rodando e que a `API_KEY` do `.env` é a mesma que o
frontend lê (ambos leem do mesmo `.env`).