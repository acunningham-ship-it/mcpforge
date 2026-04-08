"""MCPForge CLI — generate MCP servers from OpenAPI specs."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

app = typer.Typer(
    name="mcpforge",
    help="Auto-generate Model Context Protocol (MCP) servers from OpenAPI specs.",
    add_completion=False,
)
console = Console()

# Config subcommand app
config_app = typer.Typer(help="Manage MCPForge configuration")

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

EXAMPLE_META = {
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


@app.command()
def generate(
    spec: str = typer.Argument(..., help="OpenAPI spec — URL, file path (.yaml/.json), or '-' for stdin"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (default: <api_name>_mcp.py)"),
    enhance: Optional[bool] = typer.Option(None, "--enhance", "--no-enhance", help="Use Ollama to improve tool descriptions (defaults from config)"),
    no_validate: bool = typer.Option(False, "--no-validate", help="Skip validation of generated code"),
    config: Optional[str] = typer.Option(None, "--config", help="Path to config file (default: mcpforge.yaml/.json)"),
    plugin: list[str] = typer.Option([], "--plugin", "-p", help="Plugin module to load (can be used multiple times)"),
) -> None:
    """Generate an MCP server from an OpenAPI specification."""
    # Import here to keep CLI startup fast
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent))

    from mcpforge.parser import parse_spec, get_api_info
    from mcpforge.generator import generate_server
    from mcpforge.config import load_config, ConfigError
    from mcpforge.plugins import load_plugins, apply_plugins, PluginError

    # Load config
    try:
        cfg = load_config(config)
    except ConfigError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(1)

    # Determine enhance flag (command-line > config > default)
    if enhance is None:
        enhance = cfg.get("default_enhance", False)

    # Load spec
    if spec == "-":
        import json
        raw = json.load(sys.stdin)
        source: str | dict = raw
    else:
        source = spec

    console.print(f"[bold cyan]Parsing spec:[/bold cyan] {spec}")

    try:
        info = get_api_info(source)
        endpoints = parse_spec(source)
    except Exception as exc:
        console.print(f"[red]Failed to parse spec:[/red] {exc}")
        raise typer.Exit(1)

    api_title = info["title"]
    base_url = info["base_url"]

    console.print(
        f"[green]Found {len(endpoints)} endpoint(s)[/green] in [bold]{api_title}[/bold] ({base_url})"
    )

    # Load and apply plugins
    all_plugins = list(plugin) + cfg.get("plugins", [])
    if all_plugins:
        try:
            loaded_plugins = load_plugins(all_plugins)
            console.print(f"[cyan]Applying {len(loaded_plugins)} plugin(s)...[/cyan]")
            endpoints = apply_plugins(endpoints, loaded_plugins)
            console.print(f"[green]Plugins applied[/green] — {len(endpoints)} endpoint(s) after transformation")
        except PluginError as exc:
            console.print(f"[red]Plugin error:[/red] {exc}")
            raise typer.Exit(1)

    # Optional enhancement
    if enhance:
        from mcpforge.enhancer import enhance_endpoints, _ollama_available
        if not _ollama_available():
            console.print("[yellow]Ollama not available — skipping enhancement.[/yellow]")
        else:
            console.print("[cyan]Enhancing descriptions with Ollama...[/cyan]")
            endpoints = enhance_endpoints(endpoints, verbose=False)

    # Generate
    try:
        code = generate_server(endpoints, api_title=api_title, base_url=base_url)
    except Exception as exc:
        console.print(f"[red]Code generation failed:[/red] {exc}")
        raise typer.Exit(1)

    # Determine output path
    if output is None:
        import re
        safe = re.sub(r"[^a-zA-Z0-9]", "_", api_title).lower().strip("_")
        output = f"{safe}_mcp.py"

    # Validate
    if not no_validate:
        from mcpforge.validator import validate_code
        result = validate_code(code)
        if result.valid:
            console.print(
                f"[green]Validation passed[/green] — {len(result.tools)} tool(s): "
                + ", ".join(result.tools[:8])
                + ("..." if len(result.tools) > 8 else "")
            )
        else:
            for err in result.errors:
                console.print(f"[red]Validation error:[/red] {err}")

    # Write
    Path(output).write_text(code, encoding="utf-8")
    console.print(f"[bold green]Generated:[/bold green] {output}")
    console.print(f"\nRun with: [bold]python {output}[/bold]")


@app.command()
def examples() -> None:
    """List available example MCP servers."""
    table = Table(title="MCPForge Example Servers", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", min_width=12)
    table.add_column("File", style="green")
    table.add_column("Description")
    table.add_column("Tags", style="dim")

    for name, meta in EXAMPLE_META.items():
        table.add_row(
            name,
            meta["file"],
            meta["description"],
            ", ".join(meta["tags"]),
        )

    console.print(table)
    console.print("\nView an example: [bold]mcpforge demo <name>[/bold]")
    console.print("Run an example:  [bold]python examples/<file>[/bold]")


@app.command()
def demo(
    name: str = typer.Argument(..., help="Example name: github, weather, or calculator"),
    show: bool = typer.Option(True, "--show/--no-show", help="Print the server code"),
) -> None:
    """Show (and optionally run) an example MCP server."""
    if name not in EXAMPLE_META:
        console.print(f"[red]Unknown example:[/red] {name}")
        console.print(f"Available: {', '.join(EXAMPLE_META.keys())}")
        raise typer.Exit(1)

    meta = EXAMPLE_META[name]
    file_path = EXAMPLES_DIR / meta["file"]

    if not file_path.exists():
        console.print(f"[red]Example file not found:[/red] {file_path}")
        raise typer.Exit(1)

    code = file_path.read_text(encoding="utf-8")

    console.print(Panel(meta["description"], title=f"[bold cyan]{name}[/bold cyan]", expand=False))

    if show:
        syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
        console.print(syntax)

    console.print(f"\n[dim]File:[/dim] {file_path}")
    console.print(f"Run with: [bold]python {file_path}[/bold]")


@app.command()
def serve(
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev mode)"),
) -> None:
    """Start the MCPForge web server (UI + REST API)."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn not found.[/red] Install with: pip install uvicorn")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]MCPForge[/bold cyan] web server starting...")
    console.print(f"  UI:  [link]http://localhost:{port}[/link]")
    console.print(f"  API: [link]http://localhost:{port}/docs[/link]\n")

    sys.path.insert(0, str(Path(__file__).parent.parent))
    uvicorn.run("api.main:app", host=host, port=port, reload=reload)


