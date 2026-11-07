"""Read optional definition metadata and evaluate numeric cost declarations safely."""

import ast
import json
import math
import operator
from pathlib import Path


class MetainfoError(Exception):
    """Expose a metadata error code without printing or exiting."""

    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def read(def_dir) -> dict | None:
    """Read directory metadata or a JSON tool's embedded metadata."""
    path = Path(def_dir)
    embedded = path.is_file() or (not path.is_dir() and path.suffix == ".json")
    source = path if embedded else path / "_metainfo.json"
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, ValueError) as exc:
        raise MetainfoError("FileBad", f"Cannot read metadata from {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise MetainfoError("FileBad", f"Metadata in {source} must be an object")
    if embedded:
        if "_metainfo" not in data:
            return None
        data = data["_metainfo"]
        if not isinstance(data, dict):
            raise MetainfoError("FileBad", f"Embedded metadata in {source} must be an object")
    return data


def _number(value, code):
    if type(value) not in (int, float):
        raise MetainfoError(code, "Expected a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise MetainfoError(code, "Expected a finite number") from exc
    if not math.isfinite(result):
        raise MetainfoError(code, "Expected a finite number")
    return result


def timeout_ms(meta) -> int | None:
    """Return the declared timeout in integer milliseconds, if present."""
    if meta is None or "timeout_ms" not in meta:
        return None
    value = meta["timeout_ms"]
    if isinstance(value, dict):
        value = value.get("val")
    number = _number(value, "FileBad")
    if not number.is_integer():
        raise MetainfoError("FileBad", "Timeout must be an integer number of milliseconds")
    return int(number)


_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub,
           ast.Mult: operator.mul, ast.Div: operator.truediv}


def _calculate(expression, variables):
    if not isinstance(expression, str) or "__" in expression:
        raise MetainfoError("CalBad", "Formula must be text without double underscores")

    def visit(node):
        if isinstance(node, ast.Constant):
            return _number(node.value, "CalBad")
        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise MetainfoError("CalBad", f"Unknown formula variable: {node.id}")
            return _number(variables[node.id], "CalBad")
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            return _number(_BINARY[type(node.op)](visit(node.left), visit(node.right)), "CalBad")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -visit(node.operand)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ("min", "max") and not node.keywords
                and node.args):
            values = [visit(arg) for arg in node.args]
            return (min if node.func.id == "min" else max)(values)
        raise MetainfoError("CalBad", "Unsupported formula syntax")

    try:
        return visit(ast.parse(expression, mode="eval").body)
    except (SyntaxError, ArithmeticError, ValueError, TypeError, RecursionError) as exc:
        raise MetainfoError("CalBad", f"Cannot evaluate formula: {exc}") from exc


def eval_cost(value, vars) -> float | None:
    """Evaluate a numeric, val, or cal cost; ignore unknown evaluators."""
    if value is None:
        return None
    if isinstance(value, dict):
        if "val" in value:
            return _number(value["val"], "FileBad")
        if "cal" in value:
            return _calculate(value["cal"], vars)
        if len(value) == 1:
            return None
        raise MetainfoError("FileBad", "Cost must declare a value or one evaluator")
    return _number(value, "FileBad")
