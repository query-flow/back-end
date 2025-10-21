import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
DOTENV_PATH = (Path(__file__).resolve().parent.parent.parent / ".env")
load_dotenv(dotenv_path=DOTENV_PATH, override=True)


class Settings:
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview").strip()
    DISABLE_AZURE_LLM: bool = os.getenv("DISABLE_AZURE_LLM", "0").strip() in {"1", "true", "True", "YES", "yes"}

    # Database Configuration
    CONFIG_DB_URL: str = os.getenv(
        "CONFIG_DB_URL",
        "mysql+pymysql://user:pass@127.0.0.1:3306/empresas?charset=utf8mb4"
    ).strip()

    # Security Configuration
    FERNET_KEY_B64: str = os.getenv("FERNET_KEY", "").strip()

    # Superadmin Configuration (optional seed)
    SUPERADMIN_NAME: str = os.getenv("SUPERADMIN_NAME", "").strip()
    SUPERADMIN_EMAIL: str = os.getenv("SUPERADMIN_EMAIL", "").strip()
    SUPERADMIN_API_KEY: str = os.getenv("SUPERADMIN_API_KEY", "").strip()

    # App Configuration
    APP_TITLE: str = "NL→SQL Multi-Org (MySQL) + RBAC + Bootstrap + Docs + Insights"

    # Cache Configuration
    SCHEMA_INDEX_MAX_AGE: float = 300.0  # 5 minutes

    def validate(self):
        if not self.FERNET_KEY_B64:
            raise RuntimeError(
                "FERNET_KEY ausente no .env. Gere com: "
                "from cryptography.fernet import Fernet; Fernet.generate_key().decode()"
            )


settings = Settings()
settings.validate()
