import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


PLACEHOLDER_VALUES = {
    "",
    "your_groq_key",
    "your_hindsight_key",
    "your_real_groq_key_here",
    "your_real_hindsight_key_here",
    "your_real_key_here",
    "your_real_api_key_here",
    "placeholder",
    "changeme",
    "<your_groq_key>",
    "<your_hindsight_key>",
    "your_api_key",
    "your_key_here",
    "example",
    "test",
    "dummy",
    "fake",
}


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    cleaned = value.strip()
    if not cleaned:
        return True
    lowered = cleaned.lower()
    if lowered in PLACEHOLDER_VALUES:
        return True
    if lowered.startswith("your_") or lowered.startswith("example") or lowered.startswith("dummy"):
        return True
    return False


@dataclass(frozen=True)
class Settings:
    app_name: str = "Project Arbitrage"
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    hindsight_api_key: str = os.getenv("HINDSIGHT_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    hindsight_api_url: str = os.getenv("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")
    hindsight_bank_id: str = os.getenv("HINDSIGHT_BANK_ID", "project-arbitrage")
    use_mock_ai: bool = str(os.getenv("USE_MOCK_AI", "false")).lower() == "true"
    market_data_api_url: str = os.getenv("MARKET_DATA_API_URL", "https://api.frankfurter.dev/v1")
    market_base_currency: str = os.getenv("MARKET_BASE_CURRENCY", "USD").upper()
    market_quote_currency: str = os.getenv("MARKET_QUOTE_CURRENCY", "INR").upper()
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:8001")
    portfolio_database_path: str = os.getenv(
        "PORTFOLIO_DATABASE_PATH",
        str(BASE_DIR / "backend" / "data" / "project_arbitrage.sqlite3"),
    )

    @property
    def groq_configured(self) -> bool:
        return not is_placeholder(self.groq_api_key)

    @property
    def hindsight_configured(self) -> bool:
        return not is_placeholder(self.hindsight_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name="Project Arbitrage",
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        hindsight_api_key=os.getenv("HINDSIGHT_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        hindsight_api_url=os.getenv("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io"),
        hindsight_bank_id=os.getenv("HINDSIGHT_BANK_ID", "project-arbitrage"),
        use_mock_ai=str(os.getenv("USE_MOCK_AI", "false")).lower() == "true",
        market_data_api_url=os.getenv("MARKET_DATA_API_URL", "https://api.frankfurter.dev/v1"),
        market_base_currency=os.getenv("MARKET_BASE_CURRENCY", "USD").upper(),
        market_quote_currency=os.getenv("MARKET_QUOTE_CURRENCY", "INR").upper(),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:8001"),
        portfolio_database_path=os.getenv(
            "PORTFOLIO_DATABASE_PATH",
            str(BASE_DIR / "backend" / "data" / "project_arbitrage.sqlite3"),
        ),
    )


settings = get_settings()
