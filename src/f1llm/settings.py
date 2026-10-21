from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from f1llm.llm.production import DEFAULT_EFFORT, DEFAULT_MODEL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: SecretStr | None = None
    anthropic_auth_token: SecretStr | None = None
    f1llm_model: str = DEFAULT_MODEL
    f1llm_effort: str = DEFAULT_EFFORT
    f1_username: str | None = None
    f1_password: SecretStr | None = None

    def has_anthropic_credentials(self) -> bool:
        return bool(self.anthropic_api_key or self.anthropic_auth_token)

    def has_f1tv_credentials(self) -> bool:
        return bool(self.f1_username and self.f1_password)


def get_settings() -> Settings:
    return Settings()
