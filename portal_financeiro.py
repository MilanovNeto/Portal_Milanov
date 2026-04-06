import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÃO E INTERFACE
# ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Milanov | Auditoria Pro", layout="wide", page_icon="📊")

# CSS - Recuperando o design visual completo e corrigindo fontes
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }
.stApp { background-color: #F4F6FB !important; }
.metric-card {
    background-color: white; padding: 20px; border-radius: 12px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #E2E8F0;
    text-align: center; margin-bottom: 15px;
}
.metric-card h3 { margin: 0; color: #1A1E2C; font-size: 22px; }
.metric-card p { margin: 5px 0 0 0; color: #64748B; font-size: 14px; }
.section-title { color: #1A1E2C; font-size: 24px; font-weight: 600; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

def limpar_texto(txt):
    return str(txt).strip().upper()

def normalizar_colunas(df):
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df

# ──────────────────────────────────────────────────────────────
# CARREGAMENTO DE REGRAS
# ──────────────────────────────────────────────────────────────
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

# ──────────────────────────────────────────────────────────────
# SISTEMA DE LOGIN
# ──────────────────────────────────────────────────────────────
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown("<div style='height:100px'></div>", unsafe_allow_html=True)
        st.title("🔐 Portal Milanov")
        u_in = st.text_input("Usuário")
        p_in = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            if df_usuarios is not None:
                u_clean = limpar_texto(u_in)
                user_row = df_usuarios[df_usuarios['USUARIO'].apply(limpar_texto) == u_clean]
                if not user_row.empty and str(p_in).strip() == str(user_row.iloc[0]['SENHA']).strip():
                    st.session_state.autenticado = True
                    st.rerun()
            st.error("Dados de acesso inválidos.")
    st.stop()

# ──────────────────────────────────────────────────────────────
# PAINEL DE AUDITORIA
# ──────────────────────────────────────────────────────────────
st.markdown("<h1 class='section-title'>📊 Auditoria de Comissões</h1>", unsafe_allow_html=True)

arq = st.file_uploader("📂 Arraste o relatório da corretora aqui", type=['xlsx', 'csv'])

if arq and df_cadastro is not None:
    df_raw = normalizar_colunas(pd.read_csv(arq) if arq.name.endswith('.csv') else pd.read_excel(arq))
    
    st.sidebar.header("⚙️ Configurações")
    v_usd_haiti = st.sidebar.number_input("Câmbio USD Haiti (BRL)", value=5.48)
    v_htg_usd = st.sidebar.number_input("Cotação HTG / USD", value=131.0)
    
    df_raw['REALIZADO_POR'] = df_raw['REALIZADO_POR'].apply(limpar_texto)
    df_cadastro['REALIZADO_POR'] = df_cadastro['REALIZADO_POR'].apply(limpar_texto)
    
    df = pd.merge(df_raw, df_cadastro, on='REALIZADO_POR', how='left')
    df['NOME_CONSOLIDADO'] = df['NOME_CONSOLIDADO'].fillna(df['REALIZADO_POR'])
    
    if 'DATA' in df.columns:
        df['DATA'] = pd.to_datetime(df['DATA'])
        df = df.sort_values(by=['NOME_CONSOLIDADO', 'DATA'])
    
    df['ORDEM'] = df.groupby('NOME_CONSOLIDADO').cumcount() + 1

    # --- MOTOR DE CÁLCULO ---
    def motor(row):
        custo = row.get('COSTO_DE_ENVIO_BRL', 0)
        v_dest = row.get('VALOR_DESTINO', 0)
        moeda = limpar_texto(row.get('MOEDA_DESTINO', ''))
        pais = limpar_texto(row.get('PAIS_DESTINO', ''))
        pacote = str(row.get('ID_PACOTE_COMISSAO', '20'))
        ordem = row.get('ORDEM', 1)
        
        if '40' in pacote: return custo * 0.60
        
        if (moeda == 'HTG' or pais == 'HAITI'):
            if (v_dest / v_htg_usd) <= 100:
                return 2.50 * v_usd_haiti
            return custo * 0.60 if ordem > 100 else custo * 0.50
        else:
            if ordem <= 50: return custo * 0.3
