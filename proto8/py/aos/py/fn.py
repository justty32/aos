"""fn - Python functions as tools and hooks: @fn.tool, @fn.hook("event"), fn.param, fn.fail, fn.block, fn.main(function).

    from aos.py import fn

    @fn.tool(meta={"side_effect": False})
    def add(a: float, b: float) -> float:
        \"\"\"Add two numbers and return the sum. Example: {"a": 2, "b": 3} -> 5

        Args:
          a: the first number
          b: the second number
        \"\"\"
        return a + b

    fn.main(add)

Description and parameters: both are taken, the written one wins (description=, params=[fn.param(...)]), one parameter at a time.
The name fn is the user's 11-20 answer (thinking/2026-11/20/aos-pylib-plan-1120/12, question 4). Only re-exports: the code is in
aos.fn_mark (the marks and the description they compile to) and aos.fn_run (fn.main, fn.fail, fn.block)."""
from aos.fn_mark import tool, hook, param  # noqa: F401
from aos.fn_run import main, fail, block, Fail, Block  # noqa: F401

__all__ = ["tool", "hook", "param", "fail", "block", "main", "Fail", "Block"]
