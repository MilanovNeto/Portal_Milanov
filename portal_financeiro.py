import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Milanov - Processador de Comissões", layout="wide")

def carregar_dados_excel(aba_nome):
    try:
        caminho_arquivo = "regras_milanov.xlsx"
        if os.path.exists(caminho_arquivo):
            df = pd.read_excel(caminho_arquivo, sheet_name=aba_nome)
            df.columns = [str(c).strip().upper() for c in df.columns]
            return df
        return None
    except Exception as e:
        st.error(f"Erro ao acessar regras: {e}")
        return None

def login():
    st.markdown("<h1 style='text-align: center;'>Milanov Serviços Administrativos</h1>", unsafe_allow_html=True)
    with st.container():
        st.subheader("🔒 Acesso Restrito")
        u = st.text_input("Usuário").strip().upper()
        s = st.text_input("Senha", type="password").strip()
        if st.button("Entrar"):
            df_u = carregar_dados_excel("Usuarios")
            if df_u is not None:
                validacao = df_u[(df_u['USUARIO'].astype(str) == u) & (df_u['SENHA'].astype(str) == s)]
                if not validacao.empty:
                    st.session_state['logado'] = True
                    st.session_state['usuario'] = u
                    st.rerun()
                else:
                    st.error("Usuário ou Senha incorretos.")

if 'logado' not in st.session_state:
    st.session_state['logado'] = False

if not st.session_state['logado']:
    login()
else:
    # --- ÁREA LOGADA: PROCESSADOR FINANCEIRO ---
    st.sidebar.title(f"👤 {st.session_state['usuario']}")
    if st.sidebar.button("Sair"):
        st.session_state['logado'] = False
        st.rerun()

    st.title("💰 Processador de Comissões Corretora")
    
    st.markdown("---")
    st.subheader("1. Subir Extrato da Corretora")
    arquivo_extrato = st.file_uploader("Escolha o arquivo da corretora (Excel ou CSV)", type=['xlsx', 'csv'])

    if arquivo_extrato:
        try:
            # Lendo o arquivo subido
            if arquivo_extrato.name.endswith('.csv'):
                df_extrato = pd.read_csv(arquivo_extrato)
            else:
                df_extrato = pd.read_excel(arquivo_extrato)
            
            st.success("Extrato carregado com sucesso!")
            
            st.subheader("2. Resultado do Processamento")
            
            # Carregando as regras para o cálculo
            df_regras = carregar_dados_excel("Tabela_Pacotes")
            
            if df_regras is not None:
                # AQUI ENTRA A LÓGICA DE CÁLCULO
                # Exemplo visual do cruzamento de dados:
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Resumo das Movimentações:**")
                    st.dataframe(df_extrato.head(10)) # Mostra as primeiras 10 linhas do extrato
                
                with col2:
                    st.write("**Cálculo Estimado de Comissões:**")
                    # Lógica simples de exemplo (ajustaremos conforme as colunas do seu extrato)
                    st.warning("Aguardando mapeamento das colunas do extrato para calcular valores reais.")
                
                st.markdown("---")
                st.download_button("Baixar Relatório Processado", data=df_extrato.to_csv().encode('utf-8'), file_name="comissoes_processadas.csv")
            
        except Exception as e:
            st.error(f"Erro ao processar arquivo: {e}")

    # Mantém as abas de consulta em baixo
    with st.expander("Ver Regras e Cadastros (Planilha Interna)"):
        t1, t2 = st.tabs(["Pacotes", "Agentes"])
        with t1:
            st.dataframe(carregar_dados_excel("Tabela_Pacotes"))
        with t2:
            st.dataframe(carregar_dados_excel("Cadastro_Agentes"))
