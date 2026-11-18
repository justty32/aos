"""atomic_file - agent-fsm 的格（idle、wait）共用的寫檔：先寫同資料夾的 .<名>.tmp 再改名（N-05），寫不成交給呼叫端的 die（WriteFailed）。

錯誤行由呼叫端那支的 die 印（程式名、格式照它自己），這裡只給代號與原因；不 import aos_flags，跟 llm_settings 一樣只靠標準庫。
"""
import os


def write_atomic(path, text, die):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")   # N-05：先寫暫存再改名
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError as e:
        die("WriteFailed", "cannot write %s: %s" % (path, e))
