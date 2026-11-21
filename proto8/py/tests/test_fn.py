"""Test aos.py.fn marks: description and parameters taken from the function and written out (the written one wins, per parameter), and SpecBad; fn.main is in test_fn_run.py."""
from pathlib import Path
import sys
import textwrap
import unittest

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
from aos.py import fn  # noqa: E402
from aos import fn_mark, tool_spec  # noqa: E402


def spec(f, scanned=()):
    return fn_mark.tool_spec_of(f, scanned)


class Taken(unittest.TestCase):
    """Table 1 of design 03: what is taken from the function, what is written, and which one wins."""

    def test_all_taken(self):
        @fn.tool
        def add(a: float, b: int = 2, words: list[str] = ["x"], on: bool = False, opts: dict = {}, n: str = "s", raw: list = []):
            """Add things.

            Second paragraph of the description.

            Args:
              a: the first number
              b: the second number,
                 continued on a deeper line
              words: some words
              on: a switch
              opts: options
              n: a name
              raw: anything
            Returns:
              c: not read
            """
        name, td, mi = spec(add)
        self.assertEqual(name, "add")
        self.assertEqual(td["description"], "Add things.\n\nSecond paragraph of the description.")
        props = td["parameters"]["properties"]
        self.assertEqual({k: v["type"] for k, v in props.items()}, {"a": "number", "b": "integer", "words": "array", "on": "boolean",
                                                                     "opts": "object", "n": "string", "raw": "array"})
        self.assertEqual(list(props), ["a", "b", "words", "on", "opts", "n", "raw"])           # signature order
        self.assertEqual(props["b"], {"type": "integer", "description": "the second number, continued on a deeper line", "default": 2})
        self.assertEqual(props["words"]["items"], {"type": "string"})
        self.assertNotIn("items", props["raw"])
        self.assertEqual(td["parameters"]["required"], ["a"])
        self.assertEqual(td["errors"], ["ArgumentsBad", "RunFailed"])
        self.assertEqual(mi, tool_spec.metainfo("Add things.\n\nSecond paragraph of the description."))

    def test_string_annotations(self):
        src = textwrap.dedent('''\
            from __future__ import annotations
            from aos.py import fn
            @fn.tool
            def f(a: float, b: int, c: str, d: bool, e: list, g: dict, h: list[str]):
                """F.

                Args:
                  a: a
                  b: b
                  c: c
                  d: d
                  e: e
                  g: g
                  h: h
                """
            ''')
        space = {}
        exec(compile(src, "<string annotations>", "exec"), space)
        self.assertIsInstance(space["f"].__annotations__["a"], str)
        props = spec(space["f"])[1]["parameters"]["properties"]
        self.assertEqual([props[k]["type"] for k in "abcdegh"], ["number", "integer", "string", "boolean", "array", "object", "array"])
        self.assertEqual(props["h"]["items"], {"type": "string"})

    def test_written_wins_per_parameter(self):
        @fn.tool(name="sum", description="Written. Example: {\"a\": 1} -> 1", errors=["TooBig"], meta={"side_effect": True},
                 params=[fn.param("b", "integer", "written b", enum=[1, 2])])
        def add(a: float, b: float = 1):
            """Taken description.

            Args:
              a: taken a
              b: taken b
            """
        name, td, mi = spec(add, ["Scanned", "TooBig"])
        self.assertEqual(name, "sum")
        self.assertEqual(td["description"], "Written. Example: {\"a\": 1} -> 1")
        props = td["parameters"]["properties"]
        self.assertEqual(props["a"], {"type": "number", "description": "taken a"})
        self.assertEqual(props["b"], {"type": "integer", "description": "written b", "enum": [1, 2], "default": 1})
        self.assertEqual(td["errors"], ["ArgumentsBad", "TooBig", "Scanned", "RunFailed"])
        self.assertTrue(mi["side_effect"])
        self.assertEqual(mi["summary"], "Written")

    def test_written_param_needs_no_annotation_or_args(self):
        @fn.tool(params=[fn.param("x", "array", "the items", items="number")])
        def f(x):
            """Count the items."""
        self.assertEqual(spec(f)[1]["parameters"]["properties"]["x"], {"type": "array", "description": "the items", "items": {"type": "number"}})

    def test_decorator_returns_the_function(self):
        @fn.tool
        def add(a: int, b: int):
            """Add.

            Args:
              a: a
              b: b
            """
            return a + b
        self.assertEqual(add(2, 3), 5)


