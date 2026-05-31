-- init_db.sql
--
-- Script de inicialização do banco de dados do Face Access System.
-- Cria todas as tabelas necessárias para o funcionamento do sistema.
--
-- Como usar:
--     psql -U seu_usuario -d face_access -f scripts/init_db.sql
--
-- Ou dentro do psql:
--     \i scripts/init_db.sql

-- ── Tabela de pessoas cadastradas ─────────────────────────────────────────────
-- Armazena o nome e a data de cadastro de cada pessoa no sistema.

CREATE TABLE IF NOT EXISTS persons (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── Tabela de embeddings (vetores dos rostos) ──────────────────────────────────
-- Armazena o vetor de 512 números gerado pelo InsightFace para cada rosto.
-- ON DELETE CASCADE garante que os embeddings são removidos junto com a pessoa.

CREATE TABLE IF NOT EXISTS face_embeddings (
    id         SERIAL PRIMARY KEY,
    person_id  INTEGER REFERENCES persons(id) ON DELETE CASCADE,
    embedding  BYTEA NOT NULL,       -- vetor de 512 floats serializado em bytes
    image_path VARCHAR(255),         -- caminho da foto usada no cadastro
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── Tabela de logs de acesso ───────────────────────────────────────────────────
-- Registra cada vez que uma pessoa é reconhecida pela câmera.
-- Alimenta o histórico exibido no frontend.

CREATE TABLE IF NOT EXISTS access_logs (
    id         SERIAL PRIMARY KEY,
    person_id  INTEGER REFERENCES persons(id),
    similarity FLOAT,                -- confiança do reconhecimento (0.0 a 1.0)
    image_path VARCHAR(255),         -- foto salva no momento do reconhecimento
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── Confirmação ────────────────────────────────────────────────────────────────

SELECT 'Tabelas criadas com sucesso!' AS status;