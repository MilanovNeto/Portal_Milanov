import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Milanov - FINANCEIRO", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# Login Simples para o Financeiro
if 'auth_fin' not in st.session_state:
    st.session_state.auth_fin = False

if not st.session_state.auth_fin:
    st.title("💰 Acesso Financeiro")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        df_u = conn.read(worksheet="Usuarios")
        user = df_u[(df_u['USUARIO'] == u) & (df_u['SENHA'].astype(str) == p)]
        if not user.empty and user.iloc[0]['DEPARTAMENTO'] in ['FINANCEIRO', 'ADMIN']:
            st.session_state.auth_fin = True
            st.rerun()
    st.stop()

st.header("📊 Processamento de Comissões")
arq = st.file_uploader("Subir Relatório (.xlsx)", type=['xlsx'])
if arq:
    df = pd.read_excel(arq)
    st.success("Relatório carregado.")
    st.dataframe(df.head(100)) # Visualização básica para conferência
