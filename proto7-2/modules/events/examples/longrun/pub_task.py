"""長跑發布者（keep 任務）：每個 tock 發一件 obs、一件 must；保存確認後才推進自己的 done_upto。"""
import argparse
import os
import sys

TOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path[:0] = [os.path.join(TOP, "modules", "tools"), os.path.join(TOP, "lib"), os.path.join(TOP, "modules", "events")]
from aos7_fs import read_json, write_json  # noqa: E402
from aos7_taskside import task_env, wait_tock  # noqa: E402
from aos7_events_pub import publish  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pad", type=int, default=200, help="payload 填充 bytes，讓段輪替快一點")
    a = ap.parse_args(argv)
    me = task_env()
    events = os.path.join(me["node"], "events")
    state_path = os.path.join(me["node"], "longrun", "pub.json")   # 固定一個檔，不每回合新檔
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    st = read_json(state_path, {}) or {}
    done, refused = st.get("done_upto", 0), st.get("refused", 0)
    last = 0
    while True:
        last = wait_tock(me["task"], last)
        i = done + 1
        src = {"node": me["node_id"], "task": "longrun", "item": i, "round": last}
        # obs 一般觀測：不必等人讀，滿了刪最舊
        o = publish(events, "longrun.tick", "%s/longrun/obs/%d" % (me["node_id"], i), {"i": i, "pad": "x" * a.pad},
                source=src, node=me["node_id"])
        # must 必讀：讀者 ack 了才清；full／unknown 不推進，下個 tock 用同 event_id 重送
        r = publish(events, "longrun.item", "%s/longrun/%d" % (me["node_id"], i), {"i": i, "pad": "y" * a.pad},
                    must=True, source=src, node=me["node_id"])
        if r["ok"] and o["ok"]:          # 兩件都保存確認才推進；否則下個 tock 兩件都用原 event_id 重送（dup 不重寫）
            done = i
        elif r.get("why") == "full":
            refused += 1
        write_json(state_path, {"done_upto": done, "refused": refused, "round": last})


if __name__ == "__main__":
    sys.exit(main())
