# think 的腦：cur/ 有上次認領沒做完的就接著做，沒有就挑 new/ 檔名排序最前面的一題搬到 cur/（認領，Maildir 的 new → cur）、題名寫 $AOS_STACK/current.txt，答案草稿印到 stdout（單子把它導到 $AOS_STACK/plan.txt）。
# 沒設 AOS_BRAIN_URL＝假腦；有設就問 OpenAI 相容的端點，只取回覆的 content。
import json, os, sys, urllib.request
stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    sys.exit("agent-cathy: 沒設定 AOS_STACK")
def ls(d):
    try:
        return sorted(os.listdir(os.path.join(ws, d)))
    except FileNotFoundError:
        return []
names = ls("cur")             # 上次認領了沒做完的（例如腦失敗）先接著做
if not names:
    names = ls("new")
    if not names:
        sys.exit("agent-cathy: new/ 是空的")
    os.makedirs(os.path.join(ws, "cur"), exist_ok=True)
    os.replace(os.path.join(ws, "new", names[0]), os.path.join(ws, "cur", names[0]))   # 認領：new/ → cur/
name = names[0]
tmp = os.path.join(stack, ".current.txt")       # N-05：先寫 . 開頭的暫存檔再改名
open(tmp, "w").write(name + "\n")
os.replace(tmp, os.path.join(stack, "current.txt"))
question = open(os.path.join(ws, "cur", name)).read()
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
