import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Milanov - Processador de Comissões", layout="wide")

# Função para ler as regras do seu Excel fixo no GitHub
def carregar_regras(aba):
    try:
        df = pd.read_excel("regras_milanov.xlsx", sheet_name=aba)
        df.columns = [str(c).strip().upper() for c in df.columns]
        return df
    except: return None

if 'logado' not in st.session_state: st.session_state['logado'] = False

if not st.session_state['logado']:
    # --- TELA DE LOGIN ---
    st.title("Milanov Serviços Administrativos")
    u = st.text_input("Usuário").strip().upper()
    s = st.text_input("Senha", type="password").strip()
    if st.button("Entrar"):
        df_u = carregar_regras("Usuarios")
        if df_u is not None:
            user_data = df_u[(df_u['USUARIO'].astype(str) == u) & (df_u['SENHA'].astype(str) == s)]
            if not user_data.empty:
                st.session_state.update({"logado": True, "usuario": u, "depto": user_data.iloc[0]['DEPARTAMENTO']})
                st.rerun()
            else: st.error("Acesso negado.")
else:
    # --- ÁREA DO AUDITOR / AGENTE ---
    st.sidebar.title(f"💼 {st.session_state['usuario']}")
    if st.sidebar.button("Sair"):
        st.session_state['logado'] = False
        st.rerun()

    st.title("💰 Processamento de Comissões")
    
    # 1. Upload do arquivo da Corretora
    arquivo = st.file_uploader("Suba o Extrato da Corretora (Excel ou CSV)", type=['xlsx', 'csv'])
    
    if arquivo:
        df_extrato = pd.read_excel(arquivo) if arquivo.name.endswith('.xlsx') else pd.read_csv(arquivo)
        df_extrato.columns = [str(c).strip().upper() for c in df_extrato.columns]
        
        # 2. Carregar Regras de Comissão
        df_pacotes = carregar_regras("Tabela_Pacotes")
        
        st.subheader("📊 Relatório Processado")
        
        # --- LÓGICA DE FILTRO E REGRA ---
        # Aqui aplicamos a regra: Se for Agente comum, filtra só os dados dele
        if st.session_state['depto'] != "ADMIN":
            df_final = df_extrato[df_extrato['AGENTE'] == st.session_state['usuario']]
        else:
            df_final = df_extrato # Admin vê tudo
            
        # 3. Exibição dos Resultados
        st.write(f"Exibindo dados para: **{st.session_state['usuario']}**")
        st.dataframe(df_final, use_container_width=True)
        
        # Botão para baixar o resultado
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Relatório (CSV)", csv, "comissoes_milanov.csv", "text/csv")

    # Área de consulta das regras (opcional)
    with st.expander("🔍 Consultar Tabelas de Referência"):
        aba1, aba2 = st.tabs(["Pacotes", "Agentes"])
        aba1.dataframe(df_pacotes)
        aba2.dataframe(carregar_regras("Cadastro_Agentes"))
