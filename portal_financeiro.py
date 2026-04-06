import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÃO E INTERFACE
# ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Milanov | Auditoria v8.5", layout="wide", page_icon="📊")

# Funções de limpeza e padronização
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
                temp_df = normalizar_colunas(pd.read_excel(caminho, sheet_name=aba))
                # Identifica aba de usuários
                if 'USUARIO' in temp_df.columns and 'SENHA' in temp_df.columns:
                    df_u = temp_df
                # Identifica aba de cadastro de agentes
                if 'REALIZADO_POR' in temp_df.columns and 'COMERCIAL' in temp_df.columns:
                    df_c = temp_df
            
            return df_u, df_c
        except Exception as e:
            st.error(f"Erro ao ler banco de dados: {e}")
    return None, None

df_usuarios, df_cadastro = carregar_regras()

# ──────────────────────────────────────────────────────────────
# SISTEMA DE ACESSO (LOGIN)
# ──────────────────────────────────────────────────────────────
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso Restrito Milanov")
    
    if df_usuarios is None:
        st.error("Base de dados 'regras_milanov.xlsx' não encontrada no repositório.")
        st.stop()
        
    col1, col2 = st.columns(2)
    with col1:
        u_input = st.text_input("Utilizador")
        p_input = st.text_input("Palavra-passe", type="password")
        
        if st.button("Entrar", use_container_width=True):
            u_clean = limpar_texto(u_input)
            user_row = df_usuarios[df_usuarios['USUARIO'].apply(limpar_texto) == u_clean]
            
            if not user_row.empty:
                senha_db = str(user_row.iloc[0]['SENHA']).strip()
                if str(p_input).strip() == senha_db:
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Palavra-passe incorreta.")
            else:
                st.error("Utilizador não cadastrado.")
    st.stop()

# ──────────────────────────────────────────────────────────────
# PAINEL DE AUDITORIA (PÓS-LOGIN)
# ──────────────────────────────────────────────────────────────
st.header("📊 Painel de Auditoria de Comissões")

# Upload do movimento da corretora
arq = st.file_uploader("Suba o Relatório da Corretora (Excel)", type=['xlsx'])

