import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# Configuração da página
st.set_page_config(page_title="Portal Milanov v8.2", layout="wide")

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
            
            # Busca inteligente por conteúdo das abas
            for aba in xl.sheet_names:
                temp_df = normalizar_colunas(pd.read_excel(caminho, sheet_name=aba))
                if 'USUARIO' in temp_df.columns:
                    df_u = temp_df
                if 'REALIZADO_POR' in temp_df.columns and 'COMERCIAL' in temp_df.columns:
                    df_c = temp_df
            
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
        st.error("Erro: Aba de usuários não identificada no arquivo 'regras_milanov.xlsx'.")
        st.stop()
        
    u_in = st.text_input("Usuário")
    p_in = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        u_clean = limpar_texto(u_in)
        # Filtra o usuário ignorando maiúsculas/minúsculas
        user_row = df_usuarios[df_usuarios['USUARIO'].apply(limpar_texto) == u_clean]
        
        if not user_row.empty:
            if str(p_in).strip() == str(user_row.iloc[0]['SENHA']).strip():
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
        else:
            st.error("Usuário não encontrado.")
    st.stop()

# --- PAINEL PRINCIPAL ---
st.header("📊 Auditoria Milanov")
arq = st.file_uploader("📁 Relatório Corretora", type=['xlsx'])

if arq and df_cadastro is not None:
    df_raw = normalizar_colunas(pd.read_excel(arq))
    
    # Parâmetros na Sidebar
    st.sidebar.header("⚙️ Configurações")
    v_usd_haiti = st.sidebar.number_input("Câmbio USD Haiti (BRL)", value=5.48)
    v_htg_usd = st.sidebar.number_input("Cotação HTG / USD", value=130.0)
    
    # Cruzamento de Dados
    df_raw['REALIZADO_POR'] = df_raw['REALIZADO_POR'].apply(limpar_texto)
    df_cadastro['REALIZADO_POR'] = df_cadastro['REALIZADO_POR'].apply(limpar_texto)
    df_final = pd.merge(df_raw, df_cadastro, on='REALIZADO_POR', how='left')

    # Ajuste de Nomes Consolidados
    if 'NOME_CONSOLIDADO' not in df_final.columns:
        df_final['NOME_CONSOLIDADO'] = df_final['REALIZADO_POR']
    else:
        df_final['NOME_CONSOLIDADO'] = df_final['NOME_CONSOLIDADO'].fillna(df_final['REALIZADO_POR'])

    # Cálculo de Ordem e Comissões
    df_final = df_final.sort_values(by=['NOME_CONSOLIDADO', 'DATA'])
    df_final['ORDEM'] = df_final.groupby('NOME_CONSOLIDADO').cumcount() + 1

    def motor_calculo(row):
        custo = row.get('COSTO_DE_ENVIO_BRL', 0)
        v_dest = row.get('VALOR_DESTINO', 0)
        moeda = limpar_texto(row.get('MOEDA_DESTINO', ''))
        pais = limpar_texto(row.get('PAIS_DESTINO', ''))
        pacote = str(row.get('ID_PACOTE_COMISSAO', '20'))
        
        # Lógica HTG: Converte para USD para verificar se é operação de "baixo valor"
        v_usd_convertido = v_dest / v_htg_usd if (moeda == 'HTG' or pais == 'HAITI') else v_dest
            
        # Regra de Ouro: Pacote 40 sempre ganha 60%
        if '40' in pacote: return custo * 0.60
        
        # Regra Haiti Fixo: Operações até 100 USD pagam 2.50 USD (convertido para BRL)
        if (moeda == 'HTG' or pais == 'HAITI') and v_usd_convertido <= 100:
            return 2.50 * v_usd_haiti
        
        # Regra Escalonada: Acima de 100 ops = 60%, até 100 ops = 50%
        return custo * 0.60 if row['ORDEM'] > 100 else custo * 0.50

    df_final['VALOR_COMISSAO'] = df_final.apply(motor_calculo, axis=1)

    # Exibição do Resumo
    resumo = df_final.groupby(['COMERCIAL', 'NOME_CONSOLIDADO'])['VALOR_COMISSAO'].sum().reset_index()
    resumo = resumo.sort_values(by=['COMERCIAL', 'NOME_CONSOLIDADO'])
    
    st.subheader("📋 Resumo Consolidado")
    st.dataframe(resumo.style.format({'VALOR_COMISSAO': 'R$ {:.2f}'}), use_container_width=True)

    # Detalhamento por Agente
    st.markdown("---")
    with st.expander("🔍 Detalhar Agente"):
        agentes = ["Selecione..."] + sorted(resumo['NOME_CONSOLIDADO'].unique().tolist())
        sel = st.selectbox("Escolha o Agente:", agentes)
        
        if sel != "Selecione...":
            df_ag = df_final[df_final['NOME_CONSOLIDADO'] == sel].copy()
            total_ag = df_ag['VALOR_COMISSAO'].sum()
            
            st.write(f"### Total: {sel}")
            st.title(f"R$ {total_ag:,.2f}")
            
            st.table(df_ag[['ORDEM', 'DATA', 'PAIS_DESTINO', 'VALOR_DESTINO', 'VALOR_COMISSAO']].head(100))
            
            # Download do relatório individual
            buffer = io.BytesIO()
            df_ag.to_excel(buffer, index=False)
            st.download_button(f"📥 Baixar Excel {sel}", buffer.getvalue(), f"Auditoria_{sel}.xlsx")
