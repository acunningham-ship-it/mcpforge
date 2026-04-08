"""MCPForge FastAPI application."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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

_WEB_UI = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>MCPForge — Generate MCP Servers</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
  <style>
    :root { --bg:#04040f; --card:#0d0d22; --border:#1a1a35; --cyan:#00d4ff; --green:#00ff88; --purple:#8b5cf6; --text:#e2e8f0; --dim:#94a3b8; }
    * { margin:0; padding:0; box-sizing:border-box; }
    body { background:var(--bg); color:var(--text); font-family:'Inter',sans-serif; min-height:100vh; }
    header { border-bottom:1px solid var(--border); padding:16px 32px; display:flex; align-items:center; gap:12px; }
    .logo { font-weight:700; font-size:1.1rem; background:linear-gradient(135deg,var(--cyan),var(--purple)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    .logo-badge { background:rgba(0,212,255,0.1); border:1px solid rgba(0,212,255,0.2); color:var(--cyan); padding:3px 10px; border-radius:100px; font-size:0.7rem; font-weight:600; -webkit-text-fill-color:var(--cyan); }
    main { max-width:900px; margin:0 auto; padding:48px 24px; }
    h1 { font-size:2rem; font-weight:800; margin-bottom:8px; }
    .sub { color:var(--dim); margin-bottom:40px; }
    label { display:block; color:var(--dim); font-size:0.875rem; margin-bottom:6px; font-weight:500; }
    input, select { width:100%; background:var(--card); border:1px solid var(--border); border-radius:8px; padding:12px 16px; color:var(--text); font-family:'Inter',sans-serif; font-size:0.9rem; outline:none; transition:border-color 0.2s; }
    input:focus, select:focus { border-color:var(--cyan); }
    .row { display:grid; grid-template-columns:1fr auto; gap:12px; align-items:end; margin-bottom:24px; }
    .field { margin-bottom:20px; }
    .checkbox-row { display:flex; align-items:center; gap:10px; }
    input[type=checkbox] { width:auto; }
    button { background:linear-gradient(135deg,var(--cyan),var(--purple)); color:#000; font-weight:700; border:none; padding:12px 28px; border-radius:8px; cursor:pointer; font-size:0.9rem; transition:opacity 0.2s; white-space:nowrap; }
    button:hover { opacity:0.9; }
    button:disabled { opacity:0.5; cursor:not-allowed; }
    .examples { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:32px; }
    .ex-btn { background:rgba(0,212,255,0.08); border:1px solid rgba(0,212,255,0.2); color:var(--cyan); padding:6px 14px; border-radius:100px; font-size:0.8rem; cursor:pointer; transition:all 0.2s; white-space:nowrap; }
    .ex-btn:hover { background:rgba(0,212,255,0.15); }
    .result { display:none; margin-top:32px; }
    .result-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }
    .result-title { font-weight:700; }
    .result-meta { color:var(--dim); font-size:0.85rem; }
    .copy-btn { background:var(--border); color:var(--dim); border:none; padding:6px 14px; border-radius:6px; font-size:0.8rem; cursor:pointer; font-weight:500; }
    .copy-btn:hover { background:var(--cyan); color:#000; }
    pre { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:24px; overflow-x:auto; font-family:'JetBrains Mono',monospace; font-size:0.8rem; line-height:1.7; max-height:500px; overflow-y:auto; }
    .tools-list { display:flex; flex-wrap:wrap; gap:6px; margin-top:16px; }
    .tool-pill { background:rgba(0,255,136,0.08); border:1px solid rgba(0,255,136,0.2); color:var(--green); padding:3px 12px; border-radius:100px; font-size:0.75rem; font-family:monospace; }
    .error { background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.2); color:#f87171; padding:16px; border-radius:8px; margin-top:20px; }
    .loading { display:none; color:var(--dim); font-size:0.9rem; margin-top:12px; }
    .spinner { display:inline-block; width:14px; height:14px; border:2px solid var(--border); border-top-color:var(--cyan); border-radius:50%; animation:spin 0.8s linear infinite; margin-right:8px; vertical-align:middle; }
    @keyframes spin { to { transform:rotate(360deg); } }
    .divider { border:none; border-top:1px solid var(--border); margin:32px 0; }
  </style>
</head>
<body>
<header>
  <div class="logo">⚡ MCPForge</div>
  <span class="logo-badge">v0.1.0</span>
  <div style="margin-left:auto;display:flex;gap:16px;">
    <a href="/docs" style="color:var(--dim);text-decoration:none;font-size:0.85rem;">API Docs</a>
    <a href="https://github.com/acunningham-ship-it/mcpforge" style="color:var(--dim);text-decoration:none;font-size:0.85rem;" target="_blank">GitHub</a>
  </div>
</header>

<main>
  <h1>Generate an MCP Server</h1>
  <p class="sub">Paste an OpenAPI spec URL to generate a ready-to-run Python MCP server.</p>

  <p style="color:var(--dim);font-size:0.85rem;margin-bottom:12px;">Try an example:</p>
  <div class="examples">
    <button class="ex-btn" onclick="setUrl('https://petstore.swagger.io/v2/swagger.json')">🐾 Petstore (Swagger 2.0)</button>
    <button class="ex-btn" onclick="setUrl('https://petstore3.swagger.io/api/v3/openapi.json')">🐾 Petstore (OpenAPI 3.0)</button>
    <button class="ex-btn" onclick="setUrl('built-in:github')">🐙 GitHub (built-in)</button>
    <button class="ex-btn" onclick="setUrl('built-in:weather')">🌤 Weather (built-in)</button>
    <button class="ex-btn" onclick="setUrl('built-in:calculator')">🧮 Calculator (built-in)</button>
  </div>

  <hr class="divider"/>

  <div class="row">
    <div>
      <label for="spec-url">OpenAPI spec URL</label>
      <input id="spec-url" type="text" placeholder="https://api.example.com/openapi.json" />
    </div>
    <button id="gen-btn" onclick="generate()">Generate →</button>
  </div>

  <div class="field">
    <div class="checkbox-row">
      <input type="checkbox" id="enhance" />
      <label for="enhance" style="margin:0;">Enhance descriptions with local Ollama <span style="color:var(--dim)">(requires Ollama running)</span></label>
    </div>
  </div>

  <div class="loading" id="loading">
    <span class="spinner"></span> Fetching spec and generating MCP server...
  </div>

  <div id="error" class="error" style="display:none"></div>

  <div class="result" id="result">
    <div class="result-header">
      <div>
        <div class="result-title" id="result-title"></div>
        <div class="result-meta" id="result-meta"></div>
      </div>
      <button class="copy-btn" onclick="copyCode()">Copy code</button>
    </div>
    <pre id="result-code"></pre>
    <div class="tools-list" id="tools-list"></div>
    <p style="color:var(--dim);font-size:0.85rem;margin-top:20px;">
      Save as <code style="color:var(--cyan);">my_server.py</code> and run with <code style="color:var(--cyan);">python my_server.py</code>
    </p>
  </div>
</main>

<script>
function setUrl(url) {
  if (url.startsWith('built-in:')) {
    document.getElementById('spec-url').value = url;
  } else {
    document.getElementById('spec-url').value = url;
  }
}

async function generate() {
  const url = document.getElementById('spec-url').value.trim();
  const enhance = document.getElementById('enhance').checked;
  if (!url) return;

  document.getElementById('gen-btn').disabled = true;
  document.getElementById('loading').style.display = 'block';
  document.getElementById('result').style.display = 'none';
  document.getElementById('error').style.display = 'none';

  try {
    let body;
    if (url.startsWith('built-in:')) {
      const name = url.replace('built-in:', '');
      const resp = await fetch(`/api/examples/${name}`);
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      showResult({ api_name: data.name, server_code: data.code, tools: data.tools, generated_at: new Date().toISOString() });
      return;
    } else {
      const resp = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ spec_url: url, enhance })
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || 'Generation failed');
      }
      showResult(await resp.json());
    }
  } catch (e) {
    document.getElementById('error').textContent = '⚠ ' + e.message;
    document.getElementById('error').style.display = 'block';
  } finally {
    document.getElementById('gen-btn').disabled = false;
    document.getElementById('loading').style.display = 'none';
  }
}

function showResult(data) {
  document.getElementById('result-title').textContent = data.api_name + ' — MCP Server';
  document.getElementById('result-meta').textContent = `${data.tools?.length ?? 0} tools generated`;
  document.getElementById('result-code').textContent = data.server_code;
  const tl = document.getElementById('tools-list');
  tl.innerHTML = (data.tools || []).map(t => `<span class="tool-pill">${t}</span>`).join('');
  document.getElementById('result').style.display = 'block';
  document.getElementById('result').scrollIntoView({ behavior: 'smooth' });
}

function copyCode() {
  const code = document.getElementById('result-code').textContent;
  navigator.clipboard.writeText(code).then(() => {
    const btn = document.querySelector('.copy-btn');
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy code', 2000);
  });
}

document.getElementById('spec-url').addEventListener('keydown', e => {
  if (e.key === 'Enter') generate();
});
</script>
</body>
</html>"""


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "mcpforge", "version": "0.1.0"}


@app.get("/", response_class=HTMLResponse, tags=["ui"])
async def web_ui() -> str:
    """Web UI for generating MCP servers."""
    return _WEB_UI


@app.get("/api", tags=["meta"])
async def api_info() -> dict:
    """API info endpoint."""
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
