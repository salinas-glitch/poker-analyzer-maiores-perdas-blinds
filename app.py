"""
=============================================================================
  POKER LEAK DETECTOR — WEB APP PROFISSIONAL
  Interface Web moderna em Streamlit para processamento e download de relatórios.
  Execução local: streamlit run app.py
=============================================================================
"""

import sys
import io
import tempfile
from pathlib import Path
import pandas as pd
import streamlit as st

# Importa o motor modular de cálculo e análise
from poker_engine import run_poker_leak_engine

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Poker Leak Detector | MTT Data Science",
    page_icon="♠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# CUSTOM CSS / ESTILIZAÇÃO PREMIUM
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Estilo geral */
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #F8F9FA;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #94A3B8;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #1E293B;
        border-radius: 10px;
        padding: 16px 20px;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .metric-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #F8F9FA;
        margin-top: 4px;
    }
    .metric-bad {
        color: #EF4444 !important;
    }
    .metric-accent {
        color: #38BDF8 !important;
    }
    .stDownloadButton > button {
        width: 100%;
        background-color: #059669 !important;
        color: white !important;
        font-weight: 600 !important;
        padding: 0.6rem 1rem !important;
        border-radius: 8px !important;
        border: none !important;
        transition: all 0.2s ease;
    }
    .stDownloadButton > button:hover {
        background-color: #10B981 !important;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3) !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1511193311914-0346f16efe90?auto=format&fit=crop&w=400&q=80", use_container_width=True)
    st.markdown("### ♠️ Poker Leak Engine")
    st.markdown("Automatize a auditoria estatística de perdas **> 20BB** em torneios e cash games.")
    
    st.markdown("---")
    st.markdown("#### 📁 Como Usar:")
    st.markdown("""
    1. Faça o upload dos relatórios em `.csv` (PT4, Hand2Note, CoinPoker, etc.).
    2. *(Opcional)* Suba os logs de histórico em `.txt` para re-parse de showdown e vilão.
    3. Clique em **'Processar Dados'**.
    4. Explore a tabela consolidada e baixe o **Dashboard Excel (.xlsx)** completo.
    """)
    
    st.markdown("---")
    st.caption("Poker Leak Detector v2.5 • Antigravity AI Engine")

# ---------------------------------------------------------------------------
# CABEÇALHO PRINCIPAL
# ---------------------------------------------------------------------------
st.markdown('<div class="main-header">♠️ ♥️ Poker Leak Detector — Pipeline Web ♦️ ♣️</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Diagnóstico Automatizado de Leaks, Análise Estrutural de Erros e Curadoria de EV</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# UPLOAD DE ARQUIVOS
# ---------------------------------------------------------------------------
st.markdown("#### 📥 1. Ingestão de Dados")
col_upload1, col_upload2 = st.columns([2, 1])

with col_upload1:
    uploaded_csvs = st.file_uploader(
        "Selecione um ou mais arquivos de relatório (.csv):",
        type=["csv"],
        accept_multiple_files=True,
        help="Suporta relatórios exportados do PokerTracker 4, Hand2Note, CoinPoker ou CSVs detalhados."
    )

with col_upload2:
    uploaded_txts = st.file_uploader(
        "(Opcional) Logs brutos de histórico (.txt):",
        type=["txt"],
        accept_multiple_files=True,
        help="Suba os arquivos de histórico brutos para habilitar o re-parse completo do vilão e showdown."
    )

# Estado da sessão para manter resultados entre interações
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

process_clicked = st.button("🚀 Processar Dados", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# PROCESSAMENTO DOS DADOS
# ---------------------------------------------------------------------------
if process_clicked:
    if not uploaded_csvs:
        st.warning("⚠️ Por favor, faça o upload de pelo menos um arquivo `.csv` para continuar.")
    else:
        with st.spinner("⚙️ Processando arquivos, recalculando SPR, avaliando flop e gerando dashboard..."):
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                csv_disk_paths = []
                txt_disk_paths = []

                # Salva os CSVs temporariamente
                for uf in uploaded_csvs:
                    dst = temp_path / uf.name
                    dst.write_bytes(uf.getvalue())
                    csv_disk_paths.append(dst)

                # Salva os TXTs temporariamente se fornecidos
                if uploaded_txts:
                    for uf in uploaded_txts:
                        dst = temp_path / uf.name
                        dst.write_bytes(uf.getvalue())
                        txt_disk_paths.append(dst)

                # Também inclui a pasta do projeto local como fallback de logs se houver
                local_base = Path(__file__).resolve().parent
                log_dirs = [temp_path, local_base, local_base / "Input", local_base / "Processed"]

                # Executa o motor modular
                result = run_poker_leak_engine(
                    csv_paths=csv_disk_paths,
                    log_dirs=log_dirs,
                    output_xlsx_path=None  # gera diretamente em memória
                )

                st.session_state.analysis_result = result

# ---------------------------------------------------------------------------
# EXIBIÇÃO DE RESULTADOS E PREVIEW
# ---------------------------------------------------------------------------
result = st.session_state.analysis_result

if result:
    if not result.get("success"):
        st.error(f"❌ Erro no processamento: {result.get('error')}")
    else:
        st.success("✅ Processamento concluído com sucesso!")
        enriched_data = result.get("enriched_data", [])
        df = pd.DataFrame(enriched_data)

        # ── CARDS DE MÉTRICAS EXECUTIVAS ─────────────────────────────────────
        st.markdown("#### 📊 2. Resumo Executivo das Perdas (>20BB)")
        m1, m2, m3, m4 = st.columns(4)

        with m1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Total de Mãos Analisadas</div>
                <div class="metric-value">{result['total_hands']}</div>
            </div>
            """, unsafe_allow_html=True)

        with m2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Prejuízo Total Acumulado</div>
                <div class="metric-value metric-bad">{result['total_loss_bb']:,.2f} BB</div>
            </div>
            """, unsafe_allow_html=True)

        with m3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Perda Média por Mão</div>
                <div class="metric-value metric-bad">{result['avg_loss_bb']:,.2f} BB</div>
            </div>
            """, unsafe_allow_html=True)

        with m4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Pior Mão Registrada</div>
                <div class="metric-value metric-bad">{result['worst_hand_bb']:,.2f} BB</div>
            </div>
            """, unsafe_allow_html=True)

        # ── DESTAQUE ESTRUTURAL — PREMIUM OFFSUIT ──────────────────────────────
        po = result.get("premium_offsuit", {})
        if po and po.get("total_hands", 0) > 0:
            tot_po = po["total_hands"]
            agg_po = po["aggressor_hands"]
            cal_po = po["caller_hands"]
            loss_po = po["loss_bb"]
            pct_agg = (agg_po / tot_po) * 100 if tot_po else 0

            st.markdown(f"""
            > 💡 **Insight Chave de Vazamento (Leak):** Em mãos **Premium Offsuit** ({tot_po} ocorrências, total de **{loss_po:,.2f} BB** perdidos), 
            > **{agg_po} mãos ({pct_agg:.1f}%)** ocorreram quando você foi o **AGRESSOR PRÉ-FLOP**, demonstrando que o maior dreno vem de overplay/falta de escape OOP, e não de passividade como caller.
            """)

        # ── DOWNLOAD DO ARQUIVO CONSOLIDADO ──────────────────────────────────
        st.markdown("#### 📥 3. Download do Dashboard Consolidado")
        excel_data = result.get("excel_bytes")
        if excel_data:
            st.download_button(
                label="📥 Baixar Dashboard_Leaks_Poker.xlsx (6 Abas Completas)",
                data=excel_data,
                file_name="Dashboard_Leaks_Poker.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        # ── PREVIEW INTERATIVO DA TABELA ─────────────────────────────────────
        st.markdown("#### 🔍 4. Pré-visualização da Tabela Consolidada")

        # Filtros interativos
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            all_pos = ["Todas"] + sorted(list(df["position"].dropna().unique()))
            sel_pos = st.selectbox("Filtrar por Posição:", all_pos)
        with col_f2:
            all_agg = ["Todos"] + sorted(list(df["pf_aggressor"].dropna().unique()))
            sel_agg = st.selectbox("Filtrar por Agressor PF:", all_agg)
        with col_f3:
            all_cats = ["Todas"] + sorted(list(df["hand_cat"].dropna().unique()))
            sel_cat = st.selectbox("Filtrar por Categoria da Mão:", all_cats)

        # Aplica filtros
        filtered_df = df.copy()
        if sel_pos != "Todas":
            filtered_df = filtered_df[filtered_df["position"] == sel_pos]
        if sel_agg != "Todos":
            filtered_df = filtered_df[filtered_df["pf_aggressor"] == sel_agg]
        if sel_cat != "Todas":
            filtered_df = filtered_df[filtered_df["hand_cat"] == sel_cat]

        # Colunas prioritárias para preview limpo
        cols_to_show = [
            "hand_id", "platform", "position", "ip_oop", "hero_cards", "hand_cat",
            "pf_aggressor", "stack_bb", "spr", "flop_cards", "flop_strength",
            "fd_flag", "went_allin", "ai_street", "net_bb", "hero_final", "winner_hand"
        ]
        cols_available = [c for c in cols_to_show if c in filtered_df.columns]

        st.dataframe(
            filtered_df[cols_available],
            use_container_width=True,
            height=400,
            column_config={
                "hand_id": st.column_config.TextColumn("Hand ID"),
                "platform": st.column_config.TextColumn("Site"),
                "position": st.column_config.TextColumn("Posição"),
                "ip_oop": st.column_config.TextColumn("IP/OOP"),
                "hero_cards": st.column_config.TextColumn("Hole Cards"),
                "hand_cat": st.column_config.TextColumn("Categoria"),
                "pf_aggressor": st.column_config.TextColumn("Agressor?"),
                "stack_bb": st.column_config.NumberColumn("Stack BB", format="%.1f"),
                "spr": st.column_config.NumberColumn("SPR", format="%.3f"),
                "flop_cards": st.column_config.TextColumn("Flop"),
                "flop_strength": st.column_config.TextColumn("Força Flop"),
                "fd_flag": st.column_config.TextColumn("FD?"),
                "went_allin": st.column_config.TextColumn("All-In?"),
                "ai_street": st.column_config.TextColumn("Rua AI"),
                "net_bb": st.column_config.NumberColumn("Net BB", format="%.2f"),
                "hero_final": st.column_config.TextColumn("Mão Final Hero"),
                "winner_hand": st.column_config.TextColumn("Mão Vencedora"),
            }
        )
        st.caption(f"Mostrando {len(filtered_df)} de {len(df)} mãos filtradas.")

        # ── TABS ADICIONAIS COM GRÁFICOS E RESUMOS ───────────────────────────
        t1, t2, t3 = st.tabs(["📊 Distribuição por Posição", "🛣 Perdas por Rua do All-In", "🃏 Piores Confrontos"])

        with t1:
            pos_grp = df.groupby("position")["net_bb"].sum().sort_values()
            st.bar_chart(pos_grp)

        with t2:
            street_grp = df.groupby("ai_street")["net_bb"].sum().sort_values()
            st.bar_chart(street_grp)

        with t3:
            conf_counts = df["confronto"].value_counts().head(8)
            st.write("Top 8 Confrontos mais Frequentes:")
            st.table(conf_counts.reset_index().rename(columns={"index": "Confronto (Hero × Vilão)", "confronto": "Mãos", "count": "Nº Mãos"}))
