import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# Configuração da página
st.set_page_config(page_title="Portal Milanov v7.9", layout="wide")

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
            df_u = pd.read_excel(caminho, sheet_name=0) # Pega a 1ª aba
            df_c = pd.read_excel(caminho, sheet_name=1) # Pega a 2ª aba
            return normalizar_colunas(df_u), normalizar_colunas(df_c)
        except:
            return None, None
    return None, None

df_usuarios, df_cadastro = carregar_regras()

# --- LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso Milanov")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar") and df_usuarios is not None:
        user_row = df_usuarios[df_usuarios['USUARIO'].apply(limpar_texto) == limpar_texto(u)]
        if not user_row.empty and str(user_row.iloc[0]['SENHA']).strip() == str(p).strip():
            st.session_state.autenticado = True
            st.rerun()
    st.stop()

# --- PAINEL PRINCIPAL ---
st.header("📊 Auditoria Milanov")
arq = st.file_uploader("📁 Relatório Corretora", type=['xlsx'])

if arq and df_cadastro is not None:
    df_raw = normalizar_colunas(pd.read_excel(arq))
    
    # Parâmetros na Sidebar
    st.sidebar.header("⚙️ Câmbio")
    v_usd_haiti = st.sidebar.number_input("USD Haiti (BRL)", value=5.48)
    v_htg_usd = st.sidebar.number_input("HTG / USD", value=130.0)
    
    # Cruzamento
    df_raw['REALIZADO_POR'] = df_raw['REALIZADO_POR'].apply(limpar_texto)
    df_cadastro['REALIZADO_POR'] = df_cadastro['REALIZADO_POR'].apply(limpar_texto)
    df_final = pd.merge(df_raw, df_cadastro, on='REALIZADO_POR', how='left')

    # Consolidação de Nomes
    if 'NOME_CONSOLIDADO' not in df_final.columns:
        df_final['NOME_CONSOLIDADO'] = df_final['REALIZADO_POR']
    else:
        df_final['NOME_CONSOLIDADO'] = df_final['NOME_CONSOLIDADO'].fillna(df_final['REALIZADO_POR'])

    # Motor de Cálculo v7.9
    df_final = df_final.sort_values(by=['NOME_CONSOLIDADO', 'DATA'])
    df_final['ORDEM'] = df_final.groupby('NOME_CONSOLIDADO').cumcount() + 1

    def calcular_comissao(row):
        custo = row.get('COSTO_DE_ENVIO_BRL', 0)
        v_dest = row.get('VALOR_DESTINO', 0)
        moeda = limpar_texto(row.get('MOEDA_DESTINO', ''))
        pais = limpar_texto(row.get('PAIS_DESTINO', ''))
        pacote = str(row.get('ID_PACOTE_COMISSAO', '20'))
        
        # Converte para USD para checar limite de 100
        v_usd = v_dest / v_htg_usd if (moeda == 'HTG' or pais == 'HAITI') else v_dest
            
        if '40' in pacote: return custo * 0.60
        if (moeda == 'HTG' or pais == 'HAITI') and v_usd <= 100:
            return 2.50 * v_usd_haiti
        
        return custo * 0.60 if row['ORDEM'] > 100 else custo * 0.50

    df_final['VALOR_COMISSAO'] = df_final.apply(calcular_comissao, axis=1)

    # Resumo
    resumo = df_final.groupby('NOME_CONSOLIDADO')['VALOR_COMISSAO'].sum().reset_index()
    resumo = resumo.sort_values('NOME_CONSOLIDADO')
    st.dataframe(resumo.style.format({'VALOR_COMISSAO': 'R$ {:.2f}'}))

    # Detalhamento (Onde dava o erro)
    st.markdown("---")
    with st.expander("🔍 Detalhar Agente"):
        lista = ["Selecione..."] + resumo['NOME_CONSOLIDADO'].tolist()
        sel = st.selectbox("Agente:", lista)
        
        if sel != "Selecione...":
            df_ag = df_final[df_final['NOME_CONSOLIDADO'] == sel].copy()
            total = df_ag['VALOR_COMISSAO'].sum()
            
            # Usei variáveis curtas para evitar quebra de linha errada
            txt_total = f"R$ {total:,.2f}"
            st.subheader(f"Total: {sel}")
            st.title(txt_total)

            st.table(df_ag[['ORDEM', 'PAIS_DESTINO', 'VALOR_DESTINO', 'VALOR_COMISSAO']].head(50))

            # Download
            out = io.BytesIO()
            df_ag.to_excel(out, index=False)
            st.download_button("📥 Baixar Excel", out.getvalue(), f"{sel}.xlsx")
