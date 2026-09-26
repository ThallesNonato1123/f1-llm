import copy
import json
from datetime import date, timedelta
from types import SimpleNamespace

from f1llm.llm.chat import GAVE_UP_TEXT, MAX_TOOL_ROUNDS, REFUSAL_TEXT, ChatReply, answer


def text(value):
    return SimpleNamespace(type="text", text=value)


def tool_use(id, name, input):
    return SimpleNamespace(type="tool_use", id=id, name=name, input=input)


def reply(*blocks, stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


class ScriptedClaude:
    """Stands in for the Anthropic API: returns scripted responses and records every request."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.requests = []

    def __call__(self, *, system, messages, tools):
        self.requests.append({"system": system, "messages": copy.deepcopy(messages), "tools": tools})
        return self._responses.pop(0)


def test_answers_directly_and_appends_the_exchange_to_the_history():
    history = [
        {"role": "user", "content": "Quem venceu Monza 2024?"},
        {"role": "assistant", "content": "Charles Leclerc."},
    ]
    claude = ScriptedClaude(reply(text("Ele largou em 4º.")))

    result = answer(history, "E de onde ele largou?", create_message=claude, loaders=None)

    assert claude.requests[0]["messages"] == history + [{"role": "user", "content": "E de onde ele largou?"}]
    assert result == ChatReply(
        text="Ele largou em 4º.",
        charts=[],
        history=history + [
            {"role": "user", "content": "E de onde ele largou?"},
            {"role": "assistant", "content": "Ele largou em 4º."},
        ],
    )


MONZA_LAPS = [
    {"Driver": "LEC", "LapNumber": 1.0, "LapTime": timedelta(seconds=85.5)},
    {"Driver": "LEC", "LapNumber": 2.0, "LapTime": timedelta(seconds=84.0)},
]
LAP_TIMES_INPUT = {"year": 2024, "event": "Monza", "session_type": "Race", "drivers": ["LEC"], "plot": True}


def test_runs_the_requested_tool_sends_its_summary_back_and_hands_the_chart_to_the_ui():
    thinking_then_call = reply(
        SimpleNamespace(type="thinking", thinking="", signature="sig"),
        tool_use("toolu_1", "get_lap_times", LAP_TIMES_INPUT),
        stop_reason="tool_use",
    )
    claude = ScriptedClaude(thinking_then_call, reply(text("A melhor volta do LEC foi a 2, em 1:24.0.")))
    loaders = SimpleNamespace(load_laps=lambda year, event, session_type, drivers: MONZA_LAPS)

    result = answer([], "Qual a melhor volta do LEC em Monza 2024?", create_message=claude, loaders=loaders)

    second_request = claude.requests[1]["messages"]
    assert second_request[1] == {"role": "assistant", "content": thinking_then_call.content}
    [tool_result] = second_request[2]["content"]
    assert second_request[2]["role"] == "user"
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "toolu_1"
    assert tool_result["is_error"] is False
    assert json.loads(tool_result["content"])["drivers"][0]["best_lap"] == {"lap": 2, "seconds": 84.0}

    assert result.text == "A melhor volta do LEC foi a 2, em 1:24.0."
    [chart] = result.charts
    assert chart["data"][0]["y"] == [85.5, 84.0]


def test_a_failing_tool_goes_back_to_the_model_as_an_error_it_can_react_to():
    bad_year = {**LAP_TIMES_INPUT, "year": 2017}
    claude = ScriptedClaude(
        reply(tool_use("toolu_1", "get_lap_times", bad_year), stop_reason="tool_use"),
        reply(text("Só tenho dados a partir de 2018.")),
    )

    result = answer(
        [], "Tempos do LEC em Monza 2017?", create_message=claude, loaders=SimpleNamespace(load_laps=None)
    )

    [tool_result] = claude.requests[1]["messages"][2]["content"]
    assert tool_result["is_error"] is True
    assert "year" in json.loads(tool_result["content"])["error"]
    assert result.charts == []


def test_parallel_tool_calls_are_answered_together_in_a_single_message():
    claude = ScriptedClaude(
        reply(
            tool_use("toolu_1", "get_lap_times", LAP_TIMES_INPUT),
            tool_use("toolu_2", "get_lap_times", {**LAP_TIMES_INPUT, "plot": False}),
            stop_reason="tool_use",
        ),
        reply(text("Pronto.")),
    )
    loaders = SimpleNamespace(load_laps=lambda year, event, session_type, drivers: MONZA_LAPS)

    result = answer([], "Compare.", create_message=claude, loaders=loaders)

    messages = claude.requests[1]["messages"]
    assert len(messages) == 3
    assert [r["tool_use_id"] for r in messages[2]["content"]] == ["toolu_1", "toolu_2"]
    assert len(result.charts) == 1


def test_returned_history_keeps_only_the_question_and_final_text_after_tool_calls():
    claude = ScriptedClaude(
        reply(tool_use("toolu_1", "get_lap_times", LAP_TIMES_INPUT), stop_reason="tool_use"),
        reply(text("A melhor foi a volta 2.")),
    )
    loaders = SimpleNamespace(load_laps=lambda year, event, session_type, drivers: MONZA_LAPS)

    result = answer([], "Melhor volta do LEC?", create_message=claude, loaders=loaders)

    assert result.history == [
        {"role": "user", "content": "Melhor volta do LEC?"},
        {"role": "assistant", "content": "A melhor foi a volta 2."},
    ]


def test_stops_calling_tools_after_the_round_limit_and_says_it_could_not_finish():
    endless = [
        reply(tool_use(f"toolu_{n}", "get_lap_times", {**LAP_TIMES_INPUT, "plot": False}), stop_reason="tool_use")
        for n in range(MAX_TOOL_ROUNDS + 1)
    ]
    claude = ScriptedClaude(*endless)
    loaders = SimpleNamespace(load_laps=lambda year, event, session_type, drivers: MONZA_LAPS)

    result = answer([], "Analise tudo.", create_message=claude, loaders=loaders)

    assert MAX_TOOL_ROUNDS == 10
    assert len(claude.requests) == MAX_TOOL_ROUNDS + 1
    assert result.text == GAVE_UP_TEXT
    assert result.history[-1] == {"role": "assistant", "content": GAVE_UP_TEXT}


def test_a_refusal_becomes_a_fixed_reply_instead_of_the_cut_off_text():
    claude = ScriptedClaude(reply(text("Sobre isso eu"), stop_reason="refusal"))

    result = answer([], "Pergunta qualquer", create_message=claude, loaders=None)

    assert result.text == REFUSAL_TEXT
    assert result.history[-1] == {"role": "assistant", "content": REFUSAL_TEXT}


def test_tells_the_model_todays_date_so_it_can_resolve_relative_dates():
    claude = ScriptedClaude(reply(text("...")))

    answer([], "Quem venceu a última corrida?", create_message=claude, loaders=None)

    assert date.today().isoformat() in claude.requests[0]["system"]
