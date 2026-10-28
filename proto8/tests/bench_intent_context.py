"""bench_intent_context - 同一段 15 題、主題跳來跳去又回頭引用的對話，各跑 agent-dan（整份 history）、agent-kai（按意圖組 context）與 kai0（同 kai 但腦沒有 recall、只靠程式挑），比每題送出的 token 與答對率。

用法：python3 proto8/tests/bench_intent_context.py [--out DIR] [--upstream URL] [--model M] [--only dan|kai|kai0]
  --upstream 給了（例 http://localhost:4000/v1）＝真腦：中間夾一個記錄用的轉送 server，token 取回覆的 usage.prompt_tokens；
  沒給＝「照證據回答」的假腦：送去的訊息裡看得到答案要的證據才答對，看不到就先 recall、再重讀檔、最後答不知道——量的是「context 有沒有帶到該帶的」，不是模型聰不聰明；token 用字數粗估（英數 4 字 1 個、中文 1 字 1 個，見 turns.estimate）。
跑的東西放 --out（預設 ~/code/try/intent-context/runs/<時間>/）：兩隻 agent 的快照、工作區、results.json。
不是 unittest（檔名不叫 test_*），不會被 ctest／unittest 撿到。設計：proto8/thinking/2026-10-24-intent-context.md。"""
import argparse, datetime, http.server, json, os, re, shutil, subprocess, sys, threading, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from aos_bins import ROOT, tool, path_with  # noqa: E402
sys.path.insert(0, str(ROOT / "demo" / "agent-kai" / "tools" / "recall"))
import turns  # noqa: E402

DOC = """# 藍鯨專案規格（內部）

## 1. 背景
藍鯨是一個把舊的訂單系統搬到新架構的專案。舊系統跑了九年，程式碼散在四個 repo，沒有人敢動。
{filler1}

## 2. 架構
前端沿用現有的 React 18，後端改成 Go 1.22 寫的三個服務：order、billing、notify。
資料庫選用 PostgreSQL 16，所有服務共用一個叢集、各自一個 schema。快取用 Redis 7。
{filler2}

## 3. 部署
正式環境部署在 AWS 的 ap-northeast-1（東京）區域，測試環境在 us-west-2。
每次部署走藍綠切換，切換前要跑完整的回歸測試。
{filler3}

## 4. 人員
專案負責人：林小雨。後端組長：陳大山。前端由外包團隊「青蛙工作室」負責。
{filler4}

## 5. 時程
預計 2027 年 3 月上線，2027 年 6 月關掉舊系統。
"""
FILLER = ("這一段是補充說明，內容跟上面的主題有關但不是重點：會議紀錄、討論過但沒採用的做法、"
          "各組的意見、以後可能要再看的問題。舊系統的報表、排程、權限設定都要一一盤點，"
          "盤點表放在共用雲端硬碟，負責的人每週五更新一次。")

