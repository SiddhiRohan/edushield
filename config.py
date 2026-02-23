# QuantumLeap - configuration
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "dev-secret-change-in-production"
    database_url: str = "sqlite+aiosqlite:///./quantumleap.db"
    openai_api_key: str = ""
    openai_base_url: str = "http://localhost:11434/v1"  # Ollama default
    data_dir: Path = Path("./data")
    pdf_dir: Path = Path("./data/pdfs")
    faiss_index_path: Path = Path("./data/faiss_index")

    class Config:
        env_file = ".env"
        extra = "ignore"


def get_settings() -> Settings:
    return Settings()
