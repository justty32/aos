# improve.py - improve 格：從最好的那一版開新的一版，交給改進者（improver/，一隻 agent）改，改完拍下來
# 改進者看到的工作區只有兩樣：new/task.txt（目標、這版的判定、之前各版的分數）和 target/（最好那版的複本）；
# 判準、別的版本、工作區原版都不在裡面。改完只收 target/，其他地方寫的東西不採用（記在 version.json 的 ignored）。
# 改進者失敗（腦連不上、逾時…）＝stderr 一行 ImproverFailed、退 1；那個半成品下次開跑時搬到 $AOS_STACK/failed/，從頭再來一次。
import json, os, shutil, subprocess
import common
from common import VERSIONS, stack, ws

base = common.best()
if base is None:
    common.die("StackBad", "還沒有判過的版本，不知道從哪一版改")
done = common.versions()
new = "v%03d" % len(done)
vdir = os.path.join(VERSIONS, new)
if os.path.exists(vdir):                                     # 上次改到一半斷掉：留著看、算一輪，再重來
    failed = os.path.join(stack, "failed")
    os.makedirs(failed, exist_ok=True)
    k = 1
    while os.path.exists(os.path.join(failed, "%s.%d" % (new, k))):
        k += 1
    os.replace(vdir, os.path.join(failed, "%s.%d" % (new, k)))
iws = os.path.join(vdir, "improve", "ws")
istack = os.path.join(vdir, "improve", "stack")
os.makedirs(istack)
copy = common.copy_target(os.path.join(VERSIONS, base), iws)
name = os.path.basename(copy)

# ---- 任務說明
kind, crit = common.criteria()
d = common.verdict(base)
if kind == "cases":
    hidden = sum(1 for c in crit if c.get("hidden"))
    how = ("一組例子共 %d 組（其中 %d 組你看不到）。每組的跑法：`aos-exec %s 參數...`，stdin 餵進去，"
           "比 stdout（行尾空白、頭尾空行不計）%s。" % (len(crit), hidden, name,
                                                   "；有寫結束碼的也要對" if any("code" in c for c in crit) else ""))
else:
    how = "一支檢查程式（你看不到），它會跑 %s，結束碼 0 才算達成；下面是它這次的輸出。" % name
if os.path.isdir(copy):
    files = sorted(os.path.relpath(os.path.join(dp, f), iws) for dp, _, fs in os.walk(copy) for f in fs)
else:
    files = [name]
history = []
for v in done:
    dv = common.verdict(v)
    if dv:
        meta = common.read_json(os.path.join(VERSIONS, v, "version.json"), {})
        history.append("- %s：%d/%d%s" % (v, dv["score"], dv["total"],
                                          "（跟 %s 一模一樣）" % meta["same_as"] if meta.get("same_as") else ""))
goal = (common.read(os.path.join(ws, "goal.txt")) or "（沒寫目標）").strip()
task = """# 目標
{goal}

# 要改的函數
{name}（就是 {base} 那一版，目前最好的）。檔案：
{files}

# 怎麼判定
{how}

# {base} 的結果：{score}/{total}
{feedback}

# 到目前為止各版的分數
{history}

# 要做的
找出為什麼沒達成，改 {name} 底下的檔，用 try_run 試過再收手。只改 {name}；照目標寫通用的做法，不要把例子的答案寫死。最後用幾句話說改了什麼。
""".format(goal=goal, name=name, base=base, files="\n".join("- " + f for f in files), how=how,
           score=d["score"], total=d["total"], feedback=d["feedback"] or "（沒有細節）", history="\n".join(history))
common.write(os.path.join(iws, "new", "task.txt"), task)

# ---- 叫改進者（相對路徑、零個 ..：improver/ 就在 self-improve 自己的資料夾裡）
env = dict(os.environ, AOS_STACK=istack + "/")
env.pop("AOS_ENTRY", None)
if common.sandbox():                                  # 10-24 沙箱接線：try_run 也照同一份設定關函數
    env["AOS_IMPROVE_SANDBOX"] = common.sandbox()
r = subprocess.run(["aos-exec", "--ws", iws, "improver"], env=env)
if r.returncode != 0:
    common.die("ImproverFailed", "improver 結束碼 %d（半成品在 %s，下次開跑會搬到 failed/ 重來）" % (r.returncode, vdir))

# ---- 收 target/、拍成新版
answer = common.read(os.path.join(iws, "out", "task.txt"))
if answer is not None:
    common.write(os.path.join(vdir, "answer.txt"), answer)
ignored = sorted(n for n in os.listdir(iws) if n not in (name, "new", "cur", "done", "out"))
if common.copy_target(iws, vdir) is None:
    ignored.append("（%s 被刪掉了：這一版沒有函數）" % name)
d = subprocess.run(["diff", "-ruN", os.path.join(VERSIONS, base, name), os.path.join(vdir, name)],
                   stdout=subprocess.PIPE, text=True, errors="replace")
common.write(os.path.join(vdir, "diff.txt"), d.stdout.replace(VERSIONS + "/", ""))
h = common.tree_hash(vdir)
same = next((v for v in done if (common.read_json(os.path.join(VERSIONS, v, "version.json"), {}) or {}).get("hash") == h), None)
common.write(os.path.join(vdir, "version.json"), json.dumps(
    {"version": new, "from": base, "hash": h, "same_as": same, "ignored": ignored, "created_at": common.now()},
    ensure_ascii=False) + "\n")
common.write(os.path.join(stack, "current.txt"), new + "\n")
