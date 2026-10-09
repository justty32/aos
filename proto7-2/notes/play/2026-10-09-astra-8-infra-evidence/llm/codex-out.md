確認 **8 條：A 類 2 條、B 類 6 條，均為中／低嚴重度**；受測 HEAD `cd544440`。
全程唯讀、未呼叫 LLM／網路；已實跑既有 baseline、唯讀 CLI 與純記憶體探針。
下列會建檔的重現腳本供隊長核對，均只寫入 `/tmp/astra8-llm-*`。
已排除已記錄的 pending 不自動補帳、overrun 不停准入，以及 brain 長 ID 前綴碰撞限制。

### NEW-llm-1〔A／metrics，中〕改指上層資料夾，同一批紀錄從 13 件變成 2 件，憑空增加 11 次重試

- 契約：`proto7-2/modules/metrics/README.md:37`「不確定是哪一層就指大一點的上層，工具會自己往下找」；`:26`「同一張需求（含審查／學習）算一件」。
- 程式：`proto7-2/modules/metrics/aos7_metrics.py:124`「`flow = logical if isinstance(logical, str) else 'call:' + c['id']`」；`:131`「`grouped.setdefault(flow, []).append(c)`」。分組丟掉 node／證據根身分；`:104` 的 author 帳及 `:106` 的 jobs 也只按名稱存。`:205` 再把合併後的呼叫算成 reask。
- 重現：使用 repo 現有資料，不建檔。

```bash
python3 -B - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "proto7-2/modules/metrics")
import aos7_metrics as m

root = Path("proto7-2/modules/metrics/baseline/r1")
whole = m.scan(root)
parts = [m.scan(p) for p in root.iterdir() if p.is_dir()]
print("上層:", len(whole["flows"]), whole["calls"], whole["retries"]["total"])
print("逐夾:", sum(len(p["flows"]) for p in parts),
      sum(p["calls"] for p in parts),
      sum(p["retries"]["total"] for p in parts))
PY
```

- 預期／推斷實際：照上層遞迴承諾，兩種量法都應是 **13 件、13 次呼叫、0 次重試**。唯讀實跑得到上層 **2、13、11**，逐夾 **13、13、0**。不同實驗／node 的 `author/csv1` 被當成同一需求；平均每件用量也因此改變。這不是已知的 brain 長 ID 碰撞。
- 修法：flow、author、job 的內部鍵加入所屬 node／證據根；跨 node 的 author 與 llm node 關聯使用明確來源識別。

### NEW-llm-2〔B／metrics＋budget，中〕一般 fakeapi 預算也被算成 AI 呼叫，並混入 token 帳差

- 契約：`proto7-2/modules/metrics/README.md:5`「看 AI 工作留下的紀錄」；`proto7-2/packs/budget/spec.md:72`「帳的 `used`／`available` 是加權成本，`accepted` 才是受理次數」。
- 程式：`proto7-2/modules/metrics/aos7_metrics.py:91` 無條件納入所有 budget 的 `used`；`:97`「`call((base, budget, cid))['ledger'] = op`」，未核對 `content.resource`／gateway。`:221` 把這些帳一起算進 llmcall 回條帳差。
- 重現：直接用 budget 的正式函式完成一筆本機 fakeapi 操作，無 daemon、無網路。

```bash
T=$(mktemp -d /tmp/astra8-llm-XXXX)
python3 -B - "$T" <<'PY'
import json, sys
from pathlib import Path
sys.path[:0] = ["proto7-2/packs/budget", "proto7-2/modules/metrics"]
import aos7_budget as b
import aos7_budget_gate as g
import aos7_metrics as m

t = Path(sys.argv[1])
def put(rel, value):
    p = t / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value))

put(".aos/round.json", {"round": 0, "open": False})
put("budget/demo/grant.json", {
    "v": 1, "grant": "g", "budget": "demo", "holder": "api",
    "resource": "fakeapi.calls", "gateway": "fakeapi", "amount": 20,
    "clock": "completed_tock", "from": 0, "until": 100, "delegate": False
})
bud = b.Bud(t / "budget/demo")
assert b.init(bud)[0]
key = b.make_key("demo", "api", "r1")
content = dict(resource="fakeapi.calls", gateway="fakeapi",
               amount=7, payload_sha=b.sha({}))
assert b.handle(bud, dict(op="reserve", key=key, content=content))["result"] == "reserved"
assert g.run(bud, key, content, {})["used"] == 7
assert b.handle(bud, dict(op="settle", key=key))["result"] == "settled"
s = m.scan(t)
print("calls =", s["calls"], "tokens.used =", s["tokens"]["used"])
print("ledger =", s["ledger"])
PY
rm -rf "$T"
```

