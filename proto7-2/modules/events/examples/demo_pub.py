"""once 示範：工作可重做，保存確認後才推進任務進度。"""
import argparse
import os
import sys

TOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path[:0] = [os.path.join(TOP, "modules", "tools"), os.path.join(TOP, "lib"), os.path.join(TOP, "modules", "events")]
from aos7_fs import read_json, write_json, test_point  # noqa: E402
from aos7_taskside import task_env  # noqa: E402
from aos7_events_pub import publish, exit_code  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--batch", default="demo")
    for name in ("events", "node", "state", "out"):
        ap.add_argument("--" + name)
    a = ap.parse_args(argv)
    if a.n < 0:
        ap.error("--n 不可為負")
    if not all((a.events, a.node, a.state, a.out)):
        try:
            me = task_env()
        except (KeyError, ValueError):
            ap.error("須提供 events／node／state／out 或完整任務環境")
        a.events = a.events or os.path.join(me["node"], "events")
        a.node = a.node or me["node_id"]
        a.state = a.state or os.path.join(me["task"], "state.json")
        a.out = a.out or os.path.join(me["node"], "demo-out")
    st = read_json(a.state, {})
    done = st.get("done_upto", 0) if isinstance(st, dict) else 0
    if type(done) is not int or done < 0:
        ap.error("done_upto 須為非負整數")
    os.makedirs(a.out, exist_ok=True)
    for i in range(done + 1, a.n + 1):
        with open(os.path.join(a.out, "item-%d.txt" % i), "w", encoding="utf-8") as f:
            f.write("item %d: ok\n" % i)
        test_point("events:demo-after-work")
        result = publish(a.events, "demo.item.done", "%s/%s/%d" % (a.node, a.batch, i),
                         {"item": i, "result": "ok"}, must=True,
                         source={"node": a.node, "task": a.batch, "item": i}, node=a.node)
        test_point("events:demo-after-publish")
        if not result["ok"]:
            print(result.get("why"), file=sys.stderr)
            return exit_code(result)
        write_json(a.state, {"done_upto": i})
    return 0


if __name__ == "__main__":
    sys.exit(main())
