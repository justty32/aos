"""smoke：探針工具本身能用（起 daemon、跑三回合、收乾淨）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import probelib as pl  # noqa: E402


def main():
    r = pl.Result("smoke")
    with pl.Space("smoke") as sp:
        sp.node("a", [{"name": "q", "argv": ["true"]}], interval_ms=50)
        sp.start()
        sp.wait_for(lambda: len(sp.rounds("a")) >= 3)
        r.check("三回合都有總結", len(sp.rounds("a")) >= 3)
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
