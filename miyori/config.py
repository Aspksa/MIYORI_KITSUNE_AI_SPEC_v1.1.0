from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    root_dir: Path = ROOT_DIR
    data_dir: Path = ROOT_DIR / "data"
    database_path: Path = ROOT_DIR / "data" / "miyori.sqlite3"
    cloudru_api_key: str = os.getenv("CLOUDRU_API_KEY", "").strip()
    cloudru_base_url: str = os.getenv(
        "CLOUDRU_BASE_URL", "https://foundation-models.api.cloud.ru/v1"
    ).rstrip("/")
    cloudru_model_id: str = os.getenv("CLOUDRU_MODEL_ID", "").strip()
    # Optional user-supplied rates. An unset rate means unknown price, not zero cost.
    cloudru_input_rub_per_million: float = float(
        os.getenv("CLOUDRU_INPUT_RUB_PER_1M_TOKENS", "0")
    )
    cloudru_output_rub_per_million: float = float(
        os.getenv("CLOUDRU_OUTPUT_RUB_PER_1M_TOKENS", "0")
    )
    host: str = os.getenv("MIYORI_HOST", "127.0.0.1").strip()
    port: int = int(os.getenv("MIYORI_PORT", "8765"))
    open_browser: bool = os.getenv("MIYORI_OPEN_BROWSER", "1").strip() not in {"0", "false", "False"}


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
