"""
streamlit_app.py

Responsabilidade: Interface principal do sistema Face Access System.
Lê a API Key do .env e a passa para todas as páginas via session_state,
para que as requisições à API sejam autenticadas.

Como rodar:
    streamlit run frontend/streamlit_app.py
"""

import os
import requests
import streamlit as st
from dotenv import load_dotenv  # Lê variáveis do .env

# Carrega o .env para obter a API Key
load_dotenv()

# ── Configuração da página ─────────────────────────────────────────────────────

st.set_page_config(
    page_title="Face Access System",
    page_icon="👤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Armazena a API Key no session_state ────────────────────────────────────────
# session_state persiste entre páginas no Streamlit
# Todas as páginas podem acessar st.session_state.api_key

if "api_key" not in st.session_state:
    st.session_state.api_key = os.getenv("API_KEY", "")

# ── Cabeçalho ──────────────────────────────────────────────────────────────────

st.title("👤 Face Access System")
st.markdown("Sistema de reconhecimento facial em tempo real.")
st.divider()

# ── Status da API ──────────────────────────────────────────────────────────────

try:
    # Envia a API Key no header de todas as requisições
    headers = {"X-API-Key": st.session_state.api_key}
    response = requests.get("http://localhost:8000/health", headers=headers, timeout=2)
    data = response.json()

    if response.status_code == 200 and data["status"] == "ok":
        st.success("✅ API conectada | Banco de dados online")
    elif response.status_code == 403:
        st.error("❌ API Key inválida. Verifique o arquivo .env")
    else:
        st.warning("⚠️ API conectada | Banco de dados offline")

except Exception:
    st.error("❌ API offline — rode: uvicorn app.main:app --reload")

st.divider()

# ── Menu de navegação ──────────────────────────────────────────────────────────

st.markdown("### Navegue pelas páginas no menu lateral ←")
st.markdown("""
| Página | Descrição |
|---|---|
| 📸 **Cadastrar Pessoa** | Envie uma foto para cadastrar uma pessoa no sistema |
| 🎥 **Câmera Ao Vivo** | Acompanhe o reconhecimento facial em tempo real |
| 📋 **Histórico** | Veja todos os acessos registrados pelo sistema |
| 👥 **Pessoas Cadastradas** | Gerencie as pessoas cadastradas no banco |
""")