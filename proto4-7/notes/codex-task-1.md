# proto4-7 任務書 1：簡單的 agent（`aos-agent`、`aos-user`）

規格就是 `proto4/notes/24-agent.md` 的 **§24.3**，逐字照做；為什麼這樣定在 `proto4/notes/agent/legacy-harvest.md`（可以看，別的 `proto4/notes/` 不用讀）。這本只補規格沒講的工程細節。

## 規矩

- 你在 repo `/home/lorkhan/repo/simple_tools/aos`。先讀 `AGENTS.md` 開頭三軸、`wf/workflows/dev-env.md`，再讀 `proto4-3/README.md`（inst.json、kernel、`aos-kernel add`）、`proto4-5/README.md`（`aos-kernel llm K req --name X`，結果 `K/llm/results/X.json` 的欄位）、`proto4-6/README.md`（逐步 Python 那節、`aos_py.py` 的 `call`／`llm_submit`／`wait_for`），以及 `playground/README.md`（遊樂場長什麼樣）。
- **只新增 `proto4-7/`，外加 `playground/` 加第 6 站**（`playground/stations/6-agent/` 與 `playground/README.md` 多一節、`up.sh` 若要鋪新站不用改，它是 `stations/*` 全鋪）。**不要碰 `proto4-3`／`4-4`／`4-5`／`4-6`、`wf/`**——另一個 codex 正在那邊整理拆檔。
- Python 3，只用標準庫。呼叫地基一律用**子程序**：`aos-kernel llm`（在 `proto4-3/aos-kernel`）、`aos-exec`（`proto4-3/aos-exec`）；可以 `sys.path` 加 `proto4-6` 直接 `import aos_py` 用它的 `call`／`llm_submit`（它會處理 `AOS_KERNEL`／`AOS_EXEC` 路徑覆蓋），不要複製那些函式。
- 檔案寫法照地基慣例：先寫 `.tmp` 再 `os.replace`；JSON `ensure_ascii=False, indent=1`。
- 程式碼與 README 單檔不超過 300 行；狀態機一檔、信箱／outbox 一檔、工具一檔、CLI 一檔，自然就不會破。
- 測試用 `unittest`，放 `proto4-7/test/`，**不打真 LLM**：模擬 kernel 的方法是自己在假的 `K/llm/results/` 放結果檔（欄位照 proto4-5 README：`ok`、`text`、`raw.choices[0].message` 含 `tool_calls`）、把 `AOS_KERNEL` 指到一支假的 `aos-kernel` 腳本（收 `llm K req --name X` 就把 req 抄到 `K/llm/requests/X.json`、退 0 印路徑）。工具用 `tools/echo/run` 這種 shell 檔。要覆蓋：四格每條轉移、退出碼 0／101／100／1／2、信整封進記憶＋搬 read、outbox 遞增、`max_steps_per_question` 到了寫 outbox 標 stuck、`checks` 上限算錯、`errors≥5` stuck、20 格重送、安全網（尾巴是沒人回的 user 訊息就會重送）、文字 tool call 救回、工具不存在／退非 0／輸出截斷、`aos-user` 四個子命令＋`new`。
- README（`proto4-7/README.md`，大白話、繁體中文、≤ 200 行）：一段講它是什麼、資料夾長什麼樣（抄 §24.3 那張）、四格那張表、`aos-user` 用法、怎麼放進 kernel、怎麼寫一個工具（`tool.json`＋`run` 範例，用 `echo '{"cmd":"ls"}' | tools/sh/run` 就能單獨測）、退出碼、沒做什麼。最後一節「測試與出處」跟 proto4-6 同格式。
- **不 commit、不 push、不開 agent。** 最後 markdown 回報：檔案清單、每個規格點怎麼落地、測試數字、沒做或改了規格的地方（改規格要說為什麼）。

## 工程細節

