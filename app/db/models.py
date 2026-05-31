"""
models.py

Responsabilidade: Funções para salvar e buscar dados no banco de dados.

Este módulo contém todas as operações de banco (CRUD) para as tabelas
persons, face_embeddings e access_logs. Os services chamam essas funções
para persistir e recuperar dados sem precisar escrever SQL diretamente.

Tabelas:
    persons         → cadastro de pessoas (id, name, created_at)
    face_embeddings → vetores dos rostos (id, person_id, embedding, image_path)
    access_logs     → histórico de reconhecimentos (id, person_id, similarity, image_path)
"""

import numpy as np                          # Para serializar/deserializar embeddings
from app.db.database import get_connection, get_cursor  # Conexão com o banco


# ══════════════════════════════════════════════════════════════════════════════
# PERSONS — operações na tabela de pessoas
# ══════════════════════════════════════════════════════════════════════════════

def create_person(name: str) -> dict:
    """
    Cadastra uma nova pessoa no banco de dados.

    :param name: Nome da pessoa
    :return:     Dicionário com os dados da pessoa criada (id, name, created_at)
    """

    conn = get_connection()
    cursor = get_cursor(conn)

    try:
        # Insere a pessoa e retorna os dados inseridos com RETURNING
        cursor.execute(
            "INSERT INTO persons (name) VALUES (%s) RETURNING *;",
            (name,)  # Parâmetro seguro — evita SQL injection
        )

        # Obtém a linha inserida como dicionário
        person = dict(cursor.fetchone())

        # Confirma a transação no banco
        conn.commit()

        print(f"✅ Pessoa cadastrada: {person['name']} (ID: {person['id']})")
        return person

    finally:
        # Garante que a conexão seja fechada mesmo se houver erro
        cursor.close()
        conn.close()


def get_person_by_id(person_id: int) -> dict:
    """
    Busca uma pessoa pelo ID.

    :param person_id: ID da pessoa no banco
    :return:          Dicionário com os dados da pessoa ou None se não encontrada
    """

    conn = get_connection()
    cursor = get_cursor(conn)

    try:
        cursor.execute(
            "SELECT * FROM persons WHERE id = %s;",
            (person_id,)
        )

        # fetchone() retorna None se não encontrou nenhuma linha
        result = cursor.fetchone()
        return dict(result) if result else None

    finally:
        cursor.close()
        conn.close()


def get_all_persons() -> list:
    """
    Retorna todas as pessoas cadastradas no banco.

    :return: Lista de dicionários com os dados de cada pessoa
    """

    conn = get_connection()
    cursor = get_cursor(conn)

    try:
        # Busca todas as pessoas ordenadas pelo nome
        cursor.execute("SELECT * FROM persons ORDER BY name;")

        # fetchall() retorna uma lista de linhas
        results = cursor.fetchall()
        return [dict(row) for row in results]

    finally:
        cursor.close()
        conn.close()


def delete_person(person_id: int) -> bool:
    """
    Remove uma pessoa e todos os seus embeddings do banco.
    O ON DELETE CASCADE na tabela face_embeddings garante que
    os embeddings são removidos automaticamente.

    :param person_id: ID da pessoa a remover
    :return:          True se removeu, False se não encontrou
    """

    conn = get_connection()
    cursor = get_cursor(conn)

    try:
        cursor.execute(
            "DELETE FROM persons WHERE id = %s;",
            (person_id,)
        )

        # rowcount indica quantas linhas foram afetadas
        removed = cursor.rowcount > 0
        conn.commit()

        if removed:
            print(f"✅ Pessoa ID {person_id} removida.")
        else:
            print(f"⚠️ Pessoa ID {person_id} não encontrada.")

        return removed

    finally:
        cursor.close()
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# FACE EMBEDDINGS — operações na tabela de vetores de rostos
# ══════════════════════════════════════════════════════════════════════════════

def save_embedding(person_id: int, embedding: np.ndarray, image_path: str = None) -> dict:
    """
    Salva o embedding (vetor de 512 números) de um rosto no banco.

    O NumPy array é serializado para bytes (BYTEA) antes de salvar,
    e deserializado de volta para array quando for lido.

    :param person_id:   ID da pessoa dona do rosto
    :param embedding:   Vetor NumPy de 512 floats
    :param image_path:  Caminho da imagem usada no cadastro (opcional)
    :return:            Dicionário com os dados do embedding salvo
    """

    conn = get_connection()
    cursor = get_cursor(conn)

    try:
        # Serializa o array NumPy para bytes para salvar no campo BYTEA
        # tobytes() converte o array para uma sequência de bytes
        embedding_bytes = embedding.astype(np.float32).tobytes()

        cursor.execute(
            """
            INSERT INTO face_embeddings (person_id, embedding, image_path)
            VALUES (%s, %s, %s)
            RETURNING id, person_id, image_path, created_at;
            """,
            (person_id, embedding_bytes, image_path)
        )

        result = dict(cursor.fetchone())
        conn.commit()

        print(f"✅ Embedding salvo para pessoa ID {person_id}")
        return result

    finally:
        cursor.close()
        conn.close()


