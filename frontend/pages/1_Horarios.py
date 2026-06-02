"""
1_Horarios.py — Cadastro e listagem de horários (turnos com período).
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

st.set_page_config(page_title="Horários", page_icon="🕒", layout="wide")
st.title("🕒 Horários")
st.markdown("Defina os turnos do sistema com nome e período (início e fim).")
st.divider()

# ── Criar horário ───────────────────────────────────────────────────────────────
st.subheader("Novo Horário")
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    nome = st.text_input("Nome", placeholder="Ex: Matutino")
with col2:
    inicio = st.time_input("Início")
with col3:
    fim = st.time_input("Fim")

if st.button("➕ Criar horário", type="primary", disabled=not nome):
    try:
        resp = requests.post(
            f"{API}/horarios/",
            headers=HEADERS,
            data={"nome": nome, "inicio": inicio.strftime("%H:%M"), "fim": fim.strftime("%H:%M")}
        )
        if resp.status_code == 200:
            st.success(f"✅ {resp.json()['message']}")
            st.rerun()
        else:
            st.error(f"❌ {resp.json().get('detail', 'Erro')}")
    except requests.exceptions.ConnectionError:
        st.error("❌ API offline.")

st.divider()

# ── Listar horários ─────────────────────────────────────────────────────────────
st.subheader("Horários cadastrados")
try:
    data = requests.get(f"{API}/horarios/", headers=HEADERS, timeout=5).json()
    horarios = data.get("horarios", [])
    if not horarios:
        st.info("Nenhum horário cadastrado ainda.")
    else:
        df = pd.DataFrame(horarios)
        df = df.rename(columns={"id": "ID", "nome": "Nome", "inicio": "Início", "fim": "Fim"})
        st.dataframe(df[["ID", "Nome", "Início", "Fim"]], use_container_width=True, hide_index=True)

        st.markdown("**Remover horário**")
        opcoes = {f"{h['nome']} ({h['inicio']}–{h['fim']})": h["id"] for h in horarios}
        sel = st.selectbox("Selecione", options=list(opcoes.keys()))
        if st.button("🗑️ Remover horário"):
            resp = requests.delete(f"{API}/horarios/{opcoes[sel]}", headers=HEADERS)
            if resp.status_code == 200:
                st.success("✅ Removido!")
                st.rerun()
            else:
                try:
                    st.error(f"❌ {resp.json().get('detail', 'Erro')}")
                except ValueError:
                    st.error(f"❌ HTTP {resp.status_code}")
except requests.exceptions.ConnectionError:
    st.error("❌ API offline. Rode: uvicorn app.main:app --reload --env-file .env")