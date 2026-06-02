"""
4_Camera_Ao_Vivo.py — Reconhecimento ao vivo com decisão de acesso por horário.
"""

import time
import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}
API = "http://localhost:8000"

st.set_page_config(page_title="Câmera Ao Vivo", page_icon="🎥", layout="wide")
st.title("🎥 Câmera Ao Vivo")
st.markdown("Controle a câmera e acompanhe os reconhecimentos em tempo real.")
st.divider()


def get_status():
    try:
        return requests.get(f"{API}/camera/status", headers=HEADERS, timeout=2).json()
    except Exception:
        return {}


status = get_status()
camera_running = status.get("camera_running", False)
candidates_loaded = status.get("candidates_loaded", 0)

if status:
    if camera_running:
        st.success(f"🟢 Câmera ativa | {candidates_loaded} cadastro(s)")
    else:
        st.warning(f"🔴 Câmera inativa | {candidates_loaded} cadastro(s)")
else:
    st.error("❌ API offline. Rode: uvicorn app.main:app --reload")

st.divider()

col1, col2 = st.columns(2)
with col1:
    if st.button("▶️ Ligar Câmera", type="primary", use_container_width=True):
        try:
            resp = requests.post(f"{API}/camera/start", headers=HEADERS,
                                 params={"source": 0, "threshold": 0.6})
            if resp.status_code == 200:
                st.success("✅ Câmera iniciada!"); st.rerun()
            else:
                st.error(f"❌ {resp.json().get('detail', 'Erro')}")
        except Exception:
            st.error("❌ API offline.")
with col2:
    if st.button("⏹️ Desligar Câmera", use_container_width=True):
        try:
            resp = requests.post(f"{API}/camera/stop", headers=HEADERS)
            if resp.status_code == 200:
                st.success("✅ Câmera encerrada!"); st.rerun()
            else:
                st.error(f"❌ {resp.json().get('detail', 'Erro')}")
        except Exception:
            st.error("❌ API offline.")

st.divider()
st.subheader("🔍 Último Reconhecimento")

try:
    last = requests.get(f"{API}/camera/last", headers=HEADERS, timeout=2).json()
except Exception:
    last = {}

if last and last.get("status"):
    granted = last.get("access_granted", False)
    message = last.get("message", "")
    status_code = last.get("status")

    # Banner grande de acesso
    if granted:
        st.success(f"## ✅ ACESSO LIBERADO\n**{message}**")
    else:
        st.error(f"## ⛔ ACESSO NEGADO\n**{message}**")

    if status_code == "nao_cadastrado":
        st.caption(f"Horário: {last.get('timestamp', '—')}")
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Aluno", last.get("aluno_nome", "—"))
        c2.metric("Turma", last.get("turma_nome", "—"))
        c3.metric("Turno", last.get("horario_nome", "—"))
        c4.metric("Confiança", f"{last.get('similarity', 0):.0%}")
        c5.metric("Horário", last.get("timestamp", "—"))
else:
    st.info("Nenhum reconhecimento ainda. Ligue a câmera e apareça na frente dela!")

st.divider()
st.caption("🔄 Atualiza automaticamente a cada 3 segundos.")

if camera_running:
    time.sleep(3)
    st.rerun()