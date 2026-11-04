from pathlib import Path


def proc(path: str) -> int:
    return len(Path(path).read_text(encoding='utf-8').splitlines())


def proc2(path: str) -> int:
    return len(Path(path).read_text(encoding='utf-8').split())


def proc3(path: str) -> int:
    return len(Path(path).read_bytes())


def xf(text: str) -> str:
    return text[::-1]


def xf2(text: str) -> str:
    return ' '.join(w.capitalize() for w in text.split())


def calc2(a: int, b: int) -> int:
    return a * b


def calc3(a: int, b: int) -> int:
    return (a + b) % 7
