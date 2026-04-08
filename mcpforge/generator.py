"""MCP server code generator — takes parsed endpoints and produces a Python file."""

from __future__ import annotations

import re
from typing import Any

from .parser import Endpoint, Parameter, SecurityRequirement


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_name(api_title: str) -> str:
    """Convert API title to a safe Python identifier prefix."""
    name = re.sub(r"[^a-zA-Z0-9]", "_", api_title)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def _python_default(param: Parameter) -> str:
    """Return a Python literal for the parameter default."""
    d = param.default
    if d is None:
        return "None"
    if isinstance(d, bool):
        return str(d)
    if isinstance(d, (int, float)):
        return str(d)
    if isinstance(d, str):
        return repr(d)
    return "None"


def _build_func_signature(ep: Endpoint) -> str:
    """Build the function signature line for a tool function."""
    parts: list[str] = []

    # Path params first (always required)
    for p in ep.parameters:
        if p.location == "path":
            parts.append(f"{p.name}: {p.python_type}")

    # Required query/header params
    for p in ep.parameters:
        if p.location in ("query", "header") and p.required:
            parts.append(f"{p.name}: {p.python_type}")

    # Request body
    if ep.request_body:
        required = ep.request_body.get("required", False)
        if required:
            parts.append("body: dict")
        else:
            parts.append("body: dict = None")

    # Optional query/header params
    for p in ep.parameters:
        if p.location in ("query", "header") and not p.required:
            default = _python_default(p)
            parts.append(f"{p.name}: {p.python_type} = {default}")

    # Optional body if not already added
    if ep.request_body and not ep.request_body.get("required", False):
        # Already added above as optional
        pass

    sig = ", ".join(parts)
    return f"def {ep.function_name}({sig}) -> dict:"


def _build_url_line(ep: Endpoint) -> str:
    """Build the URL construction line."""
    # Replace {param} with {param} in f-string
    path = ep.path
    return f'    url = f"{{BASE_URL}}{path}"'


def _build_params_dict(ep: Endpoint) -> list[str]:
    """Return lines building the query params dict."""
    query_params = [p for p in ep.parameters if p.location == "query"]
    if not query_params:
        return []
    lines = ["    params = {"]
    for p in query_params:
        lines.append(f'        "{p.name}": {p.name},')
    lines.append("    }")
    lines.append("    # Remove None values")
    lines.append("    params = {k: v for k, v in params.items() if v is not None}")
    return lines


def _build_headers(ep: Endpoint, all_security: list[SecurityRequirement]) -> list[str]:
    """Return lines building the headers dict."""
    lines = ["    headers = {}"]
    # Collect unique security requirements for this endpoint
    seen = set()
    for sec in ep.security:
        key = (sec.scheme, sec.env_var)
        if key in seen:
            continue
        seen.add(key)
        if sec.scheme == "bearer":
            env = sec.env_var
            lines.append(f'    if {env}:')
            lines.append(f'        headers["Authorization"] = f"Bearer {{{env}}}"')
        elif sec.scheme == "basic":
            env = sec.env_var
            lines.append(f'    if {env}:')
            lines.append(f'        headers["Authorization"] = f"Basic {{{env}}}"')
        elif sec.scheme == "apiKey":
            env = sec.env_var
            header_name = sec.header
            lines.append(f'    if {env}:')
            lines.append(f'        headers["{header_name}"] = {env}')

    # Header params
    for p in ep.parameters:
        if p.location == "header":
            lines.append(f'    if {p.name}:')
            lines.append(f'        headers["{p.name}"] = str({p.name})')
    return lines


def _build_http_call(ep: Endpoint) -> list[str]:
    """Return the httpx call lines."""
    method = ep.method.lower()
    has_query = any(p.location == "query" for p in ep.parameters)
    has_body = bool(ep.request_body)

    call_args = ["url", "headers=headers"]
    if has_query:
        call_args.append("params=params")
    if has_body and method in ("post", "put", "patch"):
        call_args.append("json=body")

    call = f"    resp = httpx.{method}({', '.join(call_args)}, timeout=30)"
    return [
        call,
        "    resp.raise_for_status()",
        "    try:",
        "        return resp.json()",
        "    except Exception:",
        '        return {"status_code": resp.status_code, "text": resp.text}',
    ]


def _generate_tool_function(ep: Endpoint, all_security: list[SecurityRequirement]) -> str:
    """Generate a single @mcp.tool() decorated function."""
    desc = ep.tool_description.replace('"', "'")
    lines: list[str] = [
        "@mcp.tool()",
        _build_func_signature(ep),
        f'    """{desc}"""',
    ]

    # URL
    lines.append(_build_url_line(ep))

    # Params dict
    lines.extend(_build_params_dict(ep))

    # Headers
    lines.extend(_build_headers(ep, all_security))

    # HTTP call
    lines.extend(_build_http_call(ep))

    return "\n".join(lines)


def _collect_env_vars(endpoints: list[Endpoint]) -> list[tuple[str, str]]:
    """Return list of (env_var_name, description) for all unique security env vars."""
    seen: dict[str, str] = {}
    for ep in endpoints:
        for sec in ep.security:
            if sec.env_var not in seen:
                if sec.scheme == "bearer":
                    seen[sec.env_var] = "Bearer token"
                elif sec.scheme == "basic":
                    seen[sec.env_var] = "Base64-encoded user:pass"
                elif sec.scheme == "apiKey":
                    seen[sec.env_var] = f"API key for {sec.header} header"
                else:
                    seen[sec.env_var] = "Auth credential"
    return list(seen.items())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_server(
    endpoints: list[Endpoint],
    api_title: str = "API",
    base_url: str = "",
    description: str = "",
) -> str:
    """
    Generate a complete, runnable MCP server Python file.

    Args:
        endpoints: Parsed Endpoint objects.
        api_title: Human-readable API title (used in docstrings / FastMCP name).
        base_url: Base URL for the API (e.g. "https://api.github.com").
        description: Optional extra description for the module docstring.

    Returns:
        String containing the full Python source code.
    """
    if not endpoints:
        raise ValueError("No endpoints provided — cannot generate an empty server.")

    env_vars = _collect_env_vars(endpoints)
    all_security = [sec for ep in endpoints for sec in ep.security]

    safe_title = _safe_name(api_title)

    # ---- Header ----
    header = f'''#!/usr/bin/env python3
"""MCP server for {api_title} — auto-generated by MCPForge."""

import os
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("{api_title}")
BASE_URL = "{base_url}"
'''

    # Env var declarations
    env_lines: list[str] = []
    for env_var, env_desc in env_vars:
        env_lines.append(f'{env_var} = os.environ.get("{env_var}", "")  # {env_desc}')

    if env_lines:
        header += "\n# Authentication\n"
        header += "\n".join(env_lines) + "\n"

    # ---- Tool functions ----
    tool_blocks: list[str] = []
    seen_names: set[str] = set()
    for ep in endpoints:
        # Deduplicate by function name
        fn = ep.function_name
        if fn in seen_names:
            continue
        seen_names.add(fn)
        tool_blocks.append(_generate_tool_function(ep, all_security))

    tools_section = "\n\n\n".join(tool_blocks)

    # ---- Footer ----
    footer = '''

if __name__ == "__main__":
    mcp.run()
'''

    return header + "\n\n" + tools_section + footer
