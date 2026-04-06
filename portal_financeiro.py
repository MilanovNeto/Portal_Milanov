import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Portal Milanov v9", layout="wide", page_icon="💸")

REGRAS_PATH = "regras_milanov.xlsx"

# ──────────────────────────────────────────────────────────────
# FUNÇÕES UTILITÁRIAS
# ──────────────────────────────────────────────────────────────
def limpar(txt):
    return str(txt).strip().upper()

def norm_cols(df):
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df

def fmt_brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ──────────────────────────────────────────────────────────────
# CARREGAMENTO DE REGRAS (cache)
# ──────────────────────────────────────────────────────────────
@st.cache_data
def carregar_regras():
    if not os.path.exists(REGRAS_PATH):
        return None, None, None
    try:
        df_usuarios  = norm_cols(pd.read_excel(REGRAS_PATH, sheet_name="Usuarios"))
        df_cadastro  = norm_cols(pd.read_excel(REGRAS_PATH, sheet_name="Cadastro_Agentes"))
        return df_usuarios, df_cadastro
    except Exception as e:
        st.error(f"Erro ao carregar regras: {e}")
        return None, None

df_usuarios, df_cadastro = carregar_regras()

# ──────────────────────────────────────────────────────────────
# LOGIN
# ──────────────────────────────────────────────────────────────
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    _, col, _ = st.columns([1, 1.1, 1])
    with col:
        st.markdown("## 🔐 Portal Milanov")
        if df_usuarios is None:
            st.error(f"Arquivo '{REGRAS_PATH}' não encontrado.")
            st.stop()
        usuario = st.text_input("Usuário")
        senha   = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True, type="primary"):
            match = df_usuarios[df_usuarios["USUARIO"].apply(limpar) == limpar(usuario)]
            if not match.empty and str(senha).strip() == str(match.iloc[0]["SENHA"]).strip():
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
    st.stop()

# ──────────────────────────────────────────────────────────────
# PAINEL PRINCIPAL
# ──────────────────────────────────────────────────────────────
st.title("💸 Portal Milanov — Auditoria de Comissões")

arq = st.file_uploader("📁 Carregar Relatório da Corretora (.xlsx)", type=["xlsx"])
if not arq:
    st.info("Faça upload do relatório para iniciar a auditoria.")
    st.stop()

if df_cadastro is None:
    st.error(f"Planilha '{REGRAS_PATH}' não encontrada.")
    st.stop()

df_raw = norm_cols(pd.read_excel(arq))

# ──────────────────────────────────────────────────────────────
# SIDEBAR — PARÂMETROS
# ──────────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Parâmetros")
v_usd_brl = st.sidebar.number_input("Câmbio USD → BRL (Haiti)", value=5.48, format="%.4f",
                                     help="Usado para converter comissão fixa de USD 2,50 para BRL")
v_htg_usd = st.sidebar.number_input("Cotação HTG / USD", value=130.0, format="%.2f",
                                     help="Usado para converter VALOR_DESTINO em HTG para USD")

# Filtro de período
if "DATA" in df_raw.columns:
    df_raw["DATA"] = pd.to_datetime(df_raw["DATA"], errors="coerce")
    d_min = df_raw["DATA"].min().date()
    d_max = df_raw["DATA"].max().date()
    periodo = st.sidebar.date_input("📅 Período:", [d_min, d_max])
    if len(periodo) == 2:
        df_raw = df_raw[
            (df_raw["DATA"].dt.date >= periodo[0]) &
            (df_raw["DATA"].dt.date <= periodo[1])
        ]

# ──────────────────────────────────────────────────────────────
# CRUZAMENTO COM CADASTRO
# ──────────────────────────────────────────────────────────────
df_raw["REALIZADO_POR"]      = df_raw["REALIZADO_POR"].apply(limpar)
df_cadastro["REALIZADO_POR"] = df_cadastro["REALIZADO_POR"].apply(limpar)

df = pd.merge(df_raw, df_cadastro, on="REALIZADO_POR", how="left")

# Nome consolidado: alias do cadastro ou código bruto
if "NOME_CONSOLIDADO" not in df.columns:
    df["NOME_CONSOLIDADO"] = df["REALIZADO_POR"]
else:
    df["NOME_CONSOLIDADO"] = df["NOME_CONSOLIDADO"].fillna(df["REALIZADO_POR"])

# Pacote: garante string limpa, default "20"
df["ID_PACOTE_COMISSAO"] = df["ID_PACOTE_COMISSAO"].fillna(20).astype(int).astype(str)

# ──────────────────────────────────────────────────────────────
# FILTRO DE COMERCIAL
# ──────────────────────────────────────────────────────────────
sel_com = "TODOS"
if "COMERCIAL" in df.columns:
    lista_com = ["TODOS"] + sorted(df["COMERCIAL"].dropna().unique().tolist())
    sel_com   = st.sidebar.selectbox("👤 Filtrar Comercial:", lista_com)
    if sel_com != "TODOS":
        df = df[df["COMERCIAL"] == sel_com]

# ──────────────────────────────────────────────────────────────
# ORDENAÇÃO E CONTAGEM DE OPERAÇÕES POR NOME_CONSOLIDADO
# (a contagem é por NOME_CONSOLIDADO para agentes com múltiplos logins)
# ──────────────────────────────────────────────────────────────
df = df.sort_values(["NOME_CONSOLIDADO", "DATA"]).reset_index(drop=True)
df["ORDEM"] = df.groupby("NOME_CONSOLIDADO").cumcount() + 1

# ──────────────────────────────────────────────────────────────
# MOTOR DE CÁLCULO
#
# HIERARQUIA:
#   1. Pacote 40 → 60% fixo sobre COSTO_DE_ENVIO_BRL (qualquer país)
#   2. Haiti / HTG:
#        ≤ 100 USD → USD 2,50 × câmbio BRL
#        > 100 USD → escalonamento (ORDEM ≤ 100 → 50% | > 100 → 60%)
#   3. Qualquer outro país → escalonamento (ORDEM ≤ 100 → 50% | > 100 → 60%)
# ──────────────────────────────────────────────────────────────
def calcular_comissao(row):
    custo  = float(row.get("COSTO_DE_ENVIO_BRL", 0) or 0)
    v_dest = float(row.get("VALOR_DESTINO", 0)       or 0)
    moeda  = limpar(row.get("MOEDA_DESTINO", ""))
    pais   = limpar(row.get("PAIS_DESTINO", ""))
    pacote = str(row.get("ID_PACOTE_COMISSAO", "20")).strip()
    ordem  = int(row.get("ORDEM", 1))

    # ── 1. PACOTE 40: sempre 60% ──────────────────────────────
    if pacote == "40":
        return custo * 0.60

    # ── 2. HAITI / HTG ───────────────────────────────────────
    is_haiti = (pais == "HAITI" or moeda == "HTG")
    if is_haiti:
        # Converte para USD
        if moeda == "HTG":
            v_usd = v_dest / v_htg_usd if v_htg_usd > 0 else 0
        else:
            # Moeda já é USD (destino Haiti com moeda USD)
            v_usd = v_dest

        if v_usd <= 100:
            return 2.50 * v_usd_brl          # comissão fixa: USD 2,50 em BRL

        # Acima de 100 USD → escalonamento (cai no bloco abaixo)

    # ── 3. ESCALONAMENTO (pacote 20 ou Haiti > 100 USD) ──────
    if ordem <= 100:
        return custo * 0.50
    else:
        return custo * 0.60

df["VALOR_COMISSAO"] = df.apply(calcular_comissao, axis=1)

# ──────────────────────────────────────────────────────────────
# RESUMO CONSOLIDADO
# ──────────────────────────────────────────────────────────────
group_cols = ["COMERCIAL", "NOME_CONSOLIDADO"] if "COMERCIAL" in df.columns else ["NOME_CONSOLIDADO"]

resumo = (
    df.groupby(group_cols)
    .agg(
        TOTAL_OPS    =("ORDEM", "max"),
        TOTAL_COMISSAO=("VALOR_COMISSAO", "sum"),
    )
    .reset_index()
)

# ──────────────────────────────────────────────────────────────
# EXIBIÇÃO — MÉTRICAS RÁPIDAS
# ──────────────────────────────────────────────────────────────
st.subheader(f"📋 Resumo de Comissões — {sel_com}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Agentes",          resumo["NOME_CONSOLIDADO"].nunique())
c2.metric("Operações",        f"{len(df):,}".replace(",", "."))
c3.metric("Total Comissões",  fmt_brl(resumo["TOTAL_COMISSAO"].sum()))
c4.metric("Período",          f"{df['DATA'].min().strftime('%d/%m/%y')} → {df['DATA'].max().strftime('%d/%m/%y')}"
                               if "DATA" in df.columns else "—")

st.markdown("---")

# Tabela resumo
fmt = {"TOTAL_COMISSAO": "R$ {:.2f}", "TOTAL_OPS": "{:.0f}"}
st.dataframe(
    resumo.sort_values(group_cols)
          .style.format(fmt),
    use_container_width=True,
    height=420,
)

# ──────────────────────────────────────────────────────────────
# INVESTIGAÇÃO POR AGENTE
# ──────────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("🔍 Investigar Agente em Detalhe"):
    agentes = ["Selecione..."] + sorted(resumo["NOME_CONSOLIDADO"].unique().tolist())
    sel_ag  = st.selectbox("Agente:", agentes)

    if sel_ag != "Selecione...":
        df_ag = df[df["NOME_CONSOLIDADO"] == sel_ag].copy()

        total_com = df_ag["VALOR_COMISSAO"].sum()
        pacote_ag = df_ag["ID_PACOTE_COMISSAO"].mode()[0] if len(df_ag) else "—"

        ca, cb, cc = st.columns(3)
        ca.metric("Total Comissão",  fmt_brl(total_com))
        cb.metric("Total Operações", len(df_ag))
        cc.metric("Pacote",          pacote_ag)

        # Colunas relevantes para exibir
        cols_det = [c for c in [
            "ORDEM", "DATA", "REALIZADO_POR", "PAIS_DESTINO",
            "MOEDA_DESTINO", "VALOR_DESTINO", "COSTO_DE_ENVIO_BRL",
            "ID_PACOTE_COMISSAO", "VALOR_COMISSAO"
        ] if c in df_ag.columns]

        st.dataframe(
            df_ag[cols_det].style.format({
                "VALOR_COMISSAO":     "R$ {:.2f}",
                "COSTO_DE_ENVIO_BRL": "R$ {:.2f}",
                "VALOR_DESTINO":      "{:,.2f}",
            }),
            use_container_width=True,
        )

        # Download individual
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_ag[cols_det].to_excel(writer, index=False, sheet_name="Detalhe")
            resumo[resumo["NOME_CONSOLIDADO"] == sel_ag].to_excel(writer, index=False, sheet_name="Resumo")
        st.download_button(
            label=f"📥 Baixar Excel — {sel_ag}",
            data=buf.getvalue(),
            file_name=f"comissao_{sel_ag}_{datetime.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# ──────────────────────────────────────────────────────────────
# EXPORTAÇÃO GERAL
# ──────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("📤 Exportar Relatório Completo")

buf_geral = io.BytesIO()
with pd.ExcelWriter(buf_geral, engine="openpyxl") as writer:
    resumo.to_excel(writer, index=False, sheet_name="Resumo")
    df.to_excel(writer, index=False, sheet_name="Detalhes")

st.download_button(
    label="📥 Baixar Relatório Completo",
    data=buf_geral.getvalue(),
    file_name=f"auditoria_milanov_{datetime.today().strftime('%Y%m%d_%H%M')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)
