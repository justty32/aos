"""check - 拿 proto8/schema/comm/1/ 的四份 schema 驗一個值：有 Python jsonschema 就用它，沒有就用這裡只認這四份用到的關鍵字的小驗證器。

兩邊都把 format: date-time 當真檢查（照 times.parse：ISO 8601、要帶時區），jsonschema 預設不查 format，這裡另給 FormatChecker。
小驗證器認的關鍵字：$ref（只認 #/$defs/…）、type、const、enum、required、properties、additionalProperties、items、maxItems、
minLength、maxLength、minimum、if／then、format；$schema、$id、title、description、default 不影響結果；別的關鍵字＝SchemaBad（不默默放過）。"""
import json
import os

from . import Fail
from . import times

NAMES = ("board", "letter-comm", "channel", "channel-members")
BY_FORMAT = {"board/1": "board", "channel/1": "channel", "channel-members/1": "channel-members"}
_IGNORED = {"$schema", "$id", "$defs", "title", "description", "default"}
_KNOWN = _IGNORED | {"$ref", "type", "const", "enum", "required", "properties", "additionalProperties", "items",
                     "maxItems", "minLength", "maxLength", "minimum", "if", "then", "format"}


def schema_dir(start=None):
    """往上找 schema/comm/1/（從這支的真實位置起；repo 裡＝proto8/schema/comm/1）。找不到＝SchemaMissing。"""
    here = os.path.dirname(os.path.realpath(start or __file__))
    while True:
        d = os.path.join(here, "schema", "comm", "1")
        if os.path.isfile(os.path.join(d, "board.json")):
            return d
        up = os.path.dirname(here)
        if up == here:
            raise Fail("SchemaMissing", "schema/comm/1/ not found above %s" % os.path.dirname(os.path.realpath(start or __file__)))
        here = up


def load_schema(name, folder=None):
    if name not in NAMES:
        raise Fail("ArgumentsBad", "schema must be one of %s, not %r" % (", ".join(NAMES), name))
    path = os.path.join(folder or schema_dir(), name + ".json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as e:
        raise Fail("SchemaMissing", "cannot read %s: %s" % (path, e))


def engine():
    """'jsonschema'（裝了）或 'builtin'。"""
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        return "builtin"
    return "jsonschema"


def problems(value, schema, use=None):
    """value 不合 schema 的地方：[(JSON 指標, 原因)]；合＝[]。use＝'jsonschema'／'builtin'，沒給＝engine()。"""
    use = use or engine()
    if use == "jsonschema":
        import jsonschema
        fc = jsonschema.FormatChecker(formats=())
        fc.checks("date-time")(lambda v: not isinstance(v, str) or times.is_time(v))
        v = jsonschema.Draft202012Validator(schema, format_checker=fc)
        out = [("/" + "/".join(str(p) for p in e.absolute_path), e.message) for e in v.iter_errors(value)]
    else:
        out = []
        _walk(value, schema, schema, "", out)
    return sorted(out)


# ---- 小驗證器 --------------------------------------------------------------------------

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is(value, t):
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[t])


def _same(a, b):
    """JSON 的相等：true 不等於 1。"""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    return a == b


def _resolve(ref, root):
    if not ref.startswith("#/"):
        raise Fail("SchemaBad", "only local $ref like #/$defs/x is supported, not %r" % ref)
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _walk(value, node, root, at, out):
    unknown = set(node) - _KNOWN
    if unknown:
        raise Fail("SchemaBad", "the builtin checker does not know %s; install jsonschema" % ", ".join(sorted(unknown)))
    if "$ref" in node:
        _walk(value, _resolve(node["$ref"], root), root, at, out)
    where = at or "/"
    if "type" in node:
        ts = node["type"] if isinstance(node["type"], list) else [node["type"]]
        if not any(_is(value, t) for t in ts):
            out.append((where, "%s is not of type %s" % (json.dumps(value, ensure_ascii=False)[:60], " or ".join(ts))))
            return
    if "const" in node and not _same(value, node["const"]):
        out.append((where, "%s was expected" % json.dumps(node["const"], ensure_ascii=False)))
    if "enum" in node and not any(_same(value, e) for e in node["enum"]):
        out.append((where, "%s is not one of %s" % (json.dumps(value, ensure_ascii=False)[:60], node["enum"])))
    if isinstance(value, str):
        if "minLength" in node and len(value) < node["minLength"]:
            out.append((where, "shorter than %d characters" % node["minLength"]))
        if "maxLength" in node and len(value) > node["maxLength"]:
            out.append((where, "longer than %d characters" % node["maxLength"]))
        if node.get("format") == "date-time" and not times.is_time(value):
            out.append((where, "%r is not a date-time" % value[:60]))
    if _is(value, "number") and "minimum" in node and value < node["minimum"]:
        out.append((where, "%s is less than the minimum of %s" % (value, node["minimum"])))
    if isinstance(value, list):
        if "maxItems" in node and len(value) > node["maxItems"]:
            out.append((where, "has more than %d items" % node["maxItems"]))
        if "items" in node:
            for i, item in enumerate(value):
                _walk(item, node["items"], root, "%s/%d" % (at, i), out)
    if isinstance(value, dict):
        for k in node.get("required", ()):
            if k not in value:
                out.append((where, "%r is a required property" % k))
        props = node.get("properties", {})
        extra = node.get("additionalProperties", True)
        for k, v in value.items():
            if k in props:
                _walk(v, props[k], root, "%s/%s" % (at, k), out)
            elif extra is False:
                out.append((where, "additional property %r is not allowed" % k))
            elif isinstance(extra, dict):
                _walk(v, extra, root, "%s/%s" % (at, k), out)
    if "if" in node:
        trial = []
        _walk(value, node["if"], root, at, trial)
        if not trial and "then" in node:
            _walk(value, node["then"], root, at, out)
