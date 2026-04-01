import streamlit as st
import pandas as pd

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Milanov Serviços Administrativos", layout="centered")

# LINK AJUSTADO PARA FORMATO CSV (DADOS PUROS)
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSL6ftgznAq3Z-q8iWajnshFvGeRPXw_Gl7GeZydA-9qa18nOsa4Wb5xqCQ93VpC5V8YZ0l7w6xR0tb/pub?output=csv"

def carregar_dados():
    try:
        # Lê a planilha diretamente
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha: {e}")
        return None

def login():
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>Milanov Serviços Administrativos</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #4B5563;'>Portal de Gestão Financeira</h3>", unsafe_allow_html=True)
    st.write("---")

    with st.container():
        st.subheader("Acesso Restrito")
        # .upper() para garantir que funcione mesmo se digitar em minúsculo
        usuario_input = st.text_input("Usuário").strip().upper()
        senha_input = st.text_input("Senha", type="password").strip()
        botao_entrar = st.button("Entrar")

        if botao_entrar:
            df_usuarios = carregar_dados()
            
            if df_usuarios is not None:
                # Verificação exata baseada na sua planilha (USUARIO, SENHA, DEPARTAMENTO)
                validacao = df_usuarios[
                    (df_usuarios['USUARIO'].astype(str).str.upper() == usuario_input) & 
                    (df_usuarios['SENHA'].astype(str) == senha_input)
                ]
                
                if not validacao.empty:
                    depto = validacao.iloc[0]['DEPARTAMENTO']
                    st.session_state['logado'] = True
                    st.session_state['usuario'] = usuario_input
                    st.session_state['depto'] = depto
                    st.rerun()
                else:
                    st.error("Usuário ou Senha incorretos.")
            else:
                st.error("Erro na base de dados. Verifique a publicação da planilha.")

def area_logada():
    st.sidebar.title(f"Olá, {st.session_state['usuario']}")
    st.sidebar.write(f"Setor: {st.session_state['depto']}")
    if st.sidebar.button("Sair"):
        st.session_state['logado'] = False
        st.rerun()

    st.title("📊 Painel de Gestão")
    st.success(f"Acesso autorizado: {st.session_state['depto']}")
    st.write("Conexão com a planilha Milanov estabelecida com sucesso.")
    st.info("Os seus relatórios financeiros aparecerão nesta área.")

# CONTROLE DE ACESSO
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

if not st.session_state['logado']:
    login()
else:
    area_logada()
