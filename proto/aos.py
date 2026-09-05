#!/usr/bin/env python3
"""aos 原型入口。用法：python3 proto/aos.py <子命令> …

這是玩的原型，不是正式實作。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aosp import cli  # noqa: E402

if __name__ == "__main__":
    sys.exit(cli.main() or 0)