# 每題：text＝題目；expect＝答案裡要全部出現的字（判對錯）；
# 假腦用：tool＝這題一定要叫的工具（算、查時間）；need＝送去的訊息裡要看得到的證據；answer＝看得到證據時的回答；
# recall＝看不到證據時拿什麼去 recall 搜；fallback＝recall 也沒有時重新叫的工具（重讀檔）。
QUESTIONS = [
    {"text": "我養了一隻貓叫 Momo，三歲，最愛吃鮭魚。記住就好，回一句收到。",
     "expect": ["收到"], "need": [], "answer": "收到。"},
    {"text": "請讀 docs/whale.md，告訴我藍鯨專案的資料庫用哪一套。",
     "expect": ["PostgreSQL"], "fallback": ("read", {"path": "docs/whale.md"}), "need": ["PostgreSQL 16"],
     "answer": "藍鯨專案的資料庫用 PostgreSQL 16。", "recall": "藍鯨 資料庫"},
    {"text": "17*23 再加 100 是多少？", "expect": ["491"], "tool": ("math", {"expr": "17*23+100"}),
     "need": [], "answer": "17*23+100 = 491。"},
    {"text": "把剛剛那個結果除以 7，取到小數兩位。", "expect": ["70.14"], "need": ["491"],
     "tool": ("math", {"expr": "491/7"}), "answer": "491 ÷ 7 ≈ 70.14。", "recall": "491"},
    {"text": "我的貓叫什麼名字、幾歲？", "expect": ["Momo", "三"], "need": ["Momo", "三歲"],
     "answer": "你的貓叫 Momo，三歲。", "recall": "貓"},
    {"text": "現在 UTC 幾點？", "expect": ["UTC"], "tool": ("clock", {}), "need": [], "answer": "現在 UTC 時間如工具所示。"},
    {"text": "順便記一下行程：我下週二早上搭華航飛大阪參加客戶的年度檢討會，住在難波車站旁邊的飯店，房號是 1207，記住就好，回一句收到。",
     "expect": ["收到"], "need": [], "answer": "收到。"},
    {"text": "藍鯨專案的正式環境部署在哪個區域？", "expect": ["ap-northeast-1"], "need": ["ap-northeast-1"],
     "answer": "正式環境部署在 AWS 的 ap-northeast-1（東京）。", "recall": "藍鯨",
     "fallback": ("read", {"path": "docs/whale.md"})},
    {"text": "我上次問你的資料庫是哪一套？版本呢？", "expect": ["PostgreSQL", "16"], "need": ["PostgreSQL 16"],
     "answer": "是 PostgreSQL，版本 16。", "recall": "資料庫"},
    {"text": "Momo 最愛吃什麼？", "expect": ["鮭魚"], "need": ["鮭魚"], "answer": "Momo 最愛吃鮭魚。", "recall": "Momo"},
    {"text": "第三題那個算式是什麼？", "expect": ["17", "23", "100"], "need": ["17*23"],
     "answer": "第三題的算式是 17*23 再加 100。", "recall": "算式 17"},
    {"text": "幫我算 491 加上我的貓的年齡。", "expect": ["494"], "need": ["三歲"], "tool": ("math", {"expr": "491+3"}),
     "answer": "491 + 3 = 494。", "recall": "貓 年齡"},
    {"text": "我住的房間號碼是多少？", "expect": ["1207"], "need": ["1207"], "answer": "你的房號是 1207。",
     "recall": "飯店 房號"},
    {"text": "藍鯨專案的負責人是誰？", "expect": ["林小雨"], "need": ["林小雨"], "answer": "負責人是林小雨。",
     "recall": "藍鯨 負責人", "fallback": ("read", {"path": "docs/whale.md"})},
    {"text": "總結一下我們今天聊過哪些主題，各一句。", "expect": ["Momo", "藍鯨"], "need": ["Momo", "藍鯨", "491"],
     "answer": "聊過：你的貓 Momo；藍鯨專案（PostgreSQL 16、東京區域、負責人林小雨）；算數 491 與 70.14；UTC 時間。",
     "recall": "藍鯨"},
]


class Proxy:
    """agent 的腦都指到這裡：每個 request 記下 (agent, 題號, 粗估 token, 真 token)；有 upstream 就轉送，沒有就當假腦。"""

    def __init__(self, upstream=None):
        self.upstream, self.records, self.now = upstream, [], None
        me = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                est = turns.estimate(body.get("messages", []) + body.get("tools", []))
                rec = {"agent": me.now[0], "q": me.now[1], "est_tokens": est, "messages": len(body.get("messages", []))}
                if me.upstream:
                    req = urllib.request.Request(me.upstream.rstrip("/") + "/chat/completions",
                                                 json.dumps(body).encode(), {"Content-Type": "application/json"})
                    try:
                        with urllib.request.urlopen(req, timeout=180) as r:
                            status, data = r.status, r.read()
                    except urllib.error.HTTPError as e:
                        status, data = e.code, e.read()
                    try:
                        u = json.loads(data).get("usage") or {}
                        rec["prompt_tokens"], rec["completion_tokens"] = u.get("prompt_tokens"), u.get("completion_tokens")
                        rec["cached_tokens"] = (u.get("prompt_tokens_details") or {}).get("cached_tokens")
                    except ValueError:
                        pass
                else:
                    status, data = 200, json.dumps(oracle(QUESTIONS[me.now[1]], body)).encode()
                me.records.append(rec)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


