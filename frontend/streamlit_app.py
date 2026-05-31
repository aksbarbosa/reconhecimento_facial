"""
streamlit_app.py

Responsabilidade: Interface principal do sistema Face Access System.

Este é o ponto de entrada do frontend. Exibe o menu de navegação
e redireciona para as páginas de acordo com a seleção do usuário.

Como rodar:
    streamlit run frontend/streamlit_app.py

Páginas disponíveis:
    1. Cadastrar Pessoa   → envia foto e cadastra no banco
    2. Câmera Ao Vivo     → exibe feed da câmera com reconhecimento em tempo real
    3. Histórico          → lista todos os acessos registrados
    4. Pessoas Cadastradas → lista e remove pessoas do banco
"""

import streamlit as st  # Framework de interface web em Python

# ── Configuração da página ─────────────────────────────────────────────────────

# Deve ser a primeira chamada Streamlit do arquivo
st.set_page_config(
    page_title="Face Access System",   # Título na aba do navegador
    page_icon="👤",                    # Ícone na aba do navegador
    layout="wide",                     # Layout em tela cheia
    initial_sidebar_state="expanded"   # Menu lateral aberto por padrão
)

# ── Cabeçalho principal ────────────────────────────────────────────────────────

st.title("👤 Face Access System")
st.markdown("Sistema de reconhecimento facial em tempo real.")
st.divider()

# ── Status da API ──────────────────────────────────────────────────────────────

import requests  # Para verificar se a API está rodando

try:
    # Tenta chamar o endpoint /health da API
    response = requests.get("http://localhost:8000/health", timeout=2)
    data = response.json()

    if data["status"] == "ok":
        # API e banco respondendo normalmente
        st.success("✅ API conectada | Banco de dados online")
    else:
        # API respondeu mas banco está com problema
        st.warning("⚠️ API conectada | Banco de dados offline")

except Exception:
    # API não está rodando
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