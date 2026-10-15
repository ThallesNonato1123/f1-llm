from types import SimpleNamespace

import anthropic
import httpx
from fastapi.testclient import TestClient

from f1llm.api.app import UPSTREAM_ERROR_TEXT, app, get_create_message, get_loaders


def text(value):
    return SimpleNamespace(type="text", text=value)


def reply(*blocks, stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


class ScriptedClaude:
    def __init__(self, *responses):
        self._responses = list(responses)

    def __call__(self, *, system, messages, tools):
        return self._responses.pop(0)


def test_chat_answers_directly_and_appends_the_exchange_to_the_history():
    history = [
        {"role": "user", "content": "Quem venceu Monza 2024?"},
        {"role": "assistant", "content": "Charles Leclerc."},
    ]
    claude = ScriptedClaude(reply(text("Ele largou em 4º.")))
    app.dependency_overrides[get_create_message] = lambda: claude
    app.dependency_overrides[get_loaders] = lambda: None

    with TestClient(app) as client:
        response = client.post("/chat", json={"question": "E de onde ele largou?", "history": history})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "text": "Ele largou em 4º.",
        "charts": [],
        "history": history + [
            {"role": "user", "content": "E de onde ele largou?"},
            {"role": "assistant", "content": "Ele largou em 4º."},
        ],
    }


def test_chat_returns_503_when_the_anthropic_api_fails():
    def failing_create_message(*, system, messages, tools):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))

    app.dependency_overrides[get_create_message] = lambda: failing_create_message
    app.dependency_overrides[get_loaders] = lambda: None

    with TestClient(app) as client:
        response = client.post("/chat", json={"question": "Qualquer coisa", "history": []})

    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": UPSTREAM_ERROR_TEXT}


def test_chat_allows_cross_origin_requests():
    app.dependency_overrides[get_create_message] = lambda: ScriptedClaude(reply(text("...")))
    app.dependency_overrides[get_loaders] = lambda: None

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"question": "Qualquer coisa", "history": []},
            headers={"Origin": "http://127.0.0.1:5500"},
        )

    app.dependency_overrides.clear()

    assert response.headers["access-control-allow-origin"] == "*"


def test_health_reports_ok():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_serves_the_frontend_page():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "f1llm" in response.text


def test_chat_returns_503_when_no_anthropic_credentials_are_configured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    app.dependency_overrides[get_loaders] = lambda: None
    # get_create_message is NOT overridden here: this exercises the real production wiring.

    with TestClient(app) as client:
        response = client.post("/chat", json={"question": "Qualquer coisa", "history": []})

    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": UPSTREAM_ERROR_TEXT}