- 預期／推斷實際：沒有任何 LLM 呼叫，應為 0 次 AI 呼叫；fakeapi 的 7 單位成本不能成為 token 帳差。推斷實際為 `calls=1`、`tokens.used=0`、`ledger.used=7`、`receipts=0`、`diff=7`。正常的一般預算帳被呈現成 AI 帳不平。
- 修法：依 resource／meter 隔離統計與對帳，LLM 統計排除 `fakeapi.calls` 等其他單位。

### NEW-llm-3〔B／metrics＋llmcall，中〕超支時「每件花掉的 token」少算 overrun，預設輸出也不提示

- 契約：`proto7-2/modules/metrics/README.md:27`「平均一件工作花掉的 token（錢主要看這個）」；`proto7-2/packs/llmcall/spec.md:47`「`used=min(U,R)、overrun=max(0,U−R)`」。
- 程式：`proto7-2/modules/metrics/aos7_metrics.py:160`「`token['used'] += number(final.get('used'))`」；`:267` 直接將它印成「每件用 … token」。`plain()` 只提示 pending／unreadable，不提示 overrun。`ADVANCED.md:39` 的算法也只寫 receipt.used，因此是**對外用語和跨包計量語意不一致**，不只是漏改一行程式。
- 重現：用 llmcall 正式計量函式產生「預留 10、實用 100」的回條。

```bash
T=$(mktemp -d /tmp/astra8-llm-XXXX)
python3 -B - "$T" <<'PY'
import json, sys
from pathlib import Path
sys.path[:0] = ["proto7-2/packs/llmcall", "proto7-2/modules/metrics"]
import aos7_llmcall as l
import aos7_metrics as m

t = Path(sys.argv[1])
request = {"fake": {"usage": 100}}
key = l.bg.make_key("llm", "h", "c1")
kid = l.bg.kid_of(key)
req = dict(v=1, call_id="c1", logical="demo", budget="llm", holder="h",
           req_sha=l.bg.sha(request), reserve=10,
           meter=l.METER, endpoint="fake", request=request)
raw = dict(v=1, call_id="c1", req_sha=req["req_sha"], source="transport",
           at="2026-10-09T00:00:01+00:00",
           reply=dict(status="ok", billed=True, body="ok",
                      usage=dict(total_tokens=100, prompt_tokens=70,
                                 completion_tokens=30), elapsed=1))
done = l.done_from(raw, key, kid, "probe", 10)
receipt = l.receipt_from(req, key, kid, done, raw,
                        dict(used=10, overrun=90, at=raw["at"]))
cd = t / "llmcall/llm/c1"
cd.mkdir(parents=True)
for name, value in [("request", req), ("raw", raw), ("receipt", receipt)]:
    (cd / (name + ".json")).write_text(json.dumps(value))
print("回條:", receipt["usage"], receipt["used"], receipt["overrun"])
print(m.plain(m.scan(t)))
PY
rm -rf "$T"
```

- 預期／推斷實際：應顯示實用 100 token，或清楚標示「帳內 10、超支 90」。推斷實際只顯示「每件用 10 token」，沒有超支提示；纯記憶體探針已確認。這和已知限制「超支不停准入」不同。
- 修法：保留凍結的 `used` 帳務欄，另計實際消耗，並在預設輸出顯示超支。

### NEW-llm-4〔A／author，中〕CSV propose 的鎖／寫檔 OSError 會直接漏出 traceback

- 契約：`proto7-2/packs/author/spec.md:101`「`3` unknown（帳或表讀不到／壞、鎖逾時、只有 intent）」且不成功時另印白話；`proto7-2/notes/blueprint-errors.md:18` 將讀寫故障列為退出 3。
- 程式：`proto7-2/packs/author/aos7_author.py:646`「`with nd.lock():`」；`:657`、`:659` 只捕捉 `Refuse`、`Unknown`，沒有 `OSError`。`:130` 使用的 `locked()` 會在 `proto7-2/lib/aos7_fs.py:199` 執行「`with open(path + ".lock", "a") as lk:`」，其 OSError 沒有轉換。
- 重現：用鎖路徑不是一般檔，穩定模擬鎖檔無法開啟，不依賴 chmod 或執行者權限。

```bash
T=$(mktemp -d /tmp/astra8-llm-XXXX)
R="$PWD"
mkdir -p "$T/author/req/csv1" "$T/author/author.lock"
cp proto7-2/packs/author/examples/csv-request/request.json \
   "$T/author/req/csv1/request.json"
cp proto7-2/packs/author/examples/csv-request/valid.json "$T/candidate.json"
(
  cd "$T"
  python3 -B "$R/proto7-2/packs/author/bin/aos7-author" \
    propose csv1 --candidate candidate.json
  printf 'exit=%s\n' "$?"
)
rm -rf "$T"
```

