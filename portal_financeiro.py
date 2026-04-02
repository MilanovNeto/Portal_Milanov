import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# Configuração da página
st.set_page_config(page_title="Portal Milanov v7.2", layout="wide")

# --- FUNÇÕES DE APOIO ---
def limpar_texto(txt):
    return str(txt).strip().upper()

def normalizar_colunas(df):
    """Remove espaços e coloca nomes das colunas em MAIÚSCULO"""
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

# --- CARREGAMENTO INICIAL ---
df_usuarios, df_cadastro = carregar_regras()

# --- SISTEMA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso Restrito - Milanov")
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
            st.error("Arquivo de regras não encontrado.")
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.header(f"📊 Painel de Auditoria Milanov")
arq_corr = st.file_uploader("📁 Subir Relatório da Corretora (Excel)", type=['xlsx'])

if arq_corr and df_cadastro is not None:
    # 1. Leitura e Normalização
    df_raw = pd.read_excel(arq_corr)
    df_raw = normalizar_colunas(df_raw)
    
    if 'DATA' in df_raw.columns:
        df_raw['DATA'] = pd.to_datetime(df_raw['DATA'])
        st.sidebar.header("📅 Período")
        d_min, d_max = df_raw['DATA'].min().date(), df_raw['DATA'].max().date()
        periodo = st.sidebar.date_input("Intervalo:", [d_min, d_max])
        
        if len(periodo) == 2:
            df_raw = df_raw[(df_raw['DATA'].dt.date >= periodo[0]) & (df_raw['DATA'].dt.date <= periodo[1])]
    
    st.sidebar.markdown("---")
    v_dolar_haiti = st.sidebar.number_input("💵 Dólar Haiti (BRL)", value=5.48)
    v_conv_moeda = st.sidebar.number_input("🔄 Moeda Local -> USD", value=1.0)

    # 2. CRUZAMENTO (MERGE)
    df_raw['REALIZADO_POR'] = df_raw['REALIZADO_POR'].apply(limpar_texto)
    df_cadastro['REALIZADO_POR'] = df_cadastro['REALIZADO_POR'].apply(limpar_texto)
    df_final = pd.merge(df_raw, df_cadastro, on='REALIZADO_POR', how='left')

    if 'COMERCIAL' in df_final.columns:
        lista_com = ["TODOS"] + sorted(df_final['COMERCIAL'].dropna().unique().tolist())
        sel_com = st.sidebar.selectbox("Filtrar Comercial:", lista_com)
        if sel_com != "TODOS":
            df_final = df_final[df_final['COMERCIAL'] == sel_com]
    else:
        sel_com = "TODOS"

    # 3. MOTOR DE CÁLCULO V6.5
    def motor_v6_5(row):
        custo_brl = row.get('COSTO_DE_ENVIO_BRL', 0)
        v_usd = row.get('VALOR_DESTINO', 0) / v_conv_moeda
        pais = limpar_texto(row.get('PAIS_DESTINO', ''))
        vol = len(df_final[df_final['REALIZADO_POR'] == row['REALIZADO_POR']])
        
        if pais == 'HAITI':
            if v_usd <= 100: return 2.5 * v_dolar_haiti
            return custo_brl * (0.50 if vol <= 100 else 0.60)
        
        id_p = str(row.get('ID_PACOTE_COMISSAO', '20'))
        if '40' in id_p: return custo_brl * 0.60
        
        p = 0.30 if vol <= 50 else (0.50 if vol <= 100 else 0.60)
        return custo_brl * p

    # Criando as colunas de cálculo
    df_final['COMISSAO_AGENTE'] = df_final.apply(motor_v6_5, axis=1)
    df_final['COMISSAO_COMERCIAL'] = df_final.get('REGRA_FIXO_COMERCIAL', 0)

    # 4. EXIBIÇÃO DO RESUMO
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

    # 5. INVESTIGAÇÃO E DOWNLOAD POR AGENTE
    st.markdown("---")
    with st.expander("🔍 Ver Operações Detalhadas e Baixar Relatório"):
        agente_sel = st.selectbox("Escolha um Agente:", ["Selecione..."] + df_resumo['REALIZADO_POR'].tolist())
        
        if agente_sel != "Selecione...":
            df_agente = df_final[df_final['REALIZADO_POR'] == agente_sel].copy()
            
            total_ag = df_agente['COMISSAO_AGENTE'].sum()
            st.markdown(f"### Total de Comissões: {agente_sel}")
            st.title(f"R$ {total_ag:,.2f}")

            # Define as colunas que vão para o Excel (Originais + Comissão)
            colunas_excel = list(df_raw.columns)
            if 'COMISSAO_AGENTE' not in colunas_excel:
                colunas_excel.append('COMISSAO_AGENTE')

            # Tabela visual formatada
            cols_vista = ['DATA', 'PAIS_DESTINO', 'VALOR_DESTINO', 'COMISSAO_AGENTE']
            st.table(df_agente[cols_vista].style.format({
                'VALOR_DESTINO': 'R$ {:.2f}', 
                'COMISSAO_AGENTE': 'R$ {:.2f}'
            }))

            # Função de conversão
            def gerar_xlsx(df, colunas):
                output = io.BytesIO()
                df_export = df[colunas]
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Extrato')
                return output.getvalue()

            # Botão de download
            st.download_button(
                label=f"📥 Baixar Relatório - {agente_sel}",
                data=gerar_xlsx(df_agente, colunas_excel),
                file_name=f"Milanov_{agente_sel}_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
