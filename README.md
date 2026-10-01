# ♠️ Poker Leak Detector — Web App & Pipeline Automatizado

Aplicação web interativa e motor de data science para detecção, diagnóstico e auditoria de **leaks (perdas > 20BB)** em Poker MTT e Cash Games. 

Desenvolvido para eliminar a necessidade de terminal e automatizar a geração do **Dashboard_Leaks_Poker.xlsx** completo com 6 abas analíticas.

---

## 🚀 Como Rodar Localmente

### 1. Pré-requisitos
Certifique-se de ter o Python 3.10 ou superior instalado. Instale as dependências:
```bash
pip install -r requirements.txt
```

### 2. Executando o Web App (Streamlit)
Para abrir o app interativo no seu navegador:
```bash
streamlit run app.py
```
*(No Windows, caso o comando `streamlit` não esteja no seu PATH, utilize: `python -m streamlit run app.py`)*

O app abrirá automaticamente em seu navegador padrão em `http://localhost:8501`.

### 3. (Opcional) Execução via Terminal / Pipeline em Lote
Se preferir o modo tradicional em lote por pastas:
```bash
# 1. Coloque seus arquivos .csv em /Input
# 2. Execute:
python pipeline_poker.py
# 3. O relatório será salvo em /Output/Dashboard_Leaks_Poker.xlsx
```

---

## ☁️ Como Publicar no Streamlit Community Cloud (Deploy Gratuito)

O **Streamlit Community Cloud** permite hospedar seu Web App gratuitamente, com link compartilhável e atualização automática a cada push no GitHub.

### Passo 1: Subir o projeto no GitHub
1. Crie um novo repositório no seu [GitHub](https://github.com/new) (exemplo: `poker-leak-detector`). Pode ser **Público** ou **Privado**.
2. No terminal do seu computador (dentro da pasta do projeto), inicialize o repositório git e envie os arquivos:
   ```bash
   git init
   git add app.py poker_engine.py requirements.txt README.md
   git commit -m "feat: Poker Leak Detector Streamlit App"
   git branch -M main
   git remote add origin https://github.com/SEU_USUARIO/poker-leak-detector.git
   git push -u origin main
   ```

### Passo 2: Conectar ao Streamlit Community Cloud
1. Acesse **[share.streamlit.io](https://share.streamlit.io/)** e faça login com sua conta do **GitHub**.
2. Clique no botão azul **"Create app"** (ou **"New app"**).
3. Selecione a opção **"I already have an app"**.
4. Preencha os campos de configuração:
   - **Repository:** `SEU_USUARIO/poker-leak-detector`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** (Opcional) escolha um subdomínio personalizado, ex: `poker-leak-detector.streamlit.app`
5. Clique em **"Deploy!"**.

### Passo 3: Pronto!
O Streamlit Cloud irá automaticamente:
- Clonar seu repositório.
- Ler o arquivo `requirements.txt` e instalar as bibliotecas necessárias (`streamlit`, `pandas`, `openpyxl`).
- Inicializar sua aplicação web na nuvem com certificado HTTPS seguro e acesso de qualquer dispositivo (computador, tablet ou celular).

---

## 🧩 Arquitetura do Projeto

```text
├── app.py                 # Interface Web interativa (Streamlit)
├── poker_engine.py        # Motor de cálculo, regras de poker e gerador do Excel
├── pipeline_poker.py      # Script alternativo para processamento em lote via terminal
├── requirements.txt       # Dependências do projeto (streamlit, pandas, openpyxl)
├── README.md              # Documentação e guia de deploy
├── Input/                 # Pasta de ingestão para pipeline local
├── Processed/             # Pasta de arquivamento pós-processamento
└── Output/                # Pasta de saída do Dashboard_Leaks_Poker.xlsx
```

---

## 📊 Estrutura do Dashboard Gerado (6 Abas)

1. 📋 **Guia**: Visão geral e guia de navegação rápida.
2. 🏆 **Ranking Top50**: As 50 mãos mais caras da amostra com medalhas e detalhes do showdown.
3. 📊 **Matriz Posição-Stack**: Perdas cruzadas por posição na mesa, faixas de stack depth e plataforma.
4. 🛣 **Análise de Ruas**: Em qual rua o dinheiro foi investido e perdido (Pré-flop, Flop, Turn, River ou Sem All-in).
5. 🃏 **Perfil de Mão**: Classificação pré-flop (Premium Offsuit, Premium Suited, Pares, Conectores).
6. 🔬 **Análise Estrutural de Erros**:
   - Agressor Pré-Flop (`Sim` vs `Não`).
   - Índice de SPR ($\frac{\text{Pot}}{\text{Stack}}$).
   - Posição Relativa (`IP` vs `OOP`).
   - Força estrita no Flop ($\text{Quadra} > \text{Full House} > \dots > \text{Carta Alta}$).
   - Piores confrontos no Showdown (Mão Final Hero × Mão Vencedora do Vilão).