def oracle(q, body):
    """照證據回答的假腦（見檔頭）。"""
    msgs = body.get("messages", [])
    tools = {t["function"]["name"] for t in body.get("tools", [])}
    start = max(i for i, m in enumerate(msgs) if m.get("role") == "user")     # 這題從最後一則 user 起
    cur = msgs[start:]
    called = [c["function"]["name"] for m in cur if m.get("role") == "assistant" for c in (m.get("tool_calls") or [])]
    results = [m.get("content") or "" for m in cur if m.get("role") == "tool"]
    seen = "\n".join(m.get("content") or "" for m in msgs if isinstance(m.get("content"), str))

    def call(name, args):
        n = len(called) + 1
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c%d" % n, "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]}}]}

    def say(text):
        return {"choices": [{"message": {"role": "assistant", "content": text}}]}

    if all(e in seen for e in q["need"]):
        if q.get("tool") and q["tool"][0] not in called:
            return call(*q["tool"])
        text = q["answer"]
        if q.get("tool") == ("clock", {}) and results:
            text = "現在 UTC 時間是 %s。" % results[-1].strip()
        return say(text)
    if "recall" in tools and q.get("recall") and "## 先前對話的目錄" in seen:   # 有舊題的目錄才會想去 recall
        if called.count("recall") == 0:
            return call("recall", {"op": "search", "query": q["recall"]})
        if called.count("recall") == 1:
            m = re.search(r"#(\d+)", results[-1] if results else "")
            if m:
                return call("recall", {"op": "read", "no": int(m.group(1)), "detail": True})
    if q.get("fallback") and q["fallback"][0] not in called and q["fallback"][0] in tools:
        return call(*q["fallback"])
    return say("不知道（我看到的對話裡找不到）。")


