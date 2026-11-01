from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings live here, in one place.
    Values come from the .env file, so no secrets are hardcoded."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "groq"             # "groq" or "gemini"
    groq_api_key: str = ""
    google_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chroma_dir: str = "chroma_db"
    collection_name: str = "tech_docs"
    data_dir: str = "data"

    top_k: int = 4                         # how many chunks to retrieve
    max_retries: int = 2                   # how many times we may rewrite and retry
    max_regenerations: int = 1             # how many times we may regenerate after a failed grounding check

    feedback_db: str = "feedback.db"
    max_upload_bytes: int = 1_000_000      # 1 MB per file or URL


settings = Settings()