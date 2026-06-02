"""
5_Historico.py — Histórico de reconhecimentos com aluno, turma, turno e acesso.
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

st.set_page_config(page_title="Histórico", page_icon="📋", layout="wide")
st.title("📋 Histórico de Acessos")
st.markdown("Todos os reconhecimentos registrados pelo sistema.")
st.divider()


def fmt_acesso(v):
    if v is True:
        return "✅ Liberado"
    if v is False:
        return "⛔ Negado"
    return "—"


try:
    logs = requests.get(f"{API}/camera/logs", headers=HEADERS, timeout=5).json().get("logs", [])
    if not logs:
        st.info("Nenhum acesso registrado ainda. Ligue a câmera e apareça na frente dela!")
    else:
        st.metric("Total de acessos", len(logs))
        st.divider()

        df = pd.DataFrame(logs)
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%d/%m/%Y %H:%M:%S")
        df["similarity"] = df["similarity"].apply(lambda x: f"{x:.0%}")
        df["acesso"] = df["access_granted"].apply(fmt_acesso)
        df = df.rename(columns={
            "id": "ID", "aluno_nome": "Aluno", "turma_nome": "Turma",
            "horario_nome": "Turno", "similarity": "Confiança",
            "acesso": "Acesso", "created_at": "Data/Hora",
        })
        cols = ["ID", "Aluno", "Turma", "Turno", "Confiança", "Acesso", "Data/Hora"]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)
except requests.exceptions.ConnectionError:
    st.error("❌ API offline. Rode: uvicorn app.main:app --reload --env-file .env")
except Exception as e:
    st.error(f"❌ Erro ao carregar histórico: {e}")

if st.button("🔄 Atualizar"):
    st.rerun()