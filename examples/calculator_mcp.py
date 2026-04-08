#!/usr/bin/env python3
"""MCP server for a pure-Python calculator — no network required."""

import ast
import math
import operator
from typing import Union

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Calculator")

Number = Union[int, float]

# ---------------------------------------------------------------------------
# Safe expression evaluator
# ---------------------------------------------------------------------------

_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}

_SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
    "ceil": math.ceil,
    "floor": math.floor,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "pi": math.pi,
    "e": math.e,
    "inf": math.inf,
}


def _safe_eval(node: ast.AST) -> Number:
    """Recursively evaluate an AST node using only safe operations."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")
    if isinstance(node, ast.Name):
        if node.id in _SAFE_FUNCTIONS:
            val = _SAFE_FUNCTIONS[node.id]
            if callable(val):
                raise ValueError(f"'{node.id}' must be called as a function")
            return val  # type: ignore
        raise ValueError(f"Unknown name: {node.id}")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _SAFE_OPERATORS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return _SAFE_OPERATORS[op_type](_safe_eval(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only named function calls are allowed")
        func_name = node.func.id
        if func_name not in _SAFE_FUNCTIONS:
            raise ValueError(f"Unknown function: {func_name}")
        func = _SAFE_FUNCTIONS[func_name]
        if not callable(func):
            raise ValueError(f"'{func_name}' is a constant, not a function")
        args = [_safe_eval(a) for a in node.args]
        return func(*args)
    raise ValueError(f"Unsupported AST node: {type(node).__name__}")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def add(a: float, b: float) -> dict:
    """Add two numbers together.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The sum of a and b.
    """
    result = a + b
    return {"operation": "add", "a": a, "b": b, "result": result}


@mcp.tool()
def subtract(a: float, b: float) -> dict:
    """Subtract b from a.

    Args:
        a: The minuend.
        b: The subtrahend.

    Returns:
        The difference a - b.
    """
    result = a - b
    return {"operation": "subtract", "a": a, "b": b, "result": result}


@mcp.tool()
def multiply(a: float, b: float) -> dict:
    """Multiply two numbers.

    Args:
        a: First factor.
        b: Second factor.

    Returns:
        The product of a and b.
    """
    result = a * b
    return {"operation": "multiply", "a": a, "b": b, "result": result}


@mcp.tool()
def divide(a: float, b: float) -> dict:
    """Divide a by b.

    Args:
        a: The dividend.
        b: The divisor (must not be zero).

    Returns:
        The quotient a / b, or an error if b is zero.
    """
    if b == 0:
        return {"operation": "divide", "a": a, "b": b, "error": "Division by zero"}
    result = a / b
    return {"operation": "divide", "a": a, "b": b, "result": result}


@mcp.tool()
def calculate(expression: str) -> dict:
    """Safely evaluate a mathematical expression string.

    Supports: +, -, *, /, //, **, %, and functions:
    abs, round, sqrt, ceil, floor, log, log2, log10, sin, cos, tan.
    Constants: pi, e, inf.

    Args:
        expression: A math expression as a string, e.g. '2 ** 10 + sqrt(16)'.

    Returns:
        The evaluated result, or an error message if the expression is invalid.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval(tree)
        return {
            "expression": expression,
            "result": result,
            "result_type": type(result).__name__,
        }
    except ZeroDivisionError:
        return {"expression": expression, "error": "Division by zero"}
    except (ValueError, TypeError, SyntaxError) as exc:
        return {"expression": expression, "error": str(exc)}


if __name__ == "__main__":
    mcp.run()
