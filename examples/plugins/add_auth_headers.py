"""
Example MCPForge plugin: Add Authentication Header Support

This plugin demonstrates how to modify endpoints to add authentication
headers for APIs that require them.

Usage:
  mcpforge generate spec.yaml --plugin examples.plugins.add_auth_headers
"""

from mcpforge.parser import Endpoint, Parameter


def transform(endpoints: list[Endpoint]) -> list[Endpoint]:
    """
    Add Authentication header parameter to all endpoints.

    This is useful for APIs that require custom authentication headers
    (e.g., Authorization, X-API-Key).

    Args:
        endpoints: List of Endpoint objects from parser

    Returns:
        list: Modified endpoints with auth headers added
    """
    for endpoint in endpoints:
        # Check if endpoint already has auth parameter
        has_auth = any(
            p.name.lower() in ("authorization", "auth", "x-api-key")
            for p in endpoint.parameters
        )

        if not has_auth:
            # Add Authorization header parameter
            auth_param = Parameter(
                name="Authorization",
                location="header",
                required=False,
                description="Bearer token or API key for authentication",
                schema={"type": "string", "pattern": "^Bearer .+$"},
            )
            endpoint.parameters.append(auth_param)

            # Update endpoint description to mention auth
            if endpoint.description:
                if "authentication" not in endpoint.description.lower():
                    endpoint.description += "\n\nRequires Authorization header with Bearer token or API key."
            else:
                endpoint.description = "Requires Authorization header with Bearer token or API key."

    return endpoints
