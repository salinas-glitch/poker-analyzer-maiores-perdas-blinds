"""
=============================================================================
  POKER LEAK ENGINE (MOTOR DE CÁLCULO E ANÁLISE) v2.6
  Módulo independente de cálculo, avaliação de mãos e geração do dashboard.
=============================================================================
"""

import sys
import re
import csv
import io
from pathlib import Path
from collections import defaultdict, Counter

import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

HERO_NAMES = {"Hero", "Maxaranguape", "Maxaranguap"}
RANK_VAL = {str(i): i for i in range(2, 10)}
RANK_VAL.update({'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14})
RANK_INV = {v: k for k, v in RANK_VAL.items()}

# ---------------------------------------------------------------------------
# DESIGN & ESTILOS GLOBAIS
# ---------------------------------------------------------------------------
THEME = {
    "cover_bg":   "0A192F",
    "aba1_bg":    "E94560",
    "aba2_bg":    "533483",
    "aba3_bg":    "0D7377",
    "aba4_bg":    "14A76C",
    "aba5_bg":    "D84315",
    "tbl_hdr":    "1F1B24",
    "even_row":   "F8F9FA",
    "odd_row":    "FFFFFF",
    "loss_red":   "880000",
}

def fill(h): return PatternFill("solid", fgColor=h)
def fnt(bold=False, sz=10, color="222222", italic=False):
    return Font(bold=bold, size=sz, color=color, italic=italic, name="Calibri")
def ctr(): return Alignment(horizontal="center", vertical="center", wrap_text=False)
def lft(): return Alignment(horizontal="left",   vertical="center", wrap_text=False)
def rgt(): return Alignment(horizontal="right",  vertical="center")
def bord():
    t = Side(style="thin", color="D5D8DC")
    return Border(left=t, right=t, top=t, bottom=t)

def hdr(ws, row, cols, bg="1F1B24", fg="FFFFFF"):
    for c, v in enumerate(cols, 1):
        cell = ws.cell(row, c, v)
        cell.fill = fill(bg); cell.font = fnt(True, 9, fg)
        cell.alignment = ctr(); cell.border = bord()
    ws.row_dimensions[row].height = 22

def title(ws, row, col, text, bg, span=1, sz=13):
    cell = ws.cell(row, col, text)
    cell.fill = fill(bg); cell.font = fnt(True, sz, "FFFFFF")
    cell.alignment = ctr()
    if span > 1:
        ws.merge_cells(start_row=row, start_column=col,
                       end_row=row, end_column=col+span-1)
    ws.row_dimensions[row].height = max(sz+10, 24)

def _cell(ws, r, c, v, bg, fg="222222", bold=False, align="center", fmt=None, sz=9):
    cell = ws.cell(r, c, v)
    cell.fill = fill(bg)
    cell.font = fnt(bold, sz, fg)
    cell.alignment = (ctr() if align=="center" else lft() if align=="left" else rgt())
    cell.border = bord()
    if fmt: cell.number_format = fmt
    return cell

# ---------------------------------------------------------------------------
# NORMALIZAÇÃO DE VALORES NUMÉRICOS (CSV vs TXT)
# ---------------------------------------------------------------------------
def normalizar_valor(valor, origem: str, default: float = 0.0) -> float:
    """
    Normaliza valores numéricos conforme a origem do dado para eliminar inconsistências:
    
    1. Se a origem for 'csv' (Relatórios do PT4, Hand2Note, CoinPoker, etc.):
       - O ponto (.) representa o separador decimal puro (ex: 12.50 ou -162.59).
       - Remove eventuais vírgulas de milhar (ex: 1,234.50 -> 1234.50).
       - Converte para float puro (padrão Python).
       
    2. Se a origem for 'txt' (Logs brutos de Histórico de Mãos):
       - O ponto (.) representa o separador de milhar (ex: 1.234,50 ou 1.234 ou 19.790).
       - Remove os pontos de milhar e substitui a vírgula decimal (,) por ponto (.).
       - Converte para float puro (padrão Python).
    """
    if valor is None:
        return default
    try:
        s = str(valor).strip()
        if not s or s.lower() in ("none", "nan", "null", ""):
            return default

        # Tratamento de parênteses como negativo: (12.50) -> -12.50
        is_neg = False
        if s.startswith("(") and s.endswith(")"):
            is_neg = True
            s = s[1:-1].strip()
        elif s.startswith("-"):
            is_neg = True
            s = s[1:].strip()
        elif s.startswith("+"):
            s = s[1:].strip()

        # Remove caracteres indesejados (moedas, unidades, BB, fichas, espaços)
        s = re.sub(r"[^\d.,]", "", s)
        if not s:
            return default

        origem_clean = str(origem).strip().lower()

        if "txt" in origem_clean or "log" in origem_clean:
            # ORIGEM TXT:
            # Ponto (.) é separador de milhar -> remove todos
            # Vírgula (,) é separador decimal -> converte em ponto
            s = s.replace(".", "").replace(",", ".")
        else:
            # ORIGEM CSV:
            # Ponto (.) é separador decimal puro
            if "," in s and "." in s:
                # Vírgula é milhar (1,234.50) -> remove vírgula
                s = s.replace(",", "")
            elif "," in s and "." not in s:
                # Vírgula decimal isolada (12,50) -> converte em ponto
                s = s.replace(",", ".")

        val = float(s)
        return -val if is_neg else val
    except Exception:
        return default

def safe_float(v, d=0.0):
    """Alias retrocompatível delegando para normalizar_valor com origem='csv'."""
    return normalizar_valor(v, origem="csv", default=d)

def get_col_val(row: dict, aliases: list, default=""):
    """Busca o valor da primeira coluna compatível presente no dicionário."""
    for a in aliases:
        if a in row and row[a] is not None:
            v = str(row[a]).strip()
            if v: return v
    lower_map = {k.lower(): v for k, v in row.items()}
    for a in aliases:
        al = a.lower()
        if al in lower_map and lower_map[al] is not None:
            v = str(lower_map[al]).strip()
            if v: return v
    return default

# ---------------------------------------------------------------------------
# AVALIADOR DE FLOP & CARTAS
# ---------------------------------------------------------------------------
def parse_cards(s):
    if not s or s == "None": return []
    cards = []
    for tok in re.findall(r'[2-9TJQKAtjqka][cdhs]', str(s), re.IGNORECASE):
        r = tok[0].upper(); su = tok[1].lower()
        if r in RANK_VAL:
            cards.append((RANK_VAL[r], su))
    return cards

def _straight_draw(ranks_list):
    ur = sorted(set(ranks_list), reverse=True)
    if 14 in ur: ur = sorted(set(ur + [1]), reverse=True)
    for i in range(len(ur) - 3):
        w = ur[i:i+4]
        if w[0] - w[3] == 3 and len(w) == 4:
            low = w[3] - 1; high = w[0] + 1
            if low >= 2 and high <= 14: return "OESD"
    for i in range(len(ur) - 3):
        w = ur[i:i+4]
        if w[0] - w[3] == 4 and len(w) == 4: return "Gutshot"
    return None

def evaluate_flop(hole_str, board_str):
    hole  = parse_cards(str(hole_str))
    board = parse_cards(str(board_str))
    flop  = board[:3]

    if len(hole) != 2 or len(flop) != 3:
        return "N/A", False

    all5   = hole + flop
    ranks  = [c[0] for c in all5]
    suits  = [c[1] for c in all5]
    h_rnks = [c[0] for c in hole]
    f_rnks = [c[0] for c in flop]
    sorted_f = sorted(f_rnks, reverse=True)

    rc = Counter(ranks)
    sc = Counter(suits)

    max_suit_cnt = max(sc.values())
    has_flush_5  = (max_suit_cnt == 5)
    has_fd       = (max_suit_cnt == 4)

    # 1. Quadra
    if max(rc.values()) == 4: return "Quadra", False

    # 2. Full House
    trips = [r for r, c in rc.items() if c == 3]
    pairs = [r for r, c in rc.items() if c == 2]
    if trips and pairs: return "Full House", False

    # 3. Flush
    if has_flush_5: return "Flush", False

    # 4. Sequência
    ur_desc = sorted(set(ranks), reverse=True)
    has_str5 = False
    for i in range(len(ur_desc) - 4):
        w = ur_desc[i:i+5]
        if w[0] - w[4] == 4 and len(set(w)) == 5:
            has_str5 = True; break
    if not has_str5 and {14, 2, 3, 4, 5}.issubset(set(ranks)):
        has_str5 = True
    if has_str5: return "Sequência", False

    # 5. Trinca (set ou trips)
    if trips: return "Trinca (set/trips)", has_fd

    # 6. Dois pares
    if len(pairs) >= 2: return "Dois pares", has_fd

    # 7. Pares
    if pairs:
        pr = pairs[0]
        is_pocket = (h_rnks[0] == h_rnks[1])
        if is_pocket:
            if pr > sorted_f[0]: return "Overpair", has_fd
            elif sorted_f[1] < pr < sorted_f[0]: return "Segundo par", has_fd
            elif sorted_f[2] < pr < sorted_f[1]: return "Par baixo", has_fd
            else: return "Underpair", has_fd
        else:
            if pr == sorted_f[0]: return "Top par", has_fd
            elif len(sorted_f) > 1 and pr == sorted_f[1]: return "Segundo par", has_fd
            else: return "Par baixo", has_fd

    # 8. Draws e Carta Alta
    str_draw = _straight_draw(ranks)
    if has_fd and str_draw in ("OESD", "Gutshot"):
        return f"Combo draw (FD+{str_draw})", True
    if has_fd: return "Flush draw", True
    if str_draw == "OESD": return "OESD", False
    if str_draw == "Gutshot": return "Gutshot", False

    return "Carta alta sem draw", False

# ---------------------------------------------------------------------------
# CLASSIFICAÇÃO DE MÃO E POSIÇÃO
# ---------------------------------------------------------------------------
IP_POSITIONS  = {"BTN", "CO"}
OOP_POSITIONS = {"SB", "BB", "UTG", "UTG+1", "EP", "MP", "MP+1"}

def classify_ip_oop(pos):
    if not pos or pos == "None": return "?"
    p = str(pos).strip().upper()
    if p in IP_POSITIONS:  return "IP"
    if p in OOP_POSITIONS: return "OOP"
    return "?"

def hand_category(cards_str):
    if not cards_str or cards_str == "None": return "Desconhecida"
    cards = str(cards_str).upper().replace(",", " ")
    ranks = re.findall(r"[2-9TJQKA]", cards)
    suits = re.findall(r"[CDHS]", cards.upper())
    if len(ranks) < 2: return "Desconhecida"
    r1, r2 = ranks[0], ranks[1]
    suited = (len(set(suits)) == 1 and len(suits) >= 2)
    ro = "23456789TJQKA"
    premium = {"AA","KK","QQ","JJ","TT","AK","AQ","AJ","AT","KQ"}
    mid_pp  = {"99","88","77","66","55"}
    low_pp  = {"44","33","22"}
    hk = "".join(sorted([r1, r2], key=lambda x: ro.index(x) if x in ro else 0, reverse=True))
    if hk in premium: return "Premium Suited" if suited else "Premium Offsuit"
    if hk in mid_pp:  return "Pares Medios (55-99)"
    if hk in low_pp:  return "Pares Baixos (22-44)"
    if r1 == r2:      return "Par"
    r1v = ro.index(r1) if r1 in ro else 0
    r2v = ro.index(r2) if r2 in ro else 0
    gap = abs(r1v - r2v); hi = max(r1v, r2v)
    if hi >= ro.index("T") and gap <= 4:
        return "Conectores Altos Suited" if suited else "Conectores Altos Offsuit"
    if gap <= 2: return "Conectores Suited" if suited else "Conectores Offsuit"
    return "Marginais Suited" if suited else "Marginais Offsuit"

def classify_stack_depth(stack_bb):
    v = normalizar_valor(stack_bb, origem="csv")
    if v < 10:  return "Short (<10BB)"
    if v < 20:  return "Micro (10-20BB)"
    if v < 40:  return "Medium (20-40BB)"
    if v < 80:  return "Deep (40-80BB)"
    return "Very Deep (80BB+)"

def calc_spr(hero_chips, hero_invested, pot_total):
    stack = normalizar_valor(hero_chips, origem="csv")
    if stack <= 0: return None
    if pot_total is not None:
        pot = normalizar_valor(pot_total, origem="txt")
    else:
        pot = normalizar_valor(hero_invested, origem="csv") * 2
    if pot <= 0: return None
    return round(pot / stack, 3)

def spr_bucket(spr):
    if spr is None: return "N/A"
    if spr < 0.5:   return "< 0.5 (committed)"
    if spr < 1.0:   return "0.5-1 (shallow)"
    if spr < 2.0:   return "1-2 (medium)"
    if spr < 3.0:   return "2-3 (deep)"
    return ">3 (very deep)"

def normalize_hand_category(h_str):
    if not h_str or h_str == "N/A": return "Sem Showdown"
    hl = h_str.lower()
    if "fold" in hl or "muck" in hl or "sem showdown" in hl: return "Sem Showdown"
    if "royal flush" in hl: return "Royal Flush"
    if "straight flush" in hl: return "Straight Flush"
    if "four of a kind" in hl or "quad" in hl: return "Quadra"
    if "full house" in hl: return "Full House"
    if "flush" in hl: return "Flush"
    if "straight" in hl: return "Sequência"
    if "three of a kind" in hl or "set" in hl or "trips" in hl: return "Trinca"
    if "two pair" in hl: return "Dois Pares"
    if "one pair" in hl or "pair" in hl: return "Par"
    if "high card" in hl: return "Carta Alta"
    return "Outro"

# ---------------------------------------------------------------------------
# PARSER DE LOGS DE HISTÓRICO
# ---------------------------------------------------------------------------
def detect_platform_from_name(filename):
    fn = filename.upper()
    if "_GGP" in fn: return "GGPoker"
    if "_PS"  in fn: return "PokerStars"
    if "_CNP" in fn: return "CoinPoker"
    if "_PTY" in fn: return "PartyPoker"
    if "_YN"  in fn: return "WPT/YN"
    if "_PCF" in fn: return "PCF"
    return "?"

def _hero_hand_from_block(block):
    m = re.search(r"(?:Hero|Maxaranguap[e]?)(?:\s+\([^)]*\))?\s+showed\s+\[[^\]]+\]\s+and\s+lost\s+with\s+(.*?)(?:\n|$)", block, re.IGNORECASE)
    if m: return m.group(1).strip()
    m = re.search(r"(?:Hero|Maxaranguap[e]?):\s+shows\s+\[[^\]]+\]\s+\((.*?)\)", block, re.IGNORECASE)
    if m: return m.group(1).strip()
    m = re.search(r"Hero balance \d+.* lost \d+\[[^\]]*\]\s*\[\s*([^\]]+?)\s*\]", block)
    if m: return m.group(1).strip()
    if re.search(r"(?:Hero|Maxaranguap[e]?).*?(?:mucked|folded|folds)", block, re.IGNORECASE):
        return "Fold / Sem Showdown"
    return "N/A"

def _winner_hand_from_block(block, plat):
    m = re.search(r"Seat \d+: (\S+)(?:\s+\([^)]*\))? showed \[[^\]]+\] and won.*?with (.*?)(?:\n|$)", block, re.IGNORECASE)
    if m: return f"{m.group(1).strip()}: {m.group(2).strip()}"
    m = re.search(r"(\S+) showed \[[^\]]+\] and won \([\d,.]+\) with (.*?)(?:\n|$)", block, re.IGNORECASE)
    if m: return f"{m.group(1).strip()}: {m.group(2).strip()}"
    m = re.search(r"(\S+): shows \[[^\]]+\] \(([^)]+)\)\n\1 collected", block)
    if m: return f"{m.group(1).strip()}: {m.group(2).strip()}"
    m = re.search(r"(\S+) balance \d+, bet \d+, collected \d+, net \+\d+\[[^\]]*\] \[ ([^\]]+) \]", block)
    if m and m.group(1) not in HERO_NAMES: return f"{m.group(1).strip()}: {m.group(2).strip()}"
    m = re.search(r"(\S+) shows \[[^\]]+\] \((.*?)\)\n\1 collected", block, re.IGNORECASE)
    if m and m.group(1) not in HERO_NAMES: return f"{m.group(1).strip()}: {m.group(2).strip()}"
    return "Sem Showdown (Hero fold)"

def _extract_pot_total(block, plat):
    """Extrai pot total de logs TXT normalizando com origem='txt' (ponto de milhar)."""
    if plat == "PartyPoker":
        m = re.search(r"Main Pot: ([\d,.]+)", block)
        return normalizar_valor(m.group(1), origem="txt") if m else None
    m = re.search(r"Total pot ([\d,. ]+)\|", block)
    if not m: m = re.search(r"Total pot ([\d,. ]+)", block)
    if m: return normalizar_valor(m.group(1).split("|")[0], origem="txt")
    return None

def enrich_from_logs(target_ids: set, search_dirs: list):
    log_files = []
    seen = set()
    for d in search_dirs:
        p_dir = Path(d)
        if not p_dir.exists(): continue
        for f in p_dir.glob("*.txt"):
            if "Export_" in f.name and "Summaries" not in f.name and f.name not in seen:
                log_files.append(f)
                seen.add(f.name)

    enrichment = {}
    split_pat = r"(?=Poker Hand #|PokerStars Hand #|CoinPoker Hand #|\*\*\*\*\* Hand History|Game Hand #)"

    for lf in sorted(log_files):
        plat = detect_platform_from_name(lf.name)
        try:
            text = lf.read_text(encoding="utf-8-sig", errors="replace")
        except:
            text = lf.read_text(encoding="latin1", errors="replace")
        blocks = re.split(split_pat, text)

        for block in blocks:
            if not block.strip(): continue
            for hid in target_ids:
                if hid in block:
                    if plat == "PartyPoker":
                        pf = re.search(r"\*\* Dealing down cards \*\*(.*?)(?:\*\* Dealing Flop \*\*|\*\* Summary \*\*)", block, re.DOTALL | re.IGNORECASE)
                        pfa = bool(re.search(r"Hero (?:raises|bets)", pf.group(1), re.IGNORECASE)) if pf else None
                    else:
                        pf = re.search(r"\*\*\* HOLE CARDS \*\*\*(.*?)(?:\*\*\* FLOP \*\*\*|\*\*\* SUMMARY|\*\*\* SHOWDOWN)", block, re.DOTALL | re.IGNORECASE)
                        pfa = bool(re.search(r"(?:Hero|Maxaranguap(?:e)?): raises", pf.group(1), re.IGNORECASE)) if pf else None

                    hh  = _hero_hand_from_block(block)
                    wh  = _winner_hand_from_block(block, plat)
                    pot = _extract_pot_total(block, plat)

                    enrichment[hid] = {
                        "pf_aggressor": pfa,
                        "hero_hand":    hh,
                        "winner_hand":  wh,
                        "pot_total":    pot,
                    }
    return enrichment

# ---------------------------------------------------------------------------
# INGESTÃO E ENRIQUECIMENTO DOS REGISTROS
# ---------------------------------------------------------------------------
def load_and_enrich_data(csv_paths, log_dirs):
    raw_rows = []
    seen_ids = set()

    for cp in csv_paths:
        p = Path(cp)
        if not p.exists(): continue
        
        # Leitura com detecção de encoding e separador
        content = ""
        for enc in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
            try:
                content = p.read_text(encoding=enc)
                break
            except:
                continue

        if not content:
            continue

        sample = content[:4096]
        sep = ";" if sample.count(";") > sample.count(",") else ","
        reader = csv.DictReader(io.StringIO(content), delimiter=sep)

        for r in reader:
            hid = get_col_val(r, ["hand_id", "Hand #", "Hand ID", "Hand Number", "Game #", "handid"])
            if hid and hid in seen_ids:
                continue
            if hid: seen_ids.add(hid)
            raw_rows.append(r)

    # Re-parse de logs detalhados
    enrichment = enrich_from_logs(seen_ids, log_dirs)

    enriched = []
    for row in raw_rows:
        hid = get_col_val(row, ["hand_id", "Hand #", "Hand ID", "Hand Number", "Game #", "handid"])
        ext = enrichment.get(hid, {})

        pfa_raw = ext.get("pf_aggressor")
        pfa_sim_nao = ("Sim" if pfa_raw else "Não") if pfa_raw is not None else "?"

        # NORMALIZAÇÃO DE COLUNAS DE VALORES DO CSV:
        hero_chips = normalizar_valor(get_col_val(row, ["hero_chips", "Hero Chips", "Starting Chips", "Stack", "Chips"]), origem="csv")
        hero_inv   = normalizar_valor(get_col_val(row, ["hero_invested", "Invested", "Hero Invested", "Total Invested"]), origem="csv")
        pot_total  = ext.get("pot_total")
        spr        = calc_spr(hero_chips, hero_inv, pot_total)

        pos        = get_col_val(row, ["position", "Position", "Pos"])
        ip_oop     = classify_ip_oop(pos)
        cards      = get_col_val(row, ["hero_cards", "Hole Cards", "Cards", "Hero Cards"])
        cat        = hand_category(cards)
        board_str  = get_col_val(row, ["board", "Board", "Flop", "Community Cards"])

        parsed_board = parse_cards(board_str)
        flop_raw     = parsed_board[:3]
        flop_str     = " ".join(f"{RANK_INV.get(r,'?')}{s}" for r, s in flop_raw) if flop_raw else ""

        flop_strength, fd_flag = evaluate_flop(cards, board_str)

        # NORMALIZAÇÃO DE RESULTADO E STACK (CSV):
        net_bb = normalizar_valor(get_col_val(row, ["net_bb", "All-In Adj BB", "Net BB", "Net (BB)", "Net Won (BB)"]), origem="csv")
        went_ai_str = get_col_val(row, ["went_allin", "Went All-in", "All-in", "Went All In", "AllIn"], "False")
        went_ai = went_ai_str.lower() in ("true", "1", "sim", "yes", "t", "s")
        ai_street = get_col_val(row, ["all_in_street", "AI Street", "All-in Street", "Street All-In"], "N/A")
        
        stack_bb  = normalizar_valor(get_col_val(row, ["stack_depth_bb", "Stack Depth BB", "Stack (BB)", "Stack BB"]), origem="csv")
        if stack_bb == 0.0 and hero_chips > 0:
            bb_val = normalizar_valor(get_col_val(row, ["big_blind", "Big Blind", "BB"]), origem="csv", default=1.0)
            stack_bb = round(hero_chips / bb_val, 1) if bb_val > 0 else 0.0

        hero_final  = ext.get("hero_hand") or get_col_val(row, ["hero_hand_desc", "Final Hand", "Hero Hand"]) or "N/A"
        winner_hand = ext.get("winner_hand") or get_col_val(row, ["winner_hand", "Winning Hand", "Winner Hand"]) or "Sem Showdown"

        enriched.append({
            "hand_id":       hid,
            "platform":      get_col_val(row, ["platform", "Site", "Platform", "Room"]),
            "date":          get_col_val(row, ["date", "Date", "Played Date"]),
            "position":      pos,
            "ip_oop":        ip_oop,
            "hero_cards":    cards,
            "hand_cat":      cat,
            "pf_aggressor":  pfa_sim_nao,
            "stack_bb":      round(stack_bb, 1),
            "stack_cat":     classify_stack_depth(stack_bb),
            "spr":           spr,
            "spr_bucket":    spr_bucket(spr),
            "board":         board_str,
            "flop_cards":    flop_str,
            "flop_strength": flop_strength,
            "fd_flag":       "Sim" if fd_flag else "Não",
            "went_allin":    "Sim" if went_ai else "Não",
            "ai_street":     ai_street,
            "net_bb":        round(net_bb, 2),
            "hero_final":    hero_final,
            "winner_hand":   winner_hand,
            "confronto":     f"{normalize_hand_category(hero_final)} × {normalize_hand_category(winner_hand)}",
        })

    return enriched

# ---------------------------------------------------------------------------
# CONSTRUTORES DE ABAS DO DASHBOARD
# ---------------------------------------------------------------------------
def build_cover(ws):
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = THEME["cover_bg"]

    title(ws, 2, 1, "DASHBOARD DE LEAKS — POKER MTT (WEB APP & PIPELINE)", THEME["cover_bg"], span=5, sz=15)
    title(ws, 3, 1, "Consolidação e Diagnóstico de Perdas Severas (>20BB) • Poker Leak Engine v2.6", "1B2A4A", span=5, sz=9)

    ws.row_dimensions[2].height = 28
    ws.row_dimensions[3].height = 16

    lines = [
        (5,  "GUIA RÁPIDO DAS ABAS DO DASHBOARD", "1B2A4A", "FFFFFF", 11, True),
        (6,  "🥇  Aba 1 — RANKING: Top 50 mãos que mais drenam o stack com filtros e showdown.", "0A192F", "E0E6ED", 9, False),
        (7,  "📊  Aba 2 — MATRIZ: Cruzamento Posição × Stack Depth × Plataforma.", "0A192F", "E0E6ED", 9, False),
        (8,  "🛣️   Aba 3 — RUAS: Em qual rua o dinheiro é colocado e perdido (All-in por rua).", "0A192F", "E0E6ED", 9, False),
        (9,  "🃏  Aba 4 — PERFIL: Por categoria de mão pré-flop — onde você é dominado.", "0A192F", "E0E6ED", 9, False),
        (10, "🔬  Aba 5 — ESTRUTURAL: Agressor PF (Sim/Não) × SPR × IP/OOP × Força no Flop × Piores Confrontos.", "0A192F", "E0E6ED", 9, False),
        (12, "METODOLOGIA E NORMALIZAÇÃO DE DADOS", "1B2A4A", "FFFFFF", 11, True),
        (13, "• Net BB = Saldo líquido da mão normalizado pelo valor do Big Blind (CSV com ponto decimal puro).", "0A192F", "E0E6ED", 9, False),
        (14, "• Pot/Chips nos Logs TXT = Tratamento diferenciado com remoção de ponto de milhar e vírgula decimal.", "0A192F", "E0E6ED", 9, False),
        (15, "• Agressor PF = Identificado via análise de raises do Hero entre as cartas dadas e o flop.", "0A192F", "E0E6ED", 9, False),
        (16, "• SPR Index = Razão (Pot no momento da decisão / Stack do Hero).", "0A192F", "E0E6ED", 9, False),
    ]

    for r_num, txt, bg, fg, sz, bld in lines:
        cell = ws.cell(r_num, 1, txt)
        cell.fill = fill(bg)
        cell.font = fnt(bld, sz, fg)
        cell.alignment = lft()
        ws.row_dimensions[r_num].height = 20
        ws.merge_cells(f"A{r_num}:E{r_num}")

    ws.column_dimensions["A"].width = 75
    for c in ["B", "C", "D", "E"]:
        ws.column_dimensions[c].width = 2

def build_aba1_ranking(ws, enriched):
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = THEME["aba1_bg"]

    title(ws, 1, 1, "RANKING DE PERDAS — TOP 50 MÃOS", THEME["aba1_bg"], span=10, sz=14)
    title(ws, 2, 1, "Filtro: perdas > 20BB • Ordenado por maior prejuízo acumulado (Net BB)", "2D1302", span=10, sz=9)
    ws.row_dimensions[1].height = 26
    ws.row_dimensions[2].height = 16

    headers = ["#", "Hand ID", "Site", "Posição", "Hole Cards", "Board", "Net BB", "Agressor PF?", "Mão Final Hero", "Mão Vencedora"]
    hdr(ws, 3, headers, "4E1D00")

    sorted_rows = sorted(enriched, key=lambda r: normalizar_valor(r.get("net_bb", 0), origem="csv"))
    top50 = sorted_rows[:50]
    medals = {1: fill("FFD700"), 2: fill("C0C0C0"), 3: fill("CD7F32")}

    for i, row in enumerate(top50, 1):
        r = i + 3
        nb = normalizar_valor(row["net_bb"], origem="csv")
        row_bg = medals[i] if i in medals else fill(THEME["even_row"] if i % 2 == 0 else THEME["odd_row"])
        txt_col = "1A1A2E" if i <= 3 else ("880000" if nb <= -80 else "222222")

        vals = [
            (i, "center", None),
            (str(row["hand_id"])[:14], "left", None),
            (row["platform"], "center", None),
            (row["position"], "center", None),
            (row["hero_cards"], "center", None),
            (str(row["board"])[:28], "left", None),
            (nb, "right", "#,##0.00"),
            (row["pf_aggressor"], "center", None),
            (str(row["hero_final"])[:28], "left", None),
            (str(row["winner_hand"])[:32], "left", None),
        ]
        for c, (v, al, fmt) in enumerate(vals, 1):
            cell = ws.cell(r, c, v)
            cell.fill = row_bg
            cell.font = fnt(bold=(i <= 3 or c == 7), sz=9, color=txt_col)
            cell.alignment = (ctr() if al=="center" else lft() if al=="left" else rgt())
            cell.border = bord()
            if fmt: cell.number_format = fmt
        ws.row_dimensions[r].height = 16

    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:J{3+len(top50)}"

    col_widths = [4, 16, 12, 9, 11, 28, 12, 12, 28, 32]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

def build_aba2_matrix(ws, enriched):
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = THEME["aba2_bg"]

    title(ws, 1, 1, "MATRIZ DE LEAKS — POSIÇÃO × STACK DEPTH × PLATAFORMA", THEME["aba2_bg"], span=6, sz=14)
    ws.row_dimensions[1].height = 26

    # 1. Posição
    title(ws, 3, 1, "A — PERDAS POR POSIÇÃO", "2E1B4E", span=6, sz=11)
    hdr(ws, 4, ["Posição", "Nº Mãos", "Net BB Total", "Net BB Médio", "% das Perdas", "Pior Mão"], "4A235A")
    pos_map = defaultdict(lambda: {"n": 0, "tot": 0.0, "worst": 0.0})
    tot_loss = sum(normalizar_valor(r["net_bb"], origem="csv") for r in enriched)

    for r in enriched:
        k = r["position"] or "?"
        nb = normalizar_valor(r["net_bb"], origem="csv")
        pos_map[k]["n"] += 1
        pos_map[k]["tot"] += nb
        pos_map[k]["worst"] = min(pos_map[k]["worst"], nb)

    pos_order = ["UTG", "UTG+1", "EP", "MP", "MP+1", "CO", "BTN", "SB", "BB", "?"]
    curr_r = 5
    for p in pos_order:
        if p not in pos_map: continue
        st = pos_map[p]
        avg = st["tot"] / st["n"]
        pct = 100 * st["tot"] / tot_loss if tot_loss else 0

        _cell(ws, curr_r, 1, p, "2E1B4E", "FFFFFF", True, "center")
        _cell(ws, curr_r, 2, st["n"], "F5EEF8", "222222", False, "center")
        _cell(ws, curr_r, 3, round(st["tot"], 2), "F5EEF8", "880000", True, "right", "#,##0.00")
        _cell(ws, curr_r, 4, round(avg, 2), "F5EEF8", "880000", False, "right", "#,##0.00")
        _cell(ws, curr_r, 5, f"{pct:.1f}%", "F5EEF8", "333333", False, "center")
        _cell(ws, curr_r, 6, round(st["worst"], 2), "F5EEF8", "880000", False, "right", "#,##0.00")
        ws.row_dimensions[curr_r].height = 16
        curr_r += 1

    # 2. Stack Depth
    curr_r += 1
    title(ws, curr_r, 1, "B — PERDAS POR STACK DEPTH", "2E1B4E", span=6, sz=11)
    curr_r += 1
    hdr(ws, curr_r, ["Faixa de Stack", "Nº Mãos", "Net BB Total", "Net BB Médio", "% das Perdas", "Pior Mão"], "4A235A")
    curr_r += 1

    stk_map = defaultdict(lambda: {"n": 0, "tot": 0.0, "worst": 0.0})
    for r in enriched:
        k = r["stack_cat"]
        nb = normalizar_valor(r["net_bb"], origem="csv")
        stk_map[k]["n"] += 1
        stk_map[k]["tot"] += nb
        stk_map[k]["worst"] = min(stk_map[k]["worst"], nb)

    stk_order = ["Short (<10BB)", "Micro (10-20BB)", "Medium (20-40BB)", "Deep (40-80BB)", "Very Deep (80BB+)"]
    for sc in stk_order:
        if sc not in stk_map: continue
        st = stk_map[sc]
        avg = st["tot"] / st["n"]
        pct = 100 * st["tot"] / tot_loss if tot_loss else 0

        _cell(ws, curr_r, 1, sc, "34495E", "FFFFFF", True, "center")
        _cell(ws, curr_r, 2, st["n"], "EAECEE", "222222", False, "center")
        _cell(ws, curr_r, 3, round(st["tot"], 2), "EAECEE", "880000", True, "right", "#,##0.00")
        _cell(ws, curr_r, 4, round(avg, 2), "EAECEE", "880000", False, "right", "#,##0.00")
        _cell(ws, curr_r, 5, f"{pct:.1f}%", "EAECEE", "333333", False, "center")
        _cell(ws, curr_r, 6, round(st["worst"], 2), "EAECEE", "880000", False, "right", "#,##0.00")
        ws.row_dimensions[curr_r].height = 16
        curr_r += 1

    col_widths = [18, 10, 14, 14, 12, 12]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

def build_aba3_streets(ws, enriched):
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = THEME["aba3_bg"]

    title(ws, 1, 1, "ANÁLISE DE RUAS — ONDE O DINHEIRO É PERDIDO", THEME["aba3_bg"], span=6, sz=14)
    ws.row_dimensions[1].height = 26

    title(ws, 3, 1, "A — ALL-IN POR RUA", "0E4B4E", span=6, sz=11)
    hdr(ws, 4, ["Rua", "Nº Mãos", "Perda Total (BB)", "Perda Média (BB)", "% das Perdas", "Pior Mão"], "0E6251")

    street_map = defaultdict(lambda: {"n": 0, "tot": 0.0, "worst": 0.0})
    tot_loss = sum(normalizar_valor(r["net_bb"], origem="csv") for r in enriched)

    for r in enriched:
        st = r["ai_street"].upper() if r["went_allin"] == "Sim" and r["ai_street"] != "N/A" else "Sem All-In"
        nb = normalizar_valor(r["net_bb"], origem="csv")
        street_map[st]["n"] += 1
        street_map[st]["tot"] += nb
        street_map[st]["worst"] = min(street_map[st]["worst"], nb)

    st_order = ["PREFLOP", "FLOP", "TURN", "RIVER", "Sem All-In"]
    st_colors = {"PREFLOP": "1565C0", "FLOP": "2E7D32", "TURN": "E65100", "RIVER": "B71C1C", "Sem All-In": "607D8B"}

    curr_r = 5
    for st_name in st_order:
        if st_name not in street_map: continue
        st = street_map[st_name]
        avg = st["tot"] / st["n"]
        pct = 100 * st["tot"] / tot_loss if tot_loss else 0

        _cell(ws, curr_r, 1, st_name, st_colors.get(st_name, "555555"), "FFFFFF", True, "center")
        _cell(ws, curr_r, 2, st["n"], "E8F8F5", "222222", False, "center")
        _cell(ws, curr_r, 3, round(st["tot"], 2), "E8F8F5", "880000", True, "right", "#,##0.00")
        _cell(ws, curr_r, 4, round(avg, 2), "E8F8F5", "880000", False, "right", "#,##0.00")
        _cell(ws, curr_r, 5, f"{pct:.1f}%", "E8F8F5", "333333", False, "center")
        _cell(ws, curr_r, 6, round(st["worst"], 2), "E8F8F5", "880000", False, "right", "#,##0.00")
        ws.row_dimensions[curr_r].height = 18
        curr_r += 1

    col_widths = [16, 10, 15, 15, 13, 13]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

def build_aba4_hand_profile(ws, enriched):
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = THEME["aba4_bg"]

    title(ws, 1, 1, "PERFIL DE MÃO PRÉ-FLOP — ONDE OCORRE A DOMINAÇÃO", THEME["aba4_bg"], span=6, sz=14)
    ws.row_dimensions[1].height = 26

    hdr(ws, 3, ["Categoria de Mão", "Nº Mãos", "Perda Total (BB)", "Perda Média (BB)", "% das Perdas", "Pior Mão"], "145A32")

    cat_map = defaultdict(lambda: {"n": 0, "tot": 0.0, "worst": 0.0})
    tot_loss = sum(normalizar_valor(r["net_bb"], origem="csv") for r in enriched)

    for r in enriched:
        k = r["hand_cat"]
        nb = normalizar_valor(r["net_bb"], origem="csv")
        cat_map[k]["n"] += 1
        cat_map[k]["tot"] += nb
        cat_map[k]["worst"] = min(cat_map[k]["worst"], nb)

    cat_order = [
        "Premium Offsuit", "Premium Suited", "Pares Medios (55-99)", "Pares Baixos (22-44)",
        "Conectores Altos Offsuit", "Conectores Altos Suited", "Conectores Offsuit", "Conectores Suited",
        "Marginais Offsuit", "Marginais Suited", "Desconhecida"
    ]

    curr_r = 4
    for cat in cat_order:
        if cat not in cat_map: continue
        st = cat_map[cat]
        avg = st["tot"] / st["n"]
        pct = 100 * st["tot"] / tot_loss if tot_loss else 0

        is_prem = "Premium" in cat
        bg_col = "8B0000" if cat == "Premium Offsuit" else ("1E8449" if is_prem else "2C3E50")

        _cell(ws, curr_r, 1, cat, bg_col, "FFFFFF", True, "left")
        _cell(ws, curr_r, 2, st["n"], "EAFAF1", "222222", False, "center")
        _cell(ws, curr_r, 3, round(st["tot"], 2), "EAFAF1", "880000", True, "right", "#,##0.00")
        _cell(ws, curr_r, 4, round(avg, 2), "EAFAF1", "880000", False, "right", "#,##0.00")
        _cell(ws, curr_r, 5, f"{pct:.1f}%", "EAFAF1", "333333", False, "center")
        _cell(ws, curr_r, 6, round(st["worst"], 2), "EAFAF1", "880000", False, "right", "#,##0.00")
        ws.row_dimensions[curr_r].height = 18
        curr_r += 1

    col_widths = [26, 10, 15, 15, 13, 13]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

def build_aba5_structural(ws, enriched):
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = THEME["aba5_bg"]
    ws.freeze_panes = "A6"

    title(ws, 1, 1, "ANÁLISE ESTRUTURAL DE ERROS — POKER MTT (PERDAS > 20BB)", "2D1302", span=20, sz=14)
    title(ws, 2, 1, "Agressor PF (Sim/Não) · SPR · Posição Relativa (IP/OOP) · Força no Flop · Mão Final Hero × Mão Vencedora", "4E1D00", span=20, sz=9)
    ws.row_dimensions[2].height = 16

    ws.cell(3, 1, "Agressor PF:").font = fnt(True, 9, "FFFFFF")
    ws.cell(3, 1).fill = fill("2D1302")
    ws.cell(3, 2, "Sim (Agressor)").fill = fill("1565C0")
    ws.cell(3, 2).font = fnt(True, 9, "FFFFFF"); ws.cell(3, 2).alignment = ctr()
    ws.cell(3, 3, "Não (Caller)").fill = fill("D84315")
    ws.cell(3, 3).font = fnt(True, 9, "FFFFFF"); ws.cell(3, 3).alignment = ctr()
    ws.cell(3, 4, "IP / OOP:").fill = fill("2D1302"); ws.cell(3, 4).font = fnt(True, 9, "FFFFFF")
    ws.cell(3, 5, "IP (Azul)").fill = fill("D6EAF8"); ws.cell(3, 5).font = fnt(True, 9, "1565C0")
    ws.cell(3, 6, "OOP (Vermelho)").fill = fill("FADBD8"); ws.cell(3, 6).font = fnt(True, 9, "B71C1C")
    ws.merge_cells("G3:T3")
    ws.cell(3, 7, "Fonte dos dados: Re-parse completo dos logs individuais de histórico.").font = fnt(False, 8, "777777")
    ws.row_dimensions[3].height = 16

    col_headers = [
        "#", "Hand ID", "Site", "Data", "Posição", "IP/OOP",
        "Hole Cards", "Categoria PF", "Agressor PF?",
        "Stack BB", "SPR", "SPR Range",
        "Flop", "Força no Flop", "FD?",
        "All-In?", "Rua AI", "Net BB",
        "Mão Final Hero", "Mão Vencedora"
    ]
    hdr(ws, 5, col_headers, "4E1D00")

    sorted_e = sorted(enriched, key=lambda x: normalizar_valor(x["net_bb"], origem="csv"))
    for i, row in enumerate(sorted_e, 1):
        r = 5 + i
        agg = row["pf_aggressor"]
        ip_oop = row["ip_oop"]
        fstrength = row["flop_strength"]
        net_bb = normalizar_valor(row["net_bb"], origem="csv")

        bg_base = THEME["even_row"] if (i % 2 == 0) else THEME["odd_row"]
        agg_bg = "1565C0" if agg == "Sim" else ("D84315" if agg == "Não" else "757575")
        ip_bg  = "D6EAF8" if ip_oop == "IP" else ("FADBD8" if ip_oop == "OOP" else bg_base)

        vals = [
            (i, "center", bg_base, None),
            (str(row["hand_id"])[:14], "left", bg_base, None),
            (row["platform"], "center", bg_base, None),
            (str(row["date"])[:10], "center", bg_base, None),
            (row["position"], "center", bg_base, None),
            (ip_oop, "center", ip_bg, None),
            (row["hero_cards"], "center", bg_base, None),
            (row["hand_cat"][:18], "left", bg_base, None),
            (agg, "center", agg_bg, None),
            (row["stack_bb"], "right", bg_base, "#,##0.0"),
            (row["spr"], "right", bg_base, "#,##0.000"),
            (row["spr_bucket"], "center", bg_base, None),
            (row["flop_cards"], "center", bg_base, None),
            (fstrength, "center", "FFF3E0" if "par" in fstrength.lower() else bg_base, None),
            (row["fd_flag"], "center", ("FFF9C4" if row["fd_flag"] == "Sim" else bg_base), None),
            (row["went_allin"], "center", bg_base, None),
            (row["ai_street"], "center", bg_base, None),
            (net_bb, "right", ("FFEBEE" if net_bb < -60 else "FFF3E0" if net_bb < -40 else bg_base), "#,##0.00"),
            (str(row["hero_final"])[:30], "left", bg_base, None),
            (str(row["winner_hand"])[:34], "left", bg_base, None),
        ]

        for c, (v, al, bg, fmt) in enumerate(vals, 1):
            is_agg_col = (c == 9)
            fgcol = "FFFFFF" if is_agg_col else ("880000" if c == 18 and isinstance(v, float) and v < 0 else "222222")
            _cell(ws, r, c, v, bg, fgcol, bold=is_agg_col, align=al, fmt=fmt, sz=8)
        ws.row_dimensions[r].height = 14

    last_data_row = 5 + len(sorted_e)
    ws.auto_filter.ref = f"A5:{get_column_letter(len(col_headers))}{last_data_row}"

    # Insight Premium Offsuit
    s2_r = last_data_row + 3
    title(ws, s2_r, 1, "INSIGHT CHAVE — MÃOS PREMIUM: AGRESSOR vs CALLER", THEME["aba5_bg"], span=10, sz=12)
    s2_r += 1
    sub_hdr = ["Categoria", "Hero Agressor PF?", "Nº Mãos", "Perda Total (BB)", "Perda Média (BB)", "Pior Mão (BB)", "% Perda Cat.", "IP", "OOP"]
    hdr(ws, s2_r, sub_hdr, "4E1D00")
    s2_r += 1

    for cat_filter in ["Premium Offsuit", "Premium Suited"]:
        total_cat_loss = sum(normalizar_valor(r["net_bb"], origem="csv") for r in enriched if r["hand_cat"] == cat_filter)
        for agg_val in ["Sim", "Não"]:
            sub = [r for r in enriched if r["hand_cat"] == cat_filter and r["pf_aggressor"] == agg_val]
            if not sub: continue
            tot_loss = sum(normalizar_valor(r["net_bb"], origem="csv") for r in sub)
            avg_loss = tot_loss / len(sub)
            worst    = min(normalizar_valor(r["net_bb"], origem="csv") for r in sub)
            pct      = 100 * tot_loss / total_cat_loss if total_cat_loss else 0
            ip_c     = sum(1 for r in sub if r["ip_oop"] == "IP")
            oop_c    = sum(1 for r in sub if r["ip_oop"] == "OOP")

            row_bg = "DDEEFF" if agg_val == "Sim" else "FFEEDD"
            agg_badge_bg = "1565C0" if agg_val == "Sim" else "D84315"
            agg_label = "Sim (Agressor)" if agg_val == "Sim" else "Não (Caller)"

            _cell(ws, s2_r, 1, cat_filter, "5C2A00", "FFFFFF", True, "left", sz=9)
            _cell(ws, s2_r, 2, agg_label, agg_badge_bg, "FFFFFF", True, "center", sz=9)
            _cell(ws, s2_r, 3, len(sub), row_bg, "222222", False, "center")
            _cell(ws, s2_r, 4, round(tot_loss, 2), row_bg, "880000", True, "right", "#,##0.00")
            _cell(ws, s2_r, 5, round(avg_loss, 2), row_bg, "880000", True, "right", "#,##0.00")
            _cell(ws, s2_r, 6, round(worst, 2), row_bg, "880000", False, "right", "#,##0.00")
            _cell(ws, s2_r, 7, f"{pct:.1f}%", row_bg, "333333", False, "center")
            _cell(ws, s2_r, 8, ip_c, row_bg, "1565C0", False, "center")
            _cell(ws, s2_r, 9, oop_c, row_bg, "B71C1C", False, "center")
            ws.row_dimensions[s2_r].height = 18
            s2_r += 1

    # Piores Confrontos
    s3_r = s2_r + 2
    title(ws, s3_r, 1, "PIORES CONFRONTOS NO SHOWDOWN — MÃO FINAL HERO × MÃO VENCEDORA", THEME["aba5_bg"], span=7, sz=12)
    s3_r += 1
    hdr(ws, s3_r, ["Confronto (Hero × Vilão)", "Nº Mãos", "Perda Total (BB)", "Perda Média", "Pior Mão", "% Perdas Showdown", "Diagnóstico"], "4E1D00")
    s3_r += 1

    conf_map = defaultdict(lambda: {"n": 0, "tot": 0.0, "worst": 0.0})
    for r in enriched:
        cf = r["confronto"]
        nb = normalizar_valor(r["net_bb"], origem="csv")
        conf_map[cf]["n"] += 1
        conf_map[cf]["tot"] += nb
        conf_map[cf]["worst"] = min(conf_map[cf]["worst"], nb)

    sorted_confs = sorted(conf_map.items(), key=lambda x: x[1]["tot"])
    showdown_loss = sum(v["tot"] for k, v in conf_map.items() if "Sem Showdown" not in k)

    DIAGNOSTICS = {
        "Par × Dois Pares":          "Overplay de 1 par / Hero pagou 3 streets contra 2 pares",
        "Dois Pares × Flush":        "Cooler clássico ou não foldou em board monocolor",
        "Par × Trinca":              "Hero pagou stack-off de trinca segurando apenas 1 par",
        "Dois Pares × Full House":   "Cooler severo em bordo dobrado",
        "Dois Pares × Dois Pares":   "Kicker inferior ou two pairs dominado",
        "Trinca × Trinca":           "Set over Set (Cooler inevitável de stack-off)",
        "Dois Pares × Sequência":    "Hero com 2 pares não respeitou board conectado",
        "Sem Showdown × Sem Showdown":"Hero foldou pré-flop ou pós-flop após investir >20BB",
        "Carta Alta × Par":          "Blefe pago pelo vilão ou Hero deu call em all-in com Ace-high",
    }

    for cf, st in sorted_confs[:10]:
        avg = st["tot"] / st["n"]
        pct_sd = 100 * st["tot"] / showdown_loss if (showdown_loss and "Sem Showdown" not in cf) else 0
        diag = DIAGNOSTICS.get(cf, "Confronto de showdown")
        row_bg = "FFEEEE" if st["tot"] < -500 else ("FFF8F2" if st["n"] % 2 == 0 else "FFFFFF")

        _cell(ws, s3_r, 1, cf, "5C2A00", "FFFFFF", True, "left", sz=9)
        _cell(ws, s3_r, 2, st["n"], row_bg, "222222", False, "center")
        _cell(ws, s3_r, 3, round(st["tot"], 2), row_bg, "880000", True, "right", "#,##0.00")
        _cell(ws, s3_r, 4, round(avg, 2), row_bg, "880000", False, "right", "#,##0.00")
        _cell(ws, s3_r, 5, round(st["worst"], 2), row_bg, "880000", False, "right", "#,##0.00")
        _cell(ws, s3_r, 6, f"{pct_sd:.1f}%" if "Sem Showdown" not in cf else "N/A", row_bg, "333333", False, "center")
        _cell(ws, s3_r, 7, diag, row_bg, "555555", False, "left", sz=8)
        ws.row_dimensions[s3_r].height = 16
        s3_r += 1

    col_widths = [4, 16, 12, 11, 8, 7, 10, 22, 12, 8, 7, 16, 12, 22, 5, 7, 9, 11, 26, 32]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

# ---------------------------------------------------------------------------
# MOTOR PRINCIPAL
# ---------------------------------------------------------------------------
def run_poker_leak_engine(csv_paths, log_dirs, output_xlsx_path=None):
    """
    Função principal do motor de poker:
    1. Carrega CSVs e enriquece com logs detalhados (aplicando normalizar_valor diferenciado)
    2. Constrói as 6 abas do dashboard
    3. Salva o arquivo Excel formatado (em disco ou em memória BytesIO)
    4. Retorna relatório executivo completo + registros enriquecidos para preview no app
    """
    enriched = load_and_enrich_data(csv_paths, log_dirs)
    if not enriched:
        return {"success": False, "error": "Nenhum registro válido de mãos encontrado nos arquivos CSV fornecidos."}

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default sheet

    ws_cover = wb.create_sheet("📋 Guia")
    ws_aba1  = wb.create_sheet("🏆 Ranking Top50")
    ws_aba2  = wb.create_sheet("📊 Matriz Posição-Stack")
    ws_aba3  = wb.create_sheet("🛣 Análise de Ruas")
    ws_aba4  = wb.create_sheet("🃏 Perfil de Mão")
    ws_aba5  = wb.create_sheet("🔬 Análise Estrutural de Erros")

    build_cover(ws_cover)
    build_aba1_ranking(ws_aba1, enriched)
    build_aba2_matrix(ws_aba2, enriched)
    build_aba3_streets(ws_aba3, enriched)
    build_aba4_hand_profile(ws_aba4, enriched)
    build_aba5_structural(ws_aba5, enriched)

    excel_bytes = None
    output_location = None

    if output_xlsx_path:
        if isinstance(output_xlsx_path, (str, Path)):
            out_p = Path(output_xlsx_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            wb.save(out_p)
            output_location = str(out_p.resolve())
        elif hasattr(output_xlsx_path, "write"):
            wb.save(output_xlsx_path)
            output_location = "Stream / BytesIO"
    else:
        # Buffer de memória
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        excel_bytes = buffer.getvalue()
        output_location = "In-Memory Bytes"

    # Métricas executivas
    tot_hands = len(enriched)
    tot_loss = sum(normalizar_valor(r["net_bb"], origem="csv") for r in enriched)
    avg_loss = tot_loss / tot_hands if tot_hands else 0
    worst_hand = min(normalizar_valor(r["net_bb"], origem="csv") for r in enriched) if enriched else 0

    prem_off = [r for r in enriched if r["hand_cat"] == "Premium Offsuit"]
    po_agg = sum(1 for r in prem_off if r["pf_aggressor"] == "Sim")
    po_cal = sum(1 for r in prem_off if r["pf_aggressor"] == "Não")
    po_loss = sum(normalizar_valor(r["net_bb"], origem="csv") for r in prem_off)

    return {
        "success": True,
        "total_hands": tot_hands,
        "total_loss_bb": tot_loss,
        "avg_loss_bb": avg_loss,
        "worst_hand_bb": worst_hand,
        "output_file": output_location,
        "excel_bytes": excel_bytes,
        "enriched_data": enriched,
        "premium_offsuit": {
            "total_hands": len(prem_off),
            "loss_bb": po_loss,
            "aggressor_hands": po_agg,
            "caller_hands": po_cal,
        }
    }
