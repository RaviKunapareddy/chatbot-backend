# Cloud-only environment variable configuration for production deployment
# All services require cloud credentials - no localhost fallbacks
from dotenv import load_dotenv
load_dotenv()

from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Project identification - environment-specific
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "chatbot-api")
    PROJECT_ID: str = os.getenv("PROJECT_ID", "local-test")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Redis settings with security
    REDIS_HOST: str
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PREFIX: str = f"{PROJECT_ID}:"
    REDIS_PASSWORD: Optional[str] = None
    
    # Pinecone settings
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
    PINECONE_PRODUCTS_INDEX: str = os.getenv("PINECONE_PRODUCTS_INDEX", "chatbot-products")
    PINECONE_SUPPORT_INDEX: str = os.getenv("PINECONE_SUPPORT_INDEX", "chatbot-support")
    
    # AWS settings
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_DEFAULT_REGION: Optional[str] = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    AWS_BEDROCK_MODEL_ID: Optional[str] = None
    
    # S3 settings
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "chatbot-products-data")
    S3_PRODUCTS_KEY: str = os.getenv("S3_PRODUCTS_KEY", "products.json")
    
    # LLM settings
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: Optional[str] = None
    
    # HuggingFace settings
    HF_API_KEY: Optional[str] = None
    HF_PRODUCT_MODEL: str = os.getenv("HF_PRODUCT_MODEL", "BAAI/bge-small-en-v1.5")
    HF_SUPPORT_MODEL: str = os.getenv("HF_SUPPORT_MODEL", "BAAI/bge-small-en-v1.5")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from .env file

settings = Settings() 