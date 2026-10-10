# GOVERNANÇA DE DADOS — POKER LEAK DETECTOR
## Contrato Inviolável de Tratamento de Dados

> **Versão:** 1.1  
> **Data de atualização:** 2026-10-10  
> **Escopo:** Pipeline `poker_engine.py` · `app.py` · `pipeline_poker.py`  
> **Status:** 🔴 DOCUMENTO NORMATIVO — Qualquer exceção a estas regras exige justificativa técnica escrita e aprovação explícita.

---

## 1. OBJETIVO

Garantir a **integridade matemática absoluta** entre fontes de dados distintas que alimentam o pipeline de análise de mãos de poker. O pipeline consome dois tipos estruturalmente diferentes de arquivo:

| Fonte | Formato | Separador Decimal | Separador de Milhar | Exemplo |
|---|---|---|---|---|
| **Relatórios CSV** | Exportações do PT4, Hand2Note, CoinPoker, etc. | **Ponto (`.`)** | Vírgula (`,`) opcional | `1,234.50` ou `12.50` |
| **Logs TXT** | Histórico bruto de mãos (hand histories) | **Vírgula (`,`)** | **Ponto (`.`)** | `1.234,50` ou `19.790` |

A mistura não tratada dessas duas convenções produz erros silenciosos e matematicamente destrutivos. Um valor de `19.790` oriundo de um TXT, se tratado como CSV, resulta em `19.790` ao invés de `19790` — um erro de **1000x**. Este contrato elimina essa ambiguidade em todas as camadas do código.

---

## 2. REGRAS DE NORMALIZAÇÃO — O CONTRATO

Toda e qualquer leitura de valor numérico monetário ou de BB **deve** passar pela função canônica de normalização. **Não há exceções.**

### 2.1 Ponto de Entrada Único — Função `normalizar_valor`

**Localização:** `poker_engine.py` · Linha 78

```python
def normalizar_valor(valor, origem: str, default: float = 0.0) -> float:
    ...
```

**Regra de ouro:** O argumento `origem` é **obrigatório** e deve ser sempre explicitado pelo código chamador. Nunca inferir a origem por heurística no site de chamada — a responsabilidade de saber a fonte é do módulo que lê o arquivo.

---

### 2.2 FONTE CSV — Padrão PT4 / Hand2Note / CoinPoker

**Identificador de origem:** `origem="csv"`

**Convenção:**
- O **ponto (`.`)** é o separador **decimal**.
- A **vírgula (`,`)** é o separador de **milhar** (opcional, pode estar ausente).

**Algoritmo de normalização:**

```
Entrada: "1,234.50"  →  remover vírgulas de milhar  →  "1234.50"  →  float: 1234.50  OK
Entrada: "12.50"     →  sem vírgula, nenhuma ação   →  "12.50"    →  float: 12.50    OK
Entrada: "12,50"     →  vírgula sem ponto = decimal  →  "12.50"    →  float: 12.50    OK
Entrada: "-162.59"   →  sinal negativo canônico      →  float: -162.59               OK
```

**Implementação de referência (em `poker_engine.py`):**

```python
if "," in s and "." in s:
    # Padrao "1,234.50" → milhar com virgula → remove virgula
    s = s.replace(",", "")
elif "," in s and "." not in s:
    # Padrao "12,50" → decimal com virgula → converte para ponto
    s = s.replace(",", ".")
# caso contrario: s ja esta no formato "12.50" → nenhuma acao
```

**Campos afetados nos CSVs de entrada:**
- `Net ($)` / `Net (BB)` / `Net Won` — prejuízo/lucro da mão
- `Stacks` / `Stack Size` — pilha em fichas ou BB
- `SPR` — Stack-to-Pot Ratio
- Qualquer coluna numérica exportada pelo PT4 ou equivalente

---

### 2.3 FONTE TXT — Padrão Logs Brutos de Histórico de Mãos

**Identificador de origem:** `origem="txt"` ou `origem="log"`

**Convenção:**
- O **ponto (`.`)** é o separador de **milhar**.
- A **vírgula (`,`)** é o separador **decimal**.

**Algoritmo de normalização:**

