"""Production wiring for answer()'s create_message: one real Anthropic Messages API call."""

import anthropic

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "medium"
MAX_TOKENS = 16000


def claude_create_message(client: anthropic.Anthropic, *, model: str, effort: str):
    def create_message(*, system, messages, tools):
        return client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            tools=tools,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
        )

    return create_message
