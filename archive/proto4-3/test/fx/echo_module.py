"""kernel module 測試替身。"""
import os

NAME = "echo"
OPS = ("echo",)


def handle(h, cfg, st, ticket):
    text = ticket.get("text")
    if not isinstance(text, str):
        return False, "echo 沒有 text"
    with open(os.path.join(h.dir, "echo.txt"), "w", encoding="utf-8") as stream:
        stream.write(text)
    return True, "echoed"


def tick(h, cfg, st):
    return ["echo tick"]


def status(h, cfg):
    return "echo: ok"


def cli(h, cfg, argv):
    print(" ".join(argv))
    return 0
