from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    dashboard_user: str = "admin"
    dashboard_password: str | None = None
    require_dashboard_auth: bool = False
    database_url: str = "sqlite:///./voc.db"
    openai_api_key: str | None = None
    openai_model: str = "gpt-6-luna"
    reddit_user_agent: str = "live-commerce-voc/0.1"
    reddit_bearer_token: str | None = None
    @field_validator("database_url")
    @classmethod
    def use_psycopg_for_postgres(cls, value: str) -> str:
        # Neon provides standard PostgreSQL URLs; use our installed psycopg 3 driver.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
