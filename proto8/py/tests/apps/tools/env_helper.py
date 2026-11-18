"""aos-tools 測試共用的乾淨子行程環境：拿掉 AOS_* 等前綴、不留 .pyc；aos 指令靠 PATH 上的 $AOS_HOME/bin。"""
import os


def clean_env(*, drop=(), **extra):
    """os.environ 拿掉 AOS_* 與 drop 列的前綴；PATH 照舊（env.sh 已把 $AOS_HOME/bin 排在最前）；extra 最後蓋上去。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("AOS_",) + tuple(drop))}
    env.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return env
