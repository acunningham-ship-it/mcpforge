"""Plugin system for MCPForge."""

from __future__ import annotations

import importlib
import sys
from typing import Any, Callable

from mcpforge.parser import Endpoint


class PluginError(Exception):
    """Raised when plugin cannot be loaded or executed."""
    pass


def load_plugins(plugin_names: list[str]) -> list[Callable]:
    """
    Load plugin modules by name.

    Each plugin module must provide a `transform(endpoints: list[Endpoint]) -> list[Endpoint]`
    function that modifies endpoints before code generation.

    Args:
        plugin_names: List of plugin module names (e.g., ["custom_plugin", "my_package.plugin"])

    Returns:
        list: List of loaded plugin functions

    Raises:
        PluginError: If a plugin cannot be imported or doesn't have transform function
    """
    plugins = []

    for name in plugin_names:
        try:
            module = importlib.import_module(name)
        except ImportError as exc:
            raise PluginError(f"Failed to import plugin '{name}': {exc}")

        if not hasattr(module, "transform"):
            raise PluginError(
                f"Plugin '{name}' does not have a 'transform' function. "
                "Plugin modules must define: def transform(endpoints: list) -> list"
            )

        transform_func = getattr(module, "transform")
        if not callable(transform_func):
            raise PluginError(f"Plugin '{name}' transform is not callable")

        plugins.append(transform_func)

    return plugins


def apply_plugins(endpoints: list[Endpoint], plugins: list[Callable]) -> list[Endpoint]:
    """
    Apply a sequence of plugins to endpoints.

    Each plugin transforms the endpoints list and passes to the next plugin.

    Args:
        endpoints: List of Endpoint objects
        plugins: List of transform functions from load_plugins()

    Returns:
        list: Transformed endpoints after all plugins applied

    Raises:
        PluginError: If a plugin transform fails
    """
    result = endpoints

    for i, plugin in enumerate(plugins):
        try:
            result = plugin(result)
        except Exception as exc:
            raise PluginError(f"Plugin {i} ({plugin.__module__}.{plugin.__name__}) failed: {exc}")

        if not isinstance(result, list):
            raise PluginError(
                f"Plugin {i} ({plugin.__module__}.{plugin.__name__}) did not return a list"
            )

    return result