@config_app.command()
def show(config_file: Optional[str] = typer.Option(None, "--config", help="Path to config file")) -> None:
    """Show current effective MCPForge configuration."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent))

    from mcpforge.config import load_config, get_config_source, ConfigError

    try:
        cfg = load_config(config_file)
    except ConfigError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(1)

    source = get_config_source(cfg)
    console.print(f"[bold cyan]MCPForge Configuration[/bold cyan] — {source}\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    for key, value in cfg.items():
        if key.startswith("_"):
            continue
        table.add_row(key, str(value))

    console.print(table)


@config_app.command()
def init(output_dir: Optional[str] = typer.Option(".", "--dir", "-d", help="Directory for config file")) -> None:
    """Create mcpforge.yaml in the specified directory."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent))

    output_path = Path(output_dir) / "mcpforge.yaml"

    if output_path.exists():
        console.print(f"[yellow]Config file already exists:[/yellow] {output_path}")
        raise typer.Exit(1)

    template = """# MCPForge Configuration
# Full documentation: https://github.com/anthropics/mcpforge

# Ollama settings for description enhancement
ollama_url: http://localhost:11434
ollama_model: qwen2.5:7b

# Default behavior for generate command
default_enhance: false

# Default output directory for generated servers
output_dir: ./generated

# Plugins to load (module names)
plugins: []
  # - my_plugin
  # - my_package.plugin
"""

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(template, encoding="utf-8")
        console.print(f"[bold green]Created:[/bold green] {output_path}")
    except Exception as exc:
        console.print(f"[red]Failed to create config file:[/red] {exc}")
        raise typer.Exit(1)


# Register config subcommand
app.add_typer(config_app, name="config")


if __name__ == "__main__":
    app()
