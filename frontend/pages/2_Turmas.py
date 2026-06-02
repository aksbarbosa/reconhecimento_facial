"""
2_Turmas.py — Cadastro e listagem de turmas (vinculadas a um horário).
"""

import os
import requests
import streamlit as st
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}
API = "http://localhost:8000"

st.set_page_config(page_title="Turmas", page_icon="🏫", layout="wide")
st.title("🏫 Turmas")
st.markdown("Crie turmas e vincule cada uma a um horário (turno).")
st.divider()


def carregar_horarios():
    try:
        return requests.get(f"{API}/horarios/", headers=HEADERS, timeout=5).json().get("horarios", [])
    except Exception:
        return []


horarios = carregar_horarios()

# ── Nova turma ───────────────────────────────────────────────────────────────────
st.subheader("Nova Turma")

if not horarios:
    st.warning("⚠️ Cadastre ao menos um horário antes (página **Horários**).")
else:
    nome = st.text_input("Nome *", placeholder="Ex: 3º Ano A")
    serie = st.text_input("Série / Nível", placeholder="Ex: 3º Ano")

    # Seletor de horário (turno) — vem da tabela de horários
    op_horario = {f"{h['nome']} ({h['inicio']}–{h['fim']})": h["id"] for h in horarios}
    horario_label = st.selectbox("Turno", options=list(op_horario.keys()))

    ano_atual = datetime.now().year
    ano = st.number_input("Ano Letivo", min_value=2000, max_value=2100, value=ano_atual, step=1)

    if st.button("➕ Criar turma", type="primary", disabled=not nome):
        try:
            resp = requests.post(
                f"{API}/turmas/",
                headers=HEADERS,
                data={
                    "nome": nome,
                    "serie_nivel": serie,
                    "horario_id": op_horario[horario_label],
                    "ano_letivo": int(ano),
                }
            )
            if resp.status_code == 200:
                st.success(f"✅ {resp.json()['message']}")
                st.rerun()
            else:
                st.error(f"❌ {resp.json().get('detail', 'Erro')}")
        except requests.exceptions.ConnectionError:
            st.error("❌ API offline.")

st.divider()

# ── Listar turmas ─────────────────────────────────────────────────────────────────
st.subheader("Turmas cadastradas")
try:
    data = requests.get(f"{API}/turmas/", headers=HEADERS, timeout=5).json()
    turmas = data.get("turmas", [])
    if not turmas:
        st.info("Nenhuma turma cadastrada ainda.")
    else:
        df = pd.DataFrame(turmas)
        df = df.rename(columns={
            "id": "ID", "nome": "Nome", "serie_nivel": "Série/Nível",
            "horario_nome": "Turno", "ano_letivo": "Ano Letivo",
        })
        cols = ["ID", "Nome", "Série/Nível", "Turno", "Ano Letivo"]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)

        st.markdown("**Remover turma**")
        opcoes = {f"{t['nome']} ({t.get('horario_nome', '—')})": t["id"] for t in turmas}
        sel = st.selectbox("Selecione", options=list(opcoes.keys()))
        st.caption("Os alunos da turma não são apagados — ficam sem turma (acesso negado até reatribuir).")
        if st.button("🗑️ Remover turma"):
            resp = requests.delete(f"{API}/turmas/{opcoes[sel]}", headers=HEADERS)
            if resp.status_code == 200:
                st.success("✅ Removida!")
                st.rerun()
            else:
                st.error(f"❌ {resp.json().get('detail', 'Erro')}")
except requests.exceptions.ConnectionError:
    st.error("❌ API offline. Rode: uvicorn app.main:app --reload --env-file .env")