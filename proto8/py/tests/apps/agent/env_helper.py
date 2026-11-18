"""aos-agent 測試共用的小零件：乾淨的子行程環境（拿掉 AOS_* 等前綴、不留 .pyc）、輪詢等條件成立。"""
import os
import time


def clean_env(*, drop=(), path=(), **extra):
    """os.environ 拿掉 AOS_* 與 drop 列的前綴；path＝要排在 PATH 最前面的夾（照順序）；extra 最後蓋上去。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("AOS_",) + tuple(drop))}
    if path:
        env["PATH"] = os.pathsep.join([str(p) for p in path] + [env.get("PATH", "")])
    env.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return env


def until(condition, timeout=10):
    """每 0.05 秒問一次 condition()，回第一個真值；timeout 秒內都不真＝AssertionError("timed out")。"""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = condition()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError("timed out")
