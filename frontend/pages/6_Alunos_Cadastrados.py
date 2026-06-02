"""
6_Alunos_Cadastrados.py — Lista de alunos, com troca de turma e remoção.
"""

import os
import requests
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}
API = "http://localhost:8000"

st.set_page_config(page_title="Alunos Cadastrados", page_icon="👥", layout="wide")
st.title("👥 Alunos Cadastrados")
st.markdown("Gerencie os alunos cadastrados no sistema.")
st.divider()


def carregar_turmas():
    try:
        return requests.get(f"{API}/turmas/", headers=HEADERS, timeout=5).json().get("turmas", [])
    except Exception:
        return []


try:
    data = requests.get(f"{API}/alunos/", headers=HEADERS, timeout=5).json()
    alunos = data.get("alunos", [])

    if not alunos:
        st.info("Nenhum aluno cadastrado ainda. Vá para **Cadastrar Aluno**.")
    else:
        st.metric("Total de alunos", data["total"])
        st.divider()

        df = pd.DataFrame(alunos)
        df = df.rename(columns={
            "id": "ID", "nome": "Nome", "turma_nome": "Turma",
            "horario_nome": "Turno", "created_at": "Cadastrado em",
        })
        # Garante as colunas mesmo se vierem nulas
        for c in ["Turma", "Turno"]:
            if c not in df.columns:
                df[c] = "—"
        st.dataframe(df[["ID", "Nome", "Turma", "Turno", "Cadastrado em"]],
                     use_container_width=True, hide_index=True)
        st.divider()

        op_aluno = {f"ID {a['id']} — {a['nome']}": a["id"] for a in alunos}

        # ── Trocar turma ───────────────────────────────────────────────────
        st.subheader("🏫 Mudar turma do aluno")
        turmas = carregar_turmas()
        if turmas:
            sel_aluno = st.selectbox("Aluno", options=list(op_aluno.keys()), key="sel_aluno_turma")
            op_turma = {f"{t['nome']} — {t.get('horario_nome', 'sem turno')}": t["id"] for t in turmas}
            sel_turma = st.selectbox("Nova turma", options=list(op_turma.keys()))
            if st.button("💾 Salvar turma"):
                resp = requests.patch(
                    f"{API}/alunos/{op_aluno[sel_aluno]}/turma",
                    headers=HEADERS, data={"turma_id": op_turma[sel_turma]}
                )
                if resp.status_code == 200:
                    st.success(f"✅ {resp.json()['message']}"); st.rerun()
                else:
                    st.error(f"❌ {resp.json().get('detail', 'Erro')}")
        else:
            st.caption("Cadastre turmas para poder reatribuir alunos.")

        st.divider()

        # ── Remover aluno ──────────────────────────────────────────────────
        st.subheader("🗑️ Remover Aluno")
        st.warning("Remover um aluno apaga também seus embeddings e histórico. Não pode ser desfeito.")
        sel_rem = st.selectbox("Selecione o aluno", options=list(op_aluno.keys()), key="sel_aluno_rem")
        if st.button("🗑️ Remover", type="primary"):
            resp = requests.delete(f"{API}/alunos/{op_aluno[sel_rem]}", headers=HEADERS)
            try:
                body = resp.json()
            except ValueError:
                body = {}
            if resp.status_code == 200:
                st.success(f"✅ {body.get('message', 'Removido.')}"); st.rerun()
            else:
                st.error(f"❌ {body.get('detail', f'HTTP {resp.status_code}')}")

except requests.exceptions.ConnectionError:
    st.error("❌ API offline. Rode: uvicorn app.main:app --reload --env-file .env")
except Exception as e:
    st.error(f"❌ Erro: {e}")

if st.button("🔄 Atualizar lista"):
    st.rerun()