1. **`aos-agent A`**：`A` 是 agent 資料夾（可相對）。`--status` 印 state.json 一行；`--reset` 只清 state.json（messages 與 outbox 不動）。走一格＝讀 state → 做那格 → 寫 state → 退出碼。每格只做一件事就退，**絕不 sleep、絕不等網路**。
2. **叫模型**：請求 JSON `{"messages":[system]+messages, "tools":[…]}`（工具清單空就不放 `tools` 鍵）；`tools` 每項 `{"type":"function","function":{"name":資料夾名,"description":…,"parameters":…}}`。用 `aos_py.llm_submit(K, req, name)`（它跑 `aos-kernel llm` 並回結果路徑）；name＝`<agent.name>-q<question>-s<step>`。`llm_submit` 拋例外（例如 kernel 沒活）→ 算一次錯，不是退 1。
3. **讀結果**：`ok:false` → 錯，`last_error` 放 `error.kind: error.msg`；`ok:true` 時 assistant 訊息取 `raw.choices[0].message`（有 `tool_calls` 就原樣接進 messages；沒有就用 `text`）。`text` 空且沒 tool_calls → 錯「空白回覆」。
4. **跑工具**：`aos_py.call(<A>/tools/<name>/run, stdin=json.dumps(args), capture=True, timeout_ms=60000)`；結果 content＝stdout（退非 0 時前面加一行 `[exit N] `＋stderr 頭 500 字）；超過 `tool_output_limit` 截斷加 `…（截斷）`。`arguments` 不是合法 JSON → content＝「參數不是 JSON：…」，照樣回給模型。工具的 cwd＝aos-exec 的規矩（普通檔案：它所在的資料夾），範例 `sh` 工具自己 `cd` 到 agent 資料夾（`run` 裡用 `$(dirname "$0")/../..`）。
5. **文字 tool call 救回**：assistant `text` 去頭尾空白後以 `<tool_call>`、`[TOOL_CALLS]`、`<function=` 開頭，或整段就是一個 `{"name":…,"arguments":{…}}` JSON → 挖第一個頂層 JSON 物件，`name` 在工具清單裡就組成 `tool_calls`（id 自己配 `call_<step>_<n>`）。救不回來算錯。
6. **信箱**：檔名時間戳到微秒；一個檔可以是一封或陣列；壞 JSON 的信搬到 `read/` 並記一則 outbox「有一封信讀不懂」。
7. **`aos-user A new --name bob --system "…" --K /abs/K`**：建 `agent.json`、空 `messages.json`、`inbox/user/read/`、`outbox/`、`tools/echo/`（`run`＝`cat`；tool.json 說「原樣回你給的東西」）、`tools/sh/`（`run`：讀 stdin JSON 的 `cmd`，`cd` 到 agent 資料夾跑 `sh -c`，`timeout 60`；tool.json 參數 `{"cmd":string}`）、`inst.json`（argv 絕對路徑指到 `proto4-7/aos-agent`，cwd 絕對）。印下一步：`aos-kernel add K A/inst.json --name bob`、`aos-user A say "…"`、`aos-user A listen`。
8. **遊樂場第 6 站** `playground/stations/6-agent/`：一支 `make.sh`（用 `aos-user new` 在 `$AOS_PLAY/stations/6-agent/bob/` 建 agent，K 用 `$K`），`playground/README.md` 加「第 6 站：跟 agent 說話」：`make.sh` → `aos-kernel add $K bob/inst.json --name bob` → `aos-user bob say "用 sh 工具看看你資料夾裡有什麼，然後告訴我"` → `aos-user bob listen --once` 或 `talk` → `aos-kernel ls $K` 看它 waiting／running；玩壞：說一句要它做很多步的話看 `max_steps_per_question`；`aos-daemon-ctl stop` 後 say 一句看 status。up.sh 會把 `stations/6-agent/` 整個鋪過去（含 make.sh），`__K__`／`__PLAY__` 佔位照其他站的規矩。
