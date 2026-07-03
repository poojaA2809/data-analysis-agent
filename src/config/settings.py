from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(default="sqlite:///./data/agent.db")
    log_level: str = Field(default="INFO")

    # Agent loop / executor bounds
    max_steps: int = Field(default=4)       # AGENT_MAX_STEPS — code→fix cycles cap
    exec_timeout: int = Field(default=25)   # AGENT_EXEC_TIMEOUT — subprocess seconds

    # LLM provider — auto-detected from whichever key is set if left blank
    llm_provider: str = Field(default="")   # "anthropic" | "gemini"
    llm_model: str = Field(default="")      # uses provider default when blank

    # Provider keys — set exactly one
    anthropic_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")

    # Cost metering — USD per 1M tokens (gemini-2.5-flash current pricing).
    # AGENT_COST_INPUT_PER_MTOK / AGENT_COST_OUTPUT_PER_MTOK to override.
    cost_input_per_mtok: float = Field(default=0.30)
    cost_output_per_mtok: float = Field(default=2.50)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
