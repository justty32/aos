"""Read optional definition metadata and evaluate numeric cost declarations safely.

Metadata is a point of view, not a rule: anything broken counts as not written.
read, timeout_ms and eval_cost return None for it and, given a notes list, append one English sentence.
"""

import ast
import json
import math
import operator
from pathlib import Path


class MetainfoError(Exception):
    """Internal: why a value was skipped (never raised out of read, timeout_ms or eval_cost)."""

    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def _walk(data, pointer, source):
    """Follow a JSON Pointer (RFC 6901: ~1 is /, ~0 is ~); a missing key raises MetainfoError."""
    for raw in pointer.split("/")[1:]:
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(data, list) and key.isdigit() and int(key) < len(data):
            data = data[int(key)]
        elif isinstance(data, dict) and key in data:
            data = data[key]
        else:
            raise MetainfoError("FileBad", f"{source}#{pointer} does not exist")
    return data


def _skip(notes, sentence):
    if isinstance(notes, list):
        notes.append(sentence)


def read(def_dir, notes=None) -> dict | None:
    """Read directory metadata, a JSON tool's embedded metadata, or FILE.json#/POINTER (the object there).

    No file = None. Unreadable, not JSON, not an object, or a pointer to nothing = None plus a note.
    """
    try:
        return _read(def_dir)
    except MetainfoError as exc:
        _skip(notes, f"{exc}, skipped")
        return None


def _read(def_dir):
    text = str(def_dir)
    pointer = None
    if "#/" in text:                                 # 11-10 深夜 tools-def：位置可以是 檔.json#/指標
        text, _, rest = text.partition("#")
        pointer = rest
    path = Path(text)
    embedded = pointer is not None or path.is_file() or (not path.is_dir() and path.suffix == ".json")
    source = path if embedded else path / "_metainfo.json"
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, ValueError) as exc:
        raise MetainfoError("FileBad", f"cannot read metadata from {source}: {exc}") from exc
    if pointer is not None:
        data = _walk(data, pointer, source)
        source = f"{source}#{pointer}"
    if not isinstance(data, dict):
        raise MetainfoError("FileBad", f"metadata in {source} is not an object")
    if embedded:
        if "_metainfo" not in data:
            return None
        data = data["_metainfo"]
        if not isinstance(data, dict):
            raise MetainfoError("FileBad", f"_metainfo in {source} is not an object")
    return data


def _number(value, code):
    if type(value) not in (int, float):
        raise MetainfoError(code, "not a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise MetainfoError(code, "not a finite number") from exc
    if not math.isfinite(result):
        raise MetainfoError(code, "not a finite number")
    return result


def timeout_ms(meta, notes=None) -> int | None:
    """Return the declared timeout in integer milliseconds as written (0 and negatives included).

    Not written, or meta not an object = None. A value that is not an integer number = None plus a note.
    """
    if not isinstance(meta, dict) or "timeout_ms" not in meta:
        return None
    value = meta["timeout_ms"]
    if isinstance(value, dict):
        value = value.get("val")
    try:
        number = _number(value, "FileBad")
    except MetainfoError:
        number = None
    if number is None or not number.is_integer():
        _skip(notes, "timeout_ms is not an integer number of milliseconds, skipped")
        return None
    return int(number)


_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub,
           ast.Mult: operator.mul, ast.Div: operator.truediv}


def _calculate(expression, variables):
    if not isinstance(expression, str) or "__" in expression:
        raise MetainfoError("CalBad", "formula must be text without double underscores")

    def visit(node):
        if isinstance(node, ast.Constant):
            return _number(node.value, "CalBad")
        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise MetainfoError("CalBad", f"unknown formula variable: {node.id}")
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
        raise MetainfoError("CalBad", "unsupported formula syntax")

    try:
        return visit(ast.parse(expression, mode="eval").body)
    except (SyntaxError, ArithmeticError, ValueError, TypeError, RecursionError) as exc:
        raise MetainfoError("CalBad", f"cannot evaluate formula: {exc}") from exc


def eval_cost(value, vars, notes=None) -> float | None:
    """Evaluate a numeric, val, or cal cost; an unknown evaluator = None.

    A bad value, a bad formula, or a missing variable = None plus a note.
    """
    try:
        return _eval_cost(value, vars)
    except MetainfoError as exc:
        _skip(notes, f"cost {json.dumps(value, ensure_ascii=False, default=str)}: {exc}, skipped")
        return None


def _eval_cost(value, vars):
    if value is None:
        return None
    if isinstance(value, dict):
        if "val" in value:
            return _number(value["val"], "FileBad")
        if "cal" in value:
            return _calculate(value["cal"], vars)
        if len(value) == 1:
            return None
        raise MetainfoError("FileBad", "cost must declare a value or one evaluator")
    return _number(value, "FileBad")