- 預期／推斷實際：預期 JSON `why:"unknown"`、stderr 一行 `aos7-author: 不確定：…`、退出 3。推斷實際為 `IsADirectoryError` traceback、退出 1；記憶體注入 OSError 已確認會穿出 `propose()`。
- 修法：讓 CSV propose 的故障邊界包含 OSError，和 register／publish 的处理一致。

### NEW-llm-5〔B／author，中〕CSV 模型拒答被報成使用者輸入錯誤，退出 2 而非 1

- 契約：`proto7-2/packs/author/spec.md:128`「1／2、其他未交付（CLI 退 1：模型回覆不能用）…＝invalid」。
- 程式：`proto7-2/packs/author/aos7_author_llm.py:115`「`return result(False, 'unknown' if proc.returncode == 3 else 'invalid', rid=rid, llm=llm)`」，未附退件標記；`aos7_author.py:53` 把 invalid 映射為 2，`:1013` 只有 `_rejected` 才改成 1。相同情況在 `aos7_author_aos.py:394` 則有 `_rejected`。
- 重現：只 mock llmcall 子程序的既定終局回覆；不呼叫模型或網路。

```bash
T=$(mktemp -d /tmp/astra8-llm-XXXX)
TMPDIR="$T" PYTHONDONTWRITEBYTECODE=1 python3 -B - "$T" <<'PY'
import json, os, shutil, subprocess, sys
from pathlib import Path
from unittest.mock import patch

root = Path.cwd()
sys.path.insert(0, str(root / "proto7-2/packs/author"))
import aos7_author as a
import aos7_author_llm as llm

t = Path(sys.argv[1])
dest = t / "author/req/csv1/request.json"
dest.parent.mkdir(parents=True)
shutil.copyfile(root / "proto7-2/packs/author/examples/csv-request/request.json", dest)
os.chdir(t)
reply = dict(outcome="rejected", billing="final", used=0, text=None)
fake = subprocess.CompletedProcess([], 1, json.dumps(reply) + "\n",
                                   "aos7-llmcall: 模型拒絕，已結帳。\n")
with patch.object(llm.subprocess, "run", return_value=fake):
    code = a.main(["propose", "csv1", "--llm", "demo",
                   "--budget", "budget/llm"])
print("exit =", code)
PY
rm -rf "$T"
```

- 預期／推斷實際：預期退出 1、說明模型未答成。實際分支已用記憶體探針確認：JSON 記 `llm.exit=1`、`outcome:"rejected"`，author 卻退出 **2**，人話要求使用者提供符合需求的檔案與選項。
- 修法：區分本地參數錯誤與 llmcall 終局失敗，讓 CSV／aos 學徒共用同一套映射。

### NEW-llm-6〔B／budget，中〕`--amount 0` 未在入口拒絕，會寫入 inbox

- 契約：`proto7-2/packs/budget/spec.md:85`「2＝壞輸入：參數不合…沒送任何請求」；`proto7-2/notes/blueprint-errors.md:17`「參數、檔案形狀、用法錯；什麼都沒動」。
- 程式：`proto7-2/packs/budget/aos7_budget.py:493` 只有 `type=int`，`:540` 直接呼叫 gate；`aos7_budget_gate.py:207`、`:209` 將 amount 放進 content 後送 reserve。正整數檢查直到帳端 `aos7_budget.py:303` 才做：「`content["amount"] <= 0`」。
- 重現：沿用 `error_path.json` 的持鎖測試方式，不啟動帳任務。

```bash
T=$(mktemp -d /tmp/astra8-llm-XXXX)
python3 -B - "$T" <<'PY'
import fcntl, json, subprocess, sys
from pathlib import Path

root = Path.cwd()
t = Path(sys.argv[1])
(t / ".aos").mkdir()
(t / ".aos/round.json").write_text('{"round":0,"open":false}')
bud = t / "budget/demo"
bud.mkdir(parents=True)
with (bud / "ledger.lock").open("w") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    p = subprocess.run([
        sys.executable, "-B", str(root / "proto7-2/packs/budget/bin/aos7-budget"),
        "call", str(bud), "--holder", "api", "--request", "r1",
        "--amount", "0", "--patience", "0"
    ], capture_output=True, text=True, timeout=5)
print("exit =", p.returncode)
print(p.stderr.strip())
files = list((bud / "inbox").glob("*.json"))
print("inbox files =", len(files))
for path in files:
    print("amount =", json.loads(path.read_text())["content"]["amount"])
PY
rm -rf "$T"
```

- 預期／推斷實際：預期退出 2、不新增 inbox。推斷實際退出 **3**，留下 1 份 `amount:0` 請求；若真帳接收，則帳端回 bad、CLI 退 1。記憶體探針已確認零額度仍傳入 `ask()`。
- 修法：call 在查鎖／送請求前驗證 amount 正整數，並一起驗證 patience 非負。

