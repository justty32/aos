# 任務書：proto4-5 `llm-cpu` 第一版——普通 cpu 上跑的「LLM 請求排隊／分發」程式（Python 標準庫）

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准新增／修改 `proto4-5/` 底下的檔案**（新資料夾），其他一律不碰（`proto4-3/`、`proto4-4/` 有人在改）。**不要 git commit、不要 push。** 不要開其他 agent。**不要打真的 LM Studio／DeepSeek／任何網路**——測試全用本機假 HTTP server；`DEEPSEEK_API_KEY` 只准提名字、不准印值。

## 先讀（順序）

1. `proto4/notes/llm-cpu/legacy-harvest.md` 全文——舊 proto 的 LLM 那塊怎麼做、這次撿什麼。**§3 的 v1 骨架是起點，但底下「定案」蓋過它**。
2. `proto4/notes/20-21-step-lisp-and-next.md` §21、§21.1（使用者定義：LLM cpu 就是普通 cpu 上的一支程式，收請求→排序→分發 endpoint；agent 迴圈不在這層）。
3. `proto4-3/README.md`、`proto4-3/docs/exec.md`（inst.json 規則、`aos-exec`）、`proto4-3/docs/kernel.md`（行程怎麼排進 kernel）。llm-cpu 的每一格就是 `aos-exec` 跑一次 `llm-cpu tick`。
4. `proto4-4/README.md`（lisp 用 `aos/call-dir`＋`:read :json` 叫資料夾、讀 JSON 結果——之後 lisp 就是這樣投請求、讀結果的）。
5. `reference/llmkit/llms/client.py`、`reply.py`、`usage.py`——OpenAI 相容的請求怎麼組、回應與 usage 怎麼正規化。**只抄形狀，不 import**。

## 定案（照做；harvest §4 五個問題全部照它的預設）

- **語言**：Python 3 標準庫（`urllib.request`、`json`、`subprocess`、`http.server` 只在測試用），一支可執行檔 `proto4-5/llm-cpu`（薄殼）＋ `proto4-5/llm_cpu.py`（真東西）。程式檔超過 300 行就照 `STRUCTURE.md` 拆（例如 `llm_cpu_tick.py`／`llm_cpu_worker.py`／`llm_cpu_home.py`），入口不變。
- **家**（`llm-cpu init DIR` 建）：
  ```
  DIR/endpoints.json          # {"default":"local","endpoints":[…]}，init 寫範例（三筆：local／deepseek／pi，pi 是 enabled:false）
  DIR/inst.json               # {"argv":["/abs/llm-cpu","tick","."],"cwd":"<DIR 絕對路徑>","stderr":"tick.err"}，這樣 aos-kernel add DIR/inst.json 就能上 cpu
  DIR/requests/<id>.json      # 排隊；檔名去 .json ＝ id
  DIR/requests/running/       # 已派出去的（多一個保留欄 "_aos": {"endpoint","pid","started"}）
  DIR/requests/done/          # 終局（成功、失敗、不明都在這）
  DIR/results/<id>.json       # 統一結果，原子寫
  DIR/usage.jsonl             # 一發一行（worker append；一行 <4KB，Linux 上 O_APPEND 一行是原子的，不做 pending/ 折帳）
  DIR/log/<id>.log            # worker 的 stderr
  DIR/state.json              # 最近一格：tick 次數、running 幾件、每台 endpoint 在飛幾件；不是真源
  DIR/llm-cpu.log             # 每格一行流水帳
  ```
