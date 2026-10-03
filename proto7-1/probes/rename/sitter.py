"""rename 的 keep 任務（node a）：同時用「環境變數的絕對路徑」與「相對 cwd 的路徑」等 tock，看 node 搬家後哪個還通。

每收到一次 tock（任一條路先看到）：
- 經過掛載點 mnt/b_in 寫一封信給 b（相對 cwd 走到自己的任務資料夾）；
- 往 $AOS7_NODE/abs_beat.log 加一行（絕對路徑，不建資料夾）；
- 寫 progress.json（相對 cwd）：兩條路各看到第幾回合、AOS7_NODE、getcwd、寄信成敗。
不用 aos7_fs（它的 write_json 會 makedirs，會把搬走的舊路徑建回來）。
"""
import json
import os
import sys
import time

E = os.environ
T_ABS = E["AOS7_TASK"]
TID = E["AOS7_TID"]
T_REL = os.path.join(".aos", "tasks", TID)     # cwd＝node；資料夾搬走時 cwd 跟著走


def rnd(path):
    try:
        with open(path) as f:
            return json.load(f).get("round", 0)
    except (OSError, ValueError):
        return 0


def put(path, obj):
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


st = {"abs_round": 0, "rel_round": 0, "sent": 0, "send_err": 0, "abs_beat_err": 0, "last_err": None, "last_send_err": None}
last = 0
while True:
    a, r = rnd(os.path.join(T_ABS, "tock.json")), rnd(os.path.join(T_REL, "tock.json"))
    st["abs_round"], st["rel_round"] = max(st["abs_round"], a), max(st["rel_round"], r)
    now = max(a, r)
    if now > last:
        last = now
        try:
            put(os.path.join(T_REL, "mnt", "b_in", "%s-%d.json" % (TID, now)), {"from": "a", "round": now})
            st["sent"] += 1
        except OSError as e:
            st["send_err"] += 1
            st["last_err"] = st["last_send_err"] = "send: %s" % e
        try:
            with open(os.path.join(E["AOS7_NODE"], "abs_beat.log"), "a") as f:
                f.write("%d\n" % now)
        except OSError as e:
            st["abs_beat_err"] += 1
            st["last_err"] = "abs_beat: %s" % e
        st.update(node_env=E["AOS7_NODE"], cwd=os.getcwd(), round=now)
        try:
            put(os.path.join(T_REL, "progress.json"), st)
        except OSError as e:
            print("progress 寫不出去：%s" % e, flush=True)
        print(json.dumps(st), flush=True)        # out.log 是開著的 fd，資料夾搬走也照寫
    time.sleep(0.02)
    sys.stdout.flush()
