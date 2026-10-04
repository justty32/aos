"""最小示範任務（spec.md 5.1、5.5）：證明任務讀得到同一個槽「上一次」留下的 state，也收得到 tock.json。

    tasks.json：{"name": "counter", "mode": "keep", "argv": ["python3", "<這個檔>", "3"]}

每收到一次 tock，把 `$AOS7_TASK/state.json` 的 `count` +1、記下 run 與回合；收到 N 次（預設 3）就結束。
keep 會在下一回合用同一個槽起新的 run，state.json 留著（W6），所以 count 一路接著數，`runs` 記得每個 run 號。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
from aos7_fs import read_json, task_env, wait_tock, write_json  # noqa: E402


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    n = int(argv[0]) if argv else 3
    me = task_env()
    path = os.path.join(me["task"], "state.json")
    st = read_json(path, {})
    st = st if isinstance(st, dict) else {}
    st.setdefault("count", 0)
    st["runs"] = (st.get("runs") or []) + [me["run"]]
    write_json(path, st)
    last = 0
    for _ in range(n):
        last = wait_tock(me["task"], last)
        st["count"] += 1
        st["last_round"] = last
        write_json(path, st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
