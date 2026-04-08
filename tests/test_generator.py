"""Tests for MCPForge core — parser and generator."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root is in path when running from repo root or tests/ directory
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from mcpforge.parser import parse_spec, Endpoint, Parameter
from mcpforge.generator import generate_server
from mcpforge.validator import validate_code


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_SPEC: dict = {
    "openapi": "3.0.0",
    "info": {"title": "Pet Store", "version": "1.0"},
    "servers": [{"url": "https://petstore.example.com/v1"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer", "default": 10},
                    }
                ],
                "responses": {"200": {"description": "A list of pets"}},
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a new pet",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "tag": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "getPet",
                "summary": "Get a pet by ID",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {"200": {"description": "A single pet"}},
            }
        },
    },
}

BEARER_SPEC: dict = {
    "openapi": "3.0.0",
    "info": {"title": "Secure API", "version": "2.0"},
    "servers": [{"url": "https://api.secure.example.com"}],
    "components": {
        "securitySchemes": {
            "BearerAuth": {"type": "http", "scheme": "bearer"}
        }
    },
    "security": [{"BearerAuth": []}],
    "paths": {
        "/data": {
            "get": {
                "operationId": "getData",
                "summary": "Get protected data",
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
}


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestParseSpec:
    def test_returns_list_of_endpoints(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        assert isinstance(endpoints, list)
        assert len(endpoints) > 0

    def test_endpoint_count(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        assert len(endpoints) == 3  # GET /pets, POST /pets, GET /pets/{petId}

    def test_endpoint_is_dataclass(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        for ep in endpoints:
            assert isinstance(ep, Endpoint)

    def test_list_pets_endpoint(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        list_pets = next(e for e in endpoints if e.operation_id == "listPets")
        assert list_pets.method == "GET"
        assert list_pets.path == "/pets"
        assert list_pets.summary == "List all pets"

    def test_parameters_parsed(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        list_pets = next(e for e in endpoints if e.operation_id == "listPets")
        assert len(list_pets.parameters) == 1
        param = list_pets.parameters[0]
        assert isinstance(param, Parameter)
        assert param.name == "limit"
        assert param.location == "query"
        assert param.required is False

    def test_path_param_parsed(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        get_pet = next(e for e in endpoints if e.operation_id == "getPet")
        path_params = [p for p in get_pet.parameters if p.location == "path"]
        assert len(path_params) == 1
        assert path_params[0].name == "petId"
        assert path_params[0].required is True

    def test_request_body_parsed(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        create_pet = next(e for e in endpoints if e.operation_id == "createPet")
        assert create_pet.request_body
        assert create_pet.request_body["required"] is True

    def test_function_name_generation(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        names = [e.function_name for e in endpoints]
        assert "listpets" in names
        assert "createpet" in names
        assert "getpet" in names

    def test_security_parsed(self):
        endpoints = parse_spec(BEARER_SPEC)
        assert len(endpoints) == 1
        ep = endpoints[0]
        assert len(ep.security) == 1
        sec = ep.security[0]
        assert sec.scheme == "bearer"
        assert "BEARERAUTH" in sec.env_var.upper()

    def test_swagger2_body_param(self):
        """Swagger 2.0 `in: body` parameters should appear as request_body, not be silently dropped."""
        spec = {
            "swagger": "2.0",
            "info": {"title": "Petstore", "version": "1.0"},
            "host": "petstore.example.com",
            "basePath": "/v2",
            "paths": {
                "/pet": {
                    "post": {
                        "operationId": "addPet",
                        "summary": "Add a new pet",
                        "parameters": [
                            {
                                "in": "body",
                                "name": "body",
                                "required": True,
                                "schema": {"type": "object"},
                            }
                        ],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        endpoints = parse_spec(spec)
        assert len(endpoints) == 1
        ep = endpoints[0]
        # Body param should be in request_body, not in parameters
        assert ep.request_body != {}
        assert ep.request_body.get("required") is True
        body_locations = [p.location for p in ep.parameters]
        assert "body" not in body_locations

    def test_swagger2_body_param_in_generated_code(self):
        """Generated code for Swagger 2.0 body endpoints should include body parameter."""
        spec = {
            "swagger": "2.0",
            "info": {"title": "Store API", "version": "1.0"},
            "host": "api.example.com",
            "basePath": "/v1",
            "paths": {
                "/items": {
                    "post": {
                        "operationId": "createItem",
                        "summary": "Create item",
                        "parameters": [
                            {
                                "in": "body",
                                "name": "body",
                                "required": True,
                                "schema": {"type": "object"},
                            }
                        ],
                        "responses": {"201": {"description": "Created"}},
                    }
                }
            },
        }
        endpoints = parse_spec(spec)
        code = generate_server(endpoints, api_title="Store API", base_url="https://api.example.com/v1")
        assert "def createitem(body: dict)" in code

    def test_empty_paths(self):
        spec = {"openapi": "3.0.0", "info": {"title": "Empty", "version": "1"}, "paths": {}}
        endpoints = parse_spec(spec)
        assert endpoints == []

    def test_max_endpoints_cap(self):
        # Create a spec with many endpoints
        paths = {}
        for i in range(20):
            paths[f"/resource{i}"] = {
                "get": {
                    "operationId": f"getResource{i}",
                    "summary": f"Get resource {i}",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        spec = {"openapi": "3.0.0", "info": {"title": "Big", "version": "1"}, "paths": paths}
        endpoints = parse_spec(spec, max_endpoints=5)
        assert len(endpoints) <= 5


# ---------------------------------------------------------------------------
# Generator tests
# ---------------------------------------------------------------------------

class TestGenerateServer:
    def test_returns_string(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        code = generate_server(endpoints, api_title="Pet Store", base_url="https://petstore.example.com/v1")
        assert isinstance(code, str)
        assert len(code) > 0

    def test_contains_mcp_run(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        code = generate_server(endpoints, api_title="Pet Store", base_url="https://petstore.example.com/v1")
        assert "mcp.run()" in code

    def test_contains_mcp_tool_decorator(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        code = generate_server(endpoints, api_title="Pet Store", base_url="https://petstore.example.com/v1")
        assert "@mcp.tool()" in code

    def test_contains_fastmcp_import(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        code = generate_server(endpoints, api_title="Pet Store", base_url="https://petstore.example.com/v1")
        assert "from mcp.server.fastmcp import FastMCP" in code

    def test_contains_base_url(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        code = generate_server(endpoints, api_title="Pet Store", base_url="https://petstore.example.com/v1")
        assert "https://petstore.example.com/v1" in code

    def test_contains_all_tool_functions(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        code = generate_server(endpoints, api_title="Pet Store", base_url="https://petstore.example.com/v1")
        assert "def listpets(" in code
        assert "def createpet(" in code
        assert "def getpet(" in code

    def test_path_param_in_function(self):
        endpoints = parse_spec(SIMPLE_SPEC)
        code = generate_server(endpoints, api_title="Pet Store", base_url="https://petstore.example.com/v1")
        assert "petId" in code

    def test_bearer_auth_env_var(self):
        endpoints = parse_spec(BEARER_SPEC)
        code = generate_server(endpoints, api_title="Secure API", base_url="https://api.secure.example.com")
        assert "os.environ.get" in code
        assert "Bearer" in code

    def test_raises_on_empty_endpoints(self):
        with pytest.raises(ValueError, match="No endpoints"):
            generate_server([], api_title="Empty", base_url="https://example.com")

    def test_syntax_valid(self):
        """Generated code must be syntactically valid Python."""
        import ast as _ast
        endpoints = parse_spec(SIMPLE_SPEC)
        code = generate_server(endpoints, api_title="Pet Store", base_url="https://petstore.example.com/v1")
        # This will raise SyntaxError if invalid
        tree = _ast.parse(code)
        assert tree is not None

    def test_no_duplicate_functions(self):
        """Duplicate operationIds should only produce one function."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Dupe", "version": "1"},
            "servers": [{"url": "https://example.com"}],
            "paths": {
                "/a": {"get": {"operationId": "sameName", "summary": "A", "responses": {"200": {"description": "ok"}}}},
                "/b": {"get": {"operationId": "sameName", "summary": "B", "responses": {"200": {"description": "ok"}}}},
            },
        }
        endpoints = parse_spec(spec)
        code = generate_server(endpoints, api_title="Dupe", base_url="https://example.com")
        # Only one definition of sameName should exist
        assert code.count("def samename(") == 1


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------

