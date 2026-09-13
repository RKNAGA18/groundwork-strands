"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Groundwork application settings.

    All settings can be overridden via environment variables or a .env file.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # AWS Bedrock
    AWS_REGION: str = "us-east-1"

    # Model configuration
    LLM_MODEL: str = "anthropic.claude-3-haiku-20240307-v1:0"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    # Storage paths
    CHROMA_PATH: str = "./chroma_data"
    UPLOAD_DIR: str = "./uploads"

    # Pipeline parameters
    TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 4.3
    DRAFT_TEMPERATURE: float = 0.2
    VERIFY_TEMPERATURE: float = 0.0

    # Parallelism
    MAX_WORKERS: int = 5


# Singleton instance
settings = Settings()
