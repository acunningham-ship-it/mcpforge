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
    enhance: bool = typer.Option(False, "--enhance", help="Use Ollama to improve tool descriptions"),
    no_validate: bool = typer.Option(False, "--no-validate", help="Skip validation of generated code"),
) -> None:
    """Generate an MCP server from an OpenAPI specification."""
    # Import here to keep CLI startup fast
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent))

    from mcpforge.parser import parse_spec, get_api_info
    from mcpforge.generator import generate_server

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


if __name__ == "__main__":
    app()
