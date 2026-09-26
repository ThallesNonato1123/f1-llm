import anthropic
import pytest

from f1llm import fastf1_client
from f1llm.llm.chat import answer
from f1llm.llm.cli import DEFAULT_EFFORT, DEFAULT_MODEL, claude_create_message


@pytest.mark.integration
def test_real_claude_answers_from_real_fastf1_data_and_plots_on_request():
    """Costs a few cents: proves the API accepts our tool schemas and the loop closes."""
    create_message = claude_create_message(anthropic.Anthropic(), model=DEFAULT_MODEL, effort=DEFAULT_EFFORT)

    reply = answer(
        [],
        "Quem venceu a corrida de Monza em 2024? Mostre um gráfico dos tempos de volta do vencedor.",
        create_message=create_message,
        loaders=fastf1_client,
    )

    assert "Leclerc" in reply.text
    assert reply.charts, "expected the model to ask for a chart"
    assert reply.history[-1] == {"role": "assistant", "content": reply.text}
