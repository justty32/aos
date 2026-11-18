"""aos-tools 測試共用的乾淨子行程環境：拿掉 AOS_* 等前綴、~/.local/bin 排在 PATH 最前面、不留 .pyc。"""
import os


def clean_env(*, drop=(), **extra):
    """os.environ 拿掉 AOS_* 與 drop 列的前綴；PATH 前面加 ~/.local/bin（跟搬來前一樣）；extra 最後蓋上去。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("AOS_",) + tuple(drop))}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return env
