"""
shifts.py

Responsabilidade: Decidir se um aluno pode entrar no horário atual.

Antes, o turno era um texto fixo na pessoa. Agora o horário (janela de
início/fim) vem da turma do aluno: aluno → turma → horario(inicio, fim).
Por isso a avaliação recebe diretamente as horas de início e fim, que o
worker obtém do banco junto com cada candidato.

Regra de decisão (evaluate_access):
    - rosto não reconhecido            → NEGADO  ("Rosto não cadastrado")
    - reconhecido, sem turma/horário   → NEGADO  ("Reconhecido, mas sem turma/horário definido")
    - reconhecido, fora da janela      → NEGADO  ("Reconhecido, mas horário não permitido")
    - reconhecido, dentro da janela    → LIBERADO ("Acesso liberado")
"""

from datetime import time, datetime
from typing import Optional


def is_within_window(inicio: Optional[time], fim: Optional[time],
                     now: Optional[datetime] = None) -> bool:
    """
    Verifica se o horário atual está dentro da janela [inicio, fim].

    :param inicio: Hora de início do horário (datetime.time) ou None
    :param fim:    Hora de fim do horário (datetime.time) ou None
    :param now:    Momento a avaliar (padrão: agora)
    :return:       True se está dentro da janela
    """
    if inicio is None or fim is None:
        return False
    agora = (now or datetime.now()).time()
    return inicio <= agora <= fim


def evaluate_access(matched: bool,
                    inicio: Optional[time] = None,
                    fim: Optional[time] = None,
                    now: Optional[datetime] = None) -> dict:
    """
    Decide o resultado de acesso a partir do reconhecimento e da janela
    de horário da turma do aluno.

    :param matched: True se o rosto foi reconhecido
    :param inicio:  Hora de início do horário da turma (ou None se não houver)
    :param fim:     Hora de fim do horário da turma (ou None se não houver)
    :param now:     Momento a avaliar (padrão: agora)
    :return: Dicionário com:
             - status:         "nao_cadastrado" | "sem_horario" | "horario_negado" | "liberado"
             - access_granted: bool
             - message:        texto pronto para exibir
    """
    # Caso 1 — rosto não reconhecido
    if not matched:
        return {
            "status": "nao_cadastrado",
            "access_granted": False,
            "message": "Rosto não cadastrado",
        }

    # Caso 2 — reconhecido, mas sem turma ou sem horário associado
    if inicio is None or fim is None:
        return {
            "status": "sem_horario",
            "access_granted": False,
            "message": "Reconhecido, mas sem turma/horário definido",
        }

    # Caso 3 — reconhecido e dentro da janela
    if is_within_window(inicio, fim, now):
        return {
            "status": "liberado",
            "access_granted": True,
            "message": "Acesso liberado",
        }

    # Caso 4 — reconhecido, mas fora da janela
    return {
        "status": "horario_negado",
        "access_granted": False,
        "message": "Reconhecido, mas horário não permitido",
    }