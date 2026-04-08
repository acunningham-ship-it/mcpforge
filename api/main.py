"""MCPForge FastAPI application."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure root is importable
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.routers.generate import router as generate_router

app = FastAPI(
    title="MCPForge API",
    description="Auto-generate Model Context Protocol (MCP) servers from OpenAPI specifications.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate_router, prefix="/api")


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "mcpforge", "version": "0.1.0"}


@app.get("/", tags=["meta"])
async def root() -> dict:
    """Root endpoint — basic info."""
    return {
        "service": "MCPForge",
        "description": "Auto-generate MCP servers from OpenAPI specs",
        "docs": "/docs",
        "endpoints": {
            "generate": "POST /api/generate",
            "examples": "GET /api/examples",
            "example_detail": "GET /api/examples/{name}",
            "health": "GET /health",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
