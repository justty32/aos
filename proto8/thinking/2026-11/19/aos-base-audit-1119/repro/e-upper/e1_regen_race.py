# 測 agent.py 重生（--write-defs）途中連續讀定義夾：有沒有讀到空檔、壞 JSON、找不到檔，以及同一時刻 system／llm／tools 新舊混搭（半套）。經 clean 跑：bin/clean python3 repro/e1_regen_race.py [次數]
import json, os, subprocess, sys, threading, time
E = os.path.expanduser("~/.aos/scratch/aos-base-audit-1119/e-upper")
D = os.path.join(E, "tree/defs/d1")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
stop = False
stats = {"snapshots": 0, "errors": {}, "mixed": 0, "mixed_examples": []}
def ver():
    out = {}
    with open(os.path.join(D, "system.txt")) as f:
        s = f.read()
    if not s:
        raise ValueError("system.txt empty")
    out["system"] = s.split("\n")[0][-1]
    with open(os.path.join(D, "llm.json")) as f:
        out["llm"] = "A" if json.load(f)["temperature"] == 0.1 else "B"
    with open(os.path.join(D, "tools.json")) as f:
        out["tools"] = "A" if "peek_now_time" in json.load(f)["tools"] else "B"
    with open(os.path.join(D, "interfaces.json")) as f:
        out["iface"] = json.load(f)["description"][-1]
    with open(os.path.join(D, "fsm.json")) as f:
        json.load(f)
    return out
def reader():
    while not stop:
        try:
            v = ver()
            stats["snapshots"] += 1
            if len(set(v.values())) > 1:
                stats["mixed"] += 1
                if len(stats["mixed_examples"]) < 5:
                    stats["mixed_examples"].append(v)
        except Exception as e:
            k = type(e).__name__ + ": " + str(e)[:80]
            stats["errors"][k] = stats["errors"].get(k, 0) + 1
t = threading.Thread(target=reader); t.start()
t0 = time.time()
for i in range(N):
    env = dict(os.environ, MARK="AB"[i % 2], BIG="2000")
    r = subprocess.run(["python3", "agent.py", "--write-defs"], cwd=D, env=env, capture_output=True, text=True, timeout=60)
    if r.returncode:
        print("write failed", r.stderr)
stop = True; t.join()
env = dict(os.environ, MARK="A"); subprocess.run(["python3", "agent.py", "--write-defs"], cwd=D, env=env, capture_output=True, timeout=60)
print(json.dumps(dict(stats, regens=N, secs=round(time.time() - t0, 1)), indent=1))
