"""
=============================================================================
  PIPELINE AUTOMATIZADO DE POKER — INGESTÃO E ORQUESTRAÇÃO
  Execução: python pipeline_poker.py
=============================================================================
  Fluxo de trabalho:
    1. Varre arquivos .csv na pasta /Input.
    2. Invoca o motor de cálculo (poker_engine.py).
    3. Gera o arquivo consolidado Dashboard_Leaks_Poker.xlsx em /Output.
    4. Move os arquivos processados de /Input para /Processed com versionamento.
=============================================================================
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import shutil
from datetime import datetime
from pathlib import Path

# Importa o motor modular de cálculo
from poker_engine import run_poker_leak_engine

# ---------------------------------------------------------------------------
# DEFINIÇÃO DE DIRETÓRIOS DO PIPELINE
# ---------------------------------------------------------------------------
BASE_DIR      = Path(__file__).resolve().parent
INPUT_DIR     = BASE_DIR / "Input"
PROCESSED_DIR = BASE_DIR / "Processed"
OUTPUT_DIR    = BASE_DIR / "Output"

OUTPUT_XLSX   = OUTPUT_DIR / "Dashboard_Leaks_Poker.xlsx"

SEP_LINE = "═" * 70

def setup_directories():
    """Garante que a estrutura de diretórios do pipeline existe."""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def move_to_processed(file_path: Path):
    """
    Move o arquivo para /Processed. Se já existir arquivo com o mesmo nome,
    adiciona um timestamp para preservar o histórico sem sobrescrever.
    """
    dest = PROCESSED_DIR / file_path.name
    if dest.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = PROCESSED_DIR / f"{file_path.stem}_{timestamp}{file_path.suffix}"
    shutil.move(str(file_path), str(dest))
    return dest

def run_pipeline():
    setup_directories()

    print(f"\n{SEP_LINE}")
    print("  ♠️ ♥️  PIPELINE AUTOMATIZADO DE POKER — LEAK DETECTION  ♦️ ♣️")
    print(f"{SEP_LINE}")
    print(f"  Diretório Base     : {BASE_DIR}")
    print(f"  Pasta de Ingestão  : {INPUT_DIR}")
    print(f"  Pasta de Saída     : {OUTPUT_DIR}")
    print(f"  Pasta Processados  : {PROCESSED_DIR}")
    print(f"{SEP_LINE}")

    # 1. Varredura de arquivos .csv na pasta /Input
    csv_files = sorted(list(INPUT_DIR.glob("*.csv")))
    txt_files = sorted(list(INPUT_DIR.glob("*.txt")))

    if not csv_files:
        print("\n  ⚠️  NENHUM ARQUIVO .CSV ENCONTRADO EM /Input!")
        print("  ─────────────────────────────────────────────────────────────")
        print("  Como usar:")
        print(f"  1. Deposite seus relatórios (.csv) na pasta:")
        print(f"     📁 {INPUT_DIR}")
        print("  2. (Opcional) Deposite os logs detalhados (.txt) correspondentes.")
        print("  3. Execute novamente no terminal:")
        print("     python pipeline_poker.py\n")
        return

    print(f"\n  📥 Arquivos detectados para processamento em /Input:")
    for f in csv_files:
        print(f"     • [CSV] {f.name} ({f.stat().st_size / 1024:.1f} KB)")
    for f in txt_files:
        print(f"     • [LOG] {f.name} ({f.stat().st_size / 1024:.1f} KB)")

    # 2. Execução do motor de cálculo (poker_engine)
    print(f"\n  ⚙️  Executando motor de cálculo e análise avançada (poker_engine)...")
    log_search_dirs = [INPUT_DIR, BASE_DIR]
    
    result = run_poker_leak_engine(
        csv_paths=csv_files,
        log_dirs=log_search_dirs,
        output_xlsx_path=OUTPUT_XLSX
    )

    if not result.get("success"):
        print(f"\n  ❌ ERRO NO PROCESSAMENTO:")
        print(f"     {result.get('error')}\n")
        return

    # 3. Exibição do relatório consolidado
    print(f"\n  ✅ PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
    print(f"  ─────────────────────────────────────────────────────────────")
    print(f"  📊 Total de mãos analisadas (>20BB) : {result['total_hands']}")
    print(f"  📉 Prejuízo total acumulado         : {result['total_loss_bb']:.2f} BB")
    
    po = result.get("premium_offsuit", {})
    if po and po.get("total_hands", 0) > 0:
        tot_po = po["total_hands"]
        agg_po = po["aggressor_hands"]
        cal_po = po["caller_hands"]
        loss_po = po["loss_bb"]
        print(f"\n  🔍 DESTAQUE — PREMIUM OFFSUIT:")
        print(f"     • Volume Total : {tot_po} mãos ({loss_po:.2f} BB perdidos)")
        print(f"     • Como Agressor: {agg_po} mãos ({100*agg_po/tot_po:.1f}% das mãos)")
        print(f"     • Como Caller  : {cal_po} mãos ({100*cal_po/tot_po:.1f}% das mãos)")

    print(f"\n  📁 Dashboard gerado em:")
    print(f"     👉 {result['output_file']}")

    # 4. Movimentação dos arquivos de Input -> Processed
    print(f"\n  📦 Arquivando arquivos processados em /Processed...")
    for f in csv_files:
        dest = move_to_processed(f)
        print(f"     ✓ Movido: {f.name} -> {dest.name}")
    for f in txt_files:
        dest = move_to_processed(f)
        print(f"     ✓ Movido: {f.name} -> {dest.name}")

    print(f"\n{SEP_LINE}")
    print("  🏁 PIPELINE FINALIZADO! Pastas prontas para novos dados.")
    print(f"{SEP_LINE}\n")

if __name__ == "__main__":
    run_pipeline()
