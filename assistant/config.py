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

    SOURCE_SQL: Path = ROOT / "knowledge" / "data.sql"
    HOSPITAL_DB: Path = ROOT / "knowledge" / "hospital.db"
    SCRAPED_DIR: Path = ROOT / "knowledge" / "scraped"
    QDRANT_PATH: Path = ROOT / "knowledge" / "qdrant"

    MAX_SQL_ROWS: int = 50
    SQL_TIMEOUT_SECONDS: float = 5.0

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin]


settings = Settings()
