"""最小示範任務（spec.md 5.1、5.5）：證明任務讀得到同一個槽「上一次」留下的 state，也收得到 tock.json。

    tasks.json：{"name": "counter", "mode": "keep", "argv": ["python3", "<這個檔>", "3"]}

每收到一次 tock，把 `$AOS7_TASK/state.json` 的 `count` +1、記下 run 與回合；收到 N 次（預設 3）就結束。
keep 會在下一回合用同一個槽起新的 run，state.json 留著（W6），所以 count 一路接著數，`runs` 記得每個 run 號。

由 tick 經 aos7-run 啟動；只讀環境與槽內 tock.json，讀／寫 state.json，不碰核心任務表。
這是 P2-16 的狀態接續示範，對應不變條件三（spec §8）與跨回合任務（S-11）。
"""
import os
import sys

TOP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(TOP, "modules", "tools"), os.path.join(TOP, "lib")]
from aos7_fs import read_json, write_json  # noqa: E402
from aos7_taskside import task_env, wait_tock  # noqa: E402


def main(argv=None):
    """argv（None 用命令列）的首項是等待次數 N；每收到新 tock 累加 state，完成回 0（spec §5.1、§5.5、§8）。
    state 讀不到或不是物件時從空狀態開始；此示範不提供累計資料損毀恢復，未知 tock 由 wait_tock 繼續等。"""
    argv = sys.argv[1:] if argv is None else argv
    n = int(argv[0]) if argv else 3
    me = task_env()
    path = os.path.join(me["task"], "state.json")
    # spec §5.1、§8 不變條件三：接同槽上一次的 state，不依賴換 run 就清掉的 birth／exit。
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
