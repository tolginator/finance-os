"""Application configuration — env vars + optional JSON config file.

Priority (highest wins): env vars > config file > defaults.
Config file location: ~/.config/finance-os/config.json
"""

import json
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

CONFIG_DIR = Path.home() / ".config" / "finance-os"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _load_config_file() -> dict[str, Any]:
    """Load config from ~/.config/finance-os/config.json if it exists."""
    if CONFIG_FILE.is_file():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {}


class JsonFileSource(PydanticBaseSettingsSource):
    """Settings source that reads from the JSON config file."""

    def get_field_value(
        self, field: Any, field_name: str
    ) -> tuple[Any, str, bool]:
        data = _load_config_file()
        val = data.get(field_name)
        return val, field_name, val is not None

    def __call__(self) -> dict[str, Any]:
        return _load_config_file()


class AppConfig(BaseSettings):
    """Configuration for the finance-os application layer.

    Values can be set via:
    1. Environment variables with FINANCE_OS_ prefix (highest priority)
    2. ~/.config/finance-os/config.json
    3. Built-in defaults
    """

    model_config = {"env_prefix": "FINANCE_OS_"}

    llm_provider: str = "skip"
    llm_default_model: str = "gpt-4o"
    llm_temperature: float = 0.0
    fred_api_key: str = ""
    sec_edgar_email: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-10-21"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            JsonFileSource(settings_cls),
            file_secret_settings,
        )
