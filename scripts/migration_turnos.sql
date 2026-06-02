-- migration_turnos.sql
--
-- Aplica a feature de turnos a um banco JÁ EXISTENTE (sem perder dados).
-- É idempotente: pode rodar mais de uma vez sem erro.
--
-- Como usar:
--     psql -U seu_usuario -d face_access -f scripts/migration_turnos.sql

-- ── 1. Coluna de turno em persons ──────────────────────────────────────────────
-- Cada pessoa passa a ter um turno de permissão.
-- Linhas antigas recebem 'matutino' por padrão — ajuste depois quem precisar.

ALTER TABLE persons
    ADD COLUMN IF NOT EXISTS shift VARCHAR(20) NOT NULL DEFAULT 'matutino';

-- Garante que só valores válidos sejam aceitos (recria de forma idempotente).
ALTER TABLE persons DROP CONSTRAINT IF EXISTS shift_valido;
ALTER TABLE persons
    ADD CONSTRAINT shift_valido
    CHECK (shift IN ('matutino', 'vespertino', 'noturno'));

-- ── 2. Resultado do acesso em access_logs ──────────────────────────────────────
-- Registra se o acesso foi liberado (TRUE) ou negado (FALSE) no momento do log.
-- Pode ficar NULL para registros antigos, anteriores a esta migração.

ALTER TABLE access_logs
    ADD COLUMN IF NOT EXISTS access_granted BOOLEAN;

-- ── Confirmação ────────────────────────────────────────────────────────────────

SELECT 'Migração de turnos aplicada com sucesso!' AS status;