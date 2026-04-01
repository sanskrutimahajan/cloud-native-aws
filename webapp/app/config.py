"""
Config - Loads settings from .env file (no hard-coded credentials)
"""

import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env file


class Settings:
    # Database settings
    DATABASE_HOST: str = os.getenv("DATABASE_HOST", "localhost")
    DATABASE_PORT: str = os.getenv("DATABASE_PORT", "5432")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "webapp_db")
    DATABASE_USER: str = os.getenv("DATABASE_USER", "webapp_user")
    DATABASE_PASSWORD: str = os.getenv("DATABASE_PASSWORD", "")

    # App settings
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8080"))

    # S3 settings (injected via EC2 user data)
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "")

    # SNS settings
    SNS_TOPIC_ARN: str = os.getenv("SNS_TOPIC_ARN", "")

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"


settings = Settings()
