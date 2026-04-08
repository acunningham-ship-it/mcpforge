"""Tests for MCPForge configuration system."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure root is in path
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from mcpforge.config import load_config, get_config_source, ConfigError, _find_config_file


class TestLoadConfig:
    """Test config loading from files and environment."""

    def test_default_config(self):
        """Test default config when no file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp dir so no config files are found
            old_cwd = os.getcwd()
            old_home = os.environ.get("HOME")
            try:
                os.chdir(tmpdir)
                os.environ["HOME"] = tmpdir
                # Clear any MCPFORGE env vars
                for key in list(os.environ.keys()):
                    if key.startswith("MCPFORGE_"):
                        del os.environ[key]

                config = load_config()

                assert config["ollama_url"] == "http://localhost:11434"
                assert config["ollama_model"] == "qwen2.5:7b"
                assert config["default_enhance"] is False
                assert config["output_dir"] == "./generated"
                assert config["plugins"] == []
            finally:
                os.chdir(old_cwd)
                if old_home:
                    os.environ["HOME"] = old_home

    def test_load_yaml_config(self):
        """Test loading YAML config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "mcpforge.yaml"
            config_file.write_text(
                """
ollama_url: http://custom:11434
ollama_model: custom-model
default_enhance: true
plugins:
  - my_plugin
"""
            )

            config = load_config(str(config_file))

            assert config["ollama_url"] == "http://custom:11434"
            assert config["ollama_model"] == "custom-model"
            assert config["default_enhance"] is True
            assert config["plugins"] == ["my_plugin"]
            assert "_config_file" in config

    def test_load_json_config(self):
        """Test loading JSON config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "mcpforge.json"
            config_file.write_text(
                json.dumps({
                    "ollama_url": "http://json:11434",
                    "ollama_model": "json-model",
                    "default_enhance": False,
                })
            )

            config = load_config(str(config_file))

            assert config["ollama_url"] == "http://json:11434"
            assert config["ollama_model"] == "json-model"

    def test_config_file_not_found(self):
        """Test error when config file doesn't exist."""
        with pytest.raises(ConfigError, match="Config file not found"):
            load_config("/nonexistent/path/config.yaml")

    def test_invalid_yaml_config(self):
        """Test error on invalid YAML syntax."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "mcpforge.yaml"
            config_file.write_text("invalid: yaml: syntax:")

            with pytest.raises(ConfigError, match="Failed to parse config file"):
                load_config(str(config_file))

    def test_env_var_override(self):
        """Test environment variable overrides."""
        with tempfile.TemporaryDirectory() as tmpdir:
            old_env = {}
            try:
                # Set env vars
                os.environ["MCPFORGE_OLLAMA_URL"] = "http://env:11434"
                os.environ["MCPFORGE_OLLAMA_MODEL"] = "env-model"
                os.environ["MCPFORGE_DEFAULT_ENHANCE"] = "true"

                config = load_config()

                assert config["ollama_url"] == "http://env:11434"
                assert config["ollama_model"] == "env-model"
                assert config["default_enhance"] is True
            finally:
                # Restore
                for key in ["MCPFORGE_OLLAMA_URL", "MCPFORGE_OLLAMA_MODEL", "MCPFORGE_DEFAULT_ENHANCE"]:
                    if key in os.environ:
                        del os.environ[key]

    def test_find_config_file(self):
        """Test config file discovery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                # No config file
                found = _find_config_file()
                assert found is None

                # Create yaml config
                config_file = Path(tmpdir) / "mcpforge.yaml"
                config_file.write_text("key: value")
                found = _find_config_file()
                assert found == config_file

                # Remove yaml, add json
                config_file.unlink()
                config_file = Path(tmpdir) / "mcpforge.json"
                config_file.write_text('{"key": "value"}')
                found = _find_config_file()
                assert found == config_file
            finally:
                os.chdir(old_cwd)


class TestGetConfigSource:
    """Test config source identification."""

    def test_file_source(self):
        """Test file-based config source."""
        config = {"_config_file": "/path/to/config.yaml"}
        source = get_config_source(config)
        assert "File:" in source
        assert "/path/to/config.yaml" in source

    def test_default_source(self):
        """Test default config source."""
        config = {}
        source = get_config_source(config)
        assert "Defaults" in source
