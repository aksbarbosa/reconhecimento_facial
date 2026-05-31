"""
2_Camera_Ao_Vivo.py

Responsabilidade: Página para acompanhar o reconhecimento facial
em tempo real via câmera.
"""

import time
import os
import requests
import streamlit as st
from dotenv import load_dotenv

# Carrega a API Key do .env
load_dotenv()
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}

st.set_page_config(page_title="Câmera Ao Vivo", page_icon="🎥", layout="wide")

st.title("🎥 Câmera Ao Vivo")
st.markdown("Controle a câmera e acompanhe os reconhecimentos em tempo real.")
st.divider()

# ── Status da câmera ───────────────────────────────────────────────────────────

def get_camera_status():
    """Consulta o status atual da câmera na API."""
    try:
        response = requests.get(
            "http://localhost:8000/camera/status",
            headers=HEADERS,
            timeout=2
        )
        return response.json()
    except Exception:
        return {}

status = get_camera_status()

# Usa .get() para evitar KeyError caso a chave não exista na resposta
camera_running    = status.get("camera_running", False)
candidates_loaded = status.get("candidates_loaded", 0)

if status:
    if camera_running:
        st.success(f"🟢 Câmera ativa | {candidates_loaded} pessoa(s) cadastrada(s)")
    else:
        st.warning(f"🔴 Câmera inativa | {candidates_loaded} pessoa(s) cadastrada(s)")
else:
    st.error("❌ API offline. Rode: uvicorn app.main:app --reload")

st.divider()

# ── Controles da câmera ────────────────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    if st.button("▶️ Ligar Câmera", type="primary", use_container_width=True):
        try:
            response = requests.post(
                "http://localhost:8000/camera/start",
                headers=HEADERS,
                params={"source": 0, "threshold": 0.6}
            )
            if response.status_code == 200:
                st.success("✅ Câmera iniciada!")
                st.rerun()
            else:
                st.error(f"❌ {response.json().get('detail', 'Erro desconhecido')}")
        except Exception:
            st.error("❌ API offline.")

with col2:
    if st.button("⏹️ Desligar Câmera", use_container_width=True):
        try:
            response = requests.post(
                "http://localhost:8000/camera/stop",
                headers=HEADERS
            )
            if response.status_code == 200:
                st.success("✅ Câmera encerrada!")
                st.rerun()
            else:
                st.error(f"❌ {response.json().get('detail', 'Erro desconhecido')}")
        except Exception:
            st.error("❌ API offline.")

st.divider()

# ── Último reconhecimento ──────────────────────────────────────────────────────

st.subheader("🔍 Último Reconhecimento")

try:
    response = requests.get(
        "http://localhost:8000/camera/last",
        headers=HEADERS,
        timeout=2
    )
    last = response.json()
except Exception:
    last = {}

if last and last.get("person_name"):
    col1, col2, col3 = st.columns(3)
    col1.metric("Pessoa", last.get("person_name", "—"))
    col2.metric("Confiança", f"{last.get('similarity', 0):.0%}")
    col3.metric("Horário", last.get("timestamp", "—"))
else:
    st.info("Nenhum reconhecimento registrado ainda. Ligue a câmera e apareça na frente dela!")

st.divider()

# ── Auto-atualização ───────────────────────────────────────────────────────────

st.caption("🔄 Página atualiza automaticamente a cada 3 segundos.")

if camera_running:
    time.sleep(3)
    st.rerun()