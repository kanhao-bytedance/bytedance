from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./voc.db"
    openai_api_key: str | None = None
    openai_model: str = "gpt-6-luna"
    reddit_user_agent: str = "live-commerce-voc/0.1"
    reddit_bearer_token: str | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
