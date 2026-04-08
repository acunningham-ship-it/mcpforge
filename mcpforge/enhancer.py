"""Ollama-powered description enhancer for MCP tool docstrings."""

from __future__ import annotations

import json
import textwrap
from typing import Any

import httpx

from .parser import Endpoint

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
TIMEOUT = 60.0


def _ollama_available() -> bool:
    """Return True if Ollama is reachable."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


def _get_available_model(preferred: str = DEFAULT_MODEL) -> str | None:
    """Return the first available model from Ollama, preferring `preferred`."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5.0)
        models = [m["name"] for m in resp.json().get("models", [])]
        if preferred in models:
            return preferred
        # Return any model if preferred not found
        return models[0] if models else None
    except Exception:
        return None


def _ollama_generate(prompt: str, model: str) -> str:
    """Call Ollama generate endpoint and return the response text."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 200},
    }
    resp = httpx.post(
        f"{OLLAMA_BASE}/api/generate",
        json=payload,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def _build_prompt(ep: Endpoint) -> str:
    param_list = ", ".join(p.name for p in ep.parameters) or "none"
    return textwrap.dedent(f"""
        You are documenting a REST API endpoint as an MCP (Model Context Protocol) tool.
        Write a concise 1-2 sentence description for this tool that:
        1. Explains what it does in plain English
        2. Mentions the key parameters: {param_list}
        3. Notes any important return values

        Endpoint: {ep.method} {ep.path}
        Summary: {ep.summary or '(none)'}
        Description: {ep.description or '(none)'}

        Reply with ONLY the tool description, no preamble or explanation.
    """).strip()


def enhance_endpoints(
    endpoints: list[Endpoint],
    model: str = DEFAULT_MODEL,
    verbose: bool = False,
) -> list[Endpoint]:
    """
    Use Ollama to improve the description of each endpoint.

    Modifies endpoints in-place (updates .summary) and returns the list.
    If Ollama is not available, returns endpoints unchanged.
    """
    if not _ollama_available():
        if verbose:
            print("[enhancer] Ollama not available — skipping enhancement.")
        return endpoints

    available_model = _get_available_model(model)
    if not available_model:
        if verbose:
            print("[enhancer] No Ollama models found — skipping enhancement.")
        return endpoints

    if verbose:
        print(f"[enhancer] Using model: {available_model}")

    for ep in endpoints:
        try:
            prompt = _build_prompt(ep)
            enhanced = _ollama_generate(prompt, available_model)
            if enhanced:
                ep.summary = enhanced
                if verbose:
                    print(f"[enhancer] Enhanced: {ep.function_name}")
        except Exception as exc:
            if verbose:
                print(f"[enhancer] Failed for {ep.function_name}: {exc}")
            # Leave original summary intact

    return endpoints
