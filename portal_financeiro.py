import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

st.set_page_config(page_title="Milanov | Auditoria v8.7", layout="wide", page_icon="📊")

# ──────────────────────────────────────────────────────────────
# CSS — TEMA CLARO CORPORATIVO (IGUAL À SUA VERSÃO ANTERIOR)
# ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }
.stApp { background-color: #F4F6FB !important; }
.block-container { padding-top: 1.5rem !important; }
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
# LOGIN
# ──────────────────────────────────────────────────────────────
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login Milanov")
    u_in = st.text_input("Usuário")
    p_in = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        u_clean = limpar_texto(u_in)
        if df_usuarios is not None:
            user_row = df_usuarios[df_usuarios['USUARIO'].apply(limpar_texto) == u_clean]
            if not user_row.empty and str(p_in).strip() == str(user_row.iloc[0]['SENHA']).strip():
                st.session_state.autenticado = True
                st.rerun()
        st.error("Credenciais inválidas.")
    st.stop()

# ──────────────────────────────────────────────────────────────
# INTERFACE DE AUDITORIA
# ──────────────────────────────────────────────────────────────
st.title("📊 Auditoria de Comissões")
arq = st.file_uploader("Suba o Relatório da Corretora", type=['xlsx', 'csv'])

if arq and df_cadastro is not None:
    if arq.name.endswith('.csv'):
        df_raw = normalizar_colunas(pd.read_csv(arq))
    else:
        df_raw = normalizar_colunas(pd.read_excel(arq))
    
    # --- CONFIGURAÇÃO LATERAL ---
    st.sidebar.header("⚙️ Parâmetros")
    v_usd_haiti = st.sidebar.number_input("Câmbio USD Haiti (BRL)", value=5.48)
    v_htg_usd = st.sidebar.number_input("Cotação HTG por 1 USD", value=131.0)
    
    # --- PROCESSAMENTO ---
    df_raw['REALIZADO_POR'] = df_raw['REALIZADO_POR'].apply(limpar_texto)
    df_cadastro['REALIZADO_POR'] = df_cadastro['REALIZADO_POR'].apply(limpar_texto)
    
    df = pd.merge(df_raw, df_cadastro, on='REALIZADO_POR', how='left')
    df['NOME_CONSOLIDADO'] = df['NOME_CONSOLIDADO'].fillna(df['REALIZADO_POR'])
    
    if 'DATA' in df.columns:
        df['DATA'] = pd.to_datetime(df['DATA'])
        df = df.sort_values(by=['NOME_CONSOLIDADO', 'DATA'])
    
    df['ORDEM'] = df.groupby('NOME_CONSOLIDADO').cumcount() + 1

    # --- MOTOR DE CÁLCULO V8.7 ---
    def motor(row):
        # BASE: Conforme sua imagem, usamos COSTO_DE_ENVIO_BRL
        custo = row.get('COSTO_DE_ENVIO_BRL', 0)
        v_dest = row.get('VALOR_DESTINO', 0)
        moeda = limpar_texto(row.get('MOEDA_DESTINO', ''))
        pais = limpar_texto(row.get('PAIS_DESTINO', ''))
        pacote = str(row.get('ID_PACOTE_COMISSAO', '20'))
        ordem = row.get('ORDEM', 1)
        
        # 1. Pacote Especial 40
        if '40' in pacote: return custo * 0.60
        
        # 2. Lógica HAITI (Checagem de Barreira de 100 USD)
        if (moeda == 'HTG' or pais == 'HAITI'):
            v_usd_equivalente = v_dest / v_htg_usd
            
            if v_usd_equivalente <= 100:
                # Regra: Abaixo de 100 USD paga Fixo (2.50 USD)
                return 2.50 * v_usd_haiti
            else:
                # Acima de 100 USD: Segue o Escalonamento
                return custo * 0.60 if ordem > 100 else custo * 0.50

        # 3. OUTROS PAÍSES (Regra Geral)
        else:
            if ordem <= 50: return custo * 0.30
            elif ordem <= 100: return custo * 0.50
            else: return custo * 0.60

    df['VALOR_COMISSAO'] = df.apply(motor, axis=1)

    # --- RESULTADOS ---
    resumo = df.groupby(['COMERCIAL', 'NOME_CONSOLIDADO'])['VALOR_COMISSAO'].sum().reset_index()
    st.dataframe(resumo.style.format({'VALOR_COMISSAO': 'R$ {:.2f}'}), use_container_width=True)

    # Botão de Exportação
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        resumo.to_excel(writer, index=False, sheet_name='Resumo')
        df.to_excel(writer, index=False, sheet_name='Detalhes')
    st.download_button("📥 Baixar Auditoria Completa", buf.getvalue(), "auditoria_milanov.xlsx")
