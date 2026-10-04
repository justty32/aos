"""示範發布者（adapt 包 examples/temp）：src node 的普通 keep 任務，每個 tock 寫一份 `out/temp.json`。

    {"name": "sensor", "mode": "keep", "argv": ["python3", "<這個檔>"]}

內容＝`{"v": 1, "seq": n, "round": 這個 tock 的回合, "value": {"t_dc": 整數十分之一度}, "at"}`，用核心 write_json（原子
rename）寫。`t_dc` 從 node 的 `feed.json`（`{"t_dc": 801}`，給測試與人手調）讀；沒有就用一個確定性的鋸齒波。
`seq` 存在槽內 state.json，換 run 接著數（node 重建、槽被刪才從 1 起）。
"""
import os
import sys

TOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path[:0] = [os.path.join(TOP, "modules", "tools"), os.path.join(TOP, "lib")]
from aos7_fs import OK, fact, is_int, now, write_json  # noqa: E402
from aos7_taskside import task_env, wait_tock  # noqa: E402


def reading(rnd):
    st, f = fact("feed.json")
    if st == OK and isinstance(f, dict) and is_int(f.get("t_dc")):
        return f["t_dc"]
    return 700 + (rnd * 37) % 200


def main():
    me = task_env()
    state = os.path.join(me["task"], "state.json")
    st, s = fact(state)
    seq = s["seq"] if st == OK and isinstance(s, dict) and is_int(s.get("seq")) else 0
    last = 0
    while True:
        last = wait_tock(me["task"], last, poll=0.005)
        seq += 1
        write_json(state, {"seq": seq})            # 先記號再發布：被殺在中間只會跳號，不會重號
        write_json(os.path.join("out", "temp.json"),
                   {"v": 1, "seq": seq, "round": last, "value": {"t_dc": reading(last)}, "at": now()})


if __name__ == "__main__":
    sys.exit(main())
