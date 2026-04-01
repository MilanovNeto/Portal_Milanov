import streamlit as st
import pandas as pd
import os

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Milanov Serviços Administrativos", layout="centered")

def carregar_dados_excel(aba_nome):
    try:
        caminho_arquivo = "regras_milanov.xlsx"
        if os.path.exists(caminho_arquivo):
            # Lendo a aba específica do Excel
            df = pd.read_excel(caminho_arquivo, sheet_name=aba_nome)
            # CORREÇÃO DO ERRO: Formata os nomes das colunas corretamente
            df.columns = [str(c).strip().upper() for c in df.columns]
            return df
        else:
            st.error(f"Arquivo '{caminho_arquivo}' não encontrado no GitHub.")
            return None
    except Exception as e:
        st.error(f"Erro ao acessar a aba '{aba_nome}': {e}")
        return None

def login():
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>Milanov Serviços Administrativos</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #4B5563;'>Portal de Gestão Financeira</h3>", unsafe_allow_html=True)
    st.write("---")

    with st.container():
        st.subheader("Acesso Restrito")
        usuario_input = st.text_input("Usuário").strip().upper()
        senha_input = st.text_input("Senha", type="password").strip()
        botao_entrar = st.button("Entrar")

        if botao_entrar:
            df_usuarios = carregar_dados_excel("Usuarios")
            
            if df_usuarios is not None:
                # Validação nas colunas USUARIO e SENHA
                validacao = df_usuarios[
                    (df_usuarios['USUARIO'].astype(str).str.strip().str.upper() == usuario_input) & 
                    (df_usuarios['SENHA'].astype(str).str.strip() == senha_input)
                ]
                
                if not validacao.empty:
                    st.session_state['logado'] = True
                    st.session_state['usuario'] = usuario_input
                    # Tenta pegar o departamento, se não existir usa 'Geral'
                    depto = validacao.iloc[0]['DEPARTAMENTO'] if 'DEPARTAMENTO' in df_usuarios.columns else "Geral"
                    st.session_state['depto'] = depto
                    st.rerun()
                else:
                    st.error("Usuário ou Senha incorretos.")

# LÓGICA DE NAVEGAÇÃO
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

if not st.session_state['logado']:
    login()
else:
    st.sidebar.title(f"Olá, {st.session_state['usuario']}")
    st.sidebar.write(f"Setor: {st.session_state['depto']}")
    if st.sidebar.button("Sair"):
        st.session_state['logado'] = False
        st.rerun()

    st.title("📊 Painel de Gestão Milanov")
    
    # Abas para navegar no seu Excel com 3 pastas
    tab_pacotes, tab_agentes = st.tabs(["Tabela de Pacotes", "Cadastro de Agentes"])
    
    with tab_pacotes:
        df_p = carregar_dados_excel("Tabela_Pacotes")
        if df_p is not None:
            st.dataframe(df_p, use_container_width=True)

    with tab_agentes:
        df_a = carregar_dados_excel("Cadastro_Agentes")
        if df_a is not None:
            st.dataframe(df_a, use_container_width=True)
