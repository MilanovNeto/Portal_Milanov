import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────
st.set_page_config(page_title="Portal Milanov v9.0", layout="wide", page_icon="💸")

# ─────────────────────────────────────────────
# FUNÇÕES UTILITÁRIAS
# ─────────────────────────────────────────────
def limpar_texto(txt):
    return str(txt).strip().upper()

def normalizar_colunas(df):
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df

@st.cache_data
def carregar_regras():
    caminho = "regras_milanov.xlsx"
    if not os.path.exists(caminho):
        return None, None
    try:
        xl = pd.ExcelFile(caminho)
        df_u, df_c = None, None
        for aba in xl.sheet_names:
            temp = normalizar_colunas(pd.read_excel(caminho, sheet_name=aba))
            if 'USUARIO' in temp.columns:
                df_u = temp
            if 'REALIZADO_POR' in temp.columns:
                df_c = temp
        return df_u, df_c
    except Exception:
        return None, None

df_usuarios, df_cadastro = carregar_regras()

# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    col_l, col_c, col_r = st.columns([1, 1.2, 1])
    with col_c:
        st.markdown("## 🔐 Acesso Milanov")
        if df_usuarios is None:
            st.error("Arquivo 'regras_milanov.xlsx' não encontrado.")
            st.stop()
        u_in = st.text_input("Usuário")
        p_in = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True, type="primary"):
            u_clean = limpar_texto(u_in)
            user_row = df_usuarios[df_usuarios['USUARIO'].apply(limpar_texto) == u_clean]
            if not user_row.empty and str(p_in).strip() == str(user_row.iloc[0]['SENHA']).strip():
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
    st.stop()

# ─────────────────────────────────────────────
# PAINEL PRINCIPAL
# ─────────────────────────────────────────────
st.title("💸 Portal Milanov — Auditoria de Comissões")
arq = st.file_uploader("📁 Carregar Relatório da Corretora (.xlsx)", type=['xlsx'])

if not arq:
    st.info("Aguardando o upload do relatório para iniciar a auditoria.")
    st.stop()

if df_cadastro is None:
    st.error("Planilha de cadastro 'regras_milanov.xlsx' não encontrada ou sem aba válida.")
    st.stop()

df_raw = normalizar_colunas(pd.read_excel(arq))

# ─────────────────────────────────────────────
# SIDEBAR — PARÂMETROS
# ─────────────────────────────────────────────
st.sidebar.header("⚙️ Parâmetros")
v_usd_haiti = st.sidebar.number_input("Câmbio USD Haiti (BRL)", value=5.48, format="%.4f")
v_htg_usd   = st.sidebar.number_input("Cotação HTG / USD",      value=130.0, format="%.2f")

# Filtro de período
if 'DATA' in df_raw.columns:
    df_raw['DATA'] = pd.to_datetime(df_raw['DATA'], errors='coerce')
    d_min = df_raw['DATA'].min().date()
    d_max = df_raw['DATA'].max().date()
    periodo = st.sidebar.date_input("📅 Período:", [d_min, d_max])
    if len(periodo) == 2:
        df_raw = df_raw[
            (df_raw['DATA'].dt.date >= periodo[0]) &
            (df_raw['DATA'].dt.date <= periodo[1])
        ]

# ─────────────────────────────────────────────
# CRUZAMENTO COM CADASTRO
# ─────────────────────────────────────────────
df_raw['REALIZADO_POR']      = df_raw['REALIZADO_POR'].apply(limpar_texto)
df_cadastro['REALIZADO_POR'] = df_cadastro['REALIZADO_POR'].apply(limpar_texto)

df_final = pd.merge(df_raw, df_cadastro, on='REALIZADO_POR', how='left')

# Nome consolidado: usa alias do cadastro se existir, senão o próprio código
if 'NOME_CONSOLIDADO' not in df_final.columns:
    df_final['NOME_CONSOLIDADO'] = df_final['REALIZADO_POR']
else:
    df_final['NOME_CONSOLIDADO'] = df_final['NOME_CONSOLIDADO'].fillna(df_final['REALIZADO_POR'])

# Garante que ID_PACOTE_COMISSAO seja string limpa para comparação exata
df_final['ID_PACOTE_COMISSAO'] = df_final['ID_PACOTE_COMISSAO'].fillna('20').apply(limpar_texto)

# ─────────────────────────────────────────────
# FILTRO DE COMERCIAL
# ─────────────────────────────────────────────
sel_com = "TODOS"
if 'COMERCIAL' in df_final.columns:
    lista_com = ["TODOS"] + sorted(df_final['COMERCIAL'].dropna().unique().tolist())
    sel_com = st.sidebar.selectbox("👤 Filtrar Comercial:", lista_com)
    if sel_com != "TODOS":
        df_final = df_final[df_final['COMERCIAL'] == sel_com]

# ─────────────────────────────────────────────
# ORDENAÇÃO E CONTAGEM DE OPERAÇÕES POR AGENTE
# ─────────────────────────────────────────────
df_final = df_final.sort_values(by=['NOME_CONSOLIDADO', 'DATA']).reset_index(drop=True)
df_final['ORDEM'] = df_final.groupby('NOME_CONSOLIDADO').cumcount() + 1

