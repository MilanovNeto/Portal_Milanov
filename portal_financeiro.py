import streamlit as st
import pandas as pd

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Milanov Serviços Administrativos", layout="centered")

# LINK DA SUA PLANILHA (JÁ CONFIGURADO PARA CSV)
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSL6ftgznAq3Z-q8iWajnshFvGeRPXw_Gl7GeZydA-9qa18nOsa4Wb5xqCQ93VpC5V8YZOl7w6xROtb/pub?output=csv"

def carregar_dados():
    try:
        # Lê a planilha diretamente do link público
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
        usuario_input = st.text_input("Usuário").strip()
        senha_input = st.text_input("Senha", type="password").strip()
        botao_entrar = st.button("Entrar")

        if botao_entrar:
            df_usuarios = carregar_dados()
            
            if df_usuarios is not None:
                # Procura o usuário na planilha (Coluna 'Usuario' e 'Senha')
                # Importante: O nome das colunas na sua planilha deve ser EXATAMENTE assim.
                usuario_valido = df_usuarios[(df_usuarios['Usuario'].astype(str) == usuario_input) & 
                                             (df_usuarios['Senha'].astype(str) == senha_input)]
                
                if not usuario_valido.empty:
                    nome_usuario = usuario_valido.iloc[0]['Nome']
                    st.session_state['logado'] = True
                    st.session_state['nome'] = nome_usuario
                    st.rerun()
                else:
                    st.error("Usuário ou Senha incorretos.")
            else:
                st.error("Não foi possível validar o acesso. Verifique a conexão com a planilha.")

def area_logada():
    st.sidebar.title(f"Bem-vindo, {st.session_state['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state['logado'] = False
        st.rerun()

    st.title("📊 Painel Financeiro")
    st.write(f"Olá {st.session_state['nome']}, aqui estão suas informações.")
    
    # Aqui você pode adicionar filtros e buscas para os dados das outras abas
    st.info("Sistema conectado com sucesso à planilha regras_milanov.")

# CONTROLE DE NAVEGAÇÃO
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

if not st.session_state['logado']:
    login()
else:
    area_logada()
