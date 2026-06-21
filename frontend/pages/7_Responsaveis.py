"""
7_Responsaveis.py — Gestão de responsáveis no FaceNotify via Supabase Admin API.

Permite cadastrar responsáveis (usuários do app mobile), gerenciar seus
dependentes e remover contas, sem precisar acessar o painel do Supabase.

Variáveis de ambiente necessárias:
    SUPABASE_URL             — URL do projeto Supabase
    SUPABASE_SERVICE_ROLE_KEY — chave service_role (acesso admin)
"""

import os
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL      = os.getenv("SUPABASE_URL", "")
SUPABASE_SRK      = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

st.set_page_config(page_title="Responsáveis", page_icon="👥", layout="wide")
st.title("👥 Responsáveis")
st.markdown("Cadastre e gerencie os responsáveis que recebem notificações no **FaceNotify**.")
st.divider()

# ── Verificação de configuração ────────────────────────────────────────────────
if not SUPABASE_URL or not SUPABASE_SRK:
    st.error(
        "⚠️ Variáveis **SUPABASE_URL** e **SUPABASE_SERVICE_ROLE_KEY** não configuradas no `.env`.\n\n"
        "Encontre a service role key em: Supabase → Project Settings → API → service_role."
    )
    st.stop()


@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SRK)


supabase = get_supabase()


# ── Helpers ────────────────────────────────────────────────────────────────────
def carregar_responsaveis():
    """Retorna lista de responsáveis com seus dependentes."""
    try:
        profiles = supabase.table("profiles").select("id, name, address").execute().data or []
        dependents = supabase.table("dependents").select("id, profile_id, name").execute().data or []

        dep_by_profile: dict[str, list] = {}
        for d in dependents:
            dep_by_profile.setdefault(d["profile_id"], []).append(d)

        # Busca e-mails via Admin API
        users_resp = supabase.auth.admin.list_users()
        email_by_id = {u.id: u.email for u in (users_resp or [])}

        return [
            {
                **p,
                "email": email_by_id.get(p["id"], "—"),
                "dependents": dep_by_profile.get(p["id"], []),
            }
            for p in profiles
        ]
    except Exception as e:
        st.error(f"Erro ao carregar responsáveis: {e}")
        return []


def criar_responsavel(nome: str, email: str, senha: str) -> tuple[bool, str]:
    try:
        res = supabase.auth.admin.create_user({
            "email": email,
            "password": senha,
            "email_confirm": True,
            "user_metadata": {"name": nome},
        })
        uid = res.user.id
        supabase.table("profiles").insert({"id": uid, "name": nome}).execute()
        return True, uid
    except Exception as e:
        return False, str(e)


def adicionar_dependente(profile_id: str, nome: str) -> bool:
    try:
        supabase.table("dependents").insert({"profile_id": profile_id, "name": nome}).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar dependente: {e}")
        return False