if arq and df_cadastro is not None:
    df_raw = normalizar_colunas(pd.read_excel(arq))
    
    # --- SIDEBAR: PARÂMETROS ---
    st.sidebar.header("⚙️ Parâmetros do Dia")
    v_usd_haiti = st.sidebar.number_input("Câmbio USD para BRL (Haiti)", value=5.48, step=0.01)
    v_htg_usd = st.sidebar.number_input("Cotação HTG por 1 USD", value=130.0, step=0.1)

    # Filtro de Data
    if 'DATA' in df_raw.columns:
        df_raw['DATA'] = pd.to_datetime(df_raw['DATA'])
        d_min, d_max = df_raw['DATA'].min().date(), df_raw['DATA'].max().date()
        periodo = st.sidebar.date_input("📅 Filtrar Período", [d_min, d_max])
        if len(periodo) == 2:
            df_raw = df_raw[(df_raw['DATA'].dt.date >= periodo[0]) & (df_raw['DATA'].dt.date <= periodo[1])]

    # --- PROCESSAMENTO ---
    # Normaliza chaves de cruzamento
    df_raw['REALIZADO_POR'] = df_raw['REALIZADO_POR'].apply(limpar_texto)
    df_cadastro['REALIZADO_POR'] = df_cadastro['REALIZADO_POR'].apply(limpar_texto)
    
    # Merge (Traz NOME_CONSOLIDADO, ID_PACOTE_COMISSAO, COMERCIAL)
    df = pd.merge(df_raw, df_cadastro, on='REALIZADO_POR', how='left')
    
    # Preenche nomes não encontrados
    df['NOME_CONSOLIDADO'] = df['NOME_CONSOLIDADO'].fillna(df['REALIZADO_POR'])
    
    # Ordenação e Contador de Operações (ORDEM)
    df = df.sort_values(by=['NOME_CONSOLIDADO', 'DATA'])
    df['ORDEM'] = df.groupby('NOME_CONSOLIDADO').cumcount() + 1

    # --- MOTOR DE CÁLCULO (REGRAS V8.5) ---
    def calcular_motor(row):
        custo = row.get('COSTO_DE_ENVIO_BRL', 0)
        v_dest = row.get('VALOR_DESTINO', 0)
        moeda = limpar_texto(row.get('MOEDA_DESTINO', ''))
        pais = limpar_texto(row.get('PAIS_DESTINO', ''))
        pacote = str(row.get('ID_PACOTE_COMISSAO', '20'))
        ordem = row.get('ORDEM', 1)
        
        # 1. Regra Pacote 40 (Sempre 60%)
        if '40' in pacote: 
            return custo * 0.60
        
        # 2. Conversão para USD (para checar limite de 100 USD)
        v_usd = v_dest / v_htg_usd if (moeda == 'HTG' or pais == 'HAITI') else v_dest

        # 3. BLOCO HAITI
        if (moeda == 'HTG' or pais == 'HAITI'):
            if v_usd <= 100:
                return 2.50 * v_usd_haiti # Regra Fixo 2.50 USD
            else:
                return custo * 0.60 if ordem > 100 else custo * 0.50

        # 4. BLOCO OUTROS PAÍSES
        else:
            if ordem <= 50:
                return custo * 0.30 # Até 50 envios: 30%
            elif ordem <= 100:
                return custo * 0.50 # 51 a 100 envios: 50%
            else:
                return custo * 0.60 # Acima de 100: 60%

    df['VALOR_COMISSAO'] = df.apply(calcular_motor, axis=1)

    # --- FILTRO DE COMERCIAL (SIDEBAR) ---
    if 'COMERCIAL' in df.columns:
        comerciais = ["TODOS"] + sorted(df['COMERCIAL'].dropna().unique().tolist())
        sel_com = st.sidebar.selectbox("👤 Filtrar Gestor Comercial", comerciais)
        if sel_com != "TODOS":
            df = df[df['COMERCIAL'] == sel_com]

    # --- EXIBIÇÃO DE RESULTADOS ---
    resumo = df.groupby(['COMERCIAL', 'NOME_CONSOLIDADO'])['VALOR_COMISSAO'].sum().reset_index()
    
    st.subheader("📋 Resumo de Apuração")
    st.dataframe(
        resumo.sort_values(['COMERCIAL', 'VALOR_COMISSAO'], ascending=[True, False]).style.format({'VALOR_COMISSAO': 'R$ {:.2f}'}),
        use_container_width=True
    )

    # Detalhamento Individual
    st.markdown("---")
    with st.expander("🔍 Detalhar Agente Específico"):
        lista_agentes = ["Selecione..."] + sorted(resumo['NOME_CONSOLIDADO'].unique().tolist())
        sel = st.selectbox("Escolha o Agente para Auditoria:", lista_agentes)
        
        if sel != "Selecione...":
            df_ag = df[df['NOME_CONSOLIDADO'] == sel].copy()
            total_ag = df_ag['VALOR_COMISSAO'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total de Comissões", f"R$ {total_ag:,.2f}")
            c2.metric("Qtd. Operações", len(df_ag))
            c3.metric("Média por Op.", f"R$ {total_ag/len(df_ag):,.2f}")
            
            st.table(df_ag[['ORDEM', 'DATA', 'PAIS_DESTINO', 'VALOR_DESTINO', 'MOEDA_DESTINO', 'VALOR_COMISSAO']].head(200))
            
            # Exportação Excel do Agente
            buf = io.BytesIO()
            df_ag.to_excel(buf, index=False)
            st.download_button(f"📥 Baixar Relatório {sel}", buf.getvalue(), f"{sel}_auditoria.xlsx")
