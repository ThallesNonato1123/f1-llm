import json
from dataclasses import dataclass
from datetime import date

from f1llm.llm.tools import TOOL_DEFINITIONS, run_tool

MAX_TOOL_ROUNDS = 10
GAVE_UP_TEXT = (
    "Não consegui concluir a análise: precisei de consultas demais aos dados. "
    "Tente uma pergunta mais específica."
)
REFUSAL_TEXT = "Não posso responder a essa pergunta."

SYSTEM_PROMPT = """You are a Formula 1 data analyst in a chat app. Today is {today}.

Answer questions about F1 sessions from 2018 onwards using the tools, which read official timing data. \
Every number you state must come from a tool result; if the tools cannot answer, say so instead of guessing. \
When the user refers to a date relatively ("last race", "this season"), work it out from today's date.

Set plot to true when the user asks for a chart, a comparison, or something easier to see than to read; the \
chart is shown to the user beside your answer, so describe what it shows instead of repeating every number.

If a tool returns an error, fix the input and retry when the fix is clear (e.g. a different event name); \
otherwise explain the problem to the user.

Reply in the user's language, defaulting to Brazilian Portuguese. Be concise."""


@dataclass(frozen=True)
class ChatReply:
    text: str
    charts: list[dict]
    history: list[dict]


def answer(history: list[dict], question: str, *, create_message, loaders) -> ChatReply:
    conversation = history + [{"role": "user", "content": question}]
    # The tool round trips live only inside this question; the returned history keeps plain text.
    messages = list(conversation)
    charts = []
    system = SYSTEM_PROMPT.format(today=date.today().isoformat())

    response = create_message(system=system, messages=messages, tools=TOOL_DEFINITIONS)
    rounds = 0
    while response.stop_reason == "tool_use":
        if rounds == MAX_TOOL_ROUNDS:
            return _reply(conversation, GAVE_UP_TEXT, charts)
        rounds += 1
        # The whole assistant turn goes back unchanged: the API needs its thinking and tool_use blocks.
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            outcome = run_tool(block.name, block.input, loaders=loaders)
            if outcome.figure is not None:
                charts.append(outcome.figure)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(outcome.content),
                    "is_error": outcome.is_error,
                }
            )
        messages.append({"role": "user", "content": tool_results})
        response = create_message(system=system, messages=messages, tools=TOOL_DEFINITIONS)

    if response.stop_reason == "refusal":
        return _reply(conversation, REFUSAL_TEXT, charts)
    final_text = "".join(block.text for block in response.content if block.type == "text")
    return _reply(conversation, final_text, charts)


def _reply(conversation: list[dict], text: str, charts: list[dict]) -> ChatReply:
    return ChatReply(
        text=text,
        charts=charts,
        history=conversation + [{"role": "assistant", "content": text}],
    )
