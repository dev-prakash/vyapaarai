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

    # DynamoDB Tables - Core
    DYNAMODB_ORDERS_TABLE: Optional[str] = "vyaparai-orders-dev"
    DYNAMODB_STORES_TABLE: Optional[str] = "vyaparai-stores-dev"
    DYNAMODB_CUSTOMERS_TABLE: Optional[str] = "vyaparai-customers-dev"

    # DynamoDB Tables - Khata (Digital Credit Management)
    DYNAMODB_KHATA_TRANSACTIONS_TABLE: Optional[str] = "vyaparai-khata-transactions-dev"
    DYNAMODB_CUSTOMER_BALANCES_TABLE: Optional[str] = "vyaparai-customer-balances-dev"
    DYNAMODB_PAYMENT_REMINDERS_TABLE: Optional[str] = "vyaparai-payment-reminders-dev"
    DYNAMODB_IDEMPOTENCY_KEYS_TABLE: Optional[str] = "vyaparai-idempotency-keys-dev"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # WebSocket
    SOCKETIO_CORS_ORIGINS: str = "http://localhost:3000"

    # Google APIs
    GOOGLE_API_KEY: str

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    # Firebase Cloud Messaging
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None  # Base64 encoded service account JSON
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None  # Path to service account JSON file
    FIREBASE_PROJECT_ID: str = "vyapaarai-barcode-scanner"
    ENABLE_PUSH_NOTIFICATIONS: bool = True

    # Gupshup SMS Service (for OTP delivery)
    # Sign up at https://enterprise.smsgupshup.com/
    GUPSHUP_USERID: Optional[str] = None
    GUPSHUP_PASSWORD: Optional[str] = None
    GUPSHUP_SENDER_ID: str = "VYAPAR"  # 6 character sender ID registered with DLT
    GUPSHUP_ENTITY_ID: Optional[str] = None  # DLT Principal Entity ID (required for India)
    GUPSHUP_OTP_TEMPLATE_ID: Optional[str] = None  # DLT registered OTP template ID
    GUPSHUP_PAYMENT_REMINDER_TEMPLATE_ID: Optional[str] = None  # DLT template for payment reminders
    GUPSHUP_PAYMENT_CONFIRM_TEMPLATE_ID: Optional[str] = None  # DLT template for payment confirmations
    GUPSHUP_CREDIT_SALE_TEMPLATE_ID: Optional[str] = None  # DLT template for credit sale notifications
    ENABLE_SMS: bool = True  # Master toggle for SMS service

    # Khata Rate Limiting
    MAX_REMINDERS_PER_CUSTOMER_PER_DAY: int = 3  # Max SMS reminders per customer per day
    MAX_REMINDERS_PER_STORE_PER_HOUR: int = 100  # Max SMS reminders per store per hour

    # Khata Encryption
    KHATA_ENCRYPTION_KEY: Optional[str] = None  # Fernet key for PII encryption (32 chars base64)

    class Config:
        env_file = ".env"
        extra = "ignore"  # Allow extra fields in .env without validation errors

settings = Settings()
