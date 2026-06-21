"""
3_Cadastrar_Aluno.py — Cadastro de aluno com foto e turma.
"""

import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}
API = "http://localhost:8000"

st.set_page_config(page_title="Cadastrar Aluno", page_icon="📸", layout="wide")
st.title("📸 Cadastrar Aluno")
st.markdown("Envie uma foto ou tire uma pela câmera para cadastrar um aluno.")
st.divider()


def carregar_turmas():
    try:
        return requests.get(f"{API}/turmas/", headers=HEADERS, timeout=5).json().get("turmas", [])
    except Exception:
        return []


turmas = carregar_turmas()

nome = st.text_input("Nome do aluno", placeholder="Ex: Filipe Silva")

if not turmas:
    st.warning("⚠️ Cadastre ao menos uma turma antes (página **Turmas**).")
    turma_id = None
else:
    op_turma = {
        f"{t['nome']} — {t.get('horario_nome', 'sem turno')}": t["id"]
        for t in turmas
    }
    turma_label = st.selectbox("Turma", options=list(op_turma.keys()))
    turma_id = op_turma[turma_label]

st.divider()

aba_upload, aba_camera = st.tabs(["📁 Upload de Foto", "📷 Tirar Foto"])

foto_bytes = foto_nome = foto_tipo = None

with aba_upload:
    photo = st.file_uploader("Foto", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
    if photo:
        st.image(photo, caption="Foto selecionada", width=200)
        foto_bytes, foto_nome, foto_tipo = photo.getvalue(), photo.name, photo.type

with aba_camera:
    camera_photo = st.camera_input("Tirar foto", label_visibility="collapsed")
    if camera_photo:
        foto_bytes, foto_nome, foto_tipo = camera_photo.getvalue(), "camera_capture.jpg", "image/jpeg"
        st.success("✅ Foto tirada!")

st.divider()

pode_cadastrar = bool(nome and foto_bytes and turma_id)
if st.button("✅ Cadastrar Aluno", type="primary", disabled=not pode_cadastrar, use_container_width=True):
    with st.spinner("Detectando rosto e cadastrando..."):
        try:
            data = {"nome": nome, "turma_id": turma_id}
            resp = requests.post(
                f"{API}/alunos/register",
                headers=HEADERS,
                data=data,
                files={"file": (foto_nome, foto_bytes, foto_tipo)}
            )
            if resp.status_code == 200:
                d = resp.json()
                st.success(f"✅ {d['message']}")
                st.info(f"**ID:** {d['aluno_id']} | **Confiança:** {d['confidence']}")
            elif resp.status_code == 400:
                st.error(f"❌ {resp.json()['detail']}")
                st.warning("Dica: use uma foto com rosto centralizado e boa iluminação.")
            elif resp.status_code == 403:
                st.error("❌ API Key inválida. Verifique o .env")
            else:
                st.error(f"❌ {resp.json().get('detail', 'Erro desconhecido')}")
        except requests.exceptions.ConnectionError:
            st.error("❌ API offline. Rode: uvicorn app.main:app --reload --env-file .env")

with st.expander("💡 Dicas para uma boa foto"):
    st.markdown("- Rosto centralizado\n- Boa iluminação\n- Fundo neutro\n- Apenas um rosto\n- Foto nítida")