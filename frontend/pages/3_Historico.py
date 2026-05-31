"""
3_Historico.py
"""

import os
import requests
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}

st.set_page_config(page_title="Histórico", page_icon="📋", layout="wide")
st.title("📋 Histórico de Acessos")
st.markdown("Todos os reconhecimentos registrados pelo sistema.")
st.divider()

try:
    response = requests.get("http://localhost:8000/camera/logs", headers=HEADERS, timeout=5)
    logs = response.json().get("logs", [])

    if not logs:
        st.info("Nenhum acesso registrado ainda. Ligue a câmera e apareça na frente dela!")
    else:
        st.metric("Total de acessos", len(logs))
        st.divider()

        df = pd.DataFrame(logs)
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%d/%m/%Y %H:%M:%S")
        df["similarity"] = df["similarity"].apply(lambda x: f"{x:.0%}")
        df = df.rename(columns={
            "id":          "ID",
            "person_name": "Pessoa",
            "similarity":  "Confiança",
            "created_at":  "Data/Hora",
        })

        st.dataframe(df[["ID", "Pessoa", "Confiança", "Data/Hora"]], use_container_width=True, hide_index=True)

except requests.exceptions.ConnectionError:
    st.error("❌ API offline. Rode: uvicorn app.main:app --reload --env-file .env")
except Exception as e:
    st.error(f"❌ Erro ao carregar histórico: {e}")

if st.button("🔄 Atualizar"):
    st.rerun()