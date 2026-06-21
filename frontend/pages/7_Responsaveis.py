"""
7_Responsaveis.py — Gestão de responsáveis no FaceNotify via Supabase Admin API.

Permite cadastrar responsáveis (usuários do app mobile), vincular alunos
cadastrados no Face Access como seus dependentes, e remover contas.

Variáveis de ambiente necessárias:
    SUPABASE_URL              — URL do projeto Supabase
    SUPABASE_SERVICE_ROLE_KEY — chave service_role (acesso admin)
    API_KEY                   — chave da API local do Face Access
"""

import os
import requests
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SRK = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
API_KEY      = os.getenv("API_KEY", "")
API          = "http://localhost:8000"
HEADERS      = {"X-API-Key": API_KEY}

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


# ── Helpers — Supabase ─────────────────────────────────────────────────────────
def carregar_responsaveis() -> list:
    try:
        profiles   = supabase.table("profiles").select("id, name, address").execute().data or []
        dependents = supabase.table("dependents").select("id, profile_id, name").execute().data or []
        users_resp = supabase.auth.admin.list_users()
        email_by_id = {u.id: u.email for u in (users_resp or [])}

        dep_by_profile: dict[str, list] = {}
        for d in dependents:
            dep_by_profile.setdefault(d["profile_id"], []).append(d)

        return [
            {**p, "email": email_by_id.get(p["id"], "—"),
             "dependents": dep_by_profile.get(p["id"], [])}
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
    except Exception as e:
        msg = str(e)
        if "already registered" in msg or "already been registered" in msg or "already exists" in msg:
            return False, "already registered"
        return False, msg

    try:
        supabase.table("profiles").upsert({"id": uid, "name": nome}).execute()
    except Exception:
        pass  # perfil já existe, ignora

    return True, uid


def criar_dependente_supabase(profile_id: str, nome: str) -> str | None:
    """Cria o dependente no Supabase e retorna o UUID gerado."""
    try:
        res = supabase.table("dependents").insert(
            {"profile_id": profile_id, "name": nome}
        ).execute()
        return res.data[0]["id"] if res.data else None
    except Exception as e:
        st.error(f"Erro ao criar dependente no Supabase: {e}")
        return None


def remover_dependente(dep_id: str, aluno_id: int | None = None) -> bool:
    try:
        supabase.table("dependents").delete().eq("id", dep_id).execute()
        # Limpa o vínculo no Face Access
        if aluno_id:
            requests.patch(
                f"{API}/alunos/{aluno_id}/vincular",
                data={"supabase_dependent_id": ""},
                headers=HEADERS, timeout=5
            )
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


# ── Helpers — Face Access API ──────────────────────────────────────────────────
def carregar_alunos() -> list:
    """Retorna todos os alunos do Face Access."""
    try:
        return requests.get(f"{API}/alunos/", headers=HEADERS, timeout=5).json().get("alunos", [])
    except Exception:
        return []


def vincular_aluno(aluno_id: int, dep_uuid: str) -> bool:
    """Salva o supabase_dependent_id no aluno do Face Access."""
    try:
        r = requests.patch(
            f"{API}/alunos/{aluno_id}/vincular",
            data={"supabase_dependent_id": dep_uuid},
            headers=HEADERS, timeout=5
        )
        return r.status_code == 200
    except Exception:
        return False


# ── Abas ──────────────────────────────────────────────────────────────────────
aba_lista, aba_novo = st.tabs(["📋 Responsáveis cadastrados", "➕ Novo responsável"])

# ─────────────────────────────────────────────────────────────────────────────
# ABA 1 — Lista
# ─────────────────────────────────────────────────────────────────────────────
with aba_lista:
    if st.button("🔄 Atualizar", key="refresh"):
        st.rerun()

    responsaveis = carregar_responsaveis()
    alunos_todos = carregar_alunos()

    # Alunos disponíveis para vínculo (sem dependente ainda)
    alunos_livres = [a for a in alunos_todos if not a.get("supabase_dependent_id")]
    opcoes_alunos = {
        f"{a['nome']}  ({a.get('turma_nome') or 'sem turma'})": a
        for a in alunos_livres
    }

    if not responsaveis:
        st.info("Nenhum responsável cadastrado. Use a aba **Novo responsável**.")
    else:
        for resp in responsaveis:
            with st.expander(f"👤 {resp['name']}  —  {resp['email']}"):
                col_info, col_acao = st.columns([3, 1])

                with col_info:
                    st.caption(f"**ID Supabase:** `{resp['id']}`")

                    # ── Dependentes vinculados ───────────────────────────────
                    st.markdown("**Dependentes vinculados:**")
                    if not resp["dependents"]:
                        st.caption("Nenhum dependente vinculado.")
                    else:
                        for dep in resp["dependents"]:
                            # Descobre se há aluno vinculado a este dependente
                            aluno_vinc = next(
                                (a for a in alunos_todos if a.get("supabase_dependent_id") == dep["id"]),
                                None
                            )
                            dcol1, dcol2 = st.columns([5, 1])
                            label = f"**{dep['name']}**"
                            if aluno_vinc:
                                label += f"  ←  aluno: {aluno_vinc['nome']} ({aluno_vinc.get('turma_nome') or 'sem turma'})"
                            dcol1.markdown(f"• {label}")
                            dcol1.caption(f"  `{dep['id']}`")
                            if dcol2.button("Remover", key=f"rem_dep_{dep['id']}"):
                                aluno_id = aluno_vinc["id"] if aluno_vinc else None
                                if remover_dependente(dep["id"], aluno_id):
                                    st.success(f"Dependente **{dep['name']}** removido.")
                                    st.rerun()

                    # ── Vincular novo aluno ──────────────────────────────────
                    st.markdown("---")
                    st.markdown("**Vincular aluno como dependente:**")

                    if not opcoes_alunos:
                        st.caption("Todos os alunos já estão vinculados a um responsável.")
                    else:
                        sel = st.selectbox(
                            "Selecione o aluno",
                            options=["— selecione —"] + list(opcoes_alunos.keys()),
                            key=f"sel_aluno_{resp['id']}",
                        )
                        if st.button("Vincular", key=f"add_dep_{resp['id']}"):
                            if sel == "— selecione —":
                                st.warning("Selecione um aluno.")
                            else:
                                aluno = opcoes_alunos[sel]
                                dep_uuid = criar_dependente_supabase(resp["id"], aluno["nome"])
                                if dep_uuid:
                                    ok = vincular_aluno(aluno["id"], dep_uuid)
                                    if ok:
                                        st.success(
                                            f"✅ **{aluno['nome']}** vinculado como dependente de **{resp['name']}**."
                                        )
                                        st.rerun()
                                    else:
                                        st.error("Dependente criado no Supabase, mas falha ao atualizar o aluno no Face Access.")

                with col_acao:
                    st.markdown(" ")
                    if st.button("🗑️ Remover responsável", key=f"del_{resp['id']}",
                                 type="primary", use_container_width=True):
                        st.session_state[f"confirm_{resp['id']}"] = True

                    if st.session_state.get(f"confirm_{resp['id']}"):
                        st.warning(f"Remover **{resp['name']}** e todos os seus dependentes?")
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Sim", key=f"conf_yes_{resp['id']}"):
                            if remover_responsavel(resp["id"]):
                                st.success(f"Responsável **{resp['name']}** removido.")
                                del st.session_state[f"confirm_{resp['id']}"]
                                st.rerun()
                        if c2.button("❌ Não", key=f"conf_no_{resp['id']}"):
                            del st.session_state[f"confirm_{resp['id']}"]
                            st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# ABA 2 — Novo responsável
# ─────────────────────────────────────────────────────────────────────────────
with aba_novo:
    st.markdown(
        "Crie a conta do responsável no FaceNotify. "
        "Ele poderá fazer login com o e-mail e a senha definidos aqui. "
        "Os dependentes (alunos) podem ser vinculados logo abaixo ou depois na lista."
    )
    st.divider()

    alunos_form = carregar_alunos()
    alunos_livres_form = [a for a in alunos_form if not a.get("supabase_dependent_id")]
    opcoes_form = {
        f"{a['nome']}  ({a.get('turma_nome') or 'sem turma'})": a
        for a in alunos_livres_form
    }

    with st.form("form_novo_resp", clear_on_submit=True):
        st.markdown("#### Dados do responsável")
        nome  = st.text_input("Nome completo *", placeholder="Ex: João Silva")
        email = st.text_input("E-mail *", placeholder="Ex: joao@email.com")
        senha = st.text_input("Senha provisória *", type="password",
                              help="Mínimo 6 caracteres.")

        st.markdown("#### Dependentes (opcional)")
        st.caption("Selecione os alunos que este responsável acompanha. Apenas alunos ainda não vinculados aparecem aqui.")

        if not opcoes_form:
            st.info("Nenhum aluno disponível para vincular. Cadastre alunos primeiro.")
            selecionados = []
        else:
            selecionados = st.multiselect(
                "Alunos",
                options=list(opcoes_form.keys()),
                placeholder="Selecione um ou mais alunos...",
            )

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
                vinculos_ok = []
                vinculos_erro = []

                for label in selecionados:
                    aluno = opcoes_form[label]
                    dep_uuid = criar_dependente_supabase(uid, aluno["nome"])
                    if dep_uuid:
                        if vincular_aluno(aluno["id"], dep_uuid):
                            vinculos_ok.append(aluno["nome"])
                        else:
                            vinculos_erro.append(aluno["nome"])

                st.success(f"✅ Responsável **{nome}** cadastrado com sucesso!")
                if vinculos_ok:
                    st.info(f"Dependentes vinculados: {', '.join(vinculos_ok)}")
                if vinculos_erro:
                    st.warning(
                        f"Dependentes criados no Supabase mas falha no Face Access: {', '.join(vinculos_erro)}. "
                        "Verifique se a API está rodando."
                    )
            else:
                msg = resultado
                if "already registered" in msg or "already been registered" in msg:
                    st.error("❌ Este e-mail já está cadastrado.")
                else:
                    st.error(f"❌ Erro ao criar conta: {msg}")