class TestValidator:
    def test_valid_generated_code(self):
        from mcpforge.validator import validate_code
        endpoints = parse_spec(SIMPLE_SPEC)
        code = generate_server(endpoints, api_title="Pet Store", base_url="https://petstore.example.com/v1")
        result = validate_code(code)
        assert result.valid is True
        assert result.has_mcp_run is True
        assert len(result.tools) >= 3
        assert not result.errors

    def test_detects_syntax_error(self):
        from mcpforge.validator import validate_code
        result = validate_code("def broken(: pass")
        assert result.valid is False
        assert any("Syntax" in e for e in result.errors)

    def test_detects_missing_mcp_run(self):
        from mcpforge.validator import validate_code
        code = """
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("Test")

@mcp.tool()
def my_tool() -> dict:
    return {}
"""
        result = validate_code(code)
        assert result.valid is False
        assert any("mcp.run()" in e for e in result.errors)

    def test_detects_no_tools(self):
        from mcpforge.validator import validate_code
        code = """
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("Test")

def plain_function():
    pass

if __name__ == "__main__":
    mcp.run()
"""
        result = validate_code(code)
        assert result.valid is False
        assert any("No @mcp.tool()" in e for e in result.errors)

    def test_reports_tool_names(self):
        from mcpforge.validator import validate_code
        endpoints = parse_spec(SIMPLE_SPEC)
        code = generate_server(endpoints, api_title="Pet Store", base_url="https://petstore.example.com/v1")
        result = validate_code(code)
        assert "listpets" in result.tools
        assert "getpet" in result.tools
