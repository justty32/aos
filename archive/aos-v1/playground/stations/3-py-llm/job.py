# 三格：丟問題給 kernel 排隊 → 等結果檔 → 把答案存下來。每叫一次 aos-step-py 只跑一格。
import json, os

K = "__K__"
QUESTION = "用一句話介紹你自己。"

def ask(state):
    req = {"messages": [{"role": "user", "content": QUESTION}]}
    state["result"] = aos.llm_submit(K, req, "play-py-1")   # 同名同內容再丟＝拿回同一張，不會卡
    return aos.wait_for(state["result"])                     # 這格做完後開始等結果檔

def read(state):
    state["answer"] = json.load(open(state["result"]))["text"]

def save(state):
    open(os.path.join(here, "answer.txt"), "w").write(state["answer"] + "\n")