def setup(out):
    """兩隻 agent 的快照：kai 照抄 repo 的；dan 照抄後多一個 read 工具（同 kai 用的 lib/base/read），system 也加「讀檔」。"""
    agents = out / "agents"
    ign = shutil.ignore_patterns("__pycache__")
    shutil.copytree(ROOT / "demo" / "agent-kai", agents / "agent-kai", ignore=ign)
    dan = agents / "agent-dan-read"
    shutil.copytree(ROOT / "demo" / "agent-dan", dan, ignore=ign)
    shutil.copytree(ROOT / "lib" / "base" / "read", dan / "tools" / "read", ignore=ign)
    reg = json.loads((dan / "tools.json").read_text(encoding="utf-8"))           # 登記進 tools.json 才算工具
    reg["tools"]["read"] = {"path": "tools/read"}
    (dan / "tools.json").write_text(json.dumps(reg), encoding="utf-8")
    (dan / "system.txt").write_text("你是一個問答助手。\n需要計算、查時間、讀檔時，先用提供的工具，不要自己猜。\n"
                                    "拿到工具的結果後，用純文字給出最後的回答，不要再叫工具。\n", encoding="utf-8")
    kai0 = agents / "agent-kai-norecall"          # 對照：只靠程式自動挑、腦沒有 recall 可用（從 tools.json 拿掉＝不算工具）
    shutil.copytree(agents / "agent-kai", kai0)
    r = subprocess.run([tool("aos-tools"), "--file", str(kai0 / "tools.json"), "rm", "recall"], stdout=subprocess.DEVNULL,
                       env=dict(os.environ, PATH=path_with()))   # rm 經 aos-json 改檔
    if r.returncode != 0:
        sys.exit("aos-tools rm recall 退 %d" % r.returncode)
    return {"dan": dan, "kai": agents / "agent-kai", "kai0": kai0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--upstream")
    ap.add_argument("--model", default="chatgpt-gpt-6-luna-low")
    ap.add_argument("--only", choices=["dan", "kai", "kai0"])
    a = ap.parse_args()
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    out = Path(a.out) if a.out else Path.home() / "code" / "try" / "intent-context" / "runs" / stamp
    out.mkdir(parents=True, exist_ok=False)
    agents = setup(out)
    proxy = Proxy(a.upstream)
    doc = DOC.format(**{"filler%d" % i: "\n".join([FILLER] * 6) for i in range(1, 5)})
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env.update(PATH=path_with(env.get("PATH", "")), AOS_BRAIN_URL=proxy.url, AOS_BRAIN_MODEL=a.model)
    results = {"upstream": a.upstream, "model": a.model if a.upstream else "oracle", "questions": [], "requests": proxy.records}
    names = [a.only] if a.only else ["dan", "kai", "kai0"]
    for who in names:
        ws = out / ("ws-" + who)
        (ws / "new").mkdir(parents=True)
        (ws / "docs").mkdir()
        (ws / "docs" / "whale.md").write_text(doc, encoding="utf-8")
        for i, q in enumerate(QUESTIONS):
            qn = "q%02d.txt" % (i + 1)
            (ws / "new" / qn).write_text(q["text"] + "\n", encoding="utf-8")
            proxy.now = (who, i)
            r = subprocess.run([tool("aos-exec"), "--ws", str(ws), str(agents[who])],
                               capture_output=True, text=True, env=dict(env), timeout=900)
            ans = (ws / "out" / qn).read_text(encoding="utf-8").strip() if (ws / "out" / qn).exists() else ""
            ok = r.returncode == 0 and all(e in ans for e in q["expect"])
            recs = [x for x in proxy.records if x["agent"] == who and x["q"] == i]
            results["questions"].append({"agent": who, "no": i + 1, "ok": ok, "code": r.returncode, "answer": ans,
                                         "calls": len(recs), "est_tokens": sum(x["est_tokens"] for x in recs),
                                         "prompt_tokens": sum(x.get("prompt_tokens") or 0 for x in recs) or None,
                                         "cached_tokens": sum(x.get("cached_tokens") or 0 for x in recs) if a.upstream else None,
                                         "stderr": r.stderr[-500:]})
            print("%s #%02d %s calls=%d est=%d real=%s cached=%s  %s" % (who, i + 1, "OK " if ok else "BAD", len(recs),
                  sum(x["est_tokens"] for x in recs), results["questions"][-1]["prompt_tokens"],
                  results["questions"][-1]["cached_tokens"], ans[:70].replace("\n", " ")),
                  flush=True)
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("| 題 | dan token | kai token | kai0 token | dan 對 | kai 對 | kai0 對 |")
    print("|---|---|---|---|---|---|---|")
    by = {(x["agent"], x["no"]): x for x in results["questions"]}
    key = "prompt_tokens" if a.upstream else "est_tokens"
    tot = {"dan": [0, 0], "kai": [0, 0], "kai0": [0, 0]}
    for i in range(1, len(QUESTIONS) + 1):
        row = []
        for who in ("dan", "kai", "kai0"):
            x = by.get((who, i))
            row.append(x and (x[key] or 0))
            if x:
                tot[who][0] += x[key] or 0
                tot[who][1] += x["ok"]
        oks = ["-" if (w, i) not in by else "對" if by[(w, i)]["ok"] else "錯" for w in ("dan", "kai", "kai0")]   # -＝這隻沒跑（--only）
        print("| %d | %s | %s | %s | %s |" % (i, row[0], row[1], row[2], " | ".join(oks)))
    n = len(QUESTIONS)
    print("| 合計 | %d | %d | %d | %d/%d | %d/%d | %d/%d |" % (tot["dan"][0], tot["kai"][0], tot["kai0"][0],
                                                          tot["dan"][1], n, tot["kai"][1], n, tot["kai0"][1], n))
    print("\n結果：%s" % (out / "results.json"))


if __name__ == "__main__":
    main()
