# brain.py - 腦（經 kernel 排隊才跑）：認領題目（new/ → cur/）、題名寫 $AOS_STACK/current.txt、答案草稿印到 stdout。
# 跟 agent-ann 的 brain.py 一樣，只是它不是 think 格直接跑的：think 格跑 aos-gate，把 brains/ 裡那張「python3 brain.py」單子（$BRAIN 選哪張：priority、_metainfo 不同）寄給 kernel，
# kernel 輪到它時才跑（環境、cwd 跟直接跑一樣），stdout 由閘門原樣交回、think 格把它導到 plan.txt。
# 沒設 AOS_BRAIN_URL＝假腦：睡 1 秒（假裝想很久，demo 才看得出排隊）再回 FAKE ANSWER；有設就問 OpenAI 相容的端點。
import json, os, sys, time, urllib.request
stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    sys.exit("agent-ivy: 沒設定 AOS_STACK")
def ls(d):
    try:
        return sorted(os.listdir(os.path.join(ws, d)))
    except FileNotFoundError:
        return []
names = ls("cur")             # 上次認領了沒做完的先接著做
if not names:
    names = ls("new")
    if not names:
        sys.exit("agent-ivy: new/ 是空的")
    os.makedirs(os.path.join(ws, "cur"), exist_ok=True)
    os.replace(os.path.join(ws, "new", names[0]), os.path.join(ws, "cur", names[0]))   # 認領：new/ → cur/
name = names[0]
tmp = os.path.join(stack, ".current.txt")       # N-05：先寫 . 開頭的暫存檔再改名
open(tmp, "w").write(name + "\n")
os.replace(tmp, os.path.join(stack, "current.txt"))
question = open(os.path.join(ws, "cur", name)).read()
url = os.environ.get("AOS_BRAIN_URL")
if not url:
    time.sleep(1)
    print("FAKE ANSWER to: " + question.rstrip("\n"))
else:
    body = {"model": os.environ.get("AOS_BRAIN_MODEL", "default"),
            "messages": [{"role": "user", "content": question}]}
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(), {"Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ.get("AOS_BRAIN_KEY", "none")})
    print(json.load(urllib.request.urlopen(req, timeout=120))["choices"][0]["message"]["content"])
