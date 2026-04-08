"""OpenAPI spec parser — supports OpenAPI 3.0 and Swagger 2.0."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import yaml


@dataclass
class Parameter:
    name: str
    location: str  # path, query, header, cookie
    required: bool = False
    description: str = ""
    schema: dict = field(default_factory=dict)

    @property
    def python_type(self) -> str:
        """Return a Python type hint string based on the parameter schema."""
        t = self.schema.get("type", "string")
        mapping = {
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "array": "list",
            "object": "dict",
            "string": "str",
        }
        return mapping.get(t, "str")

    @property
    def default(self) -> Any:
        return self.schema.get("default", None)


@dataclass
class SecurityRequirement:
    scheme: str       # bearer, apiKey, basic, oauth2
    env_var: str      # env var name expected at runtime
    header: str = "Authorization"  # header name for apiKey


@dataclass
class Endpoint:
    path: str
    method: str
    operation_id: str
    summary: str = ""
    description: str = ""
    parameters: list[Parameter] = field(default_factory=list)
    request_body: dict = field(default_factory=dict)
    responses: dict = field(default_factory=dict)
    security: list[SecurityRequirement] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def function_name(self) -> str:
        """Safe Python function name derived from operationId or path+method."""
        if self.operation_id:
            name = self.operation_id
        else:
            # Build from path: /users/{id}/repos -> users_id_repos
            slug = self.path.replace("/", "_").replace("{", "").replace("}", "").strip("_")
            name = f"{self.method.lower()}_{slug}"
        # Replace hyphens and spaces with underscore, strip non-alphanum
        import re
        name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        name = re.sub(r"_+", "_", name).strip("_")
        return name.lower()

    @property
    def tool_description(self) -> str:
        return self.summary or self.description or f"{self.method.upper()} {self.path}"


def _load_raw(source: str | dict) -> dict:
    """Load raw OpenAPI spec from URL, file path, or dict."""
    if isinstance(source, dict):
        return source

    path = Path(source)
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(text)
        return json.loads(text)

    # Assume URL
    resp = httpx.get(source, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    if "yaml" in content_type or source.endswith((".yaml", ".yml")):
        return yaml.safe_load(resp.text)
    return resp.json()


def _extract_security_schemes(spec: dict) -> dict[str, SecurityRequirement]:
    """Build a map of scheme name -> SecurityRequirement from components."""
    schemes: dict[str, SecurityRequirement] = {}
    # OpenAPI 3.0
    components = spec.get("components", {})
    sec_schemes = components.get("securitySchemes", {})
    # Swagger 2.0
    if not sec_schemes:
        sec_schemes = spec.get("securityDefinitions", {})

    for name, defn in sec_schemes.items():
        scheme_type = defn.get("type", "").lower()
        if scheme_type == "http":
            http_scheme = defn.get("scheme", "bearer").lower()
            env_var = f"{name.upper()}_TOKEN"
            schemes[name] = SecurityRequirement(
                scheme="bearer" if http_scheme == "bearer" else "basic",
                env_var=env_var,
            )
        elif scheme_type == "apikey":
            env_var = f"{name.upper()}_KEY"
            header = defn.get("name", "X-API-Key")
            in_loc = defn.get("in", "header")
            schemes[name] = SecurityRequirement(
                scheme="apiKey",
                env_var=env_var,
                header=header if in_loc == "header" else header,
            )
        elif scheme_type in ("oauth2", "openidconnect"):
            env_var = f"{name.upper()}_TOKEN"
            schemes[name] = SecurityRequirement(scheme="bearer", env_var=env_var)

    return schemes


def _resolve_ref(spec: dict, ref: str) -> dict:
    """Resolve a $ref like '#/components/schemas/Foo'."""
    if not ref.startswith("#/"):
        return {}
    parts = ref.lstrip("#/").split("/")
    node = spec
    for part in parts:
        if not isinstance(node, dict):
            return {}
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}


def _parse_parameters(raw_params: list, spec: dict) -> list[Parameter]:
    params = []
    for p in raw_params:
        if "$ref" in p:
            p = _resolve_ref(spec, p["$ref"])
        schema = p.get("schema", {"type": p.get("type", "string")})
        if "$ref" in schema:
            schema = _resolve_ref(spec, schema["$ref"])
        params.append(Parameter(
            name=p.get("name", "param"),
            location=p.get("in", "query"),
            required=p.get("required", False),
            description=p.get("description", ""),
            schema=schema,
        ))
    return params


def _parse_request_body(operation: dict, spec: dict) -> dict:
    rb = operation.get("requestBody", {})
    if not rb:
        return {}
    content = rb.get("content", {})
    for media_type in ("application/json", "application/x-www-form-urlencoded", "*/*"):
        if media_type in content:
            schema = content[media_type].get("schema", {})
            if "$ref" in schema:
                schema = _resolve_ref(spec, schema["$ref"])
            return {
                "required": rb.get("required", False),
                "description": rb.get("description", ""),
                "schema": schema,
            }
    return {}


def _parse_operation(
    path: str,
    method: str,
    operation: dict,
    global_params: list,
    security_schemes: dict[str, SecurityRequirement],
    global_security: list,
    spec: dict,
) -> Endpoint:
    raw_params = list(global_params) + operation.get("parameters", [])
    parameters = _parse_parameters(raw_params, spec)
    request_body = _parse_request_body(operation, spec)

    # Resolve security
    op_security = operation.get("security", global_security)
    security: list[SecurityRequirement] = []
    for sec_item in op_security:
        for scheme_name in sec_item:
            if scheme_name in security_schemes:
                security.append(security_schemes[scheme_name])

    return Endpoint(
        path=path,
        method=method.upper(),
        operation_id=operation.get("operationId", ""),
        summary=operation.get("summary", ""),
        description=operation.get("description", ""),
        parameters=parameters,
        request_body=request_body,
        responses=operation.get("responses", {}),
        security=security,
        tags=operation.get("tags", []),
    )


def parse_spec(source: str | dict, max_endpoints: int = 50) -> list[Endpoint]:
    """
    Parse an OpenAPI 3.0 or Swagger 2.0 spec.

    Args:
        source: URL string, file path string, or raw spec dict.
        max_endpoints: Cap on number of endpoints to parse (avoids huge servers).

    Returns:
        List of Endpoint dataclass instances.
    """
    spec = _load_raw(source)
    security_schemes = _extract_security_schemes(spec)
    global_security = spec.get("security", [])

    paths = spec.get("paths", {})
    endpoints: list[Endpoint] = []

    http_methods = {"get", "post", "put", "patch", "delete", "head", "options"}

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        global_params = path_item.get("parameters", [])
        for method, operation in path_item.items():
            if method not in http_methods:
                continue
            if not isinstance(operation, dict):
                continue
            ep = _parse_operation(
                path, method, operation, global_params,
                security_schemes, global_security, spec,
            )
            endpoints.append(ep)
            if len(endpoints) >= max_endpoints:
                break
        if len(endpoints) >= max_endpoints:
            break

    return endpoints


def get_api_info(source: str | dict) -> dict:
    """Return high-level info (title, version, base URL) from the spec."""
    spec = _load_raw(source)
    info = spec.get("info", {})
    title = info.get("title", "API")
    version = info.get("version", "1.0")

    # Base URL
    servers = spec.get("servers", [])
    if servers:
        base_url = servers[0].get("url", "")
    else:
        # Swagger 2.0
        scheme = (spec.get("schemes", ["https"]) or ["https"])[0]
        host = spec.get("host", "localhost")
        base_path = spec.get("basePath", "")
        base_url = f"{scheme}://{host}{base_path}"

    return {"title": title, "version": version, "base_url": base_url}
