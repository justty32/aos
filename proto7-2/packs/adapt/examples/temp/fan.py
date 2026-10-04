"""示範消費者（adapt 包 examples/temp）：dst node 的普通 keep 任務，吃暫存器 `in/temp.json`，寫 `out/fan.json`。

    {"name": "fan", "mode": "keep", "argv": ["python3", "<這個檔>", "in/temp.json"]}

- 等暫存器的 `my_round` 前進（不等 tock：同一個 tock 裡 adapt 與 fan 誰先醒沒保證，藍圖 §3.4）。
- `state: ok` 才動作：`out/fan.json`＝`{"on": hot, "basis": 抄暫存器的 basis, "my_round", "held": 0}`。
- 不是 ok（unknown／absent）：保持上一個動作，`held` +1、記 `why`——沿用舊值的 node 必須看得到 unknown。
"""
import os
import sys
import time

TOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path[:0] = [os.path.join(TOP, "lib")]
from aos7_fs import OK, fact, is_int, now, write_json  # noqa: E402

OUT = os.path.join("out", "fan.json")


def main():
    reg_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join("in", "temp.json")
    st, prev = fact(OUT)
    prev = prev if st == OK and isinstance(prev, dict) else {"on": None, "basis": None, "held": 0}
    seen = prev.get("my_round") if is_int(prev.get("my_round")) else 0
    while True:
        st, r = fact(reg_path)
        if st == OK and isinstance(r, dict) and is_int(r.get("my_round")) and r["my_round"] > seen:
            seen = r["my_round"]
            if r.get("state") == "ok" and isinstance((r.get("value") or {}).get("hot"), bool):
                prev = {"on": r["value"]["hot"], "basis": r.get("basis"), "held": 0, "why": None}
            else:
                prev = dict(prev, held=prev.get("held", 0) + 1, why=r.get("why") or r.get("state"))
            prev.update(my_round=seen, at=now())
            write_json(OUT, prev)
        time.sleep(0.01)


if __name__ == "__main__":
    sys.exit(main())
