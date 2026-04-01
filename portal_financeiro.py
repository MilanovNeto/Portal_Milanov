import streamlit as st
import pandas as pd
import os

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Milanov Serviços Administrativos", layout="centered")

def carregar_dados_excel(aba_nome):
    try:
        caminho_arquivo = "regras_milanov.xlsx"
        if os.path.exists(caminho_arquivo):
            # O pandas lê o Excel e a aba específica que você pedir
            df = pd.read_excel(caminho_arquivo, sheet_name=aba_nome)
            # Limpa os nomes das colunas (tira espaços e deixa em maiúsculo)
            df.columns = df.columns.str.strip().upper()
            return df
        else:
            st.error("Arquivo 'regras_milanov.xlsx' não encontrado no GitHub.")
            return None
    except Exception as e:
        st.error(f"Erro ao ler a aba {aba_nome}: {e}")
        return None

def login():
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>Milanov Serviços Administrativos</h1>", unsafe_allow_html=True)
    st.write("---")

    with st.container():
        st.subheader("Acesso Restrito")
        usuario_input = st.text_input("Usuário").strip().upper()
        senha_input = st.text_input("Senha", type="password").strip()
        botao_entrar = st.button("Entrar")

        if botao_entrar:
            # Busca especificamente na aba 'Usuarios'
            df_usuarios = carregar_dados_excel("Usuarios")
            
            if df_usuarios is not None:
                # Validação baseada nas colunas: USUARIO, SENHA, DEPARTAMENTO
                validacao = df_usuarios[
                    (df_usuarios['USUARIO'].astype(str).str.strip().str.upper() == usuario_input) & 
                    (df_usuarios['SENHA'].astype(str).str.strip() == senha_input)
                ]
                
                if not validacao.empty:
                    st.session_state['logado'] = True
                    st.session_state['usuario'] = usuario_input
                    st.session_state['depto'] = validacao.iloc[0]['DEPARTAMENTO']
                    st.rerun()
                else:
                    st.error("Usuário ou Senha inválidos.")

if 'logado' not in st.session_state:
    st.session_state['logado'] = False

if not st.session_state['logado']:
    login()
else:
    # ÁREA LOGADA
    st.sidebar.success(f"Logado: {st.session_state['usuario']}")
    if st.sidebar.button("Sair"):
        st.session_state['logado'] = False
        st.rerun()
    
    st.title("📊 Painel de Gestão Milanov")
    
    # Exemplo de como acessar as outras abas agora que o login funcionou:
    tab1, tab2 = st.tabs(["Pacotes", "Agentes"])
    
    with tab1:
        st.subheader("Tabela de Pacotes")
        df_pacotes = carregar_dados_excel("Tabela_Pacotes")
        if df_pacotes is not None:
            st.dataframe(df_pacotes) # Mostra a tabela de pacotes na tela

    with tab2:
        st.subheader("Cadastro de Agentes")
        df_agentes = carregar_dados_excel("Cadastro_Agentes")
        if df_agentes is not None:
            st.write(df_agentes)
