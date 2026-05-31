"""
1_Cadastrar_Pessoa.py

Responsabilidade: Página para cadastrar uma nova pessoa no sistema.

O usuário pode cadastrar de duas formas:
    1. Upload de foto — envia uma imagem salva no computador
    2. Tirar foto — usa a câmera do Mac diretamente pelo navegador

A página chama a API que detecta o rosto, gera o embedding
e salva tudo no banco de dados.
"""

import streamlit as st  # Interface web
import requests         # Chamadas HTTP para a API

# ── Configuração da página ─────────────────────────────────────────────────────

st.set_page_config(page_title="Cadastrar Pessoa", page_icon="📸", layout="wide")

st.title("📸 Cadastrar Pessoa")
st.markdown("Envie uma foto ou tire uma pela câmera para cadastrar uma nova pessoa.")
st.divider()

# ── Nome da pessoa ─────────────────────────────────────────────────────────────

name = st.text_input(
    "Nome da pessoa",
    placeholder="Ex: Filipe Silva",
    help="Este nome será exibido quando a pessoa for reconhecida pela câmera."
)

st.divider()

# ── Escolha do método de foto ──────────────────────────────────────────────────

# Abas para escolher entre upload e câmera
aba_upload, aba_camera = st.tabs(["📁 Upload de Foto", "📷 Tirar Foto"])

foto_bytes = None   # Conteúdo da imagem em bytes
foto_nome  = None   # Nome do arquivo
foto_tipo  = None   # Tipo MIME (image/jpeg, image/png)

# ── Aba 1: Upload de arquivo ───────────────────────────────────────────────────

with aba_upload:
    st.markdown("Selecione uma foto salva no seu computador.")

    photo = st.file_uploader(
        "Foto da pessoa",
        type=["jpg", "jpeg", "png"],
        help="Use uma foto com boa iluminação e rosto centralizado.",
        label_visibility="collapsed"
    )

    if photo:
        # Exibe a prévia da foto enviada
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(photo, caption="Foto selecionada", width=200)

        # Guarda os dados da foto para enviar à API
        foto_bytes = photo.getvalue()
        foto_nome  = photo.name
        foto_tipo  = photo.type

# ── Aba 2: Tirar foto pela câmera ─────────────────────────────────────────────

with aba_camera:
    st.markdown("Use a câmera do seu computador para tirar uma foto agora.")

    # st.camera_input abre a câmera do Mac diretamente no navegador
    # O navegador pede permissão de câmera na primeira vez
    camera_photo = st.camera_input(
        "Clique em 'Take Photo' para tirar a foto",
        label_visibility="collapsed"
    )

    if camera_photo:
        # Guarda os dados da foto tirada pela câmera
        foto_bytes = camera_photo.getvalue()
        foto_nome  = "camera_capture.jpg"
        foto_tipo  = "image/jpeg"

        st.success("✅ Foto tirada com sucesso!")

# ── Botão de cadastro ──────────────────────────────────────────────────────────

st.divider()

# Só habilita o botão se nome e foto estiverem preenchidos
cadastrar = st.button(
    "✅ Cadastrar Pessoa",
    type="primary",
    disabled=not (name and foto_bytes),
    use_container_width=True
)

if cadastrar:
    with st.spinner("Detectando rosto e cadastrando no banco..."):
        try:
            # Envia a foto e o nome para a API via multipart/form-data
            response = requests.post(
                "http://localhost:8000/persons/register",
                data={"name": name},
                files={"file": (foto_nome, foto_bytes, foto_tipo)}
            )

            if response.status_code == 200:
                data = response.json()
                st.success(f"✅ {data['message']}")
                st.info(
                    f"**ID no banco:** {data['person_id']} | "
                    f"**Confiança da detecção:** {data['confidence']}"
                )

            elif response.status_code == 400:
                # Não encontrou rosto na foto
                st.error(f"❌ {response.json()['detail']}")
                st.warning("Dica: use uma foto com rosto centralizado e boa iluminação.")

            else:
                st.error(f"❌ Erro na API: {response.json()['detail']}")

        except requests.exceptions.ConnectionError:
            st.error("❌ API offline. Rode: uvicorn app.main:app --reload")

# ── Dicas para boa foto ────────────────────────────────────────────────────────

with st.expander("💡 Dicas para uma boa foto"):
    st.markdown("""
    - Rosto **centralizado** na foto
    - **Boa iluminação** — evite sombras no rosto
    - **Fundo neutro** — evite fundos com muitas pessoas
    - **Foto nítida** — evite fotos borradas
    - **Apenas um rosto** na foto — se houver mais de um, o sistema usa o de maior confiança
    """)