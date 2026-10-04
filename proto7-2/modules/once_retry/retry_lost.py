"""once 保證包：把「從沒起來過就 lost」的 once 加回 tasks.json，變成至少一次（spec 見同資料夾的 README.md）。

    tasks.json：{"name": "retry", "mode": "keep", "argv": ["python3", "<這個檔>"]}
    要保證的 once 項：{"name": "fix", "mode": "once", "argv": [...], "x": {"retry_lost": true}}

普通 keep 任務。每收到一次 tock，讀自己 node 的 `.aos/last-round.json`：`ended` 裡 `lost` 且 `never_started`（核心的事實欄）的，
槽的 birth.json（槽還在）`x.retry_lost` 是 true、表上還沒有 `x.retry_of`＝那個 run id 的 → 照 birth 的定義（argv／inst、mounts、x）
拿表鎖加回一項 once（`slot` 釘同槽、`x.retry_of`）。加不回（表鎖拿不到、表壞掉）的記著，下一次 tock 再試。
"""
import os
import sys

TOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.join(TOP, "modules", "tools"), os.path.join(TOP, "lib")]
import aos7_mount  # noqa: E402
from aos7_fs import OK, Unknown, edit_json, fact  # noqa: E402


def candidates(node):
    """這一次的 last-round.json 裡要加回的：[(run id, 槽名, birth)]。"""
    st, lr = fact(os.path.join(node, ".aos", "last-round.json"))
    out = []
    for e in (lr.get("ended") or []) if st == OK and isinstance(lr, dict) else []:
        if not (isinstance(e, dict) and e.get("lost") and e.get("never_started") and isinstance(e.get("run"), str)):
            continue
        slot, _, run = e["run"].rpartition("#")
        bst, b = fact(os.path.join(node, ".aos", "tasks", slot, "birth.json"))
        if (bst == OK and isinstance(b, dict) and str(b.get("run")) == run and b.get("once") is True
                and (b.get("x") or {}).get("retry_lost") is True):
            out.append((e["run"], slot, b))
    return out


def requeue(node, rid, slot, birth):
    """照 birth 的定義把 once 加回 tasks.json（表上已有同 retry_of 的就不加）。回 True＝加了或已有；表鎖拿不到、表壞掉丟 Unknown。"""
    item = {k: birth[k] for k in ("argv", "inst") if k in birth}
    item.update({"name": birth["name"], "mode": "once", "slot": slot, "mounts": aos7_mount.decl_of(birth),
                 "x": dict(birth.get("x") or {}, retry_of=rid)})

    def add(t):
        t = {"tasks": []} if t is None else t
        if not isinstance(t, dict) or not isinstance(t.get("tasks", []), list):
            raise Unknown("tasks.json 不是 {\"tasks\": [...]}，沒加", kind="bad")
        if any(isinstance(i, dict) and (i.get("x") or {}).get("retry_of") == rid for i in t.get("tasks", [])):
            return None
        return dict(t, tasks=list(t.get("tasks", [])) + [item])
    edit_json(os.path.join(node, ".aos", "tasks.json"), add, timeout=1.0)
    return True


def scan(node, pending=None):
    """處理一次：把 last-round.json 的候選加上 pending（之前沒加成的）都試著加回。回還沒加成的 {run id: (槽, birth)}。"""
    todo = dict(pending or {})
    for rid, slot, b in candidates(node):
        todo.setdefault(rid, (slot, b))
    left = {}
    for rid, (slot, b) in todo.items():
        try:
            requeue(node, rid, slot, b)
        except (Unknown, OSError) as e:
            print("retry_lost: %s 沒加回（%s），下一次再試" % (rid, e), file=sys.stderr, flush=True)
            left[rid] = (slot, b)
    return left


def main():
    from aos7_taskside import task_env, wait_tock
    me = task_env()
    last, pending = 0, {}
    while True:
        last = wait_tock(me["task"], last)
        pending = scan(me["node"], pending)


if __name__ == "__main__":
    sys.exit(main())
