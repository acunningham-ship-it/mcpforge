"""Router for /api/generate and /api/examples endpoints."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Ensure mcpforge package is importable when running from api/ subdirectory
_ROOT = Path(__file__).parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcpforge.parser import parse_spec, get_api_info
from mcpforge.generator import generate_server
from mcpforge.validator import validate_code

router = APIRouter()

EXAMPLES_DIR = _ROOT / "examples"

EXAMPLE_META: dict[str, dict] = {
    "github": {
        "file": "github_mcp.py",
        "description": "GitHub public API — list repos, get repo details, search, list issues",
        "tags": ["vcs", "github", "no-auth-needed"],
    },
    "weather": {
        "file": "weather_mcp.py",
        "description": "wttr.in weather service — current conditions and N-day forecasts",
        "tags": ["weather", "free", "no-auth-needed"],
    },
    "calculator": {
        "file": "calculator_mcp.py",
        "description": "Pure-Python calculator — arithmetic, expressions, no network needed",
        "tags": ["math", "local", "no-network"],
    },
}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    spec_url: Optional[str] = None
    spec_dict: Optional[dict] = None
    enhance: bool = False


class GenerateResponse(BaseModel):
    server_code: str
    tools: list[str]
    api_name: str
    base_url: str
    endpoint_count: int
    valid: bool
    validation_errors: list[str]


class ExampleSummary(BaseModel):
    name: str
    description: str
    tags: list[str]
    file: str


class ExampleDetail(BaseModel):
    name: str
    description: str
    tags: list[str]
    code: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=GenerateResponse)
async def generate_mcp_server(request: GenerateRequest) -> GenerateResponse:
    """Generate an MCP server from an OpenAPI spec URL or raw spec dict."""
    if not request.spec_url and not request.spec_dict:
        raise HTTPException(
            status_code=422,
            detail="Provide either spec_url or spec_dict.",
        )

    source: str | dict = request.spec_dict if request.spec_dict else request.spec_url  # type: ignore

    try:
        info = get_api_info(source)
        endpoints = parse_spec(source)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse spec: {exc}")

    if not endpoints:
        raise HTTPException(status_code=400, detail="No endpoints found in spec.")

    # Optional Ollama enhancement
    if request.enhance:
        try:
            from mcpforge.enhancer import enhance_endpoints, _ollama_available
            if _ollama_available():
                endpoints = enhance_endpoints(endpoints)
        except Exception:
            pass  # Silently skip if enhancement fails

    try:
        code = generate_server(
            endpoints,
            api_title=info["title"],
            base_url=info["base_url"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Code generation failed: {exc}")

    validation = validate_code(code)

    return GenerateResponse(
        server_code=code,
        tools=validation.tools,
        api_name=info["title"],
        base_url=info["base_url"],
        endpoint_count=len(endpoints),
        valid=validation.valid,
        validation_errors=validation.errors,
    )


@router.get("/examples", response_model=list[ExampleSummary])
async def list_examples() -> list[ExampleSummary]:
    """List all available pre-built example MCP servers."""
    return [
        ExampleSummary(name=name, **{k: v for k, v in meta.items() if k != "file"}, file=meta["file"])
        for name, meta in EXAMPLE_META.items()
    ]


@router.get("/examples/{name}", response_model=ExampleDetail)
async def get_example(name: str) -> ExampleDetail:
    """Get the source code of a named example MCP server."""
    if name not in EXAMPLE_META:
        raise HTTPException(
            status_code=404,
            detail=f"Example '{name}' not found. Available: {list(EXAMPLE_META.keys())}",
        )
    meta = EXAMPLE_META[name]
    file_path = EXAMPLES_DIR / meta["file"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Example file not found on disk: {file_path}")

    code = file_path.read_text(encoding="utf-8")
    return ExampleDetail(
        name=name,
        description=meta["description"],
        tags=meta["tags"],
        code=code,
    )
