import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import io

st.set_page_config(page_title="Milanov - COMPLIANCE", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

if 'auth_comp' not in st.session_state:
    st.session_state.auth_comp = False

# Login Restrito (Só Admin ou Compliance)
if not st.session_state.auth_comp:
    st.title("🛡️ Investigação Compliance")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Acessar"):
        df_u = conn.read(worksheet="Usuarios")
        user = df_u[(df_u['USUARIO'] == u) & (df_u['SENHA'].astype(str) == p)]
        if not user.empty and user.iloc[0]['DEPARTAMENTO'] in ['COMPLIANCE', 'ADMIN']:
            st.session_state.auth_comp = True
            st.rerun()
    st.stop()

st.header("🚩 Painel de Alertas de Risco")
arq = st.file_uploader("Relatório para Auditoria", type=['xlsx'])
if arq:
    df_raw = pd.read_excel(arq)
    
    # Filtros de 0 a 20.000 que você definiu
    st.subheader("💰 Faixa de Valor (USD)")
    c1, c2 = st.columns(2)
    v_min = c1.number_input("Mínimo", 0.0, 20000.0, 0.0)
    v_max = c2.number_input("Máximo", 0.0, 1000000.0, 20000.0)
    
    df_f = df_raw[(df_raw['Valor_destino'] >= v_min) & (df_raw['Valor_destino'] <= v_max)]
    
    # Rankings de Nro_Doc e Beneficiário
    col_doc = next((c for c in df_f.columns if 'NRO_DOC_REMETENTE' in c.upper()), "Nro_Doc_Remetente")
    col_ben = next((c for c in df_f.columns if c.upper() == 'BENEFICIARIO'), "Beneficiario")
    
    st.write("🆔 Docs Repetidos:")
    st.dataframe(df_f[col_doc].value_counts().head(15))
    
    st.write("👤 Beneficiários Repetidos:")
    st.dataframe(df_f[col_ben].value_counts().head(15))
    
    # Botão de exportação continua aqui para suas provas
    # ... (restante do código de detalhamento e download)
