import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# Configuração da página
st.set_page_config(page_title="Portal Milanov v7.8", layout="wide")

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
            aba_u = next((s for s in xl.sheet_names if 'usu' in s.lower()), "Usuarios")
            aba_c = next((s for s in xl.sheet_names if 'cad' in s.lower()), "Cadastro_Agentes")
            df_u = pd.read_excel(caminho, sheet_name=aba_u)
            df_c = pd.read_excel(caminho, sheet_name=aba_c)
            return normalizar_colunas(df_u), normalizar_colunas(df_c)
        except Exception as e:
            st.error(f"Erro ao ler regras_milanov.xlsx: {e}")
    return None, None

df_usuarios, df_cadastro = carregar_regras()

# --- SISTEMA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso Restrito - Milanov")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar") and df_usuarios is not None:
        user_row = df_usuarios[df_usuarios['USUARIO'].apply(limpar_texto) == limpar_texto(u)]
        if not user_row.empty and str(user_row.iloc[0]['SENHA']).strip() == str(p).strip():
            st.session_state.autenticado = True
            st.session_state.usuario_logado = limpar_texto(u)
            st.rerun()
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.header("📊 Painel de Auditoria Milanov")
arq_corr = st.file_uploader("📁 Subir Relatório da Corretora", type=['xlsx'])

if arq_corr and df_cadastro is not None:
    df_raw = pd.read_excel(arq_corr)
    df_raw = normalizar_colunas(df_raw)
    
    if 'REALIZADO_POR' not in df_raw.columns:
        st.error("❌ Erro: Coluna 'REALIZADO_POR' não encontrada!")
        st.stop()

    # SIDEBAR - PARÂMETROS E COTAÇÕES
    st.sidebar.header("⚙️ Parâmetros Financeiros")
    v_dolar_haiti_brl = st.sidebar.number_input("💵 USD Haiti (em BRL)", value=5.48)
    v_cotacao_htg_usd = st.sidebar.number_input("🇭🇹 Cotação HTG/USD (Ex: 130.5)", value=130.0, help="Quantos HTG valem 1 USD")
    v_conv_geral = st.sidebar.number_input("🔄 Outras Moedas -> USD", value=1.0)

    if 'DATA' in df_raw.columns:
        df_raw['DATA'] = pd.to_datetime(df_raw['DATA'])
        d_min, d_max = df_raw['DATA'].min().date(), df_raw['DATA'].max().date()
        periodo = st.sidebar.date_input("📅 Intervalo de Datas:", [d_min, d_max])
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
    else:
        sel_com = "TODOS"

    # 3. MOTOR DE CÁLCULO v7.8 (Regra HTG e Escalonamento)
    df_final = df_final.sort_values(by=['NOME_CONSOLIDADO', 'DATA'])
    df_final['ORDEM_OP'] = df_final.groupby('NOME_CONSOLIDADO').cumcount() + 1

    def motor_v7_8(row):
        custo_brl = row.get('COSTO_DE_ENVIO_BRL', 0)
        valor_dest = row.get('VALOR_DESTINO', 0)
        moeda_dest = limpar_texto(row.get('MOEDA_DESTINO', ''))
        pais_dest = limpar_texto(row.get('PAIS_DESTINO', ''))
        id_p = str(row.get('ID_PACOTE_COMISSAO', '20'))
        n_op = row['ORDEM_OP']
        
        # Lógica de Conversão para USD (Especial para HTG)
        if moeda_dest == 'HTG' or pais_dest == 'HAITI':
            v_usd = valor_dest / v_cotacao_htg_usd
        else:
            v_usd = valor_dest / v_conv_geral
            
        # REGRA 1: Pacote 40 (60% Fixo independente do valor ou país)
        if '40' in id_p:
            return custo_brl * 0.60
        
        # REGRA 2: Haiti/HTG (Se convertido for <= 100 USD, paga Fixo)
        if (pais_dest == 'HAITI' or moeda_dest == 'HTG') and v_usd <= 100:
            return 2.50 * v_dolar_haiti_brl
        
        # REGRA 3: Escalonamento para demais operações (ou Haiti > 100 USD)
        percentual = 0.60 if n_op > 100 else 0.50
        return custo_brl * percentual

    df_final['COMISSAO_AGENTE'] = df_final.apply(motor_v7_8, axis=1)
    df_final['COMISSAO_COMERCIAL'] = df_final.get('REGRA_FIXO_COMERCIAL', 0)

    # 4. EXIBIÇÃO CONSOLIDADA
    df_resumo = df_final.groupby(['COMERCIAL', 'NOME_CONSOLIDADO']).agg({
        'COMISSAO_AGENTE': 'sum', 'COMISSAO_COMERCIAL': 'sum'
    }).reset_index().sort_values(by=['COMERCIAL', 'NOME_CONSOLIDADO'])
    
    df_resumo['TOTAL_A_PAGAR'] = df_resumo['COMISSAO_AGENTE'] + df_resumo['COMISSAO_COMERCIAL']

    st.subheader(f"📋 Resumo Consolidado - {sel_com}")
    st.dataframe(df_resumo.style.format({
        'COMISSAO_AGENTE': 'R$ {:.2f}', 'COMISSAO_COMERCIAL': 'R$ {:.2f}', 'TOTAL_A_PAGAR': 'R$ {:.2f}'
    }), use_container_width=True)

    # 5. DETALHAMENTO E DOWNLOAD
    st.markdown("---")
    with st.expander("🔍 Detalhar Operações por Agente"):
        agentes_lista = ["Selecione..."] + sorted(df_resumo['NOME_CONSOLIDADO'].tolist())
        agente_sel = st.selectbox("Selecione o Agente para Auditoria:", agentes_lista)
        
        if agente_sel != "Selecione...":
            df_agente = df_final[df_final['NOME_CONSOLIDADO'] == agente_sel].copy()
            st.title(f"R$ {df_agente['COMISSA
