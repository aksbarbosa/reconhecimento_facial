"""
4_Pessoas_Cadastradas.py
"""

import os
import requests
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}

st.set_page_config(page_title="Pessoas Cadastradas", page_icon="👥", layout="wide")
st.title("👥 Pessoas Cadastradas")
st.markdown("Gerencie as pessoas cadastradas no sistema.")
st.divider()

try:
    response = requests.get("http://localhost:8000/persons/", headers=HEADERS, timeout=5)
    data = response.json()
    persons = data.get("persons", [])

    if not persons:
        st.info("Nenhuma pessoa cadastrada ainda. Vá para a página **Cadastrar Pessoa**.")
    else:
        st.metric("Total de pessoas", data["total"])
        st.divider()

        df = pd.DataFrame(persons)
        df = df.rename(columns={
            "id":         "ID",
            "name":       "Nome",
            "created_at": "Cadastrado em",
        })

        st.dataframe(df[["ID", "Nome", "Cadastrado em"]], use_container_width=True, hide_index=True)
        st.divider()

        st.subheader("🗑️ Remover Pessoa")
        st.warning("Atenção: remover uma pessoa apaga também todos os seus embeddings e não pode ser desfeito.")

        opcoes = {f"ID {p['id']} — {p['name']}": p['id'] for p in persons}
        selecionado = st.selectbox("Selecione a pessoa para remover", options=list(opcoes.keys()))

        if st.button("🗑️ Remover", type="primary"):
            person_id = opcoes[selecionado]
            try:
                response = requests.delete(
                    f"http://localhost:8000/persons/{person_id}",
                    headers=HEADERS
                )
                if response.status_code == 200:
                    st.success(f"✅ {response.json()['message']}")
                    st.rerun()
                else:
                    st.error(f"❌ {response.json()['detail']}")
            except Exception as e:
                st.error(f"❌ Erro ao remover: {e}")

except requests.exceptions.ConnectionError:
    st.error("❌ API offline. Rode: uvicorn app.main:app --reload --env-file .env")
except Exception as e:
    st.error(f"❌ Erro: {e}")

if st.button("🔄 Atualizar lista"):
    st.rerun()