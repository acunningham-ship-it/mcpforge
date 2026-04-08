"""Configuration management for MCPForge."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None


class ConfigError(Exception):
    """Raised when config file cannot be loaded or parsed."""
    pass


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML config file."""
    if yaml is None:
        raise ConfigError(
            f"Cannot load YAML config ({path}): pyyaml not installed. "
            "Install with: pip install pyyaml"
        )
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    """Load JSON config file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _find_config_file() -> Optional[Path]:
    """Find config file in order of precedence: cwd, home dir."""
    candidates = [
        Path.cwd() / "mcpforge.yaml",
        Path.cwd() / "mcpforge.json",
        Path.home() / ".mcpforge" / "config.yaml",
        Path.home() / ".mcpforge" / "config.json",
    ]

    for path in candidates:
        if path.exists():
            return path

    return None


def load_config(config_file: Optional[str] = None) -> dict[str, Any]:
    """
    Load MCPForge config from file and environment variables.

    Precedence (highest to lowest):
    1. Command-line provided config file
    2. mcpforge.yaml in current directory
    3. mcpforge.json in current directory
    4. ~/.mcpforge/config.yaml
    5. ~/.mcpforge/config.json
    6. Environment variables (MCPFORGE_* prefix)
    7. Defaults

    Supported config fields:
    - ollama_url: Ollama API endpoint
    - ollama_model: Ollama model name
    - default_enhance: Whether to enhance by default
    - output_dir: Default output directory
    - plugins: List of plugin module names to load

    Args:
        config_file: Path to specific config file to load

    Returns:
        dict: Merged config from files and environment

    Raises:
        ConfigError: If config file cannot be parsed
    """
    config: dict[str, Any] = {
        "ollama_url": "http://localhost:11434",
        "ollama_model": "qwen2.5:7b",
        "default_enhance": False,
        "output_dir": "./generated",
        "plugins": [],
    }

    # Load from config file
    if config_file:
        path = Path(config_file)
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")
    else:
        path = _find_config_file()

    if path:
        try:
            if path.suffix in [".yaml", ".yml"]:
                file_config = _load_yaml(path)
            elif path.suffix == ".json":
                file_config = _load_json(path)
            else:
                raise ConfigError(f"Unsupported config file format: {path.suffix}")

            config.update(file_config)
            config["_config_file"] = str(path)
        except (json.JSONDecodeError, yaml.YAMLError if yaml else None) as exc:
            raise ConfigError(f"Failed to parse config file {path}: {exc}")

    # Override with environment variables
    env_overrides = {
        "ollama_url": os.environ.get("MCPFORGE_OLLAMA_URL"),
        "ollama_model": os.environ.get("MCPFORGE_OLLAMA_MODEL"),
        "default_enhance": os.environ.get("MCPFORGE_DEFAULT_ENHANCE", "").lower() in ("true", "1", "yes"),
        "output_dir": os.environ.get("MCPFORGE_OUTPUT_DIR"),
        "plugins": os.environ.get("MCPFORGE_PLUGINS", "").split(",") if os.environ.get("MCPFORGE_PLUGINS") else [],
    }

    for key, value in env_overrides.items():
        if value is not None and value != "" and value != []:
            config[key] = value

    return config


def get_config_source(config: dict[str, Any]) -> str:
    """Get human-readable source of current config."""
    if "_config_file" in config:
        return f"File: {config['_config_file']}"

    has_env = any(os.environ.get(f"MCPFORGE_{k.upper()}") for k in config if k != "_config_file")
    if has_env:
        return "Environment variables (MCPFORGE_*)"

    return "Defaults"
