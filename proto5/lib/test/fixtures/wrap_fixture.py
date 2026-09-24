"""aos-agent tools wrap-py 的固定 fixture（test_agent_tools_dev.py 用）。

上半：該收的，每種支援的型別各一支；下半：該拒收的，每種原因各一支。
最後一支 count_words 是給真模型用的實用函式（隊長會裝給工人，驗「模型沒寫任何 bash」）。
這個檔只給 wrap-py 靜態讀；測試裡 run 會 import 它的副本，所以頂層不能有副作用。
"""
from collections import Counter
import functools
import os
import re
from typing import Dict, List, Literal, Optional


# ---------------------------------------------------------------- 該收的 ----

def echo(text: str) -> str:
    """Return the text unchanged."""
    return text


def double(n: int) -> int:
    """Double an integer."""
    return n * 2


def half(x: float) -> float:
    """Halve a number."""
    return x / 2


def negate(flag: bool) -> bool:
    """Flip a boolean."""
    return not flag


def join_words(words: list[str], sep: str = ' ') -> str:
    """Join words with a separator.

    Args:
        words (list[str]): The words to join.
        sep: Separator between words.
    """
    return sep.join(words)


def total(counts: dict[str, int]) -> int:
    """Sum the values of a mapping.

    Parameters
    ----------
    counts : dict[str, int]
        Name to count.
    """
    return sum(counts.values())


def pick(color: Literal['red', 'green', 'blue']) -> str:
    """Pick a color."""
    return 'picked ' + color


def maybe(label: Optional[str] = None, times: int | None = None) -> str:
    """Show optional values."""
    return 'label=%r times=%r' % (label, times)


def scale(value: float, *, factor: float = 2.0, round_to: int = 2) -> float:
    """Scale a number (keyword-only options).

    Args:
        value: The number.
        factor: Multiplier.
        round_to: Decimal places.
    """
    return round(value * factor, round_to)


def legacy(names: List[str], table: Dict[str, float]) -> dict:
    """Old typing spellings (typing.List／typing.Dict)."""
    return {'names': names, 'keys': sorted(table)}


def stats(numbers: list[float]) -> dict:
    """Return min, max and mean of numbers as a dict."""
    return {'min': min(numbers), 'max': max(numbers), 'mean': sum(numbers) / len(numbers)}


def boom(message: str) -> str:
    """Always raise ValueError with the message."""
    raise ValueError(message)


def interrupt(n: int) -> int:
    """Raise KeyboardInterrupt (a BaseException, not an Exception)."""
    raise KeyboardInterrupt('stop %d' % n)


def quit_now(code: int) -> int:
    """Call sys.exit (SystemExit)."""
    raise SystemExit(code)


def not_json(n: int) -> object:
    """Return something json.dumps cannot handle."""
    return {n, n + 1}


def no_doc(a: int, b: int = 3):
    return a + b


def count_words(path: str, top: int = 5) -> dict:
    """Count words in a text file in the project and return the most common ones.

    Args:
        path: File path, relative to the project directory.
        top: How many of the most common words to return.
    """
    root = os.environ.get('AOS_TOOL_ROOT') or os.getcwd()
    full = os.path.join(root, path)
    with open(full, encoding='utf-8', errors='replace') as f:
        words = re.findall(r"[A-Za-z0-9_']+|[^\x00-\x7f\s\W]", f.read().lower())
    counts = Counter(words)
    return {'path': path, 'total_words': len(words), 'distinct_words': len(counts),
            'top': [[w, n] for w, n in counts.most_common(max(top, 0))]}


# ---------------------------------------------------------------- 該拒收的 ----

class Point:
    x: int = 0


def no_annotation(a, b: int) -> int:
    """a has no annotation."""
    return b


def star_args(*items: str) -> str:
    """*args is not supported."""
    return ''.join(items)


def star_kwargs(**options: str) -> str:
    """**kwargs is not supported."""
    return ''.join(options)


def positional_only(a: int, /, b: int) -> int:
    """positional-only parameters are not supported."""
    return a + b


def custom_class(p: Point) -> int:
    """A custom class is not a JSON type."""
    return p.x


async def fetch(url: str) -> str:
    """async def is not supported."""
    return url


@functools.lru_cache(maxsize=None)
def cached(n: int) -> int:
    """Decorated functions are rejected."""
    return n


def outer(n: int) -> int:
    """Only outer is top-level; inner is not."""
    def inner(m: int) -> int:
        return m + 1
    return inner(n)


def _private(n: int) -> int:
    """Underscore names are skipped."""
    return n