class Bad(unittest.TestCase):
    """Table 2 of design 03: SpecBad, one sentence that says how to fix it."""

    def check(self, f, message):
        with self.assertRaises(fn_mark.SpecBad) as caught:
            spec(f)
        self.assertEqual(str(caught.exception), message)

    def test_messages(self):
        @fn.tool
        def nodoc(a: int):
            pass
        self.check(nodoc, "tool nodoc has no description: write a docstring, or description=")

        @fn.tool
        def untyped(a, b):
            """D.

            Args:
              a: a
              b: b
            """
        self.check(untyped, 'parameter a needs a type (str, int, float, bool, list, dict), or fn.param("a", ...)')

        @fn.tool
        def odd(a: complex):
            """D.

            Args:
              a: a
            """
        self.check(odd, 'parameter a needs a type (str, int, float, bool, list, dict), or fn.param("a", ...)')

        @fn.tool
        def nodesc(a: int, b: int):
            """D.

            Args:
              a: a
            """
        self.check(nodesc, 'parameter b has no description: add "b: ..." under Args: in the docstring, or fn.param("b", ...)')

        @fn.tool
        def extra(a: int):
            """D.

            Args:
              a: a
              c: c
            """
        self.check(extra, "tool extra: Args: in the docstring names c, but the function has no parameter c")

        @fn.tool(params=[fn.param("c", "string", "c")])
        def extra2(a: int):
            """D.

            Args:
              a: a
            """
        self.check(extra2, "tool extra2: fn.param('c', ...), but the function has no parameter c")

        @fn.tool(params=[fn.param("a", "string", "x"), fn.param("a", "string", "y")])
        def twice(a):
            """D."""
        self.check(twice, "tool twice: fn.param('a', ...) is written twice")

    def test_signature_shapes(self):
        def star(*args):
            """D."""
        def kw(**kwargs):
            """D."""
        def kwonly(*, a: int):
            """D."""
        def posonly(a: int, /):
            """D."""
        for f in (star, kw, kwonly, posonly):
            with self.subTest(f=f.__name__):
                self.check(fn.tool(f), "tool %s: plain named parameters only (no *args, **kwargs, / or *)" % f.__name__)

    def test_block_in_a_tool_and_unmarked(self):
        @fn.tool
        def stop():
            """D."""
            return fn.block("no")
        self.check(stop, 'tool stop uses fn.block: only a hook can block; a tool reports its own error with fn.fail("Code", "why")')

        def plain():
            """D."""
        self.check(plain, 'plain is not marked: put @fn.tool (or @fn.hook("event")) on the function, then fn.main(it)')
        self.check(fn.hook("before_tool")(plain), "plain is a hook, not a tool")

    def test_type_errors_from_tool_spec(self):
        @fn.tool(params=[fn.param("a", "num", "x")])
        def f(a):
            """D."""
        self.check(f, "param a: type 'num' must be one of string, integer, number, boolean, array, object")

        @fn.tool
        def g(a: int = "1"):
            """D.

            Args:
              a: a
            """
        self.check(g, "param a: default '1' is not a integer")


class Marks(unittest.TestCase):
    def test_hook_mark(self):
        @fn.hook("on_clock", every_cycles=10, name="tidy", timeout_ms=5000)
        def h(event):
            pass
        self.assertEqual(getattr(h, fn_mark.MARK), {"kind": "hook", "event": "on_clock", "name": "tidy",
                                                    "entry": {"every_cycles": 10, "timeout_ms": 5000}})
        self.assertEqual(repr(fn.block("why")), "fn.block('why')")


if __name__ == "__main__":
    unittest.main()
