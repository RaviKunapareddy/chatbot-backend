# Cloud-only environment variable configuration for production deployment
# All services require cloud credentials - no localhost fallbacks
import os

from dotenv import load_dotenv

# Load environment variables from .env file without overriding actual environment vars
if os.path.exists(".env"):
    load_dotenv(".env", override=False)

from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Project identification - environment-specific
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "chatbot-api")
    PROJECT_ID: str = os.getenv("PROJECT_ID", "local-test")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Redis settings with security
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PREFIX: str = f"{PROJECT_ID}:"
    REDIS_USERNAME: Optional[str] = os.getenv("REDIS_USERNAME")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")

    # Pinecone settings
    PINECONE_API_KEY: Optional[str] = os.getenv("PINECONE_API_KEY")
    PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
    PINECONE_PRODUCTS_INDEX: str = os.getenv("PINECONE_PRODUCTS_INDEX", "chatbot-products")
    PINECONE_SUPPORT_INDEX: str = os.getenv("PINECONE_SUPPORT_INDEX", "chatbot-support")

    # AWS settings
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_DEFAULT_REGION: Optional[str] = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    AWS_BEDROCK_MODEL_ID: Optional[str] = os.getenv("AWS_BEDROCK_MODEL_ID")

    # S3 settings
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "chatbot-products-data")
    S3_PRODUCTS_KEY: str = os.getenv("S3_PRODUCTS_KEY", "products.json")
    S3_SUPPORT_KNOWLEDGE_KEY: str = os.getenv("S3_SUPPORT_KNOWLEDGE_KEY", "support_knowledge_base.json")

    # LLM settings
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    GEMINI_MODEL: Optional[str] = os.getenv("GEMINI_MODEL")

    # HuggingFace settings
    HF_API_KEY: Optional[str] = os.getenv("HF_API_KEY")
    HF_PRODUCT_MODEL: str = os.getenv("HF_PRODUCT_MODEL", "BAAI/bge-small-en-v1.5")
    HF_SUPPORT_MODEL: str = os.getenv("HF_SUPPORT_MODEL", "BAAI/bge-small-en-v1.5")

    # GitHub Webhook settings
    GITHUB_WEBHOOK_SECRET: Optional[str] = os.getenv("GITHUB_WEBHOOK_SECRET")

    # CORS settings (driven entirely by environment; no hardcoded defaults)
    ALLOWED_ORIGINS: Optional[str] = os.getenv("ALLOWED_ORIGINS")

    # Search behavior flags (env-driven)
    # Enable server-side tag filtering in Pinecone via precomputed tag_* flags
    SEARCH_TAGS_SERVER_FILTER_ENABLED: bool = os.getenv(
        "SEARCH_TAGS_SERVER_FILTER_ENABLED", "false"
    ).lower() in ("1", "true", "yes")
    # Enable case-insensitive brand/category filtering in Pinecone via *_lc fields
    SEARCH_CASE_INSENSITIVE: bool = os.getenv("SEARCH_CASE_INSENSITIVE", "false").lower() in (
        "1",
        "true",
        "yes",
    )

    @property
    def ALLOWED_ORIGINS_LIST(self) -> List[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a list.
        Example: "https://www.ravii.app,https://ravii.app,http://localhost:5173"
        """
        raw = self.ALLOWED_ORIGINS or ""
        return [o.strip() for o in raw.split(",") if o and o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from .env file


settings = Settings()