### NEW-llm-7〔B／step，低〕step 尚未接上統一錯誤格式

- 契約：`proto7-2/notes/blueprint-errors.md:25`「人看的一行永遠在 stderr」；`:33` 要求退出 2 附例子、退出 3 以「不確定：」開頭。
- 程式：`proto7-2/packs/step/aos7_step.py:744` 使用原生 `argparse.ArgumentParser`；`:785`「`print("aos7-step: %s" % e, file=sys.stderr)`」，缺不確定標記與恢復方式。`proto7-2/tests/error_path.json` 的入口列沒有 step。
- 重現：

```bash
T=$(mktemp -d /tmp/astra8-llm-XXXX)
python3 -B proto7-2/packs/step/bin/aos7-step --no-such-option
printf 'bad exit=%s\n' "$?"
mkdir -p "$T/jobs/demo"
printf '{broken\n' > "$T/jobs/demo/frame.json"
python3 -B proto7-2/packs/step/bin/aos7-step status "$T/jobs/demo"
printf 'status exit=%s\n' "$?"
rm -rf "$T"
```

- 預期／推斷實際：壞參數應退 2、stderr 恰一行人話附例子；壞 frame 應退 3、以 `aos7-step: 不確定：` 開頭並說明處置。壞參數已實跑：退 2，但印 `usage:` 加 `error:` 兩行；壞 frame 推斷退 3、缺統一格式。
- 修法：補 step 的 CLI 錯誤出口，並加入 `error_path.json` 驗收列。

### NEW-llm-8〔B／usage 轉址，低〕usage 的 `--help` 也退 1，與另一個轉址 stub 不一致

- 契約：`proto7-2/notes/blueprint-errors.md:35`「`--help`…退出 0」；`proto7-2/modules/diag/ADVANCED.md:12` 明定 llmdiag stub「`--help` 退 0」。
- 程式：`proto7-2/packs/usage/bin/aos7-usage:7` 無條件印 stderr，`:8`「`sys.exit(1)`」；相對地 `proto7-2/modules/llmdiag/aos7-llmdiag:5` 有 help 分支。
- 重現：只讀、不建檔。

```bash
python3 -B proto7-2/packs/usage/bin/aos7-usage --help
printf 'usage exit=%s\n' "$?"
python3 -B proto7-2/modules/llmdiag/aos7-llmdiag --help
printf 'llmdiag exit=%s\n' "$?"
```

- 預期／推斷實際：兩者 help 都應 stdout 印轉址、退 0。usage 已實跑為 stderr 印轉址、退 **1**；llmdiag 為 0。**一般執行停用 stub 退 1 是合理的，本條只指 help。**
- 修法：usage 增加 help 分支，並把 stub 加入錯誤路徑清單。

### 看過但沒問題

- llmcall HTTP 分類：離線 mock 核對 200 壞 JSON／空 choices、400／401、408／429、5xx、302，outcome／billing／退出碼符合現行 spec。
- 連線拒絕走 rejected、其他 DNS／逾時例外走 unknown；未發現隱藏重試。
- llmcall 保留 intent、先 raw 後 done、pending 不 settle／不寫 receipt、已有 receipt 重印的主流程，靜態核對一致。
- budget 部分結算、overrun 獨立累計、不對不可查回的 LLM intent 執行取消，靜態核對一致；先前取消回條缺欄已補齊。
- metrics 既有 brain fixture：四件 brain 工作的正常多回合均為重試 0；author fixture 的兩次重問仍單獨計入。
- metrics／diag 正式入口停用 bytecode；掃描實作沒有寫檔或取得 flock。
- diag 吸收 llmdiag 的三張表、排序及存在性判準一致；新增的 I/O 退出 3、非 node 退出 2 已在 ADVANCED 明列。
- prompt 的讀完再寫 ref、折疊／展開檢查、相對路徑與錯誤分類主流程，未找到確定的新問題。
- author 三關發布採獨立 git index、建立 apprentice 分支、不切換工作樹；CSV publish 的 intent／回條重播及不復活表項主流程，靜態核對一致。
- step 的 `unknown_codes`、request 層重送額度及過期 intent 處理，與本輪 spec 修改一致。

### 沒看完

- 未執行會寫檔的完整測試、SIGKILL 恢復、磁碟故障及跨程序鎖競爭；上述重現腳本仍需隊長實跑。
- 未驗真 LiteLLM／代理行為；HTTP 結論限於離線 mock 與傳輸實作。
- author 第二關 bwrap／systemd 隔離、publish 競爭及長時間執行僅靜態審閱，未驗作業系統現場。
- kernel 包內部依任務要求不重審。