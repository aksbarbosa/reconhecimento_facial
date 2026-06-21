"""
models.py

Responsabilidade: Operações de banco (CRUD) para o modelo escolar.

Cadeia de dados:
    horarios → turmas → alunos → face_embeddings
                                 alunos → access_logs

O acesso de um aluno é decidido pelo horário da turma dele:
    aluno.turma_id → turma.horario_id → horario(inicio, fim)

Usa o context manager get_cursor() do database.py (pool de conexões).
"""

import numpy as np
from app.db.database import get_cursor


# ══════════════════════════════════════════════════════════════════════════════
# HORÁRIOS
# ══════════════════════════════════════════════════════════════════════════════

def create_horario(nome: str, inicio: str, fim: str) -> dict:
    """
    Cria um horário (turno) com nome e período.

    :param nome:   Nome do horário (ex: "Matutino")
    :param inicio: Hora de início no formato "HH:MM" (ex: "07:00")
    :param fim:    Hora de fim no formato "HH:MM" (ex: "12:20")
    :return:       Dicionário com os dados do horário criado
    """
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            "INSERT INTO horarios (nome, inicio, fim) VALUES (%s, %s, %s) RETURNING *;",
            (nome, inicio, fim)
        )
        return dict(cursor.fetchone())


def get_all_horarios() -> list:
    """Retorna todos os horários cadastrados, ordenados por hora de início."""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM horarios ORDER BY inicio;")
        return [dict(row) for row in cursor.fetchall()]


def get_horario_by_id(horario_id: int) -> dict:
    """Busca um horário pelo ID."""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM horarios WHERE id = %s;", (horario_id,))
        result = cursor.fetchone()
        return dict(result) if result else None


def delete_horario(horario_id: int) -> bool:
    """
    Remove um horário. O banco bloqueia (RESTRICT) se houver turmas usando ele.

    :raises: Exception do psycopg2 se o horário estiver em uso por alguma turma
    """
    with get_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM horarios WHERE id = %s;", (horario_id,))
        return cursor.rowcount > 0


# ══════════════════════════════════════════════════════════════════════════════
# TURMAS
# ══════════════════════════════════════════════════════════════════════════════

def create_turma(nome: str, serie_nivel: str = None,
                 horario_id: int = None, ano_letivo: int = None) -> dict:
    """
    Cria uma turma vinculada a um horário (turno).

    :param nome:        Nome da turma (ex: "3º Ano A")
    :param serie_nivel: Série/nível (ex: "3º Ano")
    :param horario_id:  ID do horário (turno) ao qual a turma pertence
    :param ano_letivo:  Ano letivo (ex: 2026)
    :return:            Dicionário com os dados da turma criada
    """
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO turmas (nome, serie_nivel, horario_id, ano_letivo)
            VALUES (%s, %s, %s, %s) RETURNING *;
            """,
            (nome, serie_nivel, horario_id, ano_letivo)
        )
        return dict(cursor.fetchone())


def get_all_turmas() -> list:
    """
    Retorna todas as turmas, já com o nome e o período do horário (turno).
    Usado para listar turmas e para o seletor no cadastro de alunos.
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT t.id, t.nome, t.serie_nivel, t.ano_letivo, t.horario_id,
                   h.nome AS horario_nome, h.inicio, h.fim, t.created_at
            FROM turmas t
            LEFT JOIN horarios h ON h.id = t.horario_id
            ORDER BY t.ano_letivo DESC, t.nome;
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def get_turma_by_id(turma_id: int) -> dict:
    """Busca uma turma pelo ID (com dados do horário)."""
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT t.id, t.nome, t.serie_nivel, t.ano_letivo, t.horario_id,
                   h.nome AS horario_nome, h.inicio, h.fim, t.created_at
            FROM turmas t
            LEFT JOIN horarios h ON h.id = t.horario_id
            WHERE t.id = %s;
            """,
            (turma_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def delete_turma(turma_id: int) -> bool:
    """
    Remove uma turma. Os alunos da turma NÃO são apagados — ficam sem turma
    (ON DELETE SET NULL), e por isso passam a ter acesso negado.
    """
    with get_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM turmas WHERE id = %s;", (turma_id,))
        return cursor.rowcount > 0


# ══════════════════════════════════════════════════════════════════════════════
# ALUNOS
# ══════════════════════════════════════════════════════════════════════════════

def create_aluno(nome: str, turma_id: int = None,
                 supabase_dependent_id: str = None) -> dict:
    """
    Cadastra um aluno, opcionalmente vinculado a uma turma e a um
    dependente no Supabase/FaceNotify (supabase_dependent_id = UUID do
    dependente usado para disparar notificações push).
    """
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO alunos (nome, turma_id, supabase_dependent_id)
            VALUES (%s, %s, %s) RETURNING *;
            """,
            (nome, turma_id, supabase_dependent_id)
        )
        aluno = dict(cursor.fetchone())

    print(f"✅ Aluno cadastrado: {aluno['nome']} (ID: {aluno['id']}, turma: {turma_id})")
    return aluno


