import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

st.set_page_config(page_title="Portal Milanov v7.0", layout="wide")

# --- CONFIGURAÇÃO DE SEGURANÇA ---
# Ajustado para ler o arquivo que você subiu no GitHub
CAMINHO_REGRAS = "regras_milanov.xlsx"

def limpar_texto(txt):
    return str(txt).strip().upper()

@st.cache_data
def carregar_regras():
    if os.path.exists(CAMINHO_REGRAS):
        xl = pd.ExcelFile(CAMINHO_REGRAS)
        # Identificação dinâmica das abas conforme seu arquivo original
        aba_u = next((s for s in xl.sheet_names if 'usu' in s.lower()), "Usuarios")
        aba_c = next((s for s in xl.sheet_names if 'cad' in s.lower()), "Cadastro_Agentes")
        df_u = pd.read_excel(CAMINHO_REGRAS, sheet_name=aba_u)
        df_c = pd.read_excel(CAMINHO_REGRAS, sheet_name=aba_c)
        return df_u, df_c
    return None, None

df_usuarios, df_cadastro = carregar_regras()

# --- LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login Milanov")
    u, p = st.text_input("Usuário"), st.text_input("Senha", type="password")
    if st.button("Entrar") and df_usuarios is not None:
        df_usuarios.columns = [limpar_texto(c) for c in df_usuarios.columns]
        user_row = df_usuarios[df_usuarios['USUARIO'].apply(limpar_texto) == limpar_texto(u)]
        if not user_row.empty and str(user_row.iloc[0]['SENHA']).strip() == str(p).strip():
            st.session_state.autenticado = True
            st.rerun()
    st.stop()

# --- SISTEMA ---
st.header("📊 Auditoria de Fechamento Milanov")
arq_corr = st.file_uploader("📁 Subir Relatório Corretora", type=['xlsx'])

if arq_corr and df_cadastro is not None:
    # 1. Carregamento inicial
    df_raw = pd.read_excel(arq_corr)
    df_raw['Data'] = pd.to_datetime(df_raw['Data'])
    
    # 2. FILTRO DE DATA NA SIDEBAR
    st.sidebar.header("📅 Filtros de Período")
    d_min, d_max = df_raw['Data'].min().date(), df_raw['Data'].max().date()
    periodo = st.sidebar.date_input("Intervalo de Fechamento:", [d_min, d_max])
    
    # 3. PARÂMETROS FINANCEIROS
    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Financeiro")
    v_dolar_brl = st.sidebar.number_input("💵 Dólar Haiti (BRL)", value=5.48)
    v_conv_moeda = st.sidebar.number_input("🔄 Cotação Moeda Local -> USD", value=1.0)
    
    if len(periodo) == 2:
        start_date, end_date = periodo
        df_raw = df_raw[(df_raw['Data'].dt.date >= start_date) & (df_raw['Data'].dt.date <= end_date)]

    # 4. PROCESSAMENTO E CÁLCULO (Motor v6.5 Original)
    df_raw['Realizado_por'] = df_raw['Realizado_por'].apply(limpar_texto)
    df_cadastro['Realizado_por'] = df_cadastro['Realizado_por'].apply(limpar_texto)
    df_final = pd.merge(df_raw, df_cadastro, on='Realizado_por', how='left')

    lista_com = ["TODOS"] + sorted(df_final['Comercial'].dropna().unique().tolist())
    sel_com = st.sidebar.selectbox("Selecionar Comercial:", lista_com)
    if sel_com != "TODOS":
        df_final = df_final[df_final['Comercial'] == sel_com]

    def motor_v6_5(row):
        custo_brl = row.get('Costo_de_envio_BRL', 0)
        v_usd = row.get('Valor_destino', 0) / v_conv_moeda
        pais = limpar_texto(row.get('Pais_Destino', ''))
        vol = len(df_final[df_final['Realizado_por'] == row['Realizado_por']])
        if pais == 'HAITI':
            if v_usd <= 100: return 2.5 * v_dolar_brl
            return custo_brl * (0.50 if vol <= 100 else 0.60)
        id_p = str(row.get('ID_Pacote_Comissao', '20'))
        if '40' in id_p: return custo_brl * 0.60
        p = 0.30 if vol <= 50 else (0.50 if vol <= 100 else 0.60)
        return custo_brl * p

    df_final['COMISSAO_AGENTE'] = df_final.apply(motor_v6_5, axis=1)
    df_final['COMISSAO_COMERCIAL'] = df_final.get('Regra_Fixo_Comercial', 0)

    # 5. RESULTADOS
    df_resumo = df_final.groupby(['Comercial', 'Realizado_por']).agg({
        'COMISSAO_AGENTE': 'sum',
        'COMISSAO_COMERCIAL': 'sum'
    }).reset_index()
    df_resumo['TOTAL_A_PAGAR'] = df_resumo['COMISSAO_AGENTE'] + df_resumo['COMISSAO_COMERCIAL']

    st.subheader(f"📋 Resumo Consolidado")
    st.dataframe(df_resumo.style.format({'COMISSAO_AGENTE': 'R$ {:.2f}', 'COMISSAO_COMERCIAL': 'R$ {:.2f}', 'TOTAL_A_PAGAR': 'R$ {:.2f}'}))

    # --- NOVO BOTÃO DE EXCEL (.XLSX) ---
    def gerar_excel_milanov(df):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Fechamento')
        return buffer.getvalue()

    st.download_button(
        label="📥 Baixar Resumo em Excel",
        data=gerar_excel_milanov(df_resumo),
        file_name=f"Milanov_Fechamento_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # 6. INVESTIGAÇÃO (Drill-down)
    with st.expander("🔍 Ver Operações Detalhadas"):
        agente = st.selectbox("Selecione o Agente:", ["Selecione..."] + df_resumo['Realizado_por'].tolist())
        if agente != "Selecione...":
            det = df_final[df_final['Realizado_por'] == agente].copy()
            st.table(det[['Data', 'Pais_Destino', 'Valor_destino', 'COMISSAO_AGENTE']].style.format({'COMISSAO_AGENTE': '{:.2f}'}))
