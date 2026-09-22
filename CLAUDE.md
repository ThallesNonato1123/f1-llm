# f1-llm

Chatbot que responde perguntas em linguagem natural sobre Fórmula 1 e plota gráficos, usando a FastF1 como fonte de dados. Veja `CONTEXT.md` para o glossário do domínio e `docs/adr/` para as decisões arquiteturais.

## Metodologia (siga sempre, nessa ordem)

Este projeto segue a metodologia de desenvolvimento assistido por IA do Matt Pocock:

1. **Grilling** (`mattpocock-skills:grilling`) antes de desenhar qualquer feature nova — interrogar até esgotar as decisões de design, nunca assumir.
2. **Domain modeling** (`mattpocock-skills:domain-modeling`) para registrar vocabulário novo em `CONTEXT.md` e decisões arquiteturais difíceis de reverter em `docs/adr/`.
3. **TDD** (`mattpocock-skills:tdd`) para implementar. Regras não-negociáveis:
   - **Fatias verticais, nunca horizontais.** Um seam, um teste, implementação mínima, repetir. Nunca escrever todos os testes de uma feature antes de qualquer implementação — isso trava a estrutura antes de ela existir de verdade e é tratado como antipadrão pela metodologia.
   - **Confirmar os seams com o usuário antes de escrever qualquer teste.** Proponha o desenho (assinatura da função, o que cada seam cobre) e espere confirmação.
   - **Red antes de green.** Sempre rodar o teste e ver falhar antes de implementar.
   - Refatoração acontece *entre* ciclos, nunca misturada dentro de um passo red→green.

## Mock apenas na fronteira do sistema

Nunca mockamos código nosso — só a FastF1 (a fronteira externa), via injeção de dependência: cada tool recebe um parâmetro `load_*` que em produção aponta pra `fastf1_client.py`. `fastf1_client.py` em si é a própria fronteira, então é testado com **dados reais** (marcado `@pytest.mark.integration`), não mockado.

## Estrutura de cada tool

Cada tool em `src/f1llm/tools/` segue o mesmo formato:
- Validação de entrada (`session_type` ∈ {Race, Qualifying, Sprint}, `year` ∈ [2018, ano atual], pelo menos 1 piloto quando aplicável)
- Transformação de dados brutos da FastF1 em dataclasses próprias (testada com `load_*` mockado)
- Resposta estruturada `found: bool` + `reason` em vez de propagar exceções cruas ou inventar dados quando algo não é encontrado (`SessionDataUnavailable`, definida em `f1llm/errors.py`)
- Construção de gráfico (quando aplicável) como **função pura separada**, sem I/O — testável sem mock (ex: `build_lap_times_chart`, `build_telemetry_chart`). Gráficos usam Plotly (não os helpers matplotlib nativos da FastF1 — ver ADR 0004), com `showgrid: True` explícito em todo eixo.

## Como rodar os testes

```bash
uv run pytest                    # suíte rápida, sem rede — roda a cada alteração
uv run pytest -v                 # com nome de cada teste
uv run pytest -m integration -v  # dados reais da FastF1 — mais lenta na 1ª vez, cacheada depois (.fastf1cache/)
```

## Estado do projeto

Não documentamos aqui quais tools já existem — isso fica desatualizado rápido. Para saber o que já foi implementado: `ls src/f1llm/tools/`, `git log --oneline`, ou rode a suíte de testes.