def add_aluno_dependente(aluno_id: int, supabase_dependent_id: str) -> bool:
    """Adiciona um vínculo aluno↔dependente (suporta múltiplos responsáveis)."""
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO aluno_dependentes (aluno_id, supabase_dependent_id)
            VALUES (%s, %s) ON CONFLICT DO NOTHING;
            """,
            (aluno_id, supabase_dependent_id)
        )
        return True


def remove_aluno_dependente(aluno_id: int, supabase_dependent_id: str) -> bool:
    """Remove um vínculo específico aluno↔dependente."""
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            "DELETE FROM aluno_dependentes WHERE aluno_id = %s AND supabase_dependent_id = %s;",
            (aluno_id, supabase_dependent_id)
        )
        return cursor.rowcount > 0


def update_aluno_dependent_id(aluno_id: int, supabase_dependent_id: str) -> bool:
    """Mantido por compatibilidade — use add_aluno_dependente para novos vínculos."""
    return add_aluno_dependente(aluno_id, supabase_dependent_id)


def update_aluno_turma(aluno_id: int, turma_id: int) -> bool:
    """Atualiza a turma de um aluno já cadastrado."""
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            "UPDATE alunos SET turma_id = %s WHERE id = %s;",
            (turma_id, aluno_id)
        )
        return cursor.rowcount > 0


def get_aluno_by_id(aluno_id: int) -> dict:
    """Busca um aluno pelo ID, com turma e horário."""
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT a.id, a.nome, a.turma_id, a.created_at,
                   t.nome AS turma_nome,
                   h.nome AS horario_nome, h.inicio, h.fim
            FROM alunos a
            LEFT JOIN turmas t   ON t.id = a.turma_id
            LEFT JOIN horarios h ON h.id = t.horario_id
            WHERE a.id = %s;
            """,
            (aluno_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def get_all_alunos() -> list:
    """
    Retorna todos os alunos com turma, horário e lista de dependent_ids vinculados.
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT a.id, a.nome, a.turma_id, a.created_at,
                   t.nome AS turma_nome,
                   h.nome AS horario_nome, h.inicio, h.fim,
                   COALESCE(
                       ARRAY_AGG(ad.supabase_dependent_id::text)
                       FILTER (WHERE ad.supabase_dependent_id IS NOT NULL),
                       ARRAY[]::text[]
                   ) AS dependent_ids
            FROM alunos a
            LEFT JOIN turmas t            ON t.id = a.turma_id
            LEFT JOIN horarios h          ON h.id = t.horario_id
            LEFT JOIN aluno_dependentes ad ON ad.aluno_id = a.id
            GROUP BY a.id, a.nome, a.turma_id, a.created_at,
                     t.nome, h.nome, h.inicio, h.fim
            ORDER BY a.nome;
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def delete_aluno(aluno_id: int) -> bool:
    """
    Remove um aluno e, em cascata, seus embeddings e logs de acesso.

    :return: True se removeu, False se não encontrou
    """
    with get_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM alunos WHERE id = %s;", (aluno_id,))
        removed = cursor.rowcount > 0

    if removed:
        print(f"✅ Aluno ID {aluno_id} removido.")
    else:
        print(f"⚠️ Aluno ID {aluno_id} não encontrado.")
    return removed


# ══════════════════════════════════════════════════════════════════════════════
# FACE EMBEDDINGS
# ══════════════════════════════════════════════════════════════════════════════

def save_embedding(aluno_id: int, embedding: np.ndarray, image_path: str = None) -> dict:
    """Salva o embedding (vetor de 512 floats) de um aluno no banco."""
    embedding_bytes = embedding.astype(np.float32).tobytes()

    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO face_embeddings (aluno_id, embedding, image_path)
            VALUES (%s, %s, %s)
            RETURNING id, aluno_id, image_path, created_at;
            """,
            (aluno_id, embedding_bytes, image_path)
        )
        result = dict(cursor.fetchone())

    print(f"✅ Embedding salvo para aluno ID {aluno_id}")
    return result


