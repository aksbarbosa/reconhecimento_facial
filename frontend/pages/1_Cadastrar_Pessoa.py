"""
1_Cadastrar_Pessoa.py
"""

import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}

st.set_page_config(page_title="Cadastrar Pessoa", page_icon="📸", layout="wide")
st.title("📸 Cadastrar Pessoa")
st.markdown("Envie uma foto ou tire uma pela câmera para cadastrar uma nova pessoa.")
st.divider()

name = st.text_input("Nome da pessoa", placeholder="Ex: Filipe Silva")
st.divider()

aba_upload, aba_camera = st.tabs(["📁 Upload de Foto", "📷 Tirar Foto"])

foto_bytes = None
foto_nome  = None
foto_tipo  = None

with aba_upload:
    st.markdown("Selecione uma foto salva no seu computador.")
    photo = st.file_uploader("Foto", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
    if photo:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(photo, caption="Foto selecionada", width=200)
        foto_bytes = photo.getvalue()
        foto_nome  = photo.name
        foto_tipo  = photo.type

with aba_camera:
    st.markdown("Use a câmera do seu computador para tirar uma foto agora.")
    camera_photo = st.camera_input("Tirar foto", label_visibility="collapsed")
    if camera_photo:
        foto_bytes = camera_photo.getvalue()
        foto_nome  = "camera_capture.jpg"
        foto_tipo  = "image/jpeg"
        st.success("✅ Foto tirada com sucesso!")

st.divider()

if st.button("✅ Cadastrar Pessoa", type="primary", disabled=not (name and foto_bytes), use_container_width=True):
    with st.spinner("Detectando rosto e cadastrando no banco..."):
        try:
            response = requests.post(
                "http://localhost:8000/persons/register",
                headers=HEADERS,
                data={"name": name},
                files={"file": (foto_nome, foto_bytes, foto_tipo)}
            )
            if response.status_code == 200:
                data = response.json()
                st.success(f"✅ {data['message']}")
                st.info(f"**ID no banco:** {data['person_id']} | **Confiança:** {data['confidence']}")
            elif response.status_code == 400:
                st.error(f"❌ {response.json()['detail']}")
                st.warning("Dica: use uma foto com rosto centralizado e boa iluminação.")
            elif response.status_code == 403:
                st.error("❌ API Key inválida. Verifique o arquivo .env")
            else:
                st.error(f"❌ Erro: {response.json().get('detail', 'Erro desconhecido')}")
        except requests.exceptions.ConnectionError:
            st.error("❌ API offline. Rode: uvicorn app.main:app --reload --env-file .env")

with st.expander("💡 Dicas para uma boa foto"):
    st.markdown("""
    - Rosto **centralizado** na foto
    - **Boa iluminação** — evite sombras no rosto
    - **Fundo neutro** — evite fundos com muitas pessoas
    - **Foto nítida** — evite fotos borradas
    - **Apenas um rosto** na foto
    """)