-- migration_fix_delete.sql
--
-- Corrige a remoção de pessoas que já possuem registros em access_logs.
--
-- Problema: a foreign key access_logs.person_id apontava para persons(id)
-- SEM ON DELETE CASCADE. Por isso, apagar uma pessoa que já foi reconhecida
-- (e tem logs) era bloqueado pelo Postgres, resultando em erro 500 na API.
--
-- Solução: recriar a FK com ON DELETE CASCADE, para que os logs da pessoa
-- sejam removidos junto com ela (igual já acontece com os embeddings).
--
-- É idempotente: pode rodar mais de uma vez sem erro.
--
-- Como usar:
--     psql -U filipe -d face_access -f scripts/migration_fix_delete.sql

-- Remove a FK antiga (o nome veio do \d access_logs)
ALTER TABLE access_logs DROP CONSTRAINT IF EXISTS access_logs_person_id_fkey;

-- Recria a FK com remoção em cascata
ALTER TABLE access_logs
    ADD CONSTRAINT access_logs_person_id_fkey
    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE CASCADE;

SELECT 'FK de access_logs corrigida (ON DELETE CASCADE).' AS status;