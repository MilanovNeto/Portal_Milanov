import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# Configuração da página
st.set_page_config(page_title="Portal Milanov v8.1", layout="wide")

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
            # Busca as abas pelos nomes (independente da ordem)
            # Procura por 'USU' (de Usuarios) e 'CAD' (de Cadastro)
            aba_u = next((s for s in xl.sheet_names if 'USU' in s.upper()), xl.sheet_names[0])
            aba_c = next((s for s in xl.sheet_names if 'CAD' in s.upper()), xl.sheet_names[0])
            
            df_u = normalizar_colunas(pd.read_excel(caminho, sheet_name=aba_u))
            df_c = normalizar_colunas(pd.read_excel(caminho, sheet_name=aba_c))
            return df_u, df_c
        except Exception as e:
            st.error(f"Erro ao ler abas: {e}")
    return None, None

df_usuarios, df_cadastro = carregar_regras()

# --- LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso Milanov")
    if df_usuarios is None:
        st.error("Arquivo de regras não carregado.")
        st.stop()
        
    u_in = st.text_input("Usuário")
    p_in = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        # Verifica a coluna após normalização
        if 'USUARIO' in df_usuarios.columns:
            u_clean = limpar_texto(u_in)
            user_row = df_usuarios[df_usuarios['USUARIO'].apply(limpar_texto) == u_clean]
            
            if not user_row.empty:
                # Compara senhas de forma simples
                if str(p_in).strip() == str(user_row.iloc[0]['SENHA']).strip():
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
            else:
                st.error("Usuário não encontrado.")
        else:
            st.error("Coluna 'USUARIO' não encontrada na aba de usuários.")
            st.info(f"Colunas lidas: {list(df_usuarios.columns)}")
    st.stop()

# --- PAINEL ---
st.header("📊 Auditoria Milanov")
arq = st.file_uploader("📁 Relatório Corretora", type=['xlsx'])

if arq and df_cadastro is not None:
    df_raw = normalizar_colunas(pd.read_excel(arq))
    
    # Parâmetros
    st.sidebar.header("⚙️ Câmbio")
    v_usd_haiti = st.sidebar.number_input("USD Haiti (BRL)", value=5.48)
    v_htg_usd = st.sidebar.number_input("HTG / USD", value=130.0)
    
    # Merge
    df_raw['REALIZADO_POR'] = df_raw['REALIZADO_POR'].apply(limpar_texto)
    df_cadastro['REALIZADO_POR'] = df_cadastro['REALIZADO_POR'].apply(limpar_texto)
    df_final = pd.merge(df_raw, df_cadastro, on='REALIZADO_POR', how='left')

    if 'NOME_CONSOLIDADO' not in df_final.columns:
        df_final['NOME_CONSOLIDADO'] = df_final['REALIZADO_POR']
    else:
        df_final['NOME_CONSOLIDADO'] = df_final['NOME_CONSOLIDADO'].fillna(df_final['REALIZADO_POR'])

    # Motor v8.1
    df_final = df_final.sort_values(by=['NOME_CONSOLIDADO', 'DATA'])
    df_final['ORDEM'] = df_final.groupby('NOME_CONSOLIDADO').cumcount() + 1

    def motor(row):
        custo = row.get('COSTO_DE_ENVIO_BRL', 0)
        v_dest = row.get('VALOR_DESTINO', 0)
        moeda = limpar_texto(row.get('MOEDA_DESTINO', ''))
        pais = limpar_texto(row.get('PAIS_DESTINO', ''))
        pacote = str(row.get('ID_PACOTE_COMISSAO', '20'))
        
        v_usd = v_dest / v_htg_usd if (moeda == 'HTG' or pais == 'HAITI') else v_dest
            
        if '40' in pacote: return custo * 0.60
        if (moeda == 'HTG' or pais == 'HAITI') and v_usd <= 100:
            return 2.50 * v_usd_haiti
        
        return custo * 0.60 if row['ORDEM'] > 100 else custo * 0.50

    df_final['VALOR_COMISSAO'] = df_final.apply(motor, axis=1)

    # Exibição
    resumo = df_final.groupby('NOME_CONSOLIDADO')['VALOR_COMISSAO'].sum().reset_index()
    st.subheader("📋 Resumo")
    st.dataframe(resumo.sort_values('NOME_CONSOLIDADO').style.format({'VALOR_COMISSAO': 'R$ {:.2f}'}))

    with st.expander("🔍 Detalhar"):
        sel = st.selectbox("Agente:", ["Selecione..."] + resumo['NOME_CONSOLIDADO'].tolist())
        if sel != "Selecione...":
            df_ag = df_final[df_final['NOME_CONSOLIDADO'] == sel].copy()
            st.title(f"R$ {df_ag['VALOR_COMISSAO'].sum():,.2f}")
            st.table(df_ag[['ORDEM', 'PAIS_DESTINO', 'VALOR_DESTINO', 'VALOR_COMISSAO']].head(50))
            
            out = io.BytesIO()
            df_ag.to_excel(out, index=False)
            st.download_button("📥 Baixar", out.getvalue(), f"{sel}.xlsx")