def get_all_embeddings() -> list:
    """
    Retorna todos os embeddings com a identidade do aluno e a janela de horário
    da turma dele. É a base que o reconhecimento usa para comparar e decidir
    o acesso (inicio/fim vêm da turma → horario).

    Usa LEFT JOIN porque o aluno pode estar sem turma, ou a turma sem horário —
    nesses casos inicio/fim vêm como None e o acesso é negado por falta de horário.

    :return: Lista de candidatos com aluno_id, aluno_nome, turma/horário e embedding
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT fe.id, fe.aluno_id, a.nome AS aluno_nome,
                   t.nome AS turma_nome,
                   h.nome AS horario_nome, h.inicio, h.fim,
                   fe.embedding, fe.image_path,
                   COALESCE(
                       ARRAY_AGG(ad.supabase_dependent_id::text)
                       FILTER (WHERE ad.supabase_dependent_id IS NOT NULL),
                       ARRAY[]::text[]
                   ) AS dependent_ids
            FROM face_embeddings fe
            JOIN alunos a              ON a.id = fe.aluno_id
            LEFT JOIN turmas t         ON t.id = a.turma_id
            LEFT JOIN horarios h       ON h.id = t.horario_id
            LEFT JOIN aluno_dependentes ad ON ad.aluno_id = a.id
            GROUP BY fe.id, fe.aluno_id, a.nome,
                     t.nome, h.nome, h.inicio, h.fim,
                     fe.embedding, fe.image_path
            ORDER BY a.nome;
            """
        )
        rows = cursor.fetchall()

    candidates = []
    for row in rows:
        row = dict(row)
        embedding_array = np.frombuffer(row["embedding"], dtype=np.float32)
        candidates.append({
            "id":            row["id"],
            "aluno_id":      row["aluno_id"],
            "aluno_nome":    row["aluno_nome"],
            "dependent_ids": row["dependent_ids"] or [],
            "turma_nome":    row["turma_nome"],
            "horario_nome":  row["horario_nome"],
            "inicio":        row["inicio"],
            "fim":           row["fim"],
            "embedding":     embedding_array,
            "image_path":    row["image_path"],
        })
    return candidates


def get_embeddings_by_aluno(aluno_id: int) -> list:
    """Retorna todos os embeddings de um aluno específico."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM face_embeddings WHERE aluno_id = %s;",
            (aluno_id,)
        )
        rows = cursor.fetchall()

    embeddings = []
    for row in rows:
        row = dict(row)
        row["embedding"] = np.frombuffer(row["embedding"], dtype=np.float32)
        embeddings.append(row)
    return embeddings


# ══════════════════════════════════════════════════════════════════════════════
# ACCESS LOGS
# ══════════════════════════════════════════════════════════════════════════════

def save_access_log(aluno_id: int, similarity: float,
                    access_granted: bool = None, image_path: str = None) -> dict:
    """Salva um log de acesso quando um aluno é reconhecido pela câmera."""
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO access_logs (aluno_id, similarity, access_granted, image_path)
            VALUES (%s, %s, %s, %s)
            RETURNING *;
            """,
            (aluno_id, similarity, access_granted, image_path)
        )
        log = dict(cursor.fetchone())

    estado = "LIBERADO" if access_granted else "NEGADO"
    print(f"✅ Log salvo — Aluno ID: {aluno_id} | {estado} | Confiança: {similarity:.0%}")
    return log


def get_access_logs(limit: int = 50) -> list:
    """
    Retorna o histórico de reconhecimentos mais recentes, com aluno, turma,
    horário e o resultado de acesso.
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT al.id, al.aluno_id, a.nome AS aluno_nome,
                   t.nome AS turma_nome, h.nome AS horario_nome,
                   al.similarity, al.access_granted, al.image_path, al.created_at
            FROM access_logs al
            JOIN alunos a        ON a.id = al.aluno_id
            LEFT JOIN turmas t   ON t.id = a.turma_id
            LEFT JOIN horarios h ON h.id = t.horario_id
            ORDER BY al.created_at DESC
            LIMIT %s;
            """,
            (limit,)
        )
        rows = cursor.fetchall()

    logs = []
    for row in rows:
        row = dict(row)
        row["similarity_pct"] = f"{row['similarity']:.0%}"
        logs.append(row)
    return logs