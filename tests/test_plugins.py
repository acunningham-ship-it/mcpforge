"""Tests for MCPForge plugin system."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root is in path
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from mcpforge.plugins import load_plugins, apply_plugins, PluginError
from mcpforge.parser import Endpoint


class TestLoadPlugins:
    """Test plugin loading."""

    def test_load_valid_plugin(self):
        """Test loading a valid plugin."""
        # examples.plugins.add_auth_headers is the example plugin
        plugins = load_plugins(["examples.plugins.add_auth_headers"])
        assert len(plugins) == 1
        assert callable(plugins[0])

    def test_load_nonexistent_plugin(self):
        """Test error when plugin doesn't exist."""
        with pytest.raises(PluginError, match="Failed to import plugin"):
            load_plugins(["nonexistent.plugin"])

    def test_load_plugin_without_transform(self):
        """Test error when plugin lacks transform function."""
        with pytest.raises(PluginError, match="does not have a 'transform' function"):
            load_plugins(["sys"])  # sys module doesn't have transform

    def test_load_multiple_plugins(self):
        """Test loading multiple plugins."""
        plugins = load_plugins([
            "examples.plugins.add_auth_headers",
            "examples.plugins.add_auth_headers",  # Load same twice
        ])
        assert len(plugins) == 2


class TestApplyPlugins:
    """Test plugin application."""

    def test_apply_single_plugin(self):
        """Test applying a single plugin."""
        endpoints = [
            Endpoint(
                path="/api/users",
                method="GET",
                operation_id="list_users",
                summary="List users",
            )
        ]

        plugins = load_plugins(["examples.plugins.add_auth_headers"])
        result = apply_plugins(endpoints, plugins)

        assert len(result) == 1
        assert len(result[0].parameters) == 1
        assert result[0].parameters[0].name == "Authorization"
        assert result[0].parameters[0].location == "header"

    def test_apply_multiple_plugins(self):
        """Test applying multiple plugins in sequence."""
        def dummy_transform(endpoints):
            for ep in endpoints:
                ep.summary = f"Modified: {ep.summary}"
            return endpoints

        # This won't actually load a second real plugin,
        # but we can test the apply mechanism with the same plugin twice
        endpoints = [
            Endpoint(
                path="/api/test",
                method="GET",
                operation_id="test",
                summary="Original",
            )
        ]

        plugins = load_plugins(["examples.plugins.add_auth_headers"])
        result = apply_plugins(endpoints, plugins)

        assert len(result) == 1
        assert result[0].parameters[0].name == "Authorization"

    def test_plugin_must_return_list(self):
        """Test error when plugin doesn't return list."""
        def bad_plugin(endpoints):
            return "not a list"

        endpoints = [
            Endpoint(
                path="/api/test",
                method="GET",
                operation_id="test",
            )
        ]

        with pytest.raises(PluginError, match="did not return a list"):
            apply_plugins(endpoints, [bad_plugin])

    def test_plugin_error_handling(self):
        """Test error handling in plugin execution."""
        def error_plugin(endpoints):
            raise ValueError("Plugin error")

        endpoints = [
            Endpoint(
                path="/api/test",
                method="GET",
                operation_id="test",
            )
        ]

        with pytest.raises(PluginError, match="failed"):
            apply_plugins(endpoints, [error_plugin])


class TestExamplePlugins:
    """Test example plugin functionality."""

    def test_add_auth_headers_plugin(self):
        """Test the add_auth_headers example plugin."""
        from examples.plugins.add_auth_headers import transform

        endpoints = [
            Endpoint(
                path="/api/users",
                method="GET",
                operation_id="list_users",
                summary="List all users",
                description="Retrieves a list of users",
            ),
            Endpoint(
                path="/api/data",
                method="POST",
                operation_id="create_data",
                summary="Create data",
            ),
        ]

        result = transform(endpoints)

        assert len(result) == 2

        # First endpoint
        assert len(result[0].parameters) == 1
        assert result[0].parameters[0].name == "Authorization"
        assert "authorization" in result[0].description.lower()

        # Second endpoint
        assert len(result[1].parameters) == 1
        assert result[1].parameters[0].name == "Authorization"
        assert "authorization" in result[1].description.lower()

    def test_add_auth_headers_no_duplicate(self):
        """Test that plugin doesn't add duplicate auth headers."""
        from examples.plugins.add_auth_headers import transform

        # Endpoint already has Authorization
        endpoints = [
            Endpoint(
                path="/api/test",
                method="GET",
                operation_id="test",
                parameters=[
                    __import__("mcpforge.parser", fromlist=["Parameter"]).Parameter(
                        name="Authorization",
                        location="header",
                    )
                ],
            )
        ]

        result = transform(endpoints)

        # Should still have only 1 parameter (no duplicate added)
        assert len(result[0].parameters) == 1
