import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "warehouse.db")

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # SoftOne
    SOFTONE_LOGIN_URL = os.getenv("SOFTONE_LOGIN_URL", "https://ifsas.oncloud.gr/s1services")
    SOFTONE_API_URL = os.getenv(
        "SOFTONE_API_URL",
        "https://ifsas.oncloud.gr/s1services/js/CLIfsasWebConnector.S1Lib/ApiServices",
    )
    SOFTONE_USERNAME = os.getenv("SOFTONE_USERNAME", "WebConnector")
    SOFTONE_PASSWORD = os.getenv("SOFTONE_PASSWORD", "WebConnector!1")
    SOFTONE_APPID = os.getenv("SOFTONE_APPID", "2222")
    SOFTONE_COMPANY = os.getenv("SOFTONE_COMPANY", "100")
    SOFTONE_BRANCH = os.getenv("SOFTONE_BRANCH", "1000")
    SOFTONE_MODULE = os.getenv("SOFTONE_MODULE", "0")
    SOFTONE_REFID = os.getenv("SOFTONE_REFID", "2222")

    # Session
    PERMANENT_SESSION_LIFETIME = 86400 * 7  # 7 days
