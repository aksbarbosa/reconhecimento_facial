"""
3_Historico.py

Responsabilidade: Página para visualizar o histórico completo
de reconhecimentos registrados pelo sistema.

Busca os logs pela API e formata as datas no padrão brasileiro (DD/MM/AAAA HH:MM:SS).
"""

import requests
import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Histórico", page_icon="📋", layout="wide")

st.title("📋 Histórico de Acessos")
st.markdown("Todos os reconhecimentos registrados pelo sistema.")
st.divider()

try:
    response = requests.get("http://localhost:8000/camera/logs", timeout=5)
    logs = response.json().get("logs", [])

    if not logs:
        st.info("Nenhum acesso registrado ainda. Ligue a câmera e apareça na frente dela!")

    else:
        st.metric("Total de acessos", len(logs))
        st.divider()

        df = pd.DataFrame(logs)

        # Formata a data/hora para o padrão brasileiro DD/MM/AAAA HH:MM:SS
        # O PostgreSQL retorna no formato ISO (2026-05-30T10:25:35), então convertemos
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%d/%m/%Y %H:%M:%S")

        # Formata a similaridade como porcentagem
        df["similarity"] = df["similarity"].apply(lambda x: f"{x:.0%}")

        df = df.rename(columns={
            "id":          "ID",
            "person_name": "Pessoa",
            "similarity":  "Confiança",
            "created_at":  "Data/Hora",
        })

        st.dataframe(
            df[["ID", "Pessoa", "Confiança", "Data/Hora"]],
            use_container_width=True,
            hide_index=True,
        )

except requests.exceptions.ConnectionError:
    st.error("❌ API offline. Rode: uvicorn app.main:app --reload")

except Exception as e:
    st.error(f"❌ Erro ao carregar histórico: {e}")

if st.button("🔄 Atualizar"):
    st.rerun()