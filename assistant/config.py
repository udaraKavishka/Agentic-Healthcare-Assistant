from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # `extra="ignore"` so a .env carrying keys this service does not read
    # cannot stop it from starting.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Agentic Healthcare Assistant"
    ENVIRONMENT: str = "local"
    LOG_LEVEL: str = "INFO"

    CORS_ORIGINS: str = "http://localhost:8501"

    GROQ_API_KEY: str = ""
    # Routing and tool arguments are classification work, so they run on the
    # cheaper model; the patient-facing answer runs on the larger one.
    ROUTER_MODEL: str = "openai/gpt-oss-20b"
    ANSWER_MODEL: str = "openai/gpt-oss-120b"
    REQUESTS_PER_MINUTE: int = 30
    TOKENS_PER_MINUTE: int = 8_000
    # How long a caller will wait for rate-limit headroom before being told
    # the assistant is busy. Batch commands raise it; a patient will not wait.
    MAX_LIMIT_WAIT_SECONDS: float = 20.0

    SOURCE_SQL: Path = ROOT / "knowledge" / "data.sql"
    HOSPITAL_DB: Path = ROOT / "knowledge" / "hospital.db"
    SCRAPED_DIR: Path = ROOT / "knowledge" / "scraped"
    FAQ_PATH: Path = ROOT / "knowledge" / "faq.yml"
    # Written by `make index` from the FAQ sections the website publishes.
    HARVESTED_FAQ_PATH: Path = ROOT / "knowledge" / "faq.harvested.yml"
    QDRANT_PATH: Path = ROOT / "knowledge" / "qdrant"
    CONVERSATIONS_DB: Path = ROOT / "knowledge" / "conversations.db"

    RETRIEVE_TOP_K: int = 5
    # Nearly identical questions are grouped together.
    FAQ_THRESHOLD: float = 0.88
    # Turns kept verbatim for pronoun resolution; older ones are dropped so a
    # long conversation cannot grow past the minute's token budget.
    VERBATIM_TURNS: int = 6

    MAX_SQL_ROWS: int = 50
    SQL_TIMEOUT_SECONDS: float = 5.0

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin]


settings = Settings()
