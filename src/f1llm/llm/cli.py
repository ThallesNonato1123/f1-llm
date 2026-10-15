"""Terminal chat to try the LLM layer: uv run f1llm-chat"""

import os

import anthropic
import fastf1

from f1llm import fastf1_client
from f1llm.llm.chat import answer
from f1llm.llm.production import DEFAULT_EFFORT, DEFAULT_MODEL, claude_create_message
from f1llm.preview import open_in_browser

EXIT_WORDS = {"sair", "exit", "quit"}


def main() -> None:
    fastf1.set_log_level("ERROR")
    model = os.environ.get("F1LLM_MODEL", DEFAULT_MODEL)
    effort = os.environ.get("F1LLM_EFFORT", DEFAULT_EFFORT)
    create_message = claude_create_message(anthropic.Anthropic(), model=model, effort=effort)

    print(f"f1llm-chat ({model}, effort {effort}). Digite 'sair' para encerrar.\n")
    history: list[dict] = []
    while True:
        try:
            question = input("você> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question:
            continue
        if question.lower() in EXIT_WORDS:
            return

        try:
            reply = answer(history, question, create_message=create_message, loaders=fastf1_client)
        except anthropic.APIError as exc:
            # The question is dropped from the history, so the user can simply ask again.
            print(f"\n[erro na API da Anthropic: {exc}]\n")
            continue

        history = reply.history
        print(f"\nf1llm> {reply.text}\n")
        for figure in reply.charts:
            path = open_in_browser(figure, title=figure["layout"].get("title") or "f1llm")
            print(f"[gráfico: {path}]")
        if reply.charts:
            print()
