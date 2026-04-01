import streamlit as st
import pandas as pd

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Milanov - Portal Financeiro", layout="centered")

# LINKS DIRETOS PARA AS ABAS DA PLANILHA (VIA EXPORTAÇÃO CSV)
# Substituímos o con.gsheets por leitura direta do Pandas para evitar erros de permissão
URL_USUARIOS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSL6ftgznAq3Z-q8iWajnshFvGeRPXw_Gl7GeZydA-9qa18nOsa4Wb5xqCQ93VpC5V8YZOl7w6xROtb/pub?output=csv"
URL_AGENTES = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSL6ftgznAq3Z-q8iWajnshFvGeRPXw_Gl7GeZydA-9qa18nOsa4Wb5xqCQ93VpC5V8YZOl7w6xROtb/pub?output=csv"

def carregar_dados():
    try:
        # Carrega os dados usando o link de visualização do Google (mais estável)
        df_u = pd.read_csv(URL_USUARIOS)
        df_a = pd.read_csv(URL_AGENTES)
        return df_u, df_a
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha: {e}")
        return None, None

df_u, df_a = carregar_dados()

# ESTILO VISUAL (LOGOMARCA E TÍTULO)
st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>Milanov Serviços Administrativos</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center;'>Portal de Gestão Financeira</h3>", unsafe_allow_html=True)
st.divider()

# SISTEMA DE LOGIN
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    with st.form("login_form"):
        st.subheader("Acesso Restrito")
        usuario_input = st.text_input("Usuário")
        senha_input = st.text_input("Senha", type="password")
        botao_login = st.form_submit_button("Entrar")

        if botao_login:
            # Verifica se os dados foram carregados antes de validar
            if df_u is not None:
                # Procura o usuário na coluna 'Usuario' e senha na coluna 'Senha'
                user_match = df_u[(df_u['Usuario'] == usuario_input) & (df_u['Senha'].astype(str) == senha_input)]
                
                if not user_match.empty:
                    st.session_state.logado = True
                    st.session_state.nome_usuario = user_match.iloc[0]['Nome']
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
            else:
                st.error("Não foi possível validar o acesso. Verifique a conexão com a planilha.")

# ÁREA DO PORTAL (PÓS-LOGIN)
else:
    st.success(f"Bem-vindo(a), {st.session_state.nome_usuario}!")
    
    aba1, aba2 = st.tabs(["📊 Consulta de Agentes", "⚙️ Configurações"])

    with aba1:
        st.subheader("Base de Dados de Agentes")
        if df_a is not None:
            # Barra de busca
            busca = st.text_input("Pesquisar por Agente ou ID")
            if busca:
                # Filtra os dados da aba Cadastro_Agentes
                resultado = df_a[df_a.astype(str).apply(lambda x: busca.lower() in x.str.lower().values, axis=1)]
                st.dataframe(resultado, use_container_width=True)
            else:
                st.dataframe(df_a, use_container_width=True)
        else:
            st.warning("Dados de agentes não encontrados.")

    with aba2:
        if st.button("Sair do Portal"):
            st.session_state.logado = False
            st.rerun()

# RODAPÉ
st.markdown("---")
st.caption("© 2026 Milanov Serviços Administrativos Ltda - Interno")
