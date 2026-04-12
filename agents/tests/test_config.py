"""Tests for application config."""

import json

from src.application.config import AppConfig


class TestAppConfig:
    def test_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "src.application.config.CONFIG_FILE", tmp_path / "nonexistent.json"
        )
        config = AppConfig()
        assert config.llm_provider == "skip"
        assert config.llm_default_model == "gpt-4o"
        assert config.llm_temperature == 0.0
        assert config.fred_api_key == ""

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("FINANCE_OS_LLM_PROVIDER", "azure_openai")
        monkeypatch.setenv("FINANCE_OS_AZURE__DEPLOYMENT", "gpt-4o")
        config = AppConfig()
        assert config.llm_provider == "azure_openai"
        assert config.azure.deployment == "gpt-4o"

    def test_fred_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("FINANCE_OS_FRED_API_KEY", "test-key-123")
        config = AppConfig()
        assert config.fred_api_key == "test-key-123"

    def test_config_file_loads(self, tmp_path, monkeypatch):
        cfg = {"fred_api_key": "file-key-456", "llm_provider": "azure_openai"}
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps(cfg))
        monkeypatch.setattr("src.application.config.CONFIG_FILE", cfg_file)
        config = AppConfig()
        assert config.fred_api_key == "file-key-456"
        assert config.llm_provider == "azure_openai"

    def test_env_overrides_config_file(self, tmp_path, monkeypatch):
        cfg = {"fred_api_key": "file-key", "llm_provider": "azure_openai"}
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps(cfg))
        monkeypatch.setattr("src.application.config.CONFIG_FILE", cfg_file)
        monkeypatch.setenv("FINANCE_OS_FRED_API_KEY", "env-key")
        config = AppConfig()
        assert config.fred_api_key == "env-key"
        assert config.llm_provider == "azure_openai"

    def test_missing_config_file_uses_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "src.application.config.CONFIG_FILE", tmp_path / "nonexistent.json"
        )
        config = AppConfig()
        assert config.fred_api_key == ""
        assert config.llm_provider == "skip"

    def test_nested_azure_from_config_file(self, tmp_path, monkeypatch):
        cfg = {
            "llm_provider": "azure_openai",
            "azure": {
                "endpoint": "https://my-instance.openai.azure.com",
                "deployment": "gpt-4o",
            },
        }
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps(cfg))
        monkeypatch.setattr("src.application.config.CONFIG_FILE", cfg_file)
        config = AppConfig()
        assert config.llm_provider == "azure_openai"
        assert config.azure.endpoint == "https://my-instance.openai.azure.com"
        assert config.azure.deployment == "gpt-4o"
        assert config.azure.api_version == "2024-10-21"

    def test_azure_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "src.application.config.CONFIG_FILE", tmp_path / "nonexistent.json"
        )
        config = AppConfig()
        assert config.azure.endpoint == ""
        assert config.azure.deployment == ""
        assert config.azure.api_version == "2024-10-21"