# ─────────────────────────────────────────────
# MOTOR DE CÁLCULO DE COMISSÃO
# Hierarquia:
#   1. Pacote 40  → 60% fixo sobre COSTO_DE_ENVIO_BRL
#   2. Haiti/HTG  → fixo R$2,50×câmbio (≤100 USD) ou escalonamento (>100 USD)
#   3. Escalonamento → 50% até op.100 / 60% a partir op.101
# ─────────────────────────────────────────────
def motor(row):
    custo  = float(row.get('COSTO_DE_ENVIO_BRL', 0) or 0)
    v_dest = float(row.get('VALOR_DESTINO', 0)       or 0)
    moeda  = limpar_texto(row.get('MOEDA_DESTINO', ''))
    pais   = limpar_texto(row.get('PAIS_DESTINO', ''))
    pacote = limpar_texto(row.get('ID_PACOTE_COMISSAO', '20'))
    ordem  = int(row.get('ORDEM', 1))

    # ── PRIORIDADE 1: Pacote 40 ──────────────────────────────────────────
    if pacote == '40':
        return custo * 0.60

    # ── PRIORIDADE 2: Haiti / HTG ────────────────────────────────────────
    is_haiti = (pais == 'HAITI' or moeda == 'HTG')
    if is_haiti:
        v_usd = v_dest / v_htg_usd if v_htg_usd > 0 else 0
        if v_usd <= 100:
            return 2.50 * v_usd_haiti          # comissão fixa em BRL

        # Acima de 100 USD → cai no escalonamento abaixo (não retorna aqui)

    # ── PRIORIDADE 3: Escalonamento por volume ───────────────────────────
    # Operações 1–100: 50% | 101+: 60%
    # A comissão de CADA operação individual usa a faixa em que ela se encontra.
    if ordem <= 100:
        return custo * 0.50
    else:
        return custo * 0.60

df_final['VALOR_COMISSAO'] = df_final.apply(motor, axis=1)

# ─────────────────────────────────────────────
# RESUMO CONSOLIDADO
# ─────────────────────────────────────────────
agg_dict = {
    'VALOR_COMISSAO': 'sum',
    'ORDEM': 'max',               # total de operações do agente
}

group_cols = ['COMERCIAL', 'NOME_CONSOLIDADO'] if 'COMERCIAL' in df_final.columns else ['NOME_CONSOLIDADO']
resumo = df_final.groupby(group_cols).agg(agg_dict).reset_index()
resumo.rename(columns={'ORDEM': 'TOTAL_OPS'}, inplace=True)

# ─────────────────────────────────────────────
# EXIBIÇÃO DO RESUMO
# ─────────────────────────────────────────────
st.subheader(f"📋 Resumo de Comissões — {sel_com}")

# Métricas rápidas no topo
col1, col2, col3 = st.columns(3)
col1.metric("Total Agentes",     resumo['NOME_CONSOLIDADO'].nunique())
col2.metric("Total Operações",   f"{int(df_final['ORDEM'].max()):,}".replace(',', '.') if not df_final.empty else "0")
col3.metric("Total Comissões",   f"R$ {resumo['VALOR_COMISSAO'].sum():,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))

st.markdown("---")

# Monta colunas de exibição dinamicamente
cols_resumo = group_cols + ['TOTAL_OPS', 'VALOR_COMISSAO']
fmt_resumo  = {'VALOR_COMISSAO': 'R$ {:.2f}', 'TOTAL_OPS': '{:.0f}'}

st.dataframe(
    resumo[cols_resumo]
        .sort_values(group_cols)
        .style.format(fmt_resumo),
    use_container_width=True,
    height=400,
)

# ─────────────────────────────────────────────
# INVESTIGAÇÃO POR AGENTE
# ─────────────────────────────────────────────
st.markdown("---")
with st.expander("🔍 Investigar Agente em Detalhe"):
    agentes = ["Selecione..."] + sorted(resumo['NOME_CONSOLIDADO'].unique().tolist())
    sel_ag  = st.selectbox("Selecione o agente:", agentes)

    if sel_ag != "Selecione...":
        df_ag = df_final[df_final['NOME_CONSOLIDADO'] == sel_ag].copy()
        total_ag = df_ag['VALOR_COMISSAO'].sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Comissão",  f"R$ {total_ag:,.2f}")
        c2.metric("Total Operações", len(df_ag))
        c3.metric("Pacote",          df_ag['ID_PACOTE_COMISSAO'].iloc[0] if len(df_ag) else "—")

        cols_det = ['ORDEM', 'DATA', 'PAIS_DESTINO', 'MOEDA_DESTINO',
                    'VALOR_DESTINO', 'COSTO_DE_ENVIO_BRL', 'ID_PACOTE_COMISSAO', 'VALOR_COMISSAO']
        cols_det = [c for c in cols_det if c in df_ag.columns]

        st.dataframe(
            df_ag[cols_det]
                .head(200)
                .style.format({
                    'VALOR_COMISSAO':     'R$ {:.2f}',
                    'COSTO_DE_ENVIO_BRL': 'R$ {:.2f}',
                    'VALOR_DESTINO':      '{:,.2f}',
                }),
            use_container_width=True,
        )

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_ag.to_excel(writer, index=False, sheet_name='Detalhe')
            resumo[resumo['NOME_CONSOLIDADO'] == sel_ag].to_excel(writer, index=False, sheet_name='Resumo')
        st.download_button(
            label=f"📥 Baixar Excel — {sel_ag}",
            data=buf.getvalue(),
            file_name=f"comissao_{sel_ag}_{datetime.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# ─────────────────────────────────────────────
# EXPORTAÇÃO GERAL
# ─────────────────────────────────────────────
st.markdown("---")
st.subheader("📤 Exportar Relatório Completo")
buf_geral = io.BytesIO()
with pd.ExcelWriter(buf_geral, engine='openpyxl') as writer:
    resumo.to_excel(writer, index=False, sheet_name='Resumo')
    df_final.to_excel(writer, index=False, sheet_name='Detalhes')

st.download_button(
    label="📥 Baixar Relatório Completo",
    data=buf_geral.getvalue(),
    file_name=f"auditoria_milanov_{datetime.today().strftime('%Y%m%d_%H%M')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)
