from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""

    # Which backend to use: "azure_openai" or "foundry" (Azure AI Foundry).
    llm_provider: str = "azure_openai"

    # Embedding vector size. Must match the model / column:
    #   text-embedding-3-large -> 3072 (default)
    #   text-embedding-3-small -> 1536
    # (or whatever you pass to the embeddings `dimensions` parameter)
    embedding_dim: int = 3072

    # --- Azure OpenAI ---
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    embedding_deployment: str = "text-embedding-3-large"
    chat_deployment: str = "gpt-4o-mini"

    # --- Azure AI Foundry (model inference endpoint) ---
    foundry_endpoint: str = ""          # https://<resource>.services.ai.azure.com/models
    foundry_api_key: str = ""
    foundry_api_version: str = "2024-05-01-preview"
    foundry_embedding_model: str = "text-embedding-3-large"
    foundry_chat_model: str = "gpt-4o-mini"

    top_k: int = 4
    allowed_origins: str = "*"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
