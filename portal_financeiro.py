import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# Configuração da página
st.set_page_config(page_title="Portal Milanov v7.6", layout="wide")

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
    # 1. Preparação dos Dados
    df_raw = pd.read_excel(arq_corr)
    df_raw = normalizar_colunas(df_raw)
    
    if 'DATA' in df_raw.columns:
        df_raw['DATA'] = pd.to_datetime(df_raw['DATA'])
        st.sidebar.header("📅 Período")
        d_min, d_max = df_raw['DATA'].min().date(), df_raw['DATA'].max().date()
        periodo = st.sidebar.date_input("Intervalo:", [d_min, d_max])
        if len(periodo) == 2:
            df_raw = df_raw[(df_raw['DATA'].dt.date >= periodo[0]) & (df_raw['DATA'].dt.date <= periodo[1])]
    
    v_dolar_haiti = st.sidebar.number_input("💵 Dólar Haiti (BRL)", value=5.48)
    v_conv_moeda = st.sidebar.number_input("🔄 Moeda Local -> USD", value=1.0)

    # 2. Cruzamento e Consolidação
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
        sel_com = st.sidebar.selectbox("Filtrar por Comercial:", lista_com)
        if sel_com != "TODOS":
            df_final = df_final[df_final['COMERCIAL'] == sel_com]
    else:
        sel_com = "TODOS"

    # 3. MOTOR DE CÁLCULO v7.6 (Regras de Escalonamento)
    # Criamos um contador por Agente Consolidado para saber qual é a 1ª, 2ª... 101ª operação
    df_final = df_final.sort_values(by=['NOME_CONSOLIDADO', 'DATA'])
    df_final['ORDEM_OP'] = df_final.groupby('NOME_CONSOLIDADO').cumcount() + 1

    def motor_v7_6(row):
        custo_brl = row.get('COSTO_DE_ENVIO_BRL', 0)
        v_usd = row.get('VALOR_DESTINO', 0) / v_conv_moeda
        pais = limpar_texto(row.get('PAIS_DESTINO', ''))
        id_p = str(row.get('ID_PACOTE_COMISSAO', '20'))
        n_op = row['ORDEM_OP'] # Qual é o número desta operação para o agente
        
        # REGRA 1: Pacote 40 (60% Fixo em tudo)
        if '40' in id_p:
            return custo_brl * 0.60
        
        # REGRA 2: Haiti (Até 100 USD = 2.50 USD Fixo)
        if pais == 'HAITI' and v_usd <= 100:
            return 2.50 * v_dolar_haiti
        
        # REGRA 3: Escalonamento (Acima de 100 operações paga 60%, senão 50%)
        # Nota: Ajustado para que apenas a partir da 101ª pague 60%
        percentual = 0.60 if n_op > 100 else 0.50
        return custo_brl * percentual

    df_final['COMISSAO_AGENTE'] = df_final.apply(motor_v7_6, axis=1)
    df_final['COMISSAO_COMERCIAL'] = df_final.get('REGRA_FIXO_COMERCIAL', 0)

    # 4. EXIBIÇÃO CONSOLIDADA (Ordem Alfabética)
    df_resumo = df_final.groupby(['COMERCIAL', 'NOME_CONSOLIDADO']).agg({
        'COMISSAO_AGENTE': 'sum',
        'COMISSAO_COMERCIAL': 'sum'
    }).reset_index().sort_values(by=['COMERCIAL', 'NOME_CONSOLIDADO'])
    
    df_resumo['TOTAL_A_PAGAR'] = df_resumo['COMISSAO_AGENTE'] + df_resumo['COMISSAO_COMERCIAL']

    st.subheader(f"📋 Resumo Consolidado - {sel_com}")
    st.dataframe(df_resumo.style.format({
        'COMISSAO_AGENTE': 'R$ {:.2f}', 
        'COMISSAO_COMERCIAL': 'R$ {:.2f}', 
        'TOTAL_A_PAGAR': 'R$ {:.2f}'
    }), use_container_width=True)

    # 5. DETALHAMENTO E DOWNLOAD
    st.markdown("---")
    with st.expander("🔍 Detalhar e Baixar Relatório"):
        agentes_lista = ["Selecione..."] + sorted(df_resumo['NOME_CONSOLIDADO'].tolist())
        agente_sel = st.selectbox("Selecione o Agente:", agentes_lista)
        
        if agente_sel != "Selecione...":
            df_agente = df_final[df_final['NOME_CONSOLIDADO'] == agente_sel].copy()
            st.title(f"R$ {df_agente['COMISSAO_AGENTE'].sum():,.2f}")

            # Tabela mostra a ordem da operação para conferência do escalonamento
            st.table(df_agente[['ORDEM_OP', 'DATA', 'REALIZADO_POR', 'PAIS_DESTINO', 'VALOR_DESTINO', 'COMISSAO_AGENTE']].style.format({
                'VALOR_DESTINO': 'R$ {:.2f}', 'COMISSAO_AGENTE': 'R$ {:.2f}'
            }))

            def gerar_xlsx(df):
                output = io.BytesIO()
                df.to_excel(output, index=False, engine='xlsxwriter')
                return output.getvalue()

            st.download_button(
                label=f"📥 Baixar Relatório - {agente_sel}",
                data=gerar_xlsx(df_agente),
                file_name=f"Milanov_{agente_sel}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