```
Entrada: "1.234,50"  →  remover pontos  →  "123450"  →  substituir virgula  →  "1234.50"  →  float: 1234.50  OK
Entrada: "19.790"    →  remover pontos  →  "19790"   →  sem virgula         →  float: 19790.0               OK
Entrada: "2,50"      →  sem ponto       →  "2.50"    →  float: 2.50                                         OK
```

**Implementação de referência (em `poker_engine.py`):**

```python
if "txt" in origem_clean or "log" in origem_clean:
    # Ponto (.) e separador de milhar → remove todos
    # Virgula (,) e separador decimal → converte em ponto
    s = s.replace(".", "").replace(",", ".")
```

> ATENCAO: Esta lógica **inverte** a semântica do ponto e da vírgula em relação ao CSV.
> Aplicar o algoritmo CSV em dados TXT — ou vice-versa — produz erros numéricos silenciosos sem exceção de runtime.

---

## 3. TRATAMENTO DE EXCEÇÕES

Todos os casos abaixo são tratados **antes** da lógica de separador decimal/milhar, na fase de pré-processamento da string.

### 3.1 Valores Vazios / Nulos

| Valor de entrada | Comportamento |
|---|---|
| `None` | Retorna `default` (padrão: `0.0`) |
| `""` (string vazia) | Retorna `default` |
| `"none"`, `"nan"`, `"null"` (case-insensitive) | Retorna `default` |

**Nunca lançar exceção por valor vazio.** O `default` parametrizável permite que o código chamador defina o comportamento correto para cada contexto (ex: `0.0` para lucro, ou `-9999.0` como sentinela para detecção de ausência).

### 3.2 Negativos com Parênteses

Formato contábil: `(12.50)` → `-12.50`

Plataformas como o CoinPoker e algumas exportações do PT4 representam valores negativos com parênteses. O pré-processamento detecta o padrão `s.startswith("(") and s.endswith(")")`, extrai o valor interno e aplica o sinal negativo ao resultado final.

```python
if s.startswith("(") and s.endswith(")"):
    is_neg = True
    s = s[1:-1].strip()
```

O sinal negativo também é aceito no formato canônico com prefixo `-`.

### 3.3 Caracteres de Moeda e Unidades

O pré-processamento remove **todos** os caracteres não numéricos exceto ponto e vírgula, via regex:

```python
s = re.sub(r"[^\d.,]", "", s)
```

Isso garante transparência para os seguintes prefixos/sufixos encontrados em fontes reais:

| Símbolo/Texto | Plataforma | Tratamento |
|---|---|---|
| `$` | PokerStars, GGPoker | Removido automaticamente |
| `€` | PokerStars.eu, partypoker | Removido automaticamente |
| `BB`, `bb` | Hand2Note, PT4 | Removido automaticamente |
| `+` | Qualquer CSV | Removido (sinal positivo explícito) |
| Espaços | Qualquer fonte | Removidos via `.strip()` |

> Se após a remoção de todos esses caracteres a string ficar vazia, retorna `default` imediatamente.

### 3.4 Alias Retrocompatível — `safe_float`

Para compatibilidade com código legado que já existia antes da função `normalizar_valor`:

```python
def safe_float(v, d=0.0):
    """Alias retrocompativel delegando para normalizar_valor com origem='csv'."""
    return normalizar_valor(v, origem="csv", default=d)
```

**Regra:** Novos trechos de código **não devem** usar `safe_float`. Usar sempre `normalizar_valor` com `origem` explícito.

---

## 4. PROTOCOLO DE AUDITORIA DE SANIDADE

Antes de qualquer exportação do dashboard `.xlsx` ou geração de relatório, as seguintes verificações são **obrigatórias**. Esta seção define o checklist formal de auditoria.

### 4.1 Verificação de Soma Manual (Amostra vs. Normalizada)

**Procedimento:**

1. Selecione uma amostra de **10 a 20 linhas** do arquivo bruto (CSV ou TXT).
2. Some os valores da coluna `Net ($)` / `Net (BB)` **manualmente** ou via calculadora, respeitando a convenção de separador da fonte.
3. Execute a mesma amostra pelo pipeline e compare com o resultado de `normalizar_valor`.
4. O delta aceitável é **zero** (correspondência exata de float até 2 casas decimais).

**Sinal de alarme:** Se qualquer valor diferir por um fator de 10, 100 ou 1000, isso indica que `origem` foi passado incorretamente (CSV tratado como TXT ou vice-versa).

### 4.2 Verificação de Integridade de Sinal

Toda mão catalogada como "perda > 20BB" **deve** ter `net_bb < -20.0`. Qualquer `net_bb` positivo em registros que chegaram pelo filtro de perdas indica:
- Parênteses de negativo não foram detectados, **ou**
- O sinal foi invertido durante o pré-processamento.

Verificação em código:

```python
assert all(row["net_bb"] < 0 for row in perdas), \
    "FALHA DE AUDITORIA: net_bb positivo encontrado em lista de perdas!"
```

### 4.3 Verificação de Magnitude (Outlier Check)

Nenhuma mão isolada deve registrar perda superior a **500 BB** em cash games ou **5.000 fichas** em torneios MTT sem revisão manual. Valores acima deste limiar indicam provável falha de normalização (ponto de milhar não removido).

```python
OUTLIER_BB_THRESHOLD = 500.0
outliers = [r for r in data if abs(r.get("net_bb", 0)) > OUTLIER_BB_THRESHOLD]
if outliers:
    print(f"AUDITORIA: {len(outliers)} linha(s) com net_bb > {OUTLIER_BB_THRESHOLD}. Verificar manualmente.")
```

### 4.4 Verificação de Consistência Cross-Source

Quando a mesma sessão/plataforma possui registros tanto no CSV quanto no TXT, as somas agregadas por plataforma **devem convergir** dentro de uma tolerância de ±0.01 BB (arredondamento de float). Divergências maiores indicam um arquivo de uma das fontes com corrupção ou convenção de separador incorreta.

| Plataforma | Fonte CSV (Soma net_bb) | Fonte TXT (Soma net_bb) | Delta | Status |
|---|---|---|---|---|
| GGPoker | -1234.50 | -1234.50 | 0.00 | OK |
| PokerStars | -987.30 | -987.30 | 0.00 | OK |
| CoinPoker | -456.00 | -455.99 | 0.01 | Verificar |

---

## 5. PROCESSO DE DEPLOY — INTEGRAÇÃO DE NOVOS ARQUIVOS

### 5.1 Fluxo Padrão via Pipeline Automatizado

```
/Input/
    ├── novo_relatorio.csv   ← Exportacao do PT4/Hand2Note
    └── novo_log.txt         ← Hand history bruto

        ↓  python pipeline_poker.py

/Output/
    └── Dashboard_Leaks_Poker.xlsx   ← Saida consolidada

/Processed/
    ├── novo_relatorio.csv           ← Arquivado (com timestamp se duplicado)
    └── novo_log.txt
```

**Comando de execução:**

```bash
python pipeline_poker.py
```

O script varre `/Input/` automaticamente, chama o motor em `poker_engine.py`, grava o `.xlsx` em `/Output/` e move os arquivos para `/Processed/` com versionamento por timestamp se houver colisão de nomes.

### 5.2 Fluxo via Interface Web (`app.py`)

1. Inicie o servidor com `streamlit run app.py` no terminal.
2. Faça upload dos `.csv` (obrigatório) e `.txt` (opcional) diretamente na interface.
3. O motor cria um diretório temporário via `tempfile.TemporaryDirectory`, processa os arquivos e retorna o `.xlsx` para download direto — **sem persistência em disco**.

> O motor em `app.py` também busca logs locais como fallback nos diretórios `Input/` e `Processed/` do projeto, além dos arquivos carregados via upload.

### 5.3 Adicionando Suporte a uma Nova Plataforma

Ao integrar uma nova sala de poker ao pipeline, siga este checklist em ordem:

**[ ] Passo 1 — Identificar o padrão de separador da nova fonte**

Abra um arquivo de amostra e identifique:
- O campo de valor monetário/BB usa ponto ou vírgula como decimal?
- Se usa ponto como decimal → `origem="csv"`
- Se usa vírgula como decimal → `origem="txt"`

**[ ] Passo 2 — Mapear aliases de colunas em `poker_engine.py`**

Na função `get_col_val`, adicione os novos nomes de coluna da plataforma ao array `aliases` correspondente:

