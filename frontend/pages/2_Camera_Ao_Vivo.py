"""
2_Camera_Ao_Vivo.py

Responsabilidade: Página para acompanhar o reconhecimento facial
em tempo real via câmera.

Permite ligar/desligar a câmera e exibe os reconhecimentos
conforme acontecem, consultando a API periodicamente.
"""

import time
import requests         # Chamadas HTTP para a API
import streamlit as st  # Interface web

# ── Configuração da página ─────────────────────────────────────────────────────

st.set_page_config(page_title="Câmera Ao Vivo", page_icon="🎥", layout="wide")

st.title("🎥 Câmera Ao Vivo")
st.markdown("Controle a câmera e acompanhe os reconhecimentos em tempo real.")
st.divider()

# ── Status da câmera ───────────────────────────────────────────────────────────

def get_camera_status():
    """Consulta o status atual da câmera na API."""
    try:
        response = requests.get("http://localhost:8000/camera/status", timeout=2)
        return response.json()
    except Exception:
        return None

status = get_camera_status()

# Exibe o status atual
if status:
    if status["camera_running"]:
        st.success(f"🟢 Câmera ativa | {status['candidates_loaded']} pessoa(s) cadastrada(s)")
    else:
        st.warning(f"🔴 Câmera inativa | {status['candidates_loaded']} pessoa(s) cadastrada(s)")
else:
    st.error("❌ API offline. Rode: uvicorn app.main:app --reload")

st.divider()

# ── Controles da câmera ────────────────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    # Botão para ligar a câmera
    if st.button("▶️ Ligar Câmera", type="primary", use_container_width=True):
        try:
            response = requests.post(
                "http://localhost:8000/camera/start",
                params={"source": 0, "threshold": 0.6}  # câmera 0 = Mac
            )
            if response.status_code == 200:
                st.success("✅ Câmera iniciada!")
                st.rerun()  # Atualiza a página para refletir o novo status
            else:
                st.error(f"❌ {response.json()['detail']}")
        except Exception:
            st.error("❌ API offline.")

with col2:
    # Botão para desligar a câmera
    if st.button("⏹️ Desligar Câmera", use_container_width=True):
        try:
            response = requests.post("http://localhost:8000/camera/stop")
            if response.status_code == 200:
                st.success("✅ Câmera encerrada!")
                st.rerun()
            else:
                st.error(f"❌ {response.json()['detail']}")
        except Exception:
            st.error("❌ API offline.")

st.divider()

# ── Último reconhecimento ──────────────────────────────────────────────────────

st.subheader("🔍 Último Reconhecimento")

def get_last_recognition():
    """Consulta o último reconhecimento registrado."""
    try:
        response = requests.get("http://localhost:8000/camera/last", timeout=2)
        return response.json()
    except Exception:
        return None

last = get_last_recognition()

if last and "person_name" in last:
    # Exibe os dados do último reconhecimento
    col1, col2, col3 = st.columns(3)
    col1.metric("Pessoa", last.get("person_name", "—"))
    col2.metric("Confiança", f"{last.get('similarity', 0):.0%}")
    col3.metric("Horário", last.get("timestamp", "—")[:15])
else:
    st.info("Nenhum reconhecimento registrado ainda. Ligue a câmera e apareça na frente dela!")

st.divider()

# ── Auto-atualização ───────────────────────────────────────────────────────────

# Atualiza a página automaticamente a cada 3 segundos
# para mostrar novos reconhecimentos sem precisar recarregar manualmente
st.caption("🔄 Página atualiza automaticamente a cada 3 segundos.")

if status and status.get("camera_running"):
    time.sleep(3)
    st.rerun()