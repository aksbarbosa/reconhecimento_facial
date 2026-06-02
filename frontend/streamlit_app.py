"""
streamlit_app.py — Página inicial do Face Access System (modelo escolar).

Lê a API Key do .env e verifica a saúde da API.

Como rodar:
    streamlit run frontend/streamlit_app.py
"""

import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Face Access System",
    page_icon="👤",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "api_key" not in st.session_state:
    st.session_state.api_key = os.getenv("API_KEY", "")

st.title("👤 Face Access System")
st.markdown("Reconhecimento facial escolar com controle de acesso por horário.")
st.divider()

# ── Status da API ──────────────────────────────────────────────────────────────
try:
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
    st.error("❌ API offline — rode: uvicorn app.main:app --reload --env-file .env")

st.divider()

# ── Fluxo de uso ─────────────────────────────────────────────────────────────────
st.markdown("### Ordem de cadastro")
st.markdown("""
O sistema segue uma hierarquia. Cadastre nesta ordem:

1. **🕒 Horários** — defina os turnos (nome + período).
2. **🏫 Turmas** — crie turmas e vincule cada uma a um horário.
3. **📸 Cadastrar Aluno** — cadastre o aluno com foto e escolha a turma dele.
""")

st.divider()
st.markdown("### Páginas")
st.markdown("""
| Página | Descrição |
|---|---|
| 🕒 **Horários** | Defina os turnos com início e fim |
| 🏫 **Turmas** | Crie turmas vinculadas a um horário |
| 📸 **Cadastrar Aluno** | Cadastre alunos com foto e turma |
| 🎥 **Câmera Ao Vivo** | Reconhecimento e decisão de acesso em tempo real |
| 📋 **Histórico** | Acessos registrados (liberado/negado) |
| 👥 **Alunos Cadastrados** | Gerencie alunos e suas turmas |
""")