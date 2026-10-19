<h1 align="center">f1-llm</h1>

<p align="center">
  Chatbot que responde perguntas em linguagem natural sobre Fórmula 1 e plota gráficos,<br>
  usando dados oficiais de cronometragem via FastF1.
</p>

<p align="center">
  <a href="https://github.com/ThallesNonato1123/f1-llm/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/ThallesNonato1123/f1-llm/actions/workflows/ci.yml/badge.svg">
  </a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.14-blue">
  <img alt="testes" src="https://img.shields.io/badge/testes-170-success">
</p>

---

Você pergunta *"compara o ritmo de corrida do Verstappen e do Norris em Interlagos 2024"*. O modelo escolhe qual ferramenta de dados chamar e com quais parâmetros, a ferramenta lê os dados oficiais da sessão, e a resposta volta em texto com um gráfico interativo ao lado.

Este README descreve **como o projeto é construído**: a stack, a arquitetura, as regras de teste e as decisões que moldaram o código.

## Stack

| Camada | Escolha | Papel |
|---|---|---|
| Linguagem | **Python 3.14** | Gerenciado pelo [uv](https://docs.astral.sh/uv/) (`.python-version` + `uv.lock`) |
| Dados | **[FastF1](https://docs.fastf1.dev/)** | Cronometragem, telemetria, pneus e classificações oficiais da F1 |
| LLM | **[Claude](https://docs.claude.com/)** (`anthropic`) | Interpreta a pergunta e decide as chamadas de ferramenta |
| Backend | **[FastAPI](https://fastapi.tiangolo.com/)** + uvicorn | `POST /chat`, `GET /health`, serve o frontend estático |
| Frontend | **HTML/CSS/JS puro** | Sem build step, sem framework, sem `node_modules` |
| Gráficos | **Plotly** | Montados como JSON no backend, renderizados pelo `plotly.js` no navegador |
| Testes | **pytest** | 170 testes: 149 rápidos + 21 de integração |
| CI | **GitHub Actions** | Roda a suíte rápida em todo push na `main` e em todo PR |

Build backend: `uv_build`. Nenhuma dependência de frontend é instalada — o `plotly.js` vem por CDN no `index.html`.

## Arquitetura

```
  navegador                backend FastAPI                  fora do processo
 ┌───────────┐    POST    ┌──────────────┐   tool calling   ┌──────────────┐
 │ index.html│  /chat ──> │ llm/chat.py  │ <──────────────> │  Claude API  │
 │ plotly.js │ <── JSON   └──────┬───────┘                  └──────────────┘
 └───────────┘ texto +          │ chama a ferramenta escolhida
               gráficos         ▼
                         ┌──────────────┐                   ┌──────────────┐
                         │  tools/*.py  │ ────────────────> │    FastF1    │
                         └──────────────┘    load_*(...)    └──────────────┘
```

```
src/f1llm/
├── api/app.py          FastAPI: POST /chat, GET /health, estáticos montados por último
│   └── static/         index.html + app.js + style.css
├── llm/
│   ├── chat.py         loop de tool calling + system prompt
│   ├── tools.py        schemas das 9 ferramentas expostas ao modelo
│   └── production.py   wiring da API da Anthropic (modelo, effort, max_tokens)
├── tools/              uma ferramenta por arquivo: dados + gráfico
├── fastf1_client.py    a fronteira: a única coisa que fala com a FastF1
├── charts.py           tema escuro compartilhado dos gráficos
└── errors.py           SessionDataUnavailable
```

Três propriedades valem destacar:

**O LLM não gera código nem SQL.** Ele só escolhe entre 9 ferramentas com schema fixo (`strict: true`, `additionalProperties: false`). O loop em `chat.py` executa a ferramenta, devolve o resultado ao modelo e repete, com teto de 10 rodadas por pergunta.

**O backend é stateless.** Nenhuma sessão em memória: o frontend guarda o histórico e reenvia a cada pergunta ([ADR 0002](docs/adr/0002-stateless-backend-conversation-history.md)).

**A FastF1 só é tocada em um lugar.** Todo acesso passa pelas funções `load_*` de `fastf1_client.py`. É isso que torna o resto do código testável sem rede.

## Anatomia de uma ferramenta

Todas as 8 ferramentas em `src/f1llm/tools/` seguem o mesmo formato, nessa ordem:

**1. Validação de entrada** — `session_type` ∈ {Race, Qualifying, Sprint}, `year` ∈ [2018, ano atual], pelo menos 1 Piloto quando aplicável. Entrada inválida levanta `ValueError`; é bug de programação, não condição esperada.

Duas ferramentas restringem mais, por razões de domínio: `stints.py` exige `year ≥ 2019` (até 2018 os Compostos tinham nomes absolutos, HYPERSOFT…SUPERHARD, com outro esquema de cores) e `race_pace.py` aceita só {Race, Sprint} (Classificação não tem distância de corrida).

**2. Dados injetados, não importados** — a ferramenta recebe um parâmetro `load_*`. Em produção aponta pro `fastf1_client`; no teste, um `lambda`:

```python
def get_session_results(*, year: int, event: str, session_type: str, load_results=None):
```

**3. Dados brutos → dataclasses próprias** — nada de `DataFrame` da FastF1 vazando pro resto do sistema:

```python
@dataclass(frozen=True)
class DriverResult:
    position: int
    driver: str
    driver_code: str
    team: str
    time: str | None
    points: float
```

**4. Resposta estruturada em vez de exceção** — quando a sessão não existe, a ferramenta devolve `found=False` com um motivo, em vez de propagar `SessionDataUnavailable` ou inventar dados:

```python
@dataclass(frozen=True)
class SessionResultsResponse:
    found: bool
    results: list[DriverResult] | None = None
    reason: str | None = None
```

**5. Gráfico como função pura separada** — `build_*_chart` recebe as dataclasses e devolve o dict do Plotly. Sem I/O, sem rede, sem estado: testável sem mock nenhum. Todo eixo leva `showgrid: True` explícito.

## Como é desenvolvido

O projeto segue a metodologia de desenvolvimento assistido por IA do Matt Pocock, sempre nessa ordem:

1. **Grilling** — antes de desenhar qualquer feature, interrogar o desenho até esgotar as decisões, nunca assumir.
2. **Domain modeling** — vocabulário novo vai pro [`CONTEXT.md`](CONTEXT.md); decisão difícil de reverter vira [ADR](docs/adr/).
3. **TDD em fatias verticais** — um seam, um teste, implementação mínima, repetir.

Sobre o passo 3, as regras são não-negociáveis:

- **Fatia vertical, nunca horizontal.** Escrever todos os testes de uma feature antes de qualquer implementação (*horizontal slicing*) é tratado como antipadrão: trava a estrutura antes de ela existir e os testes passam a validar um comportamento imaginado. Caso real deste projeto: só ficou claro que `load_results` precisava de default `None` depois do segundo ciclo — de uma tacada só, teria sido palpite.
- **Red antes de green.** O teste roda e falha antes de existir implementação.
- **Refatorar entre ciclos**, nunca dentro de um passo red→green.

O [`CLAUDE.md`](CLAUDE.md) na raiz carrega essas regras pro agente de IA a cada sessão — é a metodologia versionada junto com o código, não um documento à parte.

### Vocabulário

Termos como **Stint**, **Composto de pneu**, **Ritmo de corrida** e **Gap para o vencedor** têm definição precisa (e termos proibidos) no [`CONTEXT.md`](CONTEXT.md), e são usados com o mesmo sentido no código, nos testes e nas respostas do bot. Exemplo: *Ritmo de corrida* mede contra um Piloto de referência fictício na média dos que estão na volta do líder; *Gap para o vencedor* mede contra o vencedor real. Nomes diferentes porque são contas diferentes.

### Decisões arquiteturais

- [0001 — Backend FastAPI, frontend HTML/CSS/JS puro, gráficos via Plotly](docs/adr/0001-web-app-architecture.md)
- [0002 — Backend stateless, histórico da conversa no frontend](docs/adr/0002-stateless-backend-conversation-history.md)
- [0003 — LLM via API cloud com tool calling](docs/adr/0003-cloud-llm-tool-calling.md)
- [0004 — Plotly em vez do matplotlib nativo da FastF1](docs/adr/0004-plotly-over-matplotlib.md)

### Integração contínua

`.github/workflows/ci.yml` roda em push na `main` e em PR: instala o uv, instala o Python do `.python-version`, faz `uv sync --locked` (falha se o `pyproject.toml` mudou sem atualizar o lock) e roda a suíte rápida. Os testes de integração ficam de fora — dependem de rede e de um cache que o runner não tem.

## Rodando

```bash
uv sync
cp .env.example .env    # preencha ANTHROPIC_API_KEY

uv run uvicorn f1llm.api.app:app --reload           # app web em :8000
uv run f1llm-chat                                   # chat no terminal
uv run f1llm-preview stints 2024 Brazil Race        # um gráfico só, sem LLM

uv run pytest                                       # suíte rápida, sem rede
uv run pytest -m integration -v                     # dados reais da FastF1
```

`F1LLM_MODEL` (padrão `claude-opus-5`) e `F1LLM_EFFORT` (padrão `medium`) trocam o modelo e o esforço de raciocínio. Ambas podem ir no mesmo `.env`.

### Docker

```bash
cp .env.example .env    # preencha ANTHROPIC_API_KEY
docker compose up --build
```

Sobe o backend FastAPI (com o frontend já buildado dentro da imagem) em `http://localhost:8000`. O cache da FastF1 persiste num volume nomeado entre execuções.
