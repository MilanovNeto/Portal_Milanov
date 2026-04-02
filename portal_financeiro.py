import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# Configuração da página
st.set_page_config(page_title="Portal Milanov v7.0", layout="wide")

# --- CONFIGURAÇÃO DE SEGURANÇA E ARQUIVOS ---
# O arquivo deve estar na raiz do seu GitHub
CAMINHO_REGRAS = "regras_milanov.xlsx"

def limpar_texto(txt):
    return str(txt).strip().upper()

@st.cache_data
def carregar_regras():
    if os.path.exists(CAMINHO_REGRAS):
        try:
            xl = pd.ExcelFile(CAMINHO_REGRAS)
            # Identifica as abas de forma flexível (Usuarios e Cadastro)
            aba_u = next((s for s in xl.sheet_names if 'usu' in s.lower()), "Usuarios")
            aba_c = next((s for s in xl.sheet_names if 'cad' in s.lower()), "Cadastro_Agentes")
            
            df_u = pd.read_excel(CAMINHO_REGRAS, sheet_name=aba_u)
            df_c = pd.read_excel(CAMINHO_REGRAS, sheet_name=aba_c)
            
            # Padroniza cabeçalhos para evitar o erro 'Index object has no attribute upper'
            df_u.columns = [str(c).strip().upper() for c in df_u.columns]
            df_c.columns = [str(c).strip().upper() for c in df_c.columns]
            
            return df_u, df_c
        except Exception as e:
            st.error(f"Erro ao processar tabelas: {e}")
            return None, None
    return None, None

df_usuarios, df_cadastro = carregar_regras()

# --- SISTEMA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Sistema de comissões")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        if df_usuarios is not None:
            user_row = df_usuarios[df_usuarios['USUARIO'].apply(limpar_texto) == limpar_texto(u)]
            if not user_row.empty and str(user_row.iloc[0]['SENHA']).strip() == str(p).strip():
                st.session_state.autenticado = True
                st.session_state.usuario_logado = limpar_texto(u)
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
        else:
            st.error("Arquivo de regras não encontrado no GitHub.")
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.header("📊 Painel de Gestão Milanov")
arq_corr = st.file_uploader("📁 Subir Relatório da Corretora (Excel)", type=['xlsx'])

if arq_corr and df_cadastro is not None:
    # 1. Leitura do Relatório
    df_raw = pd.read_excel(arq_corr)
    df_raw['Data'] = pd.to_datetime(df_raw['Data'])
    
    # 2. FILTROS NA SIDEBAR
    st.sidebar.header("📅 Período de Auditoria")
    d_min, d_max = df_raw['Data'].min().date(), df_raw['Data'].max().date()
    periodo = st.sidebar.date_input("Selecione as datas:", [d_min, d_max])
    
    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Ajustes Financeiros")
    v_dolar_brl = st.sidebar.number_input("💵 Dólar Haiti (BRL)", value=5.48)
    v_conv_moeda = st.sidebar.number_input("🔄 Cotação Moeda Local -> USD", value=1.0)
    
    # Aplicação do filtro de data
    if len(periodo) == 2:
        start_date, end_date = periodo
        df_raw = df_raw[(df_raw['Data'].dt.date >= start_date) & (df_raw['Data'].dt.date <= end_date)]

    # 3. CRUZAMENTO DE DADOS (JOIN)
    df_raw['Realizado_por'] = df_raw['Realizado_por'].apply(limpar_texto)
    df_cadastro['Realizado_por'] = df_cadastro['Realizado_por'].apply(limpar_texto)
    df_final = pd.merge(df_raw, df_cadastro, on='Realizado_por', how='left')

    # Filtro por Comercial
    lista_com = ["TODOS"] + sorted(df_final['COMERCIAL'].dropna().unique().tolist())
    sel_com = st.sidebar.selectbox("Filtrar por Comercial:", lista_com)
    if sel_com != "TODOS":
        df_final = df_final[df_final['COMERCIAL'] == sel_com]

    # 4. MOTOR DE CÁLCULO V6.5
    def motor_v6_5(row):
        custo_brl = row.get('COSTO_DE_ENVIO_BRL', 0)
        v_usd = row.get('VALOR_DESTINO', 0) / v_conv_moeda
        pais = limpar_texto(row.get('PAIS_DESTINO', ''))
        vol = len(df_final[df_final['REALIZADO_POR'] == row['REALIZADO_POR']])
        
        if pais == 'HAITI':
            if v_usd <= 100: return 2.5 * v_dolar_brl
            return custo_brl * (0.50 if vol <= 100 else 0.60)
        
        id_p = str(row.get('ID_PACOTE_COMISSAO', '20'))
        if '40' in id_p: return custo_brl * 0.60
        
        p = 0.30 if vol <= 50 else (0.50 if vol <= 100 else 0.60)
        return custo_brl * p

    # Aplicação dos Cálculos
    # Padroniza colunas do relatório carregado para garantir o cálculo
    df_final.columns = [c.upper() for c in df_final.columns]
    df_final['COMISSAO_AGENTE'] = df_final.apply(motor_v6_5, axis=1)
    df_final['COMISSAO_COMERCIAL'] = df_final.get('REGRA_FIXO_COMERCIAL', 0)

    # 5. EXIBIÇÃO DO RESUMO CONSOLIDADO
    df_resumo = df_final.groupby(['COMERCIAL', 'REALIZADO_POR']).agg({
        'COMISSAO_AGENTE': 'sum',
        'COMISSAO_COMERCIAL': 'sum'
    }).reset_index()
    df_resumo['TOTAL_A_PAGAR'] = df_resumo['COMISSAO_AGENTE'] + df_resumo['COMISSAO_COMERCIAL']

    st.subheader(f"📋 Resumo Consolidado - {sel_com}")
    st.dataframe(df_resumo.style.format({
        'COMISSAO_AGENTE': 'R$ {:.2f}', 
        'COMISSAO_COMERCIAL': 'R$ {:.2f}', 
        'TOTAL_A_PAGAR': 'R$ {:.2f}'
    }), use_container_width=True)

    # 6. INVESTIGAÇÃO DETALHADA E DOWNLOAD (FILTRADO POR AGENTE)
    st.markdown("---")
    with st.expander("🔍 Ver Operações Detalhadas e Baixar Excel do Agente"):
        agente_sel = st.selectbox("Selecione um Agente para detalhar:", ["Selecione..."] + df_resumo['REALIZADO_POR'].tolist())
        
        if agente_sel != "Selecione...":
            # Filtro exclusivo para o agente selecionado
            df_agente_unico = df_final[df_final['REALIZADO_POR'] == agente_sel].copy()
            
            # Exibe o total em destaque
            total_ag = df_agente_unico['COMISSAO_AGENTE'].sum()
            st.write(f"**Total de Comissões de {agente_sel}:**")
            st.title(f"R$ {total_ag:,.2f}")

            # Tabela de operações detalhadas
            st.table(df_agente_unico[['DATA', 'PAIS_DESTINO', 'VALOR_DESTINO', 'COMISSAO_AGENTE']].style.format({
                'VALOR_DESTINO': 'R$ {:.2f}', 
                'COMISSAO_AGENTE': 'R$ {:.2f}'
            }))

            # Função para converter para Excel (.xlsx)
            def to_excel(df):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Fechamento_Milanov')
                return output.getvalue()

            # Botão de Download Exclusivo do Agente
            excel_file = to_excel(df_agente_unico)
            st.download_button(
                label=f"📥 Baixar Relatório de Fechamento - {agente_sel}",
                data=excel_file,
                file_name=f"Fechamento_{agente_sel}_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
