#!/usr/bin/env python3
"""最小重現：直打本機 LiteLLM（不經 aos），記下每次回應的 choices 形狀與 usage。

用法：probe.py <tag> <model> <stream:0|1> <prompt:agenty|direct> <n> <out.jsonl>
只存精簡摘要（每個 choice 的字數與前 80 字），不存 encrypted reasoning。
"""
import json, sys, time, urllib.request

URL = "http://localhost:4000/v1/chat/completions"
SYS = ("你是 aos 的學徒。任務：替 repo 新增模組 modules/hello/，內含可執行檔 aos7-hello（印出 hello）"
       "與測試 tests/test_hello.py。參考檔已附在下方。完成後要能通過三關（測試、檢查器、審查）。")
REF = "### 參考：modules/echo/aos7-echo\n#!/usr/bin/env python3\nimport sys\nprint(' '.join(sys.argv[1:]))\n"
DIRECT = ("你沒有任何工具、不能看檔或跑指令，所需資料都在使用者訊息裡。"
          "不要說明計畫、不要開場白，第一個字元就是 {。")
USER = {
    "agenty": SYS + "\n\n" + REF + "\n只輸出一個 JSON：{\"files\": {路徑: 內容}}。",
    "direct": SYS + "\n\n" + REF + "\n你沒有任何工具、不能看檔或跑指令，資料都在上面。"
              "不要說明計畫、不要開場白，第一個字元就是 {，只輸出一個 JSON：{\"files\": {路徑: 內容}}。",
}


def call(model, stream, prompt):
    if prompt.startswith("replay"):
        # replay[-direct]:<aos request.json>：重送 A5 學徒的真實請求（只換模型），-direct 在 system 尾端加一句
        kind, path = prompt.split(":", 1)
        msgs = json.load(open(path))["request"]["litellm"]["messages"]
        if kind == "replay-direct":
            msgs[0]["content"] += DIRECT
    else:
        msgs = [{"role": "user", "content": USER[prompt]}]
    body = {"model": model, "messages": msgs}
    if stream:
        body["stream"] = True
        body["stream_options"] = {"include_usage": True}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        raw = r.read().decode()
    ms = int((time.time() - t) * 1000)
    if not stream:
        o = json.loads(raw)
        ch = []
        for c in o.get("choices", []):
            m = c.get("message") or {}
            ch.append({"i": c.get("index"), "finish": c.get("finish_reason"),
                       "len": len(m.get("content") or ""), "head": (m.get("content") or "")[:80],
                       "reasoning_content": bool(m.get("reasoning_content")),
                       "tool_calls": m.get("tool_calls") is not None,
                       "reasoning_items": len(m.get("reasoning_items") or [])})
        return {"ms": ms, "n_choices": len(ch), "choices": ch, "usage": o.get("usage")}
    # 串流：依 choice index 累積 delta.content
    acc, finish, usage, chunks = {}, {}, None, 0
    for line in raw.splitlines():
        if not line.startswith("data:") or line.strip() == "data: [DONE]":
            continue
        chunks += 1
        o = json.loads(line[5:])
        usage = o.get("usage") or usage
        for c in o.get("choices", []):
            i = c.get("index", 0)
            acc[i] = acc.get(i, "") + ((c.get("delta") or {}).get("content") or "")
            if c.get("finish_reason"):
                finish[i] = c["finish_reason"]
    text = acc.get(0, "")
    return {"ms": ms, "chunks": chunks, "stream_indices": sorted(acc), "len": len(text),
            "head": text[:80], "finish": finish, "usage": usage}


if __name__ == "__main__":
    tag, model, stream, prompt, n, out = sys.argv[1:7]
    with open(out, "a") as f:
        for k in range(int(n)):
            try:
                rec = call(model, stream == "1", prompt)
            except Exception as e:  # 記下失敗也算一次
                rec = {"error": repr(e)[:300]}
            rec.update({"tag": tag, "model": model, "stream": stream == "1", "prompt": (prompt.split(":")[0] + ":" + prompt.split("/")[-2]) if "/" in prompt else prompt, "k": k})
            time.sleep(5)  # 避開後端 429
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(tag, k, rec.get("n_choices", rec.get("stream_indices")),
                  [c["len"] for c in rec.get("choices", [])] or rec.get("len"), rec.get("error", ""))