- **請求**（最小）：`{"messages":[{"role":"user","content":"…"}]}`。選填：`"endpoint"`（名字；沒給用 default）、`"priority"`（整數，**大的先**，沒給＝0）、`"timeout_ms"`（沒給用 endpoint 的）、`"params"`（原樣併進 chat/completions body，例如 `max_tokens`、`temperature`）。**不准指定 model**（有就退件，原因寫清楚：model 固定在 endpoint 設定，本機一次只能載一顆）。
- **endpoint 一筆**：`{"name","kind":"openai","base_url","model","max_concurrent","timeout_ms","api_key_env"?（DeepSeek 用）,"enabled"?（預設 true）}`。`kind:"process"`（pi -p）這版**只佔設定槽**：init 範例寫 `{"name":"pi","kind":"process","argv":["pi","-p"],"enabled":false}`，請求指到它就退件「這版還不支援 process 型 endpoint」。
- **一格（`llm-cpu tick [DIR]`，DIR 沒給＝cwd）**，順序固定、做完退出 0（**永遠 0**；llm-cpu 是服務，不回 100）：
  1. **收尾 running/**：每張看 `_aos.pid`——`results/<id>.json` 已出現 → 搬 done/；pid 死了且沒結果 → 寫 error result `{"kind":"worker_died"}` 搬 done/；還活著但 `now - started > timeout_ms + 5000` → `os.kill(pid, SIGTERM)`，寫 error result `{"kind":"timeout"}` 搬 done/。**不重送**（harvest：送出後狀態不明一律 result_unknown，這裡就是 worker_died）。
  2. **驗新請求**：不是 JSON 物件／沒 messages／messages 不是非空陣列／有 model／endpoint 名字不認得或 disabled／kind 不支援 → 當格寫 error result `{"kind":"bad_request","msg":…}` 搬 done/。
  3. **排序**：priority 大者先，同分 mtime 早者先，再同名字。
  4. **分發**：每台 endpoint 數 running/ 裡指到它的件數，`< max_concurrent` 才派：先 rename 進 running/（加 `_aos`），再 `subprocess.Popen([sys.executable, llm_cpu.py, "worker", DIR, id], start_new_session=True, stdin=DEVNULL, stdout=DEVNULL, stderr=open(log/<id>.log,"ab"))`，把 pid 寫回 running/ 那張（原子）。滿了就跳過看下一件（**不擋別台**）。tick 隨即返回，**絕不等網路**。
  5. 寫 state.json、log 一行。
- **worker（`llm-cpu worker DIR ID`，內部用）**：讀 running/<id>.json，組 `POST {base_url}/chat/completions` body＝`{"model":endpoint.model,"messages":…,"stream":false} + params`，header `Content-Type: application/json`、有 `api_key_env` 就 `Authorization: Bearer <os.environ[名字]>`（沒設這個環境變數＝error result `{"kind":"no_api_key","msg":"環境變數 X 沒設"}`）；`urllib.request.urlopen(req, timeout=timeout_ms/1000)`。結果檔：
  ```
  {"ok":true,"id":…,"endpoint":…,"model":<回應的 model>,"text":<choices[0].message.content>,
   "finish_reason":…,"usage":{"prompt":…,"completion":…,"total":…,"cached":…|null,"reasoning":…|null},
   "ms":…,"raw":<整包回應>,"error":null}
  ```
  失敗：`{"ok":false,…,"text":null,"error":{"kind":"http"|"connect"|"timeout"|"bad_json"|…,"msg":…,"status":…|null,"retryable":bool}}`。**回應的 model 跟設定不符**（LM Studio 換了模型）→ `ok:false`、`kind:"model_mismatch"`（harvest 問題 5）。結果檔先 `.tmp` 再 `os.replace`；然後 append 一行到 usage.jsonl：`{"at","id","endpoint","model","prompt","completion","total","cached","reasoning","ms","ok"}`。worker 自己的任何例外也要變成 error result，不能默默死掉。
- **`llm-cpu submit [DIR] REQ.json|-` **：把一份請求（檔或 stdin）投進 requests/（先 `.tmp` 再 replace），id＝`--name` 或 `time.time_ns()`；印 `投進去了：requests/<id>.json；結果會在 results/<id>.json`。這是 lisp 之後用 `aos/call-dir` 叫的入口：所以再給一個 `DIR/.aos/inst.json`？**不要**——lisp 那邊之後自己包，這版只做 CLI。
- **`llm-cpu ls [DIR]`**：印 endpoints（名字、model、在飛/上限、enabled）、排隊幾件（按排序印前 10）、running 幾件（id、endpoint、跑了幾秒）、最近 5 件 done（id、ok、kind）。一屏看完。
- **明確不做**（README 寫）：串流、取消、重試／退避、批次、費用、公平分數、LM Studio load／unload、process 型 endpoint、agent／工具、MCP。

## 測試（`proto4-5/test/`，`python3 -m unittest discover -s test`，照 proto4-3 的風格：真開進程、暫存在 /tmp、跑完自己收）

假 endpoint：一支 `test/_fake_openai.py`，`http.server` 在 127.0.0.1 隨機 port，路由 `/v1/chat/completions`，行為由 body 的最後一則 user content 決定：`echo:xxx` 回 `xxx`（usage 假數字，含 `completion_tokens_details.reasoning_tokens`）、`slow:N` 睡 N 秒再回、`fail:500` 回 500、`badjson` 回非 JSON、`model:other` 回 model 欄位是別的名字。至少 18 條：
- init 建家、endpoints.json 三筆、inst.json 的 argv 是絕對路徑。
- submit 檔／stdin／--name；tick 對壞請求（沒 messages、有 model、endpoint 不認得、指到 pi）各寫 bad_request 結果並進 done/。
- 排序：三件 priority 2/0/5 → 5 先派；同分 mtime 早者先。
- max_concurrent=1 時第二件留在 requests/ 等下一格；第一件結果出現後下一格才派第二件。
- worker：echo 成功結果形狀齊全、usage 五欄、usage.jsonl 多一行；fail:500 → ok false kind http status 500 retryable true；badjson → bad_json；model:other → model_mismatch；`api_key_env` 沒設 → no_api_key（測試裡設一個不存在的名字）；連不上（port 沒開）→ connect。
- slow:3 ＋ timeout_ms=500 → 下一格 kill、kind timeout；worker 被外力 kill（測試直接 kill pid）→ 下一格 worker_died。
- tick 永遠退出 0，就算 endpoints.json 壞掉（那時 log 一行、什麼都不派）。
- **端到端一條**：`proto4-3/aos-exec DIR`（DIR 是 llm-cpu 的家，用 `--dir-target inst.json`）跑一格＝tick 一次，證明它就是一份普通 inst.json。

## README（`proto4-5/README.md`，大白話、繁體中文、200 行以內）

節：一句話這是什麼（普通 cpu 上的一支程式，收 LLM 請求→排序→分發，不是 agent）；怎麼跑（init → 改 endpoints.json 指到 LM Studio `http://localhost:1234/v1`、model 填你載入的那顆 → `submit` → 手動 `tick` 幾次或 `aos-kernel add K DIR/inst.json` 讓 kernel 每秒跑 → `ls`、看 `results/`）；請求長什麼樣（欄位表）；結果長什麼樣（欄位表、error.kind 一覽）；endpoint 設定（三筆範例，key 只寫環境變數名）；一格做什麼（五步）；為什麼是背景 worker（一格幾秒、推論幾十秒）；沒做什麼；出處（harvest 報告、§21）。

## 回報（十二行以內，大白話）

- 檔案清單與各自行數。
- 測試幾條、最後一行原文。
- 你自己決定的事、撞到的坑、沒做到的，一條一句。
- 確認沒印 key：`grep -rn "sk-\|Bearer sk" proto4-5/` 只該命中程式碼組 header 那行（變數，不是值）。