def remover_dependente(dep_id: str) -> bool:
    try:
        supabase.table("dependents").delete().eq("id", dep_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao remover dependente: {e}")
        return False


def remover_responsavel(uid: str) -> bool:
    try:
        supabase.auth.admin.delete_user(uid)
        return True
    except Exception as e:
        st.error(f"Erro ao remover responsável: {e}")
        return False


# ── Abas ──────────────────────────────────────────────────────────────────────
aba_lista, aba_novo = st.tabs(["📋 Responsáveis cadastrados", "➕ Novo responsável"])

# ─────────────────────────────────────────────────────────────────────────────
# ABA 1 — Lista
# ─────────────────────────────────────────────────────────────────────────────
with aba_lista:
    if st.button("🔄 Atualizar lista", key="refresh"):
        st.cache_resource.clear()
        st.rerun()

    responsaveis = carregar_responsaveis()

    if not responsaveis:
        st.info("Nenhum responsável cadastrado ainda. Use a aba **Novo responsável** para criar.")
    else:
        for resp in responsaveis:
            with st.expander(f"👤 {resp['name']}  —  {resp['email']}"):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.caption(f"**ID:** {resp['id']}")
                    if resp.get("address"):
                        st.caption(f"**Endereço:** {resp['address']}")

                    # Dependentes
                    st.markdown("**Dependentes:**")
                    if not resp["dependents"]:
                        st.caption("Nenhum dependente vinculado.")
                    else:
                        for dep in resp["dependents"]:
                            dcol1, dcol2 = st.columns([4, 1])
                            dcol1.markdown(f"• {dep['name']}  `{dep['id']}`")
                            if dcol2.button("Remover", key=f"rem_dep_{dep['id']}"):
                                if remover_dependente(dep["id"]):
                                    st.success(f"Dependente **{dep['name']}** removido.")
                                    st.rerun()

                    # Adicionar dependente inline
                    st.markdown("---")
                    novo_dep = st.text_input(
                        "Adicionar dependente",
                        placeholder="Nome do dependente",
                        key=f"new_dep_{resp['id']}",
                    )
                    if st.button("Adicionar", key=f"add_dep_{resp['id']}"):
                        if novo_dep.strip():
                            if adicionar_dependente(resp["id"], novo_dep.strip()):
                                st.success(f"Dependente **{novo_dep}** adicionado.")
                                st.rerun()
                        else:
                            st.warning("Digite o nome do dependente.")

                with col2:
                    st.markdown(" ")
                    if st.button("🗑️ Remover responsável", key=f"del_{resp['id']}",
                                 type="primary", use_container_width=True):
                        st.session_state[f"confirm_{resp['id']}"] = True

                    if st.session_state.get(f"confirm_{resp['id']}"):
                        st.warning(f"Remover **{resp['name']}** e todos os seus dependentes?")
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Confirmar", key=f"conf_yes_{resp['id']}"):
                            if remover_responsavel(resp["id"]):
                                st.success(f"Responsável **{resp['name']}** removido.")
                                del st.session_state[f"confirm_{resp['id']}"]
                                st.rerun()
                        if c2.button("❌ Cancelar", key=f"conf_no_{resp['id']}"):
                            del st.session_state[f"confirm_{resp['id']}"]
                            st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# ABA 2 — Novo responsável
# ─────────────────────────────────────────────────────────────────────────────
with aba_novo:
    st.markdown("Preencha os dados do responsável. Ele poderá fazer login no **FaceNotify** com o e-mail e a senha definidos aqui.")
    st.divider()

    with st.form("form_novo_resp", clear_on_submit=True):
        nome  = st.text_input("Nome completo *", placeholder="Ex: João Silva")
        email = st.text_input("E-mail *", placeholder="Ex: joao@email.com")
        senha = st.text_input("Senha provisória *", type="password",
                              help="Mínimo 6 caracteres. O responsável pode alterar depois no app.")

        st.markdown("**Dependentes** (opcional — pode adicionar depois)")
        dep1 = st.text_input("Dependente 1", placeholder="Nome do dependente")
        dep2 = st.text_input("Dependente 2", placeholder="Nome do dependente")
        dep3 = st.text_input("Dependente 3", placeholder="Nome do dependente")

        submitted = st.form_submit_button("✅ Cadastrar responsável", type="primary", use_container_width=True)

    if submitted:
        erros = []
        if not nome.strip():  erros.append("Nome é obrigatório.")
        if not email.strip(): erros.append("E-mail é obrigatório.")
        if len(senha) < 6:    erros.append("Senha deve ter no mínimo 6 caracteres.")

        if erros:
            for e in erros:
                st.error(e)
        else:
            with st.spinner("Criando conta..."):
                ok, resultado = criar_responsavel(nome.strip(), email.strip(), senha)

            if ok:
                uid = resultado
                # Adiciona dependentes informados
                nomes_deps = [d.strip() for d in [dep1, dep2, dep3] if d.strip()]
                for nd in nomes_deps:
                    adicionar_dependente(uid, nd)

                st.success(f"✅ Responsável **{nome}** cadastrado com sucesso!")
                if nomes_deps:
                    st.info(f"Dependentes adicionados: {', '.join(nomes_deps)}")

                st.markdown("---")
                st.markdown("**Próximo passo:** copie o ID do dependente e use no cadastro do aluno no Face Access.")

                # Mostra IDs dos dependentes criados
                try:
                    deps = supabase.table("dependents").select("id, name").eq("profile_id", uid).execute().data or []
                    if deps:
                        st.markdown("**IDs dos dependentes criados:**")
                        for d in deps:
                            st.code(f"{d['name']}: {d['id']}", language=None)
                except Exception:
                    pass
            else:
                msg = resultado
                if "already registered" in msg or "already been registered" in msg:
                    st.error("❌ Este e-mail já está cadastrado no Supabase.")
                else:
                    st.error(f"❌ Erro ao criar conta: {msg}")
