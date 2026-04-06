import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# Configuração da página
st.set_page_config(page_title="Portal Milanov v8.3", layout="wide")

# --- FUNÇÕES DE APOIO ---
def limpar_texto(txt):
    return str(txt).strip().upper()

def normalizar_colunas(df):
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df

@st.cache_data
def carregar_regras():
    caminho = "regras_milanov.xlsx"
    if os.path.exists(caminho):
        try:
            xl = pd.ExcelFile(caminho)
            df_u, df_c = None, None
            for aba in xl.sheet_names:
                temp = normalizar_colunas(pd.read_excel(caminho, sheet_name=aba))
                if 'USUARIO' in temp.columns: df_u = temp
                if 'REALIZADO_POR' in temp.columns: df_c = temp
            return df_u, df_c
        except: return None, None
    return None, None

df_usuarios, df_cadastro = carregar_regras()

# --- LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso Milanov")
    if df_usuarios is None:
        st.error("Arquivo 'regras_milanov.xlsx' não encontrado.")
        st.stop()
    u_in = st.text_input("Usuário")
    p_in = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        u_clean = limpar_texto(u_in)
        user_row = df_usuarios[df_usuarios['USUARIO'].apply(limpar_texto) == u_clean]
        if not user_row.empty and str(p_in).strip() == str(user_row.iloc[0]['SENHA']).strip():
            st.session_state.autenticado = True
            st.rerun()
        else: st.error("Dados incorretos.")
    st.stop()

# --- PAINEL PRINCIPAL ---
st.header("📊 Auditoria Milanov")
arq = st.file_uploader("📁 Relatório Corretora", type=['xlsx'])

if arq and df_cadastro is not None:
    df_raw = normalizar_colunas(pd.read_excel(arq))
    
    # 1. SIDEBAR - PARÂMETROS E FILTROS
    st.sidebar.header("⚙️ Configurações")
    v_usd_haiti = st.sidebar.number_input("Câmbio USD Haiti (BRL)", value=5.48)
    v_htg_usd = st.sidebar.number_input("Cotação HTG / USD", value=130.0)
    
    # Filtro de Data
    if 'DATA' in df_raw.columns:
        df_raw['DATA'] = pd.to_datetime(df_raw['DATA'])
        d_min, d_max = df_raw['DATA'].min().date(), df_raw['DATA'].max().date()
        periodo = st.sidebar.date_input("📅 Período:", [d_min, d_max])
        if len(periodo) == 2:
            df_raw = df_raw[(df_raw['DATA'].dt.date >= periodo[0]) & (df_raw['DATA'].dt.date <= periodo[1])]

    # 2. CRUZAMENTO E CONSOLIDAÇÃO
    df_raw['REALIZADO_POR'] = df_raw['REALIZADO_POR'].apply(limpar_texto)
    df_cadastro['REALIZADO_POR'] = df_cadastro['REALIZADO_POR'].apply(limpar_texto)
    df_final = pd.merge(df_raw, df_cadastro, on='REALIZADO_POR', how='left')

    if 'NOME_CONSOLIDADO' not in df_final.columns:
        df_final['NOME_CONSOLIDADO'] = df_final['REALIZADO_POR']
    else:
        df_final['NOME_CONSOLIDADO'] = df_final['NOME_CONSOLIDADO'].fillna(df_final['REALIZADO_POR'])

    # Filtro de Comercial
    if 'COMERCIAL' in df_final.columns:
        lista_com = ["TODOS"] + sorted(df_final['COMERCIAL'].dropna().unique().tolist())
        sel_com = st.sidebar.selectbox("👤 Filtrar Comercial:", lista_com)
        if sel_com != "TODOS":
            df_final = df_final[df_final['COMERCIAL'] == sel_com]
    else: sel_com = "TODOS"

    # 3. MOTOR DE CÁLCULO
    df_final = df_final.sort_values(by=['NOME_CONSOLIDADO', 'DATA'])
    df_final['ORDEM'] = df_final.groupby('NOME_CONSOLIDADO').cumcount() + 1

    def motor(row):
        custo = row.get('COSTO_DE_ENVIO_BRL', 0)
        v_dest = row.get('VALOR_DESTINO', 0)
        moeda, pais = limpar_texto(row.get('MOEDA_DESTINO', '')), limpar_texto(row.get('PAIS_DESTINO', ''))
        pacote = str(row.get('ID_PACOTE_COMISSAO', '20'))
        
        v_usd = v_dest / v_htg_usd if (moeda == 'HTG' or pais == 'HAITI') else v_dest
            
        if '40' in pacote: return custo * 0.60
        if (moeda == 'HTG' or pais == 'HAITI') and v_usd <= 100:
            return 2.50 * v_usd_haiti
        
        return custo * 0.60 if row['ORDEM'] > 100 else custo * 0.50

    df_final['VALOR_COMISSAO'] = df_final.apply(motor, axis=1)

    # 4. EXIBIÇÃO
    resumo = df_final.groupby(['COMERCIAL', 'NOME_CONSOLIDADO'])['VALOR_COMISSAO'].sum().reset_index()
    st.subheader(f"📋 Resumo - {sel_com}")
    st.dataframe(resumo.sort_values(['COMERCIAL', 'NOME_CONSOLIDADO']).style.format({'VALOR_COMISSAO': 'R$ {:.2f}'}), use_container_width=True)

    # 5. DETALHAMENTO
    st.markdown("---")
    with st.expander("🔍 Investigar Agente"):
        agentes = ["Selecione..."] + sorted(resumo['NOME_CONSOLIDADO'].unique().tolist())
        sel = st.selectbox("Agente:", agentes)
        if sel != "Selecione...":
            df_ag = df_final[df_final['NOME_CONSOLIDADO'] == sel].copy()
            st.write(f"### Total: {sel}")
            st.title(f"R$ {df_ag['VALOR_COMISSAO'].sum():,.2f}")
            st.table(df_ag[['ORDEM', 'DATA', 'PAIS_DESTINO', 'VALOR_DESTINO', 'VALOR_COMISSAO']].head(100))
            
            buf = io.BytesIO()
            df_ag.to_excel(buf, index=False)
            st.download_button(f"📥 Baixar Excel {sel}", buf.getvalue(), f"{sel}.xlsx")
