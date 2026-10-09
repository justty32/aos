"""長跑讀者（keep 任務）：每個 tock 讀完 must 通道，核對 i 連號，先存游標再 ack（消費確認）。"""
import os
import sys

TOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path[:0] = [os.path.join(TOP, "modules", "tools"), os.path.join(TOP, "lib"), os.path.join(TOP, "modules", "events")]
from aos7_fs import Unknown, read_json, write_json  # noqa: E402
from aos7_taskside import task_env, wait_tock  # noqa: E402
import aos7_events_read as reader  # noqa: E402
import aos7_events_store as store  # noqa: E402


def drain(events, st):
    """從游標讀到底；游標只推過連號且處理成功的紀錄，遇壞行／錯號就停在那裡（不 ack 過去）。"""
    n = 0
    while True:
        res = reader.read(events, "must", st["cursor"], limit=100)
        for rec in res["records"]:
            payload = rec.get("payload")
            i = payload.get("i") if isinstance(payload, dict) else None
            if i != st["last_i"] + 1:
                st["dups" if isinstance(i, int) and i <= st["last_i"] else "out_of_order"] += 1
                return n
            st["last_i"], st["cursor"] = i, rec["seq"] + 1
            st["got"] += 1
            n += 1
        if res["errors"] or res["gaps"]:
            st["errors"] += len(res["errors"])
            st["gaps"] += len(res["gaps"])
            return n
        if not res["records"]:
            return n


def main():
    me = task_env()
    events = os.path.join(me["node"], "events")
    path = os.path.join(me["node"], "longrun", "reader.json")   # 固定一個檔
    os.makedirs(os.path.dirname(path), exist_ok=True)
    st = {"cursor": 1, "last_i": 0, "got": 0, "dups": 0, "out_of_order": 0, "errors": 0, "gaps": 0, "ack_unknown": 0}
    st.update(read_json(path, {}) or {})
    last = 0
    while True:
        last = wait_tock(me["task"], last)
        if store.load_state(events) is None:
            continue
        drain(events, st)
        st["round"] = last
        write_json(path, st)             # 先記住讀到哪，再確認消費；被殺在中間只會晚 ack，不會漏讀
        try:
            store.ack(events, st["cursor"] - 1)
        except Unknown:
            st["ack_unknown"] += 1       # 下個 tock 用同值重送


if __name__ == "__main__":
    sys.exit(main())
