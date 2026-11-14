"""Read the shared dotenv subset without changing the process environment."""
import os
import re

ENV_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class Error(ValueError):
    """A dotenv failure with location and cause for caller-specific diagnostics."""

    code = "DotenvBad"

    def __init__(self, message, *, line=None, cause=None):
        super().__init__(message)
        self.line = line
        self.cause = cause


def read_env_file(path):
    """Read assignments; later lines override earlier ones and can expand them."""
    result = {}
    inherited = dict(os.environ)

    def bad(line, cause=None):
        raise Error("bad env file %s at line %d" % (path, line), line=line, cause=cause)

    def expand(value, line):
        parts, pos = [], 0
        while True:
            start = value.find("${", pos)
            if start < 0:
                parts.append(value[pos:])
                return "".join(parts)
            end = value.find("}", start + 2)
            if end < 0:
                bad(line)
            key = value[start + 2:end]
            if not ENV_KEY_RE.fullmatch(key) or (key not in result and key not in inherited):
                bad(line)
            parts.extend((value[pos:start], result[key] if key in result else inherited[key]))
            pos = end + 1

    try:
        with open(path, "rb") as stream:
            for number, raw in enumerate(stream, 1):
                try:
                    line = raw.decode("utf-8").removesuffix("\n").removesuffix("\r")
                except UnicodeDecodeError as e:
                    bad(number, e)
                line = line.lstrip(" \t\r\n\v\f")
                if not line or line.startswith("#"):
                    continue
                # Only treat export as a prefix when followed by whitespace, not '='.
                if line.startswith(("export ", "export\t")):
                    rest = line[6:].lstrip(" \t")
                    if not rest.startswith("="):
                        line = rest
                key, eq, value = line.partition("=")
                key = key.rstrip(" \t")
                if not eq or not ENV_KEY_RE.fullmatch(key) or "\0" in value:
                    bad(number)
                trimmed = value.lstrip()
                if trimmed.startswith("#") and trimmed != value:
                    bad(number)
                if trimmed.startswith(("'", '"')):
                    quote = trimmed[0]
                    end = trimmed.find(quote, 1)
                    if end < 0:
                        bad(number)
                    value, tail = trimmed[1:end], trimmed[end + 1:].strip()
                    if (tail and not tail.startswith("#")) or "\\" in value or (quote == "'" and "${" in value):
                        bad(number)
                    if quote == '"':
                        value = expand(value, number)
                else:
                    # A hash starts a comment only after whitespace; keep a#b and #fff.
                    for index, char in enumerate(value):
                        if char == "#" and index > 0 and value[index - 1].isspace():
                            value = value[:index]
                            break
                    value = expand(value.strip(), number)
                if "\0" in value:
                    bad(number)
                result[key] = value
    except OSError as e:
        raise Error("cannot read env file %s" % path, cause=e) from None
    return result
