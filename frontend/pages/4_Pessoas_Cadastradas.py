"""
4_Pessoas_Cadastradas.py

Responsabilidade: Página para visualizar e gerenciar as pessoas
cadastradas no sistema.

Exibe a lista completa de pessoas e permite remover cadastros.
"""

import requests         # Chamadas HTTP para a API
import streamlit as st  # Interface web
import pandas as pd     # Para exibir os dados em tabela

# ── Configuração da página ─────────────────────────────────────────────────────

st.set_page_config(page_title="Pessoas Cadastradas", page_icon="👥", layout="wide")

st.title("👥 Pessoas Cadastradas")
st.markdown("Gerencie as pessoas cadastradas no sistema.")
st.divider()

# ── Lista as pessoas cadastradas ───────────────────────────────────────────────

try:
    # Busca a lista de pessoas pela API
    response = requests.get("http://localhost:8000/persons/", timeout=5)
    data = response.json()
    persons = data.get("persons", [])

    if not persons:
        st.info("Nenhuma pessoa cadastrada ainda. Vá para a página **Cadastrar Pessoa**.")

    else:
        # Exibe o total de pessoas cadastradas
        st.metric("Total de pessoas", data["total"])
        st.divider()

        # Exibe a tabela de pessoas
        df = pd.DataFrame(persons)
        df = df.rename(columns={
            "id":         "ID",
            "name":       "Nome",
            "created_at": "Cadastrado em",
        })

        st.dataframe(
            df[["ID", "Nome", "Cadastrado em"]],
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        # ── Remover pessoa ─────────────────────────────────────────────────────

        st.subheader("🗑️ Remover Pessoa")
        st.warning("Atenção: remover uma pessoa apaga também todos os seus embeddings e não pode ser desfeito.")

        # Cria um seletor com os nomes das pessoas cadastradas
        opcoes = {f"ID {p['id']} — {p['name']}": p['id'] for p in persons}
        selecionado = st.selectbox("Selecione a pessoa para remover", options=list(opcoes.keys()))

        if st.button("🗑️ Remover", type="primary"):
            person_id = opcoes[selecionado]

            try:
                # Chama o endpoint DELETE da API
                response = requests.delete(f"http://localhost:8000/persons/{person_id}")

                if response.status_code == 200:
                    st.success(f"✅ {response.json()['message']}")
                    st.rerun()  # Atualiza a lista após remover
                else:
                    st.error(f"❌ {response.json()['detail']}")

            except Exception as e:
                st.error(f"❌ Erro ao remover: {e}")

except requests.exceptions.ConnectionError:
    st.error("❌ API offline. Rode: uvicorn app.main:app --reload")

except Exception as e:
    st.error(f"❌ Erro: {e}")

# ── Botão de atualizar ─────────────────────────────────────────────────────────

if st.button("🔄 Atualizar lista"):
    st.rerun()