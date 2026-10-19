from pydantic_settings import BaseSettings, SettingsConfigDict

from f1llm.llm.production import DEFAULT_EFFORT, DEFAULT_MODEL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str | None = None
    anthropic_auth_token: str | None = None
    f1llm_model: str = DEFAULT_MODEL
    f1llm_effort: str = DEFAULT_EFFORT

    def has_anthropic_credentials(self) -> bool:
        return bool(self.anthropic_api_key or self.anthropic_auth_token)


def get_settings() -> Settings:
    return Settings()
