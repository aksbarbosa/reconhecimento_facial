-- init_db.sql
--
-- Estrutura do banco do Face Access System (modelo escolar).
--
-- Cadeia de relacionamentos:
--   horarios → turmas → alunos → face_embeddings
--                                alunos → access_logs
--
-- O acesso de um aluno é decidido pelo horário da turma a que ele pertence:
--   aluno.turma_id → turma.horario_id → horario (inicio/fim)
--
-- Como usar (banco vazio):
--   psql -U filipe -d face_access -f init_db.sql

-- ── 1. HORÁRIOS ────────────────────────────────────────────────────────────────
-- Cada horário é um turno com nome e período (hora de início e fim).
-- Substitui os turnos que antes eram fixos no código.

CREATE TABLE IF NOT EXISTS horarios (
    id     SERIAL PRIMARY KEY,
    nome   VARCHAR(50) NOT NULL,        -- ex: "Matutino"
    inicio TIME        NOT NULL,        -- ex: 07:00
    fim    TIME        NOT NULL         -- ex: 12:20
);

-- ── 2. TURMAS ──────────────────────────────────────────────────────────────────
-- Cada turma pertence a um horário (turno) e a um ano letivo.
-- ON DELETE RESTRICT impede apagar um horário que ainda tem turmas usando ele.

CREATE TABLE IF NOT EXISTS turmas (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(100) NOT NULL,                 -- ex: "3º Ano A"
    serie_nivel VARCHAR(50),                           -- ex: "3º Ano"
    horario_id  INTEGER REFERENCES horarios(id) ON DELETE RESTRICT,
    ano_letivo  INTEGER,                               -- ex: 2026
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ── 3. ALUNOS ──────────────────────────────────────────────────────────────────
-- Pessoas reconhecidas pela câmera. Cada aluno pertence a uma turma.
-- ON DELETE SET NULL: se a turma for apagada, o aluno não some — apenas fica
-- sem turma (e, sem turma, o acesso é negado, pois não há horário associado).

CREATE TABLE IF NOT EXISTS alunos (
    id         SERIAL PRIMARY KEY,
    nome       VARCHAR(100) NOT NULL,
    turma_id   INTEGER REFERENCES turmas(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── 4. FACE EMBEDDINGS ───────────────────────────────────────────────────────────
-- Vetor de 512 números gerado pela foto do aluno (InsightFace).
-- ON DELETE CASCADE: apagar o aluno apaga seus embeddings.

CREATE TABLE IF NOT EXISTS face_embeddings (
    id         SERIAL PRIMARY KEY,
    aluno_id   INTEGER REFERENCES alunos(id) ON DELETE CASCADE,
    embedding  BYTEA NOT NULL,           -- vetor de 512 floats serializado
    image_path VARCHAR(255),             -- caminho da foto usada no cadastro
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── 5. ACCESS LOGS ───────────────────────────────────────────────────────────────
-- Histórico de reconhecimentos. access_granted = acesso liberado (TRUE) ou negado.
-- ON DELETE CASCADE: apagar o aluno apaga seus logs.

CREATE TABLE IF NOT EXISTS access_logs (
    id             SERIAL PRIMARY KEY,
    aluno_id       INTEGER REFERENCES alunos(id) ON DELETE CASCADE,
    similarity     FLOAT,                -- confiança do reconhecimento (0.0 a 1.0)
    access_granted BOOLEAN,              -- TRUE = liberado, FALSE = negado
    image_path     VARCHAR(255),         -- foto salva no momento do reconhecimento
    created_at     TIMESTAMP DEFAULT NOW()
);

-- ── Dados iniciais: três horários padrão ────────────────────────────────────────
-- Insere os turnos que você já usava. O WHERE NOT EXISTS evita duplicar
-- caso este script seja rodado mais de uma vez.

INSERT INTO horarios (nome, inicio, fim)
SELECT 'Matutino', '07:00', '12:20'
WHERE NOT EXISTS (SELECT 1 FROM horarios WHERE nome = 'Matutino');

INSERT INTO horarios (nome, inicio, fim)
SELECT 'Vespertino', '13:00', '18:20'
WHERE NOT EXISTS (SELECT 1 FROM horarios WHERE nome = 'Vespertino');

INSERT INTO horarios (nome, inicio, fim)
SELECT 'Noturno', '18:30', '22:30'
WHERE NOT EXISTS (SELECT 1 FROM horarios WHERE nome = 'Noturno');

-- ── Confirmação ──────────────────────────────────────────────────────────────────

SELECT 'Banco criado com sucesso (horarios, turmas, alunos)!' AS status;