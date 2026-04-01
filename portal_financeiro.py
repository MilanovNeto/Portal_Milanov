import streamlit as st
import pandas as pd
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal Milanov v7.0", layout="wide")

def limpar_texto(txt):
    return str(txt).strip().upper()

# --- CARREGAMENTO DE REGRAS (AGORA VIA GITHUB/LOCAL) ---
@st.cache_data
def carregar_regras():
    # O arquivo deve estar na mesma pasta que este script no GitHub
    caminho_regras = "regras_milanov.xlsx"
    if os.path.exists(caminho_regras):
        xl = pd.ExcelFile(caminho_regras)
        # Busca as abas de usuários e cadastro de agentes de forma dinâmica
        aba_u = next((s for s in xl.sheet_names if 'usu' in s.lower()), "Usuarios")
        aba_c = next((s for s in xl.sheet_names if 'cad' in s.lower()), "Cadastro_Agentes")
        
        df_u = pd.read_excel(caminho_regras, sheet_name=aba_u)
        df_c = pd.read_excel(caminho_regras, sheet_name=aba_c)
        return df_u, df_c
    return None, None

df_usuarios, df_cadastro = carregar_regras()

# --- SISTEMA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🔐 Login Milanov</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            if df_usuarios is not None:
                # Padroniza colunas para evitar erros de case
                df_usuarios.columns = [limpar_texto(c) for c in df_usuarios.columns]
                user_row = df_usuarios[df_usuarios['USUARIO'].apply(limpar_texto) == limpar_texto(u)]
                
                if not user_row.empty and str(user_row.iloc[0]['SENHA']).strip() == str(p).strip():
                    st.session_state.autenticado = True
                    st.session_state.user_tipo = limpar_texto(user_row.iloc[0]['DEPARTAMENTO']) if 'DEPARTAMENTO' in user_row.columns else "AGENTE"
                    st.rerun()
                else:
                    st.error("Usuário ou Senha incorretos.")
            else:
                st.error("Base de dados 'regras_milanov.xlsx' não encontrada no servidor.")
    st.stop()

# --- SISTEMA DE AUDITORIA (ÁREA LOGADA) ---
st.header("📊 Auditoria de Fechamento Milanov")
st.markdown("---")

# Uploader do arquivo que vem da Corretora
arq_corr = st.file_uploader("📁 Subir Relatório Corretora (Excel)", type=['xlsx'])

if arq_corr and df_cadastro is not None:
    # 1. Carregamento do Extrato
    df_raw = pd.read_excel(arq_corr)
    
    # Garante que a coluna Data seja tratada corretamente
    if 'Data' in df_raw.columns:
        df_raw['Data'] = pd.to_datetime(df_raw['Data'])
        d_min, d_max = df_raw['Data'].min().date(), df_raw['Data'].max().date()
        
        # 2. FILTROS NA SIDEBAR
        st.sidebar.header("📅 Filtros de Período")
        periodo = st.sidebar.date_input("Intervalo de Fechamento:", [d_min, d_max])
        
        st.sidebar.markdown("---")
        st.sidebar.header("⚙️ Parâmetros Financeiros")
        v_dolar_brl = st.sidebar.number_input("💵 Dólar Haiti (BRL)", value=5.48)
        v_conv_moeda = st.sidebar.number_input("🔄 Cotação Moeda Local -> USD", value=1.0)
        
        # Filtro de Data
        if isinstance(periodo, list) or isinstance(periodo, tuple):
            if len(periodo) == 2:
                start_date, end_date = periodo
                df_raw = df_raw[(df_raw['Data'].dt.date >= start_date) & (df_raw['Data'].dt.date <= end_date)]

        # 3. PROCESSAMENTO (MOTOR V6.5)
        df_raw['Realizado_por'] = df_raw['Realizado_por'].apply(limpar_texto)
        df_cadastro['Realizado_por'] = df_cadastro['Realizado_por'].apply(limpar_texto)
        
        # Cruzamento de dados com a aba Cadastro_Agentes
        df_final = pd.merge(df_raw, df_cadastro, on='Realizado_por', how='left')

        # Filtro por Comercial
        lista_com = ["TODOS"] + sorted(df_final['Comercial'].dropna().unique().tolist())
        sel_com = st.sidebar.selectbox("Selecionar Comercial:", lista_com)
        if sel_com != "TODOS":
            df_final = df_final[df_final['Comercial'] == sel_com]

        # MOTOR DE CÁLCULO ORIGINAL
        def motor_calculo(row):
            custo_brl = row.get('Costo_de_envio_BRL', 0)
            v_usd = row.get('Valor_destino', 0) / v_conv_moeda
            pais = limpar_texto(row.get('Pais_Destino', ''))
            vol = len(df_final[df_final['Realizado_por'] == row['Realizado_por']])
            
            if pais == 'HAITI':
                if v_usd <= 100: 
                    return 2.5 * v_dolar_brl
                p_haiti = 0.50 if vol <= 100 else 0.60
                return custo_brl * p_haiti
            
            id_p = str(row.get('ID_Pacote_Comissao', '20'))
            if '40' in id_p: 
                return custo_brl * 0.60
            
            p_geral = 0.30 if vol <= 50 else (0.50 if vol <= 100 else 0.60)
            return custo_brl * p_geral

        # Aplicação das fórmulas
        df_final['COMISSAO_AGENTE'] = df_final.apply(motor_calculo, axis=1)
        df_final['COMISSAO_COMERCIAL'] = df_final.get('Regra_Fixo_Comercial', 0)

        # 4. EXIBIÇÃO DE RESULTADOS
        df_resumo = df_final.groupby(['Comercial', 'Realizado_por']).agg({
            'COMISSAO_AGENTE': 'sum',
            'COMISSAO_COMERCIAL': 'sum'
        }).reset_index()
        
        df_resumo['TOTAL_A_PAGAR'] = df_resumo['COMISSAO_AGENTE'] + df_resumo['COMISSAO_COMERCIAL']

        st.subheader("📋 Resumo Consolidado")
        st.dataframe(
            df_resumo.style.format({
                'COMISSAO_AGENTE': 'R$ {:.2f}', 
                'COMISSAO_COMERCIAL': 'R$ {:.2f}', 
                'TOTAL_A_PAGAR': 'R$ {:.2f}'
            }), 
            use_container_width=True
        )

        # Drill-down para conferência
        with st.expander("🔍 Detalhamento por Operação"):
            agente = st.selectbox("Selecione o Agente para Auditoria:", ["-- Escolha --"] + df_resumo['Realizado_por'].tolist())
            if agente != "-- Escolha --":
                det = df_final[df_final['Realizado_por'] == agente].copy()
                st.write(f"Operações de {agente}:")
                st.dataframe(
                    det[['Data', 'Pais_Destino', 'Valor_destino', 'Costo_de_envio_BRL', 'COMISSAO_AGENTE']].style.format({
                        'Valor_destino': '{:.2f}',
                        'Costo_de_envio_BRL': '{:.2f}',
                        'COMISSAO_AGENTE': '{:.2f}'
                    }),
                    use_container_width=True
                )
    else:
        st.warning("O arquivo subido não possui a coluna 'Data'. Verifique o layout da corretora.")

# Botão de Logout na Sidebar
if st.session_state.autenticado:
    if st.sidebar.button("Sair do Sistema"):
        st.session_state.autenticado = False
        st.rerun()
