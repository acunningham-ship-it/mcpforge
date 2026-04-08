"""Validate generated MCP server Python files."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    has_mcp_run: bool = False

    def __str__(self) -> str:
        lines = [f"Valid: {self.valid}"]
        if self.tools:
            lines.append(f"Tools ({len(self.tools)}): {', '.join(self.tools)}")
        if self.has_mcp_run:
            lines.append("Entry point: mcp.run() present")
        for e in self.errors:
            lines.append(f"ERROR: {e}")
        for w in self.warnings:
            lines.append(f"WARNING: {w}")
        return "\n".join(lines)


def validate_code(source: str) -> ValidationResult:
    """
    Validate a generated MCP server source string.

    Checks:
    - Python syntax (ast.parse)
    - Presence of mcp.run()
    - At least one @mcp.tool() decorated function
    - Reports all discovered tool names
    """
    result = ValidationResult(valid=False)

    # ---- Syntax check ----
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        result.errors.append(f"SyntaxError: {exc}")
        return result

    # ---- Walk AST ----
    tool_names: list[str] = []
    has_mcp_run = False

    for node in ast.walk(tree):
        # Check for mcp.run() call
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (
                isinstance(call.func, ast.Attribute)
                and call.func.attr == "run"
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "mcp"
            ):
                has_mcp_run = True

        # Check for @mcp.tool() decorated functions
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                is_mcp_tool = False
                if isinstance(decorator, ast.Call):
                    func = decorator.func
                    if (
                        isinstance(func, ast.Attribute)
                        and func.attr == "tool"
                        and isinstance(func.value, ast.Name)
                        and func.value.id == "mcp"
                    ):
                        is_mcp_tool = True
                elif isinstance(decorator, ast.Attribute):
                    if (
                        decorator.attr == "tool"
                        and isinstance(decorator.value, ast.Name)
                        and decorator.value.id == "mcp"
                    ):
                        is_mcp_tool = True
                if is_mcp_tool:
                    tool_names.append(node.name)

    result.has_mcp_run = has_mcp_run
    result.tools = tool_names

    if not has_mcp_run:
        result.errors.append("Missing mcp.run() — server cannot start")

    if not tool_names:
        result.errors.append("No @mcp.tool() functions found — server has no tools")

    if not result.errors:
        result.valid = True

    # Soft warnings
    if len(tool_names) > 40:
        result.warnings.append(
            f"{len(tool_names)} tools detected — consider splitting into multiple servers"
        )

    return result


def validate_file(path: str | Path) -> ValidationResult:
    """Validate a generated MCP server from a file path."""
    source = Path(path).read_text(encoding="utf-8")
    return validate_code(source)
