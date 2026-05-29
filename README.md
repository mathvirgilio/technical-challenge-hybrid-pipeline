# Pipeline Híbrido — Modernização SQL → Python

Pipeline híbrido (**LLM + regras determinísticas**) para modernizar stored procedures **PL/pgSQL** em módulos **Python 3.12+** (compatível com 3.14), orquestrado com **LangGraph** e exposto via API local (`langgraph dev`).

> Enunciado completo: [`Desafio_Tecnico_Inovacao_v2_candidatos.pdf`](Desafio_Tecnico_Inovacao_v2_candidatos.pdf)

---

## Índice

1. [Quick Start (5 minutos)](#quick-start-5-minutos)
2. [O que este projeto faz](#o-que-este-projeto-faz)
3. [Pré-requisitos](#pré-requisitos)
4. [Instalação passo a passo](#instalação-passo-a-passo)
5. [Como testar que está funcionando](#como-testar-que-está-funcionando)
6. [Referência da API](#referência-da-api)
7. [Arquitetura e fluxo LangGraph](#arquitetura-e-fluxo-langgraph)
8. [Estrutura do repositório](#estrutura-do-repositório)
9. [Anexos B–F (casos de teste)](#anexos-bf-casos-de-teste)
10. [Variáveis de ambiente](#variáveis-de-ambiente)
11. [Testes e qualidade (QA)](#testes-e-qualidade-qa)
12. [Banco de dados PostgreSQL](#banco-de-dados-postgresql)
13. [Decisões técnicas e trade-offs](#decisões-técnicas-e-trade-offs)
14. [Métrica de evaluation (bônus)](#métrica-de-evaluation-bônus)
15. [Roteiro para a entrevista técnica](#roteiro-para-a-entrevista-técnica)
16. [Solução de problemas](#solução-de-problemas)
17. [Limitações e evoluções futuras](#limitações-e-evoluções-futuras)
18. [Conformidade com o desafio](#conformidade-com-o-desafio)

---

## Quick Start (5 minutos)

Se você só quer ver a pipeline rodando:

```bash
git clone <url-do-repositorio>
cd technical-challenge-hybrid-pipeline

# 1. Dependências Python (uv instala tudo automaticamente)
uv sync

# 2. PostgreSQL via Docker
docker compose up -d

# 3. Criar tabelas no banco
uv run python scripts/init_db.py

# 4. Subir API + LangGraph (porta 2024)
uv run langgraph dev --no-browser
```

Em outro terminal:

```bash
curl http://localhost:2024/health
```

Resposta esperada:

```json
{"status": "ok", "pipeline": "modernization", "database": "ok"}
```

> **Sem chave OpenAI?** Funciona normalmente. Os Anexos B–F usam **templates determinísticos**; a LLM só entra em cena para procedures desconhecidas.

---

## O que este projeto faz

**Entrada:** código SQL de uma stored procedure/função PL/pgSQL (+ schema opcional do Anexo A).

**Saída:** módulo Python equivalente + relatório JSON com o resultado de cada etapa.

```mermaid
flowchart LR
  START([POST /modernize]) --> parsing[1. Parsing]
  parsing --> analysis[2. Análise semântica]
  analysis --> generation[3. Geração]
  generation --> validation[4. Validação]
  validation --> persist[(PostgreSQL)]
  validation --> END([Resposta JSON])
```

| Etapa | O que faz | Onde no código |
|-------|-----------|----------------|
| **Parsing** | Extrai nome, parâmetros, variáveis, statements; usa `sqlglot` + `sqlparse` + heurísticas PL/pgSQL | `src/hybrid_pipeline/pipeline/parsing.py` |
| **Análise semântica** | Detecta cursores, transações, exceções, CTEs, JSONB etc.; marca riscos e sugere estratégia SQL vs Python | `src/hybrid_pipeline/pipeline/analysis.py` |
| **Geração** | Produz Python: templates para B–F **ou** LLM (se `OPENAI_API_KEY`) com contexto das etapas anteriores | `src/hybrid_pipeline/pipeline/generation.py` |
| **Validação** | `ast.parse`, lint leve; persiste execução em `modernization_history` | `src/hybrid_pipeline/pipeline/validation.py` |

A orquestração LangGraph está em `src/hybrid_pipeline/graph/` (estado tipado + 4 nós em sequência).

---

## Pré-requisitos

| Ferramenta | Versão mínima | Para quê |
|------------|---------------|----------|
| [Python](https://www.python.org/downloads/) | 3.12+ | Runtime da pipeline |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | latest | Gerenciamento de deps e venv |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | latest | PostgreSQL local |
| Git | qualquer | Clonar o repositório |
| OpenAI API key | opcional | Geração via LLM para SQL desconhecido |

**Instalar uv (Windows PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Instalar uv (Linux/macOS):**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Instalação passo a passo

### 1. Clonar e entrar no projeto

```bash
git clone https://github.com/mathvirgilio/technical-challenge-hybrid-pipeline.git
cd technical-challenge-hybrid-pipeline
```

### 2. Instalar dependências Python

```bash
uv sync
```

Isso cria `.venv/` e instala LangGraph, FastAPI, sqlglot, psycopg, pytest, ruff etc.

### 3. Configurar variáveis de ambiente

```bash
# Linux/macOS
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Edite `.env` se necessário. Os valores padrão já funcionam com o Docker Compose incluído:

```env
DATABASE_URL=postgresql://pipeline:pipeline@localhost:5432/modernization
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

### 4. Subir PostgreSQL

```bash
docker compose up -d
```

Aguarde o container ficar saudável:

```bash
docker compose ps
```

Coluna `STATUS` deve mostrar `healthy`.

### 5. Inicializar tabelas

```bash
uv run python scripts/init_db.py
```

Saída esperada:

```
Database initialized (modernization_history, migration_metrics).
```

### 6. (Opcional) Gerar outputs dos Anexos B–F offline

Sem subir o servidor — útil para validar a pipeline antes da demo:

```bash
uv run python scripts/run_fixtures.py
```

Arquivos gerados em `outputs/` (`.py` + `_report.json`).

### 7. Subir a API

```bash
uv run langgraph dev --no-browser
```

| URL | Descrição |
|-----|-----------|
| http://localhost:2024/health | Health check |
| http://localhost:2024/docs | Swagger UI (FastAPI) |
| http://localhost:2024/modernize | Endpoint principal |
| http://localhost:2024/metrics/evaluation | Métrica nos fixtures |

> O `langgraph dev` lê `langgraph.json`, que aponta o grafo (`build.py:graph`) e a app FastAPI customizada (`api/app.py:app`).

---

## Como testar que está funcionando

### Checklist rápido

- [ ] `docker compose ps` → Postgres `healthy`
- [ ] `uv run python scripts/init_db.py` → sem erro
- [ ] `GET /health` → `"status": "ok"`
- [ ] `POST /modernize` com Anexo B → `"status": "success"` e código Python
- [ ] `uv run pytest` → todos passando
- [ ] `uv run ruff check .` → sem erros

### Health check

**Linux/macOS (curl):**

```bash
curl http://localhost:2024/health
```

**Windows PowerShell:**

```powershell
Invoke-RestMethod http://localhost:2024/health
```

### Modernizar o Anexo B (`fn_saldo_cliente`)

**Linux/macOS:**

```bash
curl -X POST http://localhost:2024/modernize \
  -H "Content-Type: application/json" \
  -d "{\"source_code\": \"$(cat fixtures/annex_b_fn_saldo_cliente.sql | jq -Rs .)\"}"
```

**Windows PowerShell:**

```powershell
$body = @{
  source_code = Get-Content fixtures/annex_b_fn_saldo_cliente.sql -Raw
} | ConvertTo-Json

Invoke-RestMethod -Method POST -Uri http://localhost:2024/modernize `
  -ContentType "application/json" -Body $body
```

**Com schema do Anexo A (recomendado para LLM):**

```powershell
$body = @{
  source_code    = Get-Content fixtures/annex_b_fn_saldo_cliente.sql -Raw
  schema_context = Get-Content fixtures/annex_a_schema.sql -Raw
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Method POST -Uri http://localhost:2024/modernize `
  -ContentType "application/json" -Body $body
```

Resposta esperada (campos principais):

```json
{
  "generated_code": "def fn_saldo_cliente(conn, p_cliente_id): ...",
  "status": "success",
  "history_id": 1,
  "report": {
    "parsing": { "routine_name": "fn_saldo_cliente", "..." : "..." },
    "analysis": { "features": ["aggregation"], "risks": [], "..." : "..." },
    "generation": { "strategy": "template", "..." : "..." },
    "validation": { "valid": true, "ast_parse_ok": true, "..." : "..." }
  }
}
```

### Métrica de evaluation

```bash
curl http://localhost:2024/metrics/evaluation
```

Executa a pipeline sobre todos os fixtures B–F, calcula `ast_parse_rate` e grava em `migration_metrics`.

---

## Referência da API

### `GET /health`

Verifica se a API está no ar e se o PostgreSQL responde.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | string | Sempre `"ok"` se a API respondeu |
| `pipeline` | string | Nome do grafo: `"modernization"` |
| `database` | string | `"ok"` ou `"unavailable"` |

### `POST /modernize`

Moderniza uma stored procedure.

**Request body:**

```json
{
  "source_code": "CREATE OR REPLACE FUNCTION ...",
  "schema_context": "CREATE TABLE clientes (...); ..."
}
```

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| `source_code` | sim | SQL completo da procedure/função |
| `schema_context` | não | Schema DDL (Anexo A) para enriquecer geração LLM |

**Response body:**

| Campo | Descrição |
|-------|-----------|
| `generated_code` | Código Python gerado (ou `null` em falha) |
| `report` | JSON com saídas de parsing, análise, geração e validação |
| `status` | `"success"`, `"partial"` ou `"failure"` |
| `history_id` | ID em `modernization_history` (ou `null` se DB indisponível) |

**Status possíveis:**

| Status | Significado |
|--------|-------------|
| `success` | Código gerado passou em `ast.parse` e lint |
| `partial` | Código gerado com problemas menores de lint |
| `failure` | Erro no parsing ou Python inválido |

### `GET /metrics/evaluation`

Roda evaluation automática nos fixtures B–F. Requer PostgreSQL para persistir métricas.

---

## Arquitetura e fluxo LangGraph

### Camadas do projeto

```
┌─────────────────────────────────────────────────────────┐
│  API (FastAPI)          src/hybrid_pipeline/api/        │
│  /health, /modernize, /metrics                          │
├─────────────────────────────────────────────────────────┤
│  Orquestração (LangGraph)  src/hybrid_pipeline/graph/   │
│  PipelineState → parsing → analysis → generation → val  │
├─────────────────────────────────────────────────────────┤
│  Pipeline (lógica)      src/hybrid_pipeline/pipeline/   │
│  parsing, analysis, generation, validation              │
├─────────────────────────────────────────────────────────┤
│  Persistência           src/hybrid_pipeline/persistence/│
│  modernization_history, migration_metrics                 │
└─────────────────────────────────────────────────────────┘
```

### Estado tipado (`PipelineState`)

Definido em `src/hybrid_pipeline/graph/state.py`:

| Campo | Preenchido em |
|-------|---------------|
| `source_code`, `schema_context` | Entrada da API |
| `parse_result` | Nó parsing |
| `analysis_result` | Nó analysis |
| `generated_code` | Nó generation |
| `validation_result`, `report`, `status`, `history_id` | Nó validation |

### Grafo LangGraph

```mermaid
stateDiagram-v2
    [*] --> parsing
    parsing --> analysis
    analysis --> generation
    generation --> validation
    validation --> [*]
```

Código em `src/hybrid_pipeline/graph/build.py` — grafo **linear** (sem branches), cada nó lê/escreve no estado compartilhado.

### Estratégia híbrida de geração

```
                    ┌─────────────────────┐
                    │  Procedure conhecida │
                    │  (Anexos B–F)?       │
                    └─────────┬───────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
     Template determinístico          OPENAI_API_KEY definida?
     (reprodutível, offline)                    │
              │                    ┌────────────┴────────────┐
              │                    ▼                         ▼
              │              LLM com contexto          Template genérico
              │              (parse + análise          (NotImplementedError
              │               + schema)                 se desconhecida)
              └───────────────┬─────────────────────────┘
                              ▼
                    Código Python + metadados
```

**Por que híbrido?** Templates garantem demo confiável na entrevista (sem depender de rede/API). LLM generaliza para SQL novo, usando contexto estruturado — não envia a procedure “crua” ao modelo.

---

## Estrutura do repositório

```
technical-challenge-hybrid-pipeline/
├── langgraph.json              # Config do langgraph dev (grafo + app HTTP)
├── docker-compose.yml          # PostgreSQL 16
├── pyproject.toml              # Deps, pytest, ruff
├── .env.example                # Template de variáveis
│
├── fixtures/                   # Material de entrada (Anexos A–F)
│   ├── annex_a_schema.sql
│   ├── annex_b_fn_saldo_cliente.sql
│   ├── annex_c_sp_atualizar_status_contas_inativas.sql
│   ├── annex_d_sp_transferir_entre_contas.sql
│   ├── annex_e_sp_processar_lote_taxas.sql
│   └── annex_f_sp_relatorio_mensal_cliente.sql
│
├── outputs/                    # Resultados gerados (B–F)
│   ├── annex_b_fn_saldo_cliente.py
│   ├── annex_b_fn_saldo_cliente_report.json
│   └── ...
│
├── scripts/
│   ├── init_db.sql             # DDL das tabelas (referência)
│   ├── init_db.py              # Cria tabelas via psycopg
│   └── run_fixtures.py         # Roda pipeline offline nos fixtures
│
├── src/hybrid_pipeline/
│   ├── api/
│   │   ├── app.py              # FastAPI: rotas customizadas
│   │   └── schemas.py          # Pydantic request/response
│   ├── graph/
│   │   ├── state.py            # PipelineState (TypedDict)
│   │   ├── nodes.py            # Nós do grafo
│   │   └── build.py            # Montagem e compile do grafo
│   ├── pipeline/
│   │   ├── parsing.py
│   │   ├── analysis.py
│   │   ├── generation.py
│   │   └── validation.py
│   ├── persistence/
│   │   ├── db.py               # Conexão + init
│   │   └── repository.py       # CRUD modernization_history
│   ├── metrics/
│   │   └── evaluation.py       # ast_parse_rate nos fixtures
│   └── config.py               # Settings (pydantic-settings)
│
└── tests/                      # pytest
    ├── test_api.py
    ├── test_graph.py
    ├── test_parsing.py
    ├── test_analysis.py
    └── test_validation.py
```

---

## Anexos B–F (casos de teste)

Material de entrada obrigatório do desafio. Cada anexo aumenta a complexidade:

| Anexo | Procedure | Complexidade | Construções principais | Estratégia adotada |
|-------|-----------|--------------|------------------------|-------------------|
| **B** | `fn_saldo_cliente` | Baixa | Função escalar, agregação, WHERE | SQL delegado ao SGBD via psycopg |
| **C** | `sp_atualizar_status_contas_inativas` | Baixa-Média | IN/OUT, UPDATE, GET DIAGNOSTICS, RAISE | Lógica Python + SQL parametrizado |
| **D** | `sp_transferir_entre_contas` | Média | Transação, FOR UPDATE, EXCEPTION | `conn.transaction()` + locks |
| **E** | `sp_processar_lote_taxas` | Alta | Cursor, LOOP, CASE, JSONB | Cursor → `fetchall` + loop em memória |
| **F** | `sp_relatorio_mensal_cliente` | Muito alta | CTE recursiva, RETURN QUERY, EXCEPTION | SQL complexo no SGBD + fallback Python |

**Anexo A** (`fixtures/annex_a_schema.sql`) — schema DDL usado como `schema_context` opcional na geração.

Para regenerar todos os outputs:

```bash
uv run python scripts/run_fixtures.py
```

Exemplo de código gerado (Anexo B): `outputs/annex_b_fn_saldo_cliente.py`.

---

## Variáveis de ambiente

Copie `.env.example` → `.env`:

| Variável | Obrigatória | Padrão | Descrição |
|----------|-------------|--------|-----------|
| `DATABASE_URL` | não* | `postgresql://pipeline:pipeline@localhost:5432/modernization` | Conexão PostgreSQL |
| `OPENAI_API_KEY` | não | vazio | Se preenchida, habilita geração LLM |
| `OPENAI_MODEL` | não | `gpt-4o-mini` | Modelo OpenAI |
| `LANGFUSE_PUBLIC_KEY` | não | vazio | Bônus observabilidade (não integrado) |
| `LANGFUSE_SECRET_KEY` | não | vazio | Bônus observabilidade (não integrado) |
| `LANGFUSE_HOST` | não | `http://localhost:3000` | Bônus observabilidade (não integrado) |

\* A API sobe sem Postgres, mas persistência e métricas ficam desabilitadas (`database: "unavailable"`).

---

## Testes e qualidade (QA)

```bash
# Testes unitários e de integração
uv run pytest

# Testes com output verbose
uv run pytest -v

# Lint estático
uv run ruff check .

# Lint + auto-fix (quando aplicável)
uv run ruff check . --fix
```

**O que os testes cobrem:**

| Arquivo | Foco |
|---------|------|
| `test_api.py` | `/health`, `/modernize` básico |
| `test_graph.py` | Execução end-to-end do grafo |
| `test_parsing.py` | Extração de metadados PL/pgSQL |
| `test_analysis.py` | Detecção de features e riscos |
| `test_validation.py` | `ast.parse` e lint |

---

## Banco de dados PostgreSQL

### Docker Compose

```yaml
# Credenciais padrão (docker-compose.yml)
Usuário:  pipeline
Senha:    pipeline
Banco:    modernization
Porta:    5432
```

### Tabela `modernization_history`

Toda execução de `/modernize` é persistida (sucesso, falha ou parcial):

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | BIGSERIAL | PK |
| `source_code` | TEXT | SQL enviado |
| `generated_code` | TEXT | Python gerado |
| `report` | JSONB | Relatório completo das etapas |
| `status` | VARCHAR(20) | `success`, `failure`, `partial` |
| `created_at` | TIMESTAMPTZ | Timestamp da execução |

### Tabela `migration_metrics` (bônus)

| Coluna | Descrição |
|--------|-----------|
| `routine_name` | Nome da procedure avaliada |
| `ast_parse_rate` | 0.0–1.0 (1.0 = Python sintaticamente válido) |
| `execution_status` | Status da pipeline naquele fixture |

### Consultar histórico manualmente

```bash
docker compose exec postgres psql -U pipeline -d modernization \
  -c "SELECT id, status, created_at FROM modernization_history ORDER BY id DESC LIMIT 5;"
```

---

## Decisões técnicas e trade-offs

| Tema | Decisão | Trade-off |
|------|---------|-----------|
| **Parser SQL** | `sqlglot` + `sqlparse` + regex PL/pgSQL | Não é compilador PL/pgSQL completo; suficiente para o escopo |
| **Geração** | Templates B–F + LLM opcional | Templates = reprodutível; LLM = generalização |
| **SQL vs Python** | CTE recursiva / RETURN QUERY ficam no SGBD; validações simples em Python | Menos risco semântico em SQL complexo |
| **Cursores (E)** | `fetchall` + loop em memória | Evita round-trips incrementais; usa mais RAM |
| **CTE / SETOF (F)** | SQL parametrizado + `except` com linha degradada | Espelha `RAISE WARNING` da procedure original |
| **Persistência** | Timeout 2s; falha de DB não bloqueia resposta | Histórico pode ser perdido se Postgres cair |
| **Orquestração** | LangGraph linear com estado tipado | Simples de explicar; sem branches condicionais ainda |

### Bibliotecas externas (justificativas)

| Biblioteca | Papel |
|------------|-------|
| **sqlglot** | AST SQL portável para DML/SELECT dentro do corpo PL/pgSQL |
| **sqlparse** | Tokenização lexical complementar |
| **LangGraph** | Orquestração em grafo (requisito do desafio) |
| **langchain-openai** | Geração LLM com prompt enriquecido |
| **psycopg3** | Driver moderno; alinhado ao código gerado |
| **FastAPI** | Rotas HTTP integradas via `langgraph.json` |
| **uv** | Instalação reprodutível e rápida |
| **pytest + ruff** | QA (bônus) |

### Escalabilidade (proposta documentada)

- Fila assíncrona (Redis/RQ) para `/modernize` em alto volume
- Cache de parse/análise por hash do `source_code`
- Registry de dialetos SQL plugável (`postgres`, `tsql`, `plsql`)
- Pool de conexões psycopg + read replicas para histórico
- Langfuse para traces por nó (estrutura preparada em `config.py`)

---

## Métrica de evaluation (bônus)

| Aspecto | Detalhe |
|---------|---------|
| **Métrica** | `ast_parse_rate` — fração do código que passa em `ast.parse` |
| **Captura** | Sintaxe Python válida |
| **Não captura** | Equivalência comportamental com o banco |
| **Onde** | Tabela `migration_metrics` + `GET /metrics/evaluation` |
| **Evolução** | Testes golden no Postgres + diff de resultados |

---

## Roteiro para a entrevista técnica

Sessão de ~45 minutos. Sugestão de ordem:

### 1. Contexto (2 min)

> “Pipeline híbrida que recebe PL/pgSQL e produz Python 3.14, com 4 etapas orquestradas por LangGraph. Templates garantem os Anexos B–F offline; LLM generaliza procedures novas.”

### 2. Demo ao vivo (10 min)

1. `docker compose ps` — Postgres healthy
2. `GET /health` — API + DB ok
3. `POST /modernize` com Anexo D (transação) — mostrar `report.analysis.risks`
4. Abrir `outputs/annex_e_sp_processar_lote_taxas.py` — explicar cursor → bulk
5. `GET /metrics/evaluation` — `mean_ast_parse_rate`

### 3. Walk-through do código (15 min)

| Pergunta provável | Onde mostrar |
|-------------------|--------------|
| Como funciona o grafo? | `graph/build.py`, `graph/nodes.py`, `graph/state.py` |
| Como parseia PL/pgSQL? | `pipeline/parsing.py` |
| Como decide SQL vs Python? | `pipeline/analysis.py` → `generation.py` |
| Como valida? | `pipeline/validation.py` |
| Onde persiste? | `persistence/repository.py` |
| Como a API integra? | `langgraph.json` + `api/app.py` |

### 4. Trade-offs e evolução (10 min)

- Parser heurístico vs compilador completo
- Templates vs LLM puro
- Validação estática vs testes comportamentais no banco
- Langfuse (não integrado, mas preparado)
- Escalabilidade: filas, cache, novos dialetos

### 5. Perguntas e respostas (8 min)

**Frases úteis:**

- *“O foco é qualidade do desenho da pipeline, não cobertura sintática total de PL/pgSQL.”*
- *“O LLM recebe parse + análise + schema — não mando a procedure crua.”*
- *“Toda execução vai pro histórico, independente do desfecho.”*
- *“Com mais tempo: Langfuse, testes golden no Postgres, mypy no código gerado.”*

---

## Solução de problemas

### `database: "unavailable"` no `/health`

```bash
docker compose up -d
docker compose ps                    # deve estar healthy
uv run python scripts/init_db.py
```

Verifique se a porta 5432 não está ocupada por outro Postgres local.

### `langgraph: command not found`

Use sempre via uv:

```bash
uv run langgraph dev --no-browser
```

### Erro de conexão ao subir `init_db.py`

Aguarde o Postgres inicializar (~10s após `docker compose up -d`):

```bash
docker compose logs postgres
```

### Porta 2024 em uso

```bash
# Linux/macOS
lsof -i :2024

# Windows
netstat -ano | findstr :2024
```

Mate o processo ou use outra porta (consulte docs do LangGraph CLI).

### `uv sync` falha

Confirme Python 3.12+:

```bash
python --version
uv python install 3.12
uv sync
```

### Procedure desconhecida retorna erro

Sem `OPENAI_API_KEY`, apenas Anexos B–F têm templates. Com a chave, a LLM tenta gerar; sem ela, o template genérico levanta `NotImplementedError`.

### Testes falham por falta de Postgres

A maioria dos testes **não** exige DB. Se `test_api` falhar por conexão, suba o Docker ou ignore — a API foi desenhada para funcionar com `database: "unavailable"`.

---

## Limitações e evoluções futuras

**Limitações atuais:**

- Parser PL/pgSQL é heurístico, não um compilador completo
- Procedures fora dos Anexos B–F exigem LLM (ou retornam erro)
- Equivalência comportamental não é validada automaticamente
- Langfuse não integrado (campos em `config.py` preparados)

**Com mais tempo:**

- Langfuse self-hosted no `docker-compose` com spans por nó
- Testes de regressão executando procedures no Postgres de teste
- `mypy` no código gerado
- UI para revisão humana do diff SQL/Python
- Branches condicionais no grafo (retry, human-in-the-loop)

---

## Conformidade com o desafio

Resumo de aderência ao PDF. Detalhes nos checklists abaixo.

| Requisito | Status |
|-----------|--------|
| Pipeline 4 etapas (Parsing → Análise → Geração → Validação) | ✅ |
| LangGraph com estado tipado + diagrama | ✅ |
| `POST /modernize` + `GET /health` via `langgraph dev` | ✅ |
| PostgreSQL + `modernization_history` | ✅ |
| Persistência em toda execução | ✅ |
| Anexos B–F processados + outputs em `outputs/` | ✅ |
| Schema Anexo A como contexto opcional | ✅ |
| README completo | ✅ |
| Escalabilidade documentada | ✅ |
| QA: pytest + ruff | ✅ |
| Métrica `ast_parse_rate` + endpoint | ✅ |
| Langfuse (bônus observabilidade) | ❌ |

<details>
<summary><strong>Checklist completo (clique para expandir)</strong></summary>

### Instruções gerais e README
- [x] Entrega em repositório Git
- [x] README com descrição da pipeline e fluxo
- [x] README com passos locais (Docker + uv + langgraph)
- [x] README com decisões técnicas e trade-offs
- [x] README com limitações e evoluções futuras
- [x] Bibliotecas externas justificadas
- [x] Uso de IA documentado (LLM opcional + templates)

### Pipeline híbrida
- [x] Parsing: SQL → IR estruturada
- [x] Análise: IN/OUT, cursores, transações, exceções, CTEs, riscos
- [x] Geração: Python + LLM com contexto das etapas
- [x] Validação: `ast.parse` + lint leve
- [ ] Comparação comportamental no banco (evolução)

### Requisitos obrigatórios
- [x] `langgraph dev`, `/modernize`, `/health`
- [x] Separação api / graph / pipeline / persistence
- [x] Docker Compose PostgreSQL
- [x] Tabela `modernization_history` (todos os campos)
- [x] Scripts `init_db.sql` + `init_db.py`

### Entrega
- [x] Código modular em `src/hybrid_pipeline`
- [x] Resultados B–F em `outputs/`
- [x] Variáveis de ambiente documentadas

### Bônus
- [x] pytest + ruff
- [x] Métrica evaluation + tabela + endpoint
- [ ] Langfuse integrado

</details>

---

