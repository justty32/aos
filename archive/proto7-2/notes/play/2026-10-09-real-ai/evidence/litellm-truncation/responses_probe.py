#!/usr/bin/env python3
"""同一份 A5 請求改打 LiteLLM 的 /v1/responses，看原生 output 項目（type、phase、字數）。
用法：responses_probe.py <model> <aos request.json> <n> <out.jsonl>"""
import json, sys, time, urllib.request

model, path, n, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
msgs = json.load(open(path))["request"]["litellm"]["messages"]
body = {"model": model, "instructions": msgs[0]["content"],
        "input": [{"role": "user", "content": msgs[1]["content"]}]}
with open(out, "a") as f:
    for k in range(n):
        req = urllib.request.Request("http://localhost:4000/v1/responses", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                o = json.loads(r.read())
            items = []
            for it in o.get("output", []):
                text = "".join(c.get("text", "") for c in (it.get("content") or []) if isinstance(c, dict))
                items.append({"type": it.get("type"), "phase": it.get("phase"), "len": len(text), "head": text[:60]})
            rec = {"items": items, "usage": o.get("usage")}
        except Exception as e:
            rec = {"error": repr(e)[:300]}
        rec.update({"tag": "responses-api", "model": model, "k": k})
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(json.dumps(rec, ensure_ascii=False)[:400])
        time.sleep(5)