def get_all_embeddings() -> list:
    """
    Retorna todos os embeddings cadastrados com o nome da pessoa.
    Usado pelo Matcher para comparar com o rosto capturado pela câmera.

    :return: Lista de dicionários com person_id, person_name e embedding (np.ndarray)
    """

    conn = get_connection()
    cursor = get_cursor(conn)

    try:
        # Faz JOIN entre face_embeddings e persons para trazer o nome junto
        cursor.execute(
            """
            SELECT
                fe.id,
                fe.person_id,
                p.name  AS person_name,
                fe.embedding,
                fe.image_path
            FROM face_embeddings fe
            JOIN persons p ON p.id = fe.person_id
            ORDER BY p.name;
            """
        )

        rows = cursor.fetchall()
        candidates = []

        for row in rows:
            row = dict(row)

            # Deserializa os bytes de volta para array NumPy float32
            # frombuffer() reconstrói o array a partir dos bytes salvos
            embedding_array = np.frombuffer(row["embedding"], dtype=np.float32)

            candidates.append({
                "id":          row["id"],
                "person_id":   row["person_id"],
                "person_name": row["person_name"],
                "embedding":   embedding_array,   # Array NumPy pronto para o Matcher
                "image_path":  row["image_path"],
            })

        return candidates

    finally:
        cursor.close()
        conn.close()


def get_embeddings_by_person(person_id: int) -> list:
    """
    Retorna todos os embeddings de uma pessoa específica.

    :param person_id: ID da pessoa
    :return:          Lista de embeddings da pessoa
    """

    conn = get_connection()
    cursor = get_cursor(conn)

    try:
        cursor.execute(
            "SELECT * FROM face_embeddings WHERE person_id = %s;",
            (person_id,)
        )

        rows = cursor.fetchall()
        embeddings = []

        for row in rows:
            row = dict(row)

            # Deserializa os bytes para array NumPy
            embedding_array = np.frombuffer(row["embedding"], dtype=np.float32)
            row["embedding"] = embedding_array
            embeddings.append(row)

        return embeddings

    finally:
        cursor.close()
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ACCESS LOGS — operações na tabela de histórico de reconhecimentos
# ══════════════════════════════════════════════════════════════════════════════

def save_access_log(person_id: int, similarity: float, image_path: str = None) -> dict:
    """
    Salva um log de acesso no banco quando uma pessoa é reconhecida pela câmera.

    Cada vez que o sistema identifica alguém, um registro é criado aqui
    com o ID da pessoa, a confiança do reconhecimento e a foto do momento.
    Isso forma o histórico completo de acessos do sistema.

    :param person_id:  ID da pessoa reconhecida
    :param similarity: Confiança do reconhecimento (0.0 a 1.0, ex: 0.97 = 97%)
    :param image_path: Caminho da foto salva no momento do reconhecimento
    :return:           Dicionário com os dados do log salvo
    """

    conn = get_connection()
    cursor = get_cursor(conn)

    try:
        # Insere o log de acesso e retorna os dados com RETURNING
        cursor.execute(
            """
            INSERT INTO access_logs (person_id, similarity, image_path)
            VALUES (%s, %s, %s)
            RETURNING *;
            """,
            (person_id, similarity, image_path)
        )

        # Obtém o registro salvo como dicionário
        log = dict(cursor.fetchone())

        # Confirma a transação no banco
        conn.commit()

        print(f"✅ Log de acesso salvo — Pessoa ID: {person_id} | Confiança: {similarity:.0%}")
        return log

    finally:
        cursor.close()
        conn.close()


def get_access_logs(limit: int = 50) -> list:
    """
    Retorna o histórico de reconhecimentos mais recentes.

    Faz JOIN com a tabela persons para trazer o nome da pessoa
    junto com cada log, evitando consultas adicionais ao banco.

    :param limit: Número máximo de registros a retornar (padrão: 50)
    :return:      Lista de dicionários com os logs mais recentes
    """

    conn = get_connection()
    cursor = get_cursor(conn)

    try:
        # Busca os logs mais recentes com o nome da pessoa via JOIN
        cursor.execute(
            """
            SELECT
                al.id,
                al.person_id,
                p.name       AS person_name,  -- nome vem da tabela persons
                al.similarity,
                al.image_path,
                al.created_at
            FROM access_logs al
            JOIN persons p ON p.id = al.person_id
            ORDER BY al.created_at DESC        -- mais recentes primeiro
            LIMIT %s;
            """,
            (limit,)
        )

        rows = cursor.fetchall()

        # Converte cada linha para dicionário e formata a similaridade
        logs = []
        for row in rows:
            row = dict(row)

            # Adiciona a similaridade formatada como porcentagem para exibição
            row["similarity_pct"] = f"{row['similarity']:.0%}"
            logs.append(row)

        return logs

    finally:
        cursor.close()
        conn.close()


def get_access_logs_by_person(person_id: int, limit: int = 20) -> list:
    """
    Retorna o histórico de reconhecimentos de uma pessoa específica.

    Útil para ver quantas vezes uma pessoa passou pela câmera
    e com qual confiança cada reconhecimento foi feito.

    :param person_id: ID da pessoa
    :param limit:     Número máximo de registros (padrão: 20)
    :return:          Lista de logs da pessoa
    """

    conn = get_connection()
    cursor = get_cursor(conn)

    try:
        cursor.execute(
            """
            SELECT *
            FROM access_logs
            WHERE person_id = %s
            ORDER BY created_at DESC
            LIMIT %s;
            """,
            (person_id, limit)
        )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    finally:
        cursor.close()
        conn.close()