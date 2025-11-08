from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "VyaparAI"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str
    REDIS_URL: str

    # AWS Settings
    AWS_REGION: str = "ap-south-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    DYNAMODB_ENDPOINT: Optional[str] = None

    # DynamoDB Tables
    DYNAMODB_ORDERS_TABLE: Optional[str] = "vyaparai-orders-dev"
    DYNAMODB_STORES_TABLE: Optional[str] = "vyaparai-stores-dev"
    DYNAMODB_CUSTOMERS_TABLE: Optional[str] = "vyaparai-customers-dev"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # WebSocket
    SOCKETIO_CORS_ORIGINS: str = "http://localhost:3000"

    # Google APIs
    GOOGLE_API_KEY: str

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"

settings = Settings()
