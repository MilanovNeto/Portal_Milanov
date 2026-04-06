import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Milanov | Auditoria", layout="wide", page_icon="📊")

REGRAS_PATH = "regras_milanov.xlsx"

# ──────────────────────────────────────────────────────────────
# CSS GLOBAL — TEMA ESCURO CORPORATIVO
# ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.stApp { background-color: #F4F6FB; color: #1A1E2C; }

[data-testid="stSidebar"] {
    background-color: #141824 !important;
    border-right: 1px solid #E2E6F0 !important;
}
[data-testid="stSidebar"] * { color: #2C3252 !important; }

.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 1280px !important;
}

/* Cards de métricas */
.metric-card {
    background: linear-gradient(135deg, #181E2E 0%, #1C2235 100%);
    border: 1px solid #2D3454;
    border-radius: 12px;
    padding: 20px 24px;
    position: relative;
    overflow: hidden;
    height: 100%;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #4F6BFF, #7B8CFF);
}
.metric-card.gold::before  { background: linear-gradient(90deg, #C9960C, #F0C040); }
.metric-card.green::before { background: linear-gradient(90deg, #0C7A4F, #1DB87A); }
.metric-card.rose::before  { background: linear-gradient(90deg, #7A0C3A, #C4366A); }
.metric-label {
    font-size: 10px; font-weight: 600; letter-spacing: 0.12em;
    text-transform: uppercase; color: #8892B0; margin-bottom: 8px;
}
.metric-value {
    font-family: 'DM Mono', monospace;
    font-size: 26px; font-weight: 500; color: #1A1E2C; line-height: 1.1;
}
.metric-value.large { font-size: 28px; color: #2A6FDB; }
.metric-sub { font-size: 11px; color: #6B7A99; margin-top: 6px; font-family: 'DM Mono', monospace; }

/* Header */
.app-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 20px 0 20px 0; border-bottom: 1px solid #E2E6F0; margin-bottom: 28px;
}
.app-logo-name { font-size: 20px; font-weight: 600; color: #1A1E2C; letter-spacing: -0.02em; }
.app-logo-sub  { font-size: 11px; color: #6B7A99; letter-spacing: 0.08em; text-transform: uppercase; margin-top: 2px; }
.app-badge {
    background: #161A26; border: 1px solid #2D3454; border-radius: 20px;
    padding: 5px 14px; font-size: 11px; font-family: 'DM Mono', monospace;
    color: #3A5FD9; letter-spacing: 0.05em;
}

/* Seções */
.section-header {
    display: flex; align-items: center; gap: 10px;
    margin: 28px 0 14px 0; padding-bottom: 10px; border-bottom: 1px solid #E2E6F0;
}
.section-dot { width: 5px; height: 5px; border-radius: 50%; background: #3A5FD9; flex-shrink: 0; }
.section-title { font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: #3A5FD9; }

/* Sidebar */
.sidebar-logo { padding: 18px 0 14px 0; border-bottom: 1px solid #E2E6F0; margin-bottom: 12px; }
.sidebar-logo-name { font-size: 15px; font-weight: 600; color: #1A1E2C !important; }
.sidebar-logo-sub  { font-size: 10px; color: #5A6680 !important; text-transform: uppercase; letter-spacing: 0.1em; }
.sidebar-section   {
    font-size: 10px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
    color: #5A6680 !important; padding: 14px 0 6px 0;
}

/* Divider */
.divider { height: 1px; background: linear-gradient(90deg, transparent, #E2E6F0 20%, #E2E6F0 80%, transparent); margin: 24px 0; }

/* Botões */
.stButton > button, .stDownloadButton > button {
    background: linear-gradient(135deg, #2D3A8C, #4F6BFF) !important;
    color: white !important; border: none !important; border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important; font-weight: 500 !important;
    font-size: 13px !important; letter-spacing: 0.02em !important; transition: opacity 0.2s !important;
}
.stButton > button:hover, .stDownloadButton > button:hover { opacity: 0.82 !important; }
.stDownloadButton > button[kind="primary"] {
    background: linear-gradient(135deg, #0C5E38, #1DB87A) !important;
}

/* Inputs */
.stTextInput input, .stNumberInput input, .stSelectbox > div > div {
    background-color: #181E2E !important; border: 1px solid #2D3454 !important;
    border-radius: 8px !important; color: #1A1E2C !important;
}

/* Tabela */
[data-testid="stDataFrame"] { border-radius: 10px !important; border: 1px solid #2A3148 !important; overflow: hidden !important; }

/* Expander */
[data-testid="stExpander"] {
    background: #13161E !important; border: 1px solid #2A3148 !important; border-radius: 10px !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: #111827 !important; border: 1.5px dashed #2A2F42 !important; border-radius: 10px !important;
}

/* Rodapé */
.footer {
    margin-top: 56px; padding: 20px 0 14px 0; border-top: 1px solid #E2E6F0;
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;
}
.footer-brand { font-size: 12px; font-weight: 600; color: #5A6680; letter-spacing: 0.06em; }
.footer-copy  { font-size: 11px; color: #445060; font-family: 'DM Mono', monospace; }
</style>
""", unsafe_allow_html=True)


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

def card(label, value, variant="default", sub=None):
    val_class = "metric-value large" if variant == "gold" else "metric-value"
    sub_html  = f'<div class="metric-sub">{sub}</div>' if sub else ""
    return f"""<div class="metric-card {variant}">
        <div class="metric-label">{label}</div>
        <div class="{val_class}">{value}</div>{sub_html}
    </div>"""

def section(titulo):
    return f"""<div class="section-header">
        <div class="section-dot"></div>
        <div class="section-title">{titulo}</div>
    </div>"""

def footer():
    ano = datetime.today().year
    return f"""<div class="footer">
        <div class="footer-brand">MILANOV SERVIÇOS LTDA</div>
        <div class="footer-copy">© {ano} &nbsp;·&nbsp; Portal de Auditoria de Comissões &nbsp;·&nbsp; Uso interno</div>
    </div>"""


# ──────────────────────────────────────────────────────────────
# CARREGAMENTO DE REGRAS
# ──────────────────────────────────────────────────────────────
@st.cache_data
def carregar_regras():
    if not os.path.exists(REGRAS_PATH):
        return None, None
    try:
        df_u = norm_cols(pd.read_excel(REGRAS_PATH, sheet_name="Usuarios"))
        df_c = norm_cols(pd.read_excel(REGRAS_PATH, sheet_name="Cadastro_Agentes"))
        return df_u, df_c
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
    _, col, _ = st.columns([1, 0.9, 1])
    with col:
        st.markdown("""
        <div style="text-align:center; padding:48px 0 32px 0;">
            <div style="font-size:38px; font-weight:700; color:#1A1E2C; letter-spacing:-0.03em;">Milanov</div>
            <div style="font-size:11px; color:#9BA3BF; letter-spacing:0.14em; text-transform:uppercase; margin-top:5px;">
                Portal de Auditoria &nbsp;·&nbsp; Acesso Restrito
            </div>
        </div>
        <div style="background:#141824; border:1px solid #1F2433; border-radius:14px; padding:32px 28px 28px 28px;">
        """, unsafe_allow_html=True)

        if df_usuarios is None:
            st.error(f"Arquivo '{REGRAS_PATH}' não encontrado.")
            st.stop()

        usuario = st.text_input("Usuário", placeholder="seu.usuario")
        senha   = st.text_input("Senha", type="password", placeholder="••••••")

        if st.button("Entrar", use_container_width=True, type="primary"):
            match = df_usuarios[df_usuarios["USUARIO"].apply(limpar) == limpar(usuario)]
            if not match.empty and str(senha).strip() == str(match.iloc[0]["SENHA"]).strip():
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

        st.markdown("""</div>
        <div style="text-align:center; margin-top:28px; font-size:11px; color:#B0BAD0; font-family:'DM Mono',monospace;">
            MILANOV SERVIÇOS LTDA &nbsp;·&nbsp; Uso interno
        </div>""", unsafe_allow_html=True)
    st.stop()


# ──────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""<div class="sidebar-logo">
        <div class="sidebar-logo-name">Milanov</div>
        <div class="sidebar-logo-sub">Auditoria de Comissões</div>
    </div>
    <div class="sidebar-section">Câmbio</div>""", unsafe_allow_html=True)

    v_usd_brl = st.number_input("USD → BRL (Haiti)", value=5.48, format="%.4f",
                                 help="Multiplica a comissão fixa de USD 2,50 para BRL")
    v_htg_usd = st.number_input("HTG / USD", value=130.0, format="%.2f",
                                 help="Converte VALOR_DESTINO em HTG para USD")

    st.markdown('<div class="sidebar-section">Período</div>', unsafe_allow_html=True)
    periodo_ph = st.empty()

    st.markdown('<div class="sidebar-section">Filtro</div>', unsafe_allow_html=True)
    comercial_ph = st.empty()


# ──────────────────────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────────────────────
st.markdown("""<div class="app-header">
    <div>
        <div class="app-logo-name">Auditoria de Comissões</div>
        <div class="app-logo-sub">Milanov Serviços Ltda &nbsp;·&nbsp; Portal Interno</div>
    </div>
    <div class="app-badge">v9.1</div>
</div>""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# UPLOAD
# ──────────────────────────────────────────────────────────────
st.markdown(section("Relatório da Corretora"), unsafe_allow_html=True)
arq = st.file_uploader("Arquivo .xlsx", type=["xlsx"], label_visibility="collapsed")

if not arq:
    st.markdown("""<div style="background:#0D1424; border:1.5px dashed #1F2433; border-radius:12px;
                padding:44px; text-align:center; margin-top:4px;">
        <div style="font-size:32px; margin-bottom:12px; opacity:0.3;">📂</div>
        <div style="font-size:13px; color:#9BA3BF;">Faça upload do relatório exportado da corretora para iniciar</div>
    </div>""", unsafe_allow_html=True)
    st.markdown(footer(), unsafe_allow_html=True)
    st.stop()

if df_cadastro is None:
    st.error(f"Planilha '{REGRAS_PATH}' não encontrada.")
    st.stop()

df_raw = norm_cols(pd.read_excel(arq))


# ──────────────────────────────────────────────────────────────
# FILTRO DE DATA
# ──────────────────────────────────────────────────────────────
if "DATA" in df_raw.columns:
    df_raw["DATA"] = pd.to_datetime(df_raw["DATA"], errors="coerce")
    d_min, d_max   = df_raw["DATA"].min().date(), df_raw["DATA"].max().date()
    with periodo_ph:
        periodo = st.date_input("Período", [d_min, d_max], label_visibility="collapsed")
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

if "NOME_CONSOLIDADO" not in df.columns:
    df["NOME_CONSOLIDADO"] = df["REALIZADO_POR"]
else:
    df["NOME_CONSOLIDADO"] = df["NOME_CONSOLIDADO"].fillna(df["REALIZADO_POR"])

df["ID_PACOTE_COMISSAO"] = df["ID_PACOTE_COMISSAO"].fillna(20).astype(int).astype(str)


# ──────────────────────────────────────────────────────────────
# FILTRO DE COMERCIAL
# ──────────────────────────────────────────────────────────────
sel_com = "TODOS"
if "COMERCIAL" in df.columns:
    lista_com = ["TODOS"] + sorted(df["COMERCIAL"].dropna().unique().tolist())
    with comercial_ph:
        sel_com = st.selectbox("Comercial", lista_com, label_visibility="collapsed")
    if sel_com != "TODOS":
        df = df[df["COMERCIAL"] == sel_com]


# ──────────────────────────────────────────────────────────────
# ORDENAÇÃO E CONTAGEM
# ──────────────────────────────────────────────────────────────
df = df.sort_values(["NOME_CONSOLIDADO", "DATA"]).reset_index(drop=True)
df["ORDEM"] = df.groupby("NOME_CONSOLIDADO").cumcount() + 1


# ──────────────────────────────────────────────────────────────
# MOTOR DE CÁLCULO
# Hierarquia:
#   1. Pacote 40  → 60% fixo (qualquer país)
#   2. Haiti/HTG  → R$2,50×câmbio (≤100 USD) | 50%/60% (>100 USD)
#   3. Outros     → 30% (≤50 ops) / 50% (≤100) / 60% (>100)
# ──────────────────────────────────────────────────────────────
def calcular_comissao(row):
    custo  = float(row.get("COSTO_DE_ENVIO_BRL", 0) or 0)
    v_dest = float(row.get("VALOR_DESTINO", 0)       or 0)
    moeda  = limpar(row.get("MOEDA_DESTINO", ""))
    pais   = limpar(row.get("PAIS_DESTINO", ""))
    pacote = str(row.get("ID_PACOTE_COMISSAO", "20")).strip()
    ordem  = int(row.get("ORDEM", 1))

    if pacote == "40":
        return custo * 0.60

    is_haiti = (pais == "HAITI" or moeda == "HTG")
    if is_haiti:
        v_usd = v_dest / v_htg_usd if moeda == "HTG" else v_dest
        if v_usd <= 100:
            return 2.50 * v_usd_brl
        return custo * 0.50 if ordem <= 100 else custo * 0.60

    if ordem <= 50:
        return custo * 0.30
    elif ordem <= 100:
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
    .agg(TOTAL_OPS=("ORDEM", "max"), TOTAL_COMISSAO=("VALOR_COMISSAO", "sum"))
    .reset_index()
)


# ──────────────────────────────────────────────────────────────
# CARDS DE MÉTRICAS
# ──────────────────────────────────────────────────────────────
st.markdown(section("Visão Geral"), unsafe_allow_html=True)

periodo_str = "—"
if "DATA" in df.columns and df["DATA"].notna().any():
    periodo_str = f"{df['DATA'].min().strftime('%d/%m/%y')} → {df['DATA'].max().strftime('%d/%m/%y')}"

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(card("Total Comissões", fmt_brl(resumo["TOTAL_COMISSAO"].sum()), "gold",
                     sub=f"Filtro: {sel_com}"), unsafe_allow_html=True)
with c2:
    st.markdown(card("Agentes Ativos", str(resumo["NOME_CONSOLIDADO"].nunique()), "default",
                     sub="logins consolidados"), unsafe_allow_html=True)
with c3:
    st.markdown(card("Operações", f"{len(df):,}".replace(",", "."), "green",
                     sub=periodo_str), unsafe_allow_html=True)
with c4:
    media = resumo["TOTAL_COMISSAO"].mean() if len(resumo) else 0
    st.markdown(card("Ticket Médio / Agente", fmt_brl(media), "rose",
                     sub="comissão média"), unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# TABELA RESUMO
# ──────────────────────────────────────────────────────────────
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown(section(f"Resumo por Agente — {sel_com}"), unsafe_allow_html=True)

st.dataframe(
    resumo.sort_values("TOTAL_COMISSAO", ascending=False)
          .style.format({"TOTAL_COMISSAO": "R$ {:.2f}", "TOTAL_OPS": "{:.0f}"}),
    use_container_width=True,
    height=440,
)


# ──────────────────────────────────────────────────────────────
# DRILL-DOWN POR AGENTE
# ──────────────────────────────────────────────────────────────
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown(section("Drill-down por Agente"), unsafe_allow_html=True)

with st.expander("🔍 Selecionar agente para investigar", expanded=False):
    agentes = ["Selecione..."] + sorted(resumo["NOME_CONSOLIDADO"].unique().tolist())
    sel_ag  = st.selectbox("Agente:", agentes, label_visibility="collapsed")

    if sel_ag != "Selecione...":
        df_ag        = df[df["NOME_CONSOLIDADO"] == sel_ag].copy()
        total_com    = df_ag["VALOR_COMISSAO"].sum()
        pacote_ag    = df_ag["ID_PACOTE_COMISSAO"].mode()[0] if len(df_ag) else "—"
        comercial_ag = df_ag["COMERCIAL"].iloc[0] if "COMERCIAL" in df_ag.columns else "—"

        st.markdown(f"""
        <div style="display:flex; gap:14px; margin:14px 0 20px 0; flex-wrap:wrap;">
            <div style="flex:1;min-width:150px;background:#181E2E;border:1px solid #242840;border-radius:10px;padding:16px 20px;">
                <div style="font-size:10px;color:#9BA3BF;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Comissão Total</div>
                <div style="font-family:'DM Mono',monospace;font-size:22px;color:#2A6FDB;">{fmt_brl(total_com)}</div>
            </div>
            <div style="flex:1;min-width:110px;background:#181E2E;border:1px solid #242840;border-radius:10px;padding:16px 20px;">
                <div style="font-size:10px;color:#9BA3BF;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Operações</div>
                <div style="font-family:'DM Mono',monospace;font-size:22px;color:#1A1E2C;">{len(df_ag)}</div>
            </div>
            <div style="flex:1;min-width:110px;background:#181E2E;border:1px solid #242840;border-radius:10px;padding:16px 20px;">
                <div style="font-size:10px;color:#9BA3BF;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Pacote</div>
                <div style="font-family:'DM Mono',monospace;font-size:22px;color:#5B6FD9;">{pacote_ag}</div>
            </div>
            <div style="flex:1;min-width:110px;background:#181E2E;border:1px solid #242840;border-radius:10px;padding:16px 20px;">
                <div style="font-size:10px;color:#9BA3BF;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Comercial</div>
                <div style="font-family:'DM Mono',monospace;font-size:22px;color:#0E9E65;">{comercial_ag}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

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

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_ag[cols_det].to_excel(writer, index=False, sheet_name="Detalhe")
            resumo[resumo["NOME_CONSOLIDADO"] == sel_ag].to_excel(writer, index=False, sheet_name="Resumo")

        st.download_button(
            label=f"📥 Exportar Excel — {sel_ag}",
            data=buf.getvalue(),
            file_name=f"comissao_{sel_ag}_{datetime.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ──────────────────────────────────────────────────────────────
# EXPORTAÇÃO GERAL
# ──────────────────────────────────────────────────────────────
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown(section("Exportar Relatório Completo"), unsafe_allow_html=True)

col_btn, col_info = st.columns([1, 2])
with col_btn:
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
        use_container_width=True,
    )
with col_info:
    st.markdown(f"""
    <div style="padding:12px 0; font-size:12px; color:#9BA3BF; font-family:'DM Mono',monospace; line-height:2;">
        {resumo['NOME_CONSOLIDADO'].nunique()} agentes &nbsp;·&nbsp;
        {len(df)} operações &nbsp;·&nbsp;
        gerado em {datetime.today().strftime('%d/%m/%Y %H:%M')}
    </div>""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# RODAPÉ
# ──────────────────────────────────────────────────────────────
st.markdown(footer(), unsafe_allow_html=True)
