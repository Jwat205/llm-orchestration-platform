# fastapi-service/app/config.py
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional

# Load .env from project root
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
load_dotenv(dotenv_path)

class Settings(BaseSettings):
    ENV:         str             = Field(default="development", env="ENV")
    DEBUG:       bool            = Field(default=True,       env="DEBUG")
    ALLOWED_ORIGINS: List[str]   = ["http://localhost:8000", "http://localhost:3000", "*"]
    DATABASE_URL:    str         = Field(default="",         env="DATABASE_URL")
    REDIS_URL:       str         = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    LLM_MODEL_PATH:  str         = Field(default="/models/llm/",              env="LLM_MODEL_PATH")
    DJANGO_AUTH_URL: str         = Field(default="http://localhost:8000/api/auth/internal/validate-token/", env="DJANGO_AUTH_URL")
    JWT_SECRET_KEY:  str         = Field(default="insecure-dev-key",        env="JWT_SECRET_KEY")

    # Vector store (required)
    pinecone_api_key: str         = Field(..., env="PINECONE_API_KEY")
    pinecone_env:     str         = Field(..., env="PINECONE_ENV")
    pinecone_index:   str         = Field(..., env="PINECONE_INDEX")

    # Neo4j (required)
    neo4j_uri:      str           = Field(..., env="NEO4J_URI")
    neo4j_user:     str           = Field(..., env="NEO4J_USER")
    neo4j_password: str           = Field(..., env="NEO4J_PASSWORD")

    # Auth (required)
    api_key:        str           = Field(..., env="API_KEY")

    class Config:
        env_file  = dotenv_path
        case_sensitive = False

# Instantiate once for your app
settings = Settings()