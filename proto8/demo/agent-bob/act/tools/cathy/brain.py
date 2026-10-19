# think 的腦：挑 inbox 檔名排序最前面的一題、題名寫 $AOS_STACK/current，答案草稿印到 stdout（單子把它導到 $AOS_STACK/plan）。
# 沒設 AOS_BRAIN_URL＝假腦；有設就問 OpenAI 相容的端點，只取回覆的 content。
import json, os, sys, urllib.request
stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    sys.exit("agent-cathy: 沒設定 AOS_STACK")
names = sorted(os.listdir(os.path.join(ws, "inbox")))
if not names:
    sys.exit("agent-cathy: inbox 是空的")
name = names[0]
tmp = os.path.join(stack, ".current")       # N-05：先寫 . 開頭的暫存檔再改名
open(tmp, "w").write(name + "\n")
os.replace(tmp, os.path.join(stack, "current"))
question = open(os.path.join(ws, "inbox", name)).read()
url = os.environ.get("AOS_BRAIN_URL")
if not url:
    print("FAKE ANSWER to: " + question.rstrip("\n"))
else:
    body = {"model": os.environ.get("AOS_BRAIN_MODEL", "default"),
            "messages": [{"role": "user", "content": question}]}
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(), {"Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ.get("AOS_BRAIN_KEY", "none")})
    print(json.load(urllib.request.urlopen(req, timeout=120))["choices"][0]["message"]["content"])