```python
# Exemplo: adicionando suporte ao WPT Global
net_bb = get_col_val(row, ["Net ($)", "Net (BB)", "net_won", "wpt_net_amount"])
```

**[ ] Passo 3 — Validar com amostra de 50 mãos**

Execute o protocolo de auditoria da Seção 4 com os primeiros 50 registros da nova plataforma antes de incluir no pipeline de produção.

**[ ] Passo 4 — Atualizar o mapeamento de plataforma**

Verifique se a detecção de plataforma (`platform`) identifica corretamente os novos arquivos. O campo `platform` é derivado do nome do arquivo ou de campos internos do hand history.

**[ ] Passo 5 — Documentar neste arquivo**

Adicione uma linha na tabela de fontes suportadas abaixo e registre qualquer tratamento especial necessário.

### 5.4 Tabela de Fontes Suportadas

| Plataforma | Tipo de Arquivo | `origem` | Convenção Decimal | Notas Especiais |
|---|---|---|---|---|
| PokerTracker 4 (PT4) | `.csv` | `"csv"` | Ponto | Padrão primário. Colunas em inglês. |
| Hand2Note | `.csv` | `"csv"` | Ponto | Colunas podem variar por versão. |
| CoinPoker (CNP) | `.txt` | `"txt"` | Vírgula | Negativos com parênteses `(val)`. |
| GGPoker (GGP) | `.txt` | `"txt"` | Vírgula | Volume alto; priorizar validação. |
| PokerStars (PS) | `.txt` | `"txt"` | Vírgula | Moeda `$` prefixada nos valores. |
| partypoker (PTY) | `.txt` | `"txt"` | Vírgula | Moeda `€` em versões europeias. |
| Yeti Network (YN) | `.txt` | `"txt"` | Vírgula | Verificar encoding UTF-8. |

---

## 6. REFERÊNCIA RÁPIDA — ANTI-PATTERNS PROIBIDOS

Os padrões abaixo **nunca devem aparecer** em código novo. Se encontrados em code review, devem ser refatorados.

```python
# PROIBIDO: float() direto sem normalizacao
net_bb = float(row["Net ($)"])

# PROIBIDO: replace sem considerar a origem
net_bb = float(row["Net ($)"].replace(",", ""))

# PROIBIDO: usar safe_float em codigo novo
net_bb = safe_float(row["Net ($)"])

# PROIBIDO: normalizar sem especificar origem
net_bb = normalizar_valor(row["Net ($)"])  # origem e obrigatorio!

# CORRETO: sempre explicitar a origem
net_bb = normalizar_valor(row["Net ($)"], origem="csv")
net_bb = normalizar_valor(parsed_log_value, origem="txt")
```

---

## 7. GLOSSÁRIO

| Termo | Definição |
|---|---|
| **BB** | Big Blind — unidade de medida de pilha/resultado em poker |
| **PT4** | PokerTracker 4 — software de rastreamento e exportação de mãos |
| **Hand History / Log TXT** | Arquivo bruto de histórico de mãos gerado pelas salas de poker |
| **SPR** | Stack-to-Pot Ratio — relação entre pilha restante e pot no flop |
| **net_bb** | Resultado líquido da mão em Big Blinds (negativo = perda) |
| **Leak** | Padrão recorrente de erro/perda identificável estatisticamente |
| **Normalização** | Conversão de um valor de string para `float` Python sem perda de precisão |
| **Origem** | Identificador da fonte do dado (`"csv"` ou `"txt"`) que determina o algoritmo de normalização |
| **Guard Rail** | Barreira de validação obrigatória que impede que dados inválidos ou poluídos atinjam as camadas de cálculo |
| **Ruído de Linha** | Registros de sumário, subtotais, médias ou linhas sem identificador de mão que não representam mãos jogadas individuais |

---

## 8. PROTOCOLO DE FILTRAGEM DE RUÍDO E INTEGRIDADE DE LINHA

### 8.1 Objetivo e Fundamentação
Relatórios gerados por softwares de rastreamento (ex: PT4, Hand2Note) frequentemente intercalam dados individuais de mãos com registros agregados de consolidação (subtotais de posição, médias gerais, rodapés de totalização como *Total* ou *Grand Total*). Além disso, exportações podem conter linhas em branco, quebras de cabeçalho ou registros desprovidos de um identificador unívoco de mão.

