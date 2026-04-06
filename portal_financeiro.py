import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÃO E INTERFACE
# ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Milanov | Auditoria v8.6", layout="wide", page_icon="📊")

def limpar_texto(txt):
    return str(txt).strip().upper()

def normalizar_colunas(df):
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df

# ──────────────────────────────────────────────────────────────
# CARREGAMENTO DE REGRAS (LEITURA INTELIGENTE)
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

# ──────────────────────────────────────────────────────────────
# PAINEL PRINCIPAL
# ──────────────────────────────────────────────────────────────
st.header("📊 Auditoria de Comissões")
arq = st.file_uploader("📁 Relatório Corretora", type=['xlsx'])

if arq and df_cadastro is not None:
    df_raw = normalizar_colunas(pd.read_excel(arq))
    
    # Parâmetros na Sidebar
    st.sidebar.header("⚙️ Configurações de Câmbio")
    v_usd_haiti = st.sidebar.number_input("Câmbio USD Haiti (BRL)", value=5.48)
    v_htg_usd = st.sidebar.number_input("Cotação HTG / USD", value=130.0)
    
    # Filtro de Data
    if 'DATA' in df_raw.columns:
        df_raw['DATA'] = pd.to_datetime(df_raw['DATA'])
        d_min, d_max = df_raw['DATA'].min().date(), df_raw['DATA'].max().date()
        periodo = st.sidebar.date_input("📅 Período:", [d_min, d_max])
        if len(periodo) == 2:
            df_raw = df_raw[(df_raw['DATA'].dt.date >= periodo[0]) & (df_raw['DATA'].dt.date <= periodo[1])]

    # Cruzamento e Contagem
    df_raw['REALIZADO_POR'] = df_raw['REALIZADO_POR'].apply(limpar_texto)
    df_cadastro['REALIZADO_POR'] = df_cadastro['REALIZADO_POR'].apply(limpar_texto)
    df_final = pd.merge(df_raw, df_cadastro, on='REALIZADO_POR', how='left')

    df_final['NOME_CONSOLIDADO'] = df_final['NOME_CONSOLIDADO'].fillna(df_final['REALIZADO_POR'])
    df_final = df_final.sort_values(by=['NOME_CONSOLIDADO', 'DATA'])
    df_final['ORDEM'] = df_final.groupby('NOME_CONSOLIDADO').cumcount() + 1

    # --- MOTOR DE CÁLCULO (REGRAS ATUALIZADAS) ---
    def motor(row):
        custo = row.get('COSTO_DE_ENVIO_BRL', 0)
        v_dest = row.get('VALOR_DESTINO', 0)
        moeda = limpar_texto(row.get('MOEDA_DESTINO', ''))
        pais = limpar_texto(row.get('PAIS_DESTINO', ''))
        pacote = str(row.get('ID_PACOTE_COMISSAO', '20'))
        ordem = row.get('ORDEM', 1)
        
        # 1. Regra Pacote 40 (Sempre 60%)
        if '40' in pacote: 
            return custo * 0.60
        
        # 2. Conversão para USD (Haiti)
        v_usd = v_dest / v_htg_usd if (moeda == 'HTG' or pais == 'HAITI') else v_dest

        # 3. REGRA HAITI
        if (moeda == 'HTG' or pais == 'HAITI'):
            if v_usd <= 100:
                return 2.50 * v_usd_haiti  # Abaixo de 100 USD: Fixo 2.50 USD
            else:
                # Acima de 100 USD: Escalonamento Haiti
                return custo * 0.60 if ordem > 100 else custo * 0.50

        # 4. REGRA TODOS OS OUTROS PAÍSES
        else:
            if ordem <= 50:
                return custo * 0.30  # Até 50 envios: 30%
            elif ordem <= 100:
                return custo * 0.50  # 51 a 100 envios: 50%
            else:
                return custo * 0.60  # Acima de 100 envios: 60%

    df_final['VALOR_COMISSAO'] = df_final.apply(motor, axis=1)

    # Filtro Comercial
    if 'COMERCIAL' in df_final.columns:
        lista_com = ["TODOS"] + sorted(df_final['COMERCIAL'].dropna().unique().tolist())
        sel_com = st.sidebar.selectbox("👤 Comercial:", lista_com)
        if sel_com != "TODOS":
            df_final = df_final[df_final['COMERCIAL'] == sel_com]

    # Exibição
    resumo = df_final.groupby(['COMERCIAL', 'NOME_CONSOLIDADO'])['VALOR_COMISSAO'].sum().reset_index()
    st.subheader("📋 Resumo Consolidado")
    st.dataframe(resumo.style.format({'VALOR_COMISSAO': 'R$ {:.2f}'}), use_container_width=True)

    with st.expander("🔍 Detalhar por Agente"):
        sel = st.selectbox("Agente:", ["Selecione..."] + sorted(resumo['NOME_CONSOLIDADO'].unique().tolist()))
        if sel != "Selecione...":
            df_ag = df_final[df_final['NOME_CONSOLIDADO'] == sel].copy()
            st.metric("Total Comissões", f"R$ {df_ag['VALOR_COMISSAO'].sum():,.2f}")
            st.table(df_ag[['ORDEM', 'DATA', 'PAIS_DESTINO', 'VALOR_DESTINO', 'VALOR_COMISSAO']].head(100))
            
            buf = io.BytesIO()
            df_ag.to_excel(buf, index=False)
            st.download_button(f"📥 Baixar Excel {sel}", buf.getvalue(), f"{sel}.xlsx")
