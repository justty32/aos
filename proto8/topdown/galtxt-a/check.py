#!/usr/bin/env python3
# check - $AOS_STACK/drafts/ 每份草稿用 tools/lint（cwd＝galtxt-a 根）過一次（--ws $AOS_STACK：規則在頂層 stack 的 rules.json），收成 $AOS_STACK/checks.json
# checks.json：{"<N>": lint 那一行 JSON}。這是不信任寫手的硬閘門（寫手自己的 lint 是入口自檢，這裡是出口保證）。
# 錯：stderr 一行「galtxt-a check: 代號 原因」、退 1——StackMissing、DraftsMissing（沒有草稿）、LintFailed（lint 退非 0 或沒回 JSON）。
import json, os, subprocess, sys


def die(code, reason):
    print("galtxt-a check: %s %s" % (code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


stack = os.environ.get("AOS_STACK")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")
d = os.path.join(stack, "drafts")
try:
    names = sorted((n for n in os.listdir(d) if n.endswith(".txt") and not n.startswith(".") and n[:-4].isdigit()),
                   key=lambda n: int(n[:-4]))
except FileNotFoundError:
    names = []
if not names:
    die("DraftsMissing", "%s 裡沒有草稿" % d)

checks = {}
env = dict(os.environ, AOS_STACK=os.path.join(stack, "lint") + "/")      # P-17：lint 的小格（它不用，照慣例給）
for n in names:
    with open(os.path.join(d, n), encoding="utf-8") as f:
        text = f.read()
    try:
        r = subprocess.run(["aos-exec", "--ws", stack, "tools/lint"], input=json.dumps({"text": text}, ensure_ascii=False),
                           stdout=subprocess.PIPE, text=True, env=env)
    except OSError as e:
        die("LintFailed", "aos-exec 起不來：%s" % e)
    if r.returncode != 0:
        die("LintFailed", "第 %s 份 lint 結束碼 %d" % (n[:-4], r.returncode))
    try:
        checks[n[:-4]] = json.loads(r.stdout)
    except ValueError:
        die("LintFailed", "第 %s 份 lint 回的不是 JSON" % n[:-4])

path = os.path.join(stack, "checks.json")
tmp = os.path.join(stack, ".checks.json")         # N-05
with open(tmp, "w", encoding="utf-8") as f:
    f.write(json.dumps(checks, ensure_ascii=False, indent=1) + "\n")
os.replace(tmp, path)
