from f1llm.llm.production import DEFAULT_EFFORT, DEFAULT_MODEL
from f1llm.settings import get_settings


def test_get_settings_reads_anthropic_api_key_from_the_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    settings = get_settings()

    assert settings.anthropic_api_key == "sk-ant-test"


def test_get_settings_falls_back_to_the_default_model_and_effort(monkeypatch):
    monkeypatch.delenv("F1LLM_MODEL", raising=False)
    monkeypatch.delenv("F1LLM_EFFORT", raising=False)

    settings = get_settings()

    assert settings.f1llm_model == DEFAULT_MODEL
    assert settings.f1llm_effort == DEFAULT_EFFORT


def test_get_settings_reads_model_and_effort_overrides_from_the_environment(monkeypatch):
    monkeypatch.setenv("F1LLM_MODEL", "claude-haiku-4-5-20251001")
    monkeypatch.setenv("F1LLM_EFFORT", "low")

    settings = get_settings()

    assert settings.f1llm_model == "claude-haiku-4-5-20251001"
    assert settings.f1llm_effort == "low"


def test_has_anthropic_credentials_is_false_when_neither_is_set(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    assert get_settings().has_anthropic_credentials() is False


def test_has_anthropic_credentials_is_true_when_the_api_key_is_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    assert get_settings().has_anthropic_credentials() is True


def test_has_anthropic_credentials_is_true_when_the_auth_token_is_set(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "auth-token-test")

    assert get_settings().has_anthropic_credentials() is True
