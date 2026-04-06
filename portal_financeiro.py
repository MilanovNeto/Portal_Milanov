import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# Configuração da página
st.set_page_config(page_title="Portal Milanov v8.0", layout="wide")

# --- FUNÇÕES DE APOIO ---
def limpar_texto(txt):
    return str(txt).strip().upper()

def normalizar_colunas(df):
    """Garante que todas as colunas sejam MAIÚSCULAS e sem espaços"""
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df

@st.cache_data
def carregar_regras():
    caminho = "regras_milanov.xlsx"
    if os.path.exists(caminho):
        try:
            xl = pd.ExcelFile(caminho)
            # Lê as abas e já normaliza as colunas de imediato
            df_u = normalizar_colunas(pd.read_excel(caminho, sheet_name=0))
            df_c = normalizar_colunas(pd.read_excel(caminho, sheet_name=1))
            return df_u, df_c
        except Exception as e:
            st.error(f"Erro ao carregar abas: {e}")
            return None, None
    return None, None

# Carregamento Global
df_usuarios, df_cadastro = carregar_regras()

# --- SISTEMA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso Milanov")
    
    if df_usuarios is None:
        st.error("Arquivo 'regras_milanov.xlsx' não encontrado no GitHub.")
        st.stop()
        
    u_input = st.text_input("Usuário")
    p_input = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        # Verifica se a coluna USUARIO existe após a normalização
        if 'USUARIO' in df_usuarios.columns:
            u_clean = limpar_texto(u_input)
            user_row = df_usuarios[df_usuarios['USUARIO'].apply(limpar_texto) == u_clean]
            
            if not user_row.empty:
                senha_correta = str(user_row.iloc[0]['SENHA']).strip()
                if str(p_input).strip() == senha_correta:
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
            else:
                st.error("Usuário não cadastrado.")
        else:
            st.error("Coluna 'USUARIO' não encontrada na planilha.")
            st.info(f"Colunas lidas: {list(df_usuarios.columns)}")
    st.stop()

# --- PAINEL PÓS-LOGIN ---
st.header("📊 Auditoria Milanov")
arq = st.file_uploader("📁 Relatório Corretora", type=['xlsx'])

if arq and df_cadastro is not None:
    df_raw = normalizar_colunas(pd.read_excel(arq))
    
    # Parâmetros
    st.sidebar.header("⚙️ Câmbio")
    v_usd_haiti = st.sidebar.number_input("USD Haiti (BRL)", value=5.48)
    v_htg_usd = st.sidebar.number_input("HTG / USD", value=130.0)
    
    # Merge com Cadastro
    df_raw['REALIZADO_POR'] = df_raw['REALIZADO_POR'].apply(limpar_texto)
    df_cadastro['REALIZADO_POR'] = df_cadastro['REALIZADO_POR'].apply(limpar_texto)
    df_final = pd.merge(df_raw, df_cadastro, on='REALIZADO_POR', how='left')

    # Consolidação
    if 'NOME_CONSOLIDADO' not in df_final.columns:
        df_final['NOME_CONSOLIDADO'] = df_final['REALIZADO_POR']
    else:
        df_final['NOME_CONSOLIDADO'] = df_final['NOME_CONSOLIDADO'].fillna(df_final['REALIZADO_POR'])

    # Motor de Cálculo
    df_final = df_final.sort_values(by=['NOME_CONSOLIDADO', 'DATA'])
    df_final['ORDEM'] = df_final.groupby('NOME_CONSOLIDADO').cumcount() + 1

    def calcular_comissao(row):
        custo = row.get('COSTO_DE_ENVIO_BRL', 0)
        v_dest = row.get('VALOR_DESTINO', 0)
        moeda = limpar_texto(row.get('MOEDA_DESTINO', ''))
        pais = limpar_texto(row.get('PAIS_DESTINO', ''))
        pacote = str(row.get('ID_PACOTE_COMISSAO', '20'))
        
        # Conversão HTG
        v_usd = v_dest / v_htg_usd if (moeda == 'HTG' or pais == 'HAITI') else v_dest
            
        if '40' in pacote: return custo * 0.60
        if (moeda == 'HTG' or pais == 'HAITI') and v_usd <= 100:
            return 2.50 * v_usd_haiti
        
        return custo * 0.60 if row['ORDEM'] > 100 else custo * 0.50

    df_final['VALOR_COMISSAO'] = df_final.apply(calcular_comissao, axis=1)

    # Resumo Visível
    resumo = df_final.groupby('NOME_CONSOLIDADO')['VALOR_COMISSAO'].sum().reset_index()
    st.subheader("📋 Resumo de Comissões")
    st.dataframe(resumo.sort_values('NOME_CONSOLIDADO').style.format({'VALOR_COMISSAO': 'R$ {:.2f}'}))

    # Detalhes
    st.markdown("---")
    with st.expander("🔍 Detalhar Agente"):
        sel = st.selectbox("Agente:", ["Selecione..."] + resumo['NOME_CONSOLIDADO'].tolist())
        if sel != "Selecione...":
            df_ag = df_final[df_final['NOME_CONSOLIDADO'] == sel].copy()
            st.write(f"### Total: R$ {df_ag['VALOR_COMISSAO'].sum():,.2f}")
            st.table(df_ag[['ORDEM', 'PAIS_DESTINO', 'VALOR_DESTINO', 'VALOR_COMISSAO']].head(100))
            
            # Download
            out = io.BytesIO()
            df_ag.to_excel(out, index=False)
            st.download_button(f"📥 Baixar Excel {sel}", out.getvalue(), f"{sel}.xlsx")