Se tais registros atingirem as camadas de normalização e agregação matemática:
1. **Distorção Catastrófica de Volume e EV:** Totais acumulados são computados cumulativamente com as mãos individuais, multiplicando artificialmente o prejuízo ou distorcendo as taxas horárias e de BB/100.
2. **Perda de Rastreabilidade:** Mãos que não possuem um *Hand ID* único quebram a consistência relacional com logs brutos de auditoria.

Portanto, a verificação de integridade de linha é um pré-requisito mandatório e inviolável que precede qualquer cálculo no motor.

---

### 8.2 Critérios Mandatórios de Descarte de Ruído
O motor de processamento **deve descartar imediatamente**, antes de qualquer enriquecimento ou cálculo, toda e qualquer linha que satisfaça pelo menos um dos seguintes critérios:

1. **Termos Sentinela de Resumo / Totalização:**
   Qualquer linha onde qualquer uma de suas células ou valores contenha (de forma exata ou parcial, case-insensitive) um dos termos:
   - `'Total'`
   - `'Summary'`
   - `'Average'`
   - `'Averagem'`
   - `'Grand Total'`

2. **Ausência ou Invalidade de Hand ID:**
   Qualquer linha cujo campo de identificação de mão (`hand_id`, `Hand #`, `Hand ID`, `Hand Number`, `Game #`, `handid`):
   - Seja nulo (`None`), vazio (`""`), preenchido apenas por espaços em branco ou valores sentinela nulos (`"nan"`, `"null"`, `"none"`).
   - Coincida com qualquer um dos termos de resumo listados acima.

3. **Hand ID Duplicado:**
   Qualquer linha cujo *Hand ID* já tenha sido registrado anteriormente durante o ciclo de ingestão. Cada mão deve ser processada estritamente uma única vez.

---

### 8.3 Guard Rail de Validação Pré-Normalização
O sistema deve implementar uma barreira arquitetural obrigatória (**Guard Rail**) posicionada estritamente na fase de leitura do arquivo, **antes** de qualquer chamada à função `normalizar_valor`:

```
Arquivo Bruto (CSV)
       │
       ▼
[ GUARD RAIL DE INTEGRIDADE ]
(valida termos de ruído + Hand ID único)
       │
       ├─────────────────────────┐
       │ (Válida)                │ (Inválida / Ruído)
       ▼                         ▼
[ normalizar_valor(...) ]   [ LOG DE DESCARTE ]
       │                    (registra motivo, arquivo e amostra)
       ▼                         │
Enriquecimento e Métricas        └─► Gravado em log_descarte_linhas.csv
```

> **REGRA DE OURO:** É terminantemente **PROIBIDO** invocar a função `normalizar_valor` antes de a linha ser expressamente aprovada pelo Guard Rail de Integridade. Registros reprovados pelo Guard Rail não devem constar em `raw_rows` nem em `enriched`.

---

### 8.4 Registro Obrigatório de Log de Descarte (`log_descarte_linhas.csv`)
Nenhum descarte pode ser silencioso. Para cada linha expurgada pelo Guard Rail, o sistema deve documentar no log estruturado de auditoria:
- **Timestamp:** Data e hora da tentativa de ingestão.
- **Arquivo de Origem:** Nome do arquivo CSV onde a anomalia foi detectada.
- **Linha:** Número da linha no arquivo de origem (se rastreável).
- **Motivo do Descarte:** Classificação explícita do descarte:
  - `TERMO_RESUMO_DETECTADO` (ex: linha contendo 'Total', 'Summary', etc.)
  - `HAND_ID_AUSENTE_OU_INVALIDO` (linha sem identificador de mão)
  - `HAND_ID_DUPLICADO` (mão já computada anteriormente)
- **Hand ID:** O valor do identificador detectado (ou vazio se inexistente).
- **Amostra dos Dados:** Representação textual resumida da linha descartada para rastreabilidade forense.

O arquivo `log_descarte_linhas.csv` deve ser gerado junto ao relatório de saída ou na pasta de auditoria designada.

---

*Este documento é parte integrante do projeto **Poker Leak Detector** e deve ser mantido atualizado a cada alteração no contrato de normalização e integridade de dados.*

