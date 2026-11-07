# arknights-kb 盤點：aos 現在能做到哪（只陳述現況與實測，11-07 opus 隊員）

← [arknights-kb](../../../../../proto8/thinking/2026-11/07/arknights-kb/README.md)｜試驗場：`~/code/playground-ak/`（說明在該夾 `README.md`）｜撞到的問題：[不足清單](../../../../../proto8/thinking/2026-11/07/arknights-kb/不足清單.md)

本檔只寫事實（檔案路徑＋實測），不提設計。路徑相對 `proto8/`。

## 1. 知識庫

- **`lib/agent/memory`（唯讀查詢）**：stdin `{"op": "read"|"ls"|"find", "path"?, "query"?, "max_bytes"?}`。`read` 印節點文（預設最多 8000 bytes，超過附 `[truncated: N more bytes]`）＋`children:` 目錄；`ls` 只印目錄；`find` 用 `grep -r -i -l -F` 掃 `*.md`／`*.json`，最多列 20 筆再加 `… N more`。
- **定址**：`a/b`，段名**只能 `[a-z0-9_-]+`**（中文段名＝`PathBad`）；`""`／`/`＝根。資料夾節點＝`a/b/README.md`，葉＝`a/b.md` 或 `a/b.json`（同名 `.md` 優先）；`.`、`_` 開頭不算節點。
- **節點格式**：第 1 行 `# 標題`、下一個非空行＝一句話摘要（目錄印它）、之後本文；`.json` 葉的標題／摘要取頂層 `title`／`summary`。慣例（`knowledge/README.md`）：一節點 ≤ 2 KB、內容英文。程式只截 `max_bytes`，不擋大小。
- **根怎麼指**：① 工具資料夾的 `_memory.json` `{"base": 路徑}`（相對該資料夾）＞ ② `$AOS_MEMORY`（相對 `$AOS_DAEMON`）；都沒有＝`MemoryMissing`。一支 memory＝一個庫；要接多庫＝登記多支。範本 `templates/agent-fsm/tools/memory/` 就是這種包裝資料夾，指 `knowledge/aos`。
- **think 自動帶根**：`fsm.json` 的 think 格 `brain.py --memory memory`＝每次組請求前叫一次 `memory read`，根接在 system 後面。
- **`lib/agent/memory_export`**：`{"path"?, "max_bytes"? (預設 50000)}`，把整棵（或子樹）印成一份 Markdown 給人看。
- **`knowledge/aos`**：112 KB、約 25 檔；根＋`world`、`me/`、`agents/`、`brain`、`status`、`errors/`、`rules`、`cli/`；全英文。
- **K7 `memory_write`：沒有實作**。`lib/agent/memory_write/` 不存在；[05-實作步驟草稿](../../../../../proto8/thinking/2026-11/05/knowledge-write/05-實作步驟草稿.md) W1～W10 全部沒做（含 W1 的 `find` 跟捷徑、W2 的共用模組 `memory_fs.py`）。現在 `find` 用 `grep -r`，不跟子層捷徑，所以「捷徑掛多庫」的 find 找不到捷徑後的庫。

## 2. agent

- **兩個範本**（`templates/`）：`agent-fsm`（aos 自己的 loop／fsm agent：idle→think→wait→act 四格 Python，問腦寄信給 llm kernel）與 `eca-claude`（外面的 claude CLI 當身體）。掛法：`cd ws && aos-exec <定義資料夾>`（`_entry`＝`aos-agent ctl add`）或 `aos-agent ctl add --name N <定義>`。換腦：`aos-agent llm set endpoint=代號`（只存差異、下一題生效）。
- **工具登記**：定義裡的 `tools.json` `{"tools": {登記名: {"path": 工具資料夾, "env"?}}}`；工具資料夾＝`_entry`＋`_tooldef.json`（給腦看的 description／parameters，另有 `env`、`errors`）＋選填 `_metainfo.json`（`time_ms.max` 當逾時、`side_effect` 等）。每隻自己的增減存 `$AOS_STACK/` 下同名覆蓋層（`aos-agent tools add/rm`、腦用 `self_tools`）。act 用 `aos-tools call` 叫，腦看到的名字＝登記名。
- **lib 全表**（一支一句）：
  - `base/`：`bash`（跑一行 bash，30 s 預設、最多 300 s）、`clock`（UTC 時間）、`copy`、`edit`（精確字串替換）、`json_edit`（JSON pointer 改）、`json_read`（一層一層看 JSON）、`llm_fake`（假腦 endpoint 函數）、`llm_http`（OpenAI 相容端點函數）、`ls`、`math`（算式）、`mkdir`、`move`、`read`（最多 2000 行／50 KB）、`run_python`（只標準庫）、`stat`、`trash`（丟進 `.trash/`）、`view`（逐層看檔）、`write`（整檔寫）。除 bash／run_python 外都限在 `$AOS_WS`。
  - `aos/`：`aos_json`（經 aos-json 看／改 JSON）、`judge`（daemon 判官一輪）。
  - `agent/`：`agents`（生／問／拔子 agent）、`claude`、`codex`（把一件事交給外部 CLI，唯讀）、`json_rewrite`（照短指令改 JSON）、`memory`、`memory_export`、`self_tools`（改自己的工具）、`thought`（交給一次性 helper、只拿回結論）。
- **shell 類**：有，`base/bash` 與 `base/run_python`；description 明寫「It cannot keep a command inside the workspace」。範本 `tools.json` 預設**沒登記**它們（只有 clock、self_tools、agents、memory）。
- **`agents`**：op `new`（從 `from` 複製定義＋`files` 寫進去再掛）／`add`（掛現成定義）／`say`／`ask`（等答，預設 600 s）／`rm`／`ls`；子 agent **不繼承**腦與工具，要給 `llm`、`tools`；可帶 `limits`；上限＝定義的 `agents.json` `max_children`（範本 4）。
- **`thought`**：`{"goal", "from"?, "context"?, "tools"?, "endpoint"?, "max_chars"? 600, "timeout_s"? 600, "keep"?}`；`from`＝helper 定義（或登記格 `env.AOS_THOUGHT_FROM` 預設），工具呼叫不進呼叫者 history，深度靠 `AOS_THOUGHT_DEPTH` 只准再深一層。

## 3. llm kernel（`kernel/llm-kernel`，身體 `impls/aos-llm-kernel`）

- **形狀**：一台 daemon（`daemon.json` 身體＝`aos-llm-kernel kernel.json`、300 ms 一拍）；寄信進 `$AOS_LLM_KERNEL/requests/`，每封掛成一個問腦 proc 跑 endpoint 函數。
- **kernel.json**：`slots`（總在飛數，範本 2）、`timeout_ms`、`exec`（預設 endpoint 函數）、`endpoint`（預設代號，範本 `fake`）、`budget`（總／每包／每寄件人 `max_calls`、`max_tokens`，帳在 `used.json`）、`reserved: {"high": N}`、`aging_ticks`、`endpoints`（代號→包）。包裡 kernel 看 `exec`／`slots`／`budget`／`speed`（fast／normal／slow），其餘（`url`、`model`、`fixed`…）原樣交函數；`fixed` 與 `model` 信不能蓋（`RequestBad`）。
- **排程**：priority 級數（每 `aging_ticks` 升一級）→ deadline → 包的 speed → 等得久 → 先寄；包 slots 滿＝跳過讓別包補；budget 到頂＝`BudgetMissing`。佇列狀態在 `queue.json`。
- **範本代號**：`smart-high`（LiteLLM claude-haiku）、`stupid-fast`（LM Studio）、`luna`（gpt-6-luna-low）、`sol`（gpt-6-sol）、`fake` 與五個 fake 劇本。
- **LiteLLM 怎麼接**：包寫 `"exec": "endpoints/litellm", "url": "http://localhost:4000/v1", "model": "<litellm 名>"`；`endpoints/litellm/_entry` 跑 `llm_http --key-env LITELLM_KEY`，**金鑰值只能由起 llm daemon 的 root 殼 export**（不放定義）。本機 proxy 不驗金鑰，但變數沒設 `llm_http` 就 `EndpointFailed`（實測，不足 #1）。
- **嵌套轉交**：**沒有內建**，但現有介面接得起來——endpoint 函數只是「stdin `{endpoint, request}` → stdout `{"message"}`」，問腦 proc 繼承 daemon 的環境（含 `AOS_LLM_KERNEL`），所以寫一支十來行的轉交函數（讀包裡自訂的 `to`、`aos-llm ask` 寄給下游 kernel、把 message 包回 `{"message": …}`）就通了（實測見末節）。缺口：`aos-llm ask` 只印 message、不回 `usage`，上層 kernel 的 token 帳全是 0；下游 kernel 的 `senders` 只看到上層 kernel 一格（不足 #3）。

## 4. daemon

- **一棵樹**：根 daemon 的 `procs` 可掛 exec 型 proc（另一台 daemon 的定義＝子 daemon、llm kernel）與 loop 型 agent；`aos-agent ctl add` 也是往 daemon 表加一列。範例樹：`~/code/playground` 與本線的 `~/code/playground-ak`（根→總機＋領班→agent）。多台 daemon 共用一個 llm kernel＝都 export 同一個 `AOS_LLM_KERNEL`。
- **sleep／wake**：daemon 收工（Ctrl-C／TERM）時還在跑的列留 `sleeping`，再開自動 wake；整棵樹葉先睡、根最後。手動：`aos-agent ctl sleep|wake`、`aos-daemon-ctl sleep|wake`。四態指令：start／stop、sleep／wake、pause／resume、add／rm。
- **`auto_restart: true`**（procs 列）：自己退了同一拍照表重起；`restart_on_stuck` 判卡住重起。
- **資源旋鈕**：① 列的 `limits`（daemon 頂層給預設）：`mem_mb`、`cpu_s`、`procs`、`file_mb`、`files`（每個行程各自的 rlimit，不從總額扣）、`user`（要 root）；② 判官 `kernel/daemon-judge` 的 `judge.json`：`allowed` 白名單、`max_running`、`queue`（FIFO 排隊）；③ `agents.json` `max_children`；④ llm kernel 的 `slots`／`reserved`／`budget`；⑤ 整樹總額＝外面包 `systemd-run --user --scope -p MemoryMax= -p CPUQuota=`（家機未實跑）。

## 5. git

- **程式裡沒有呼叫 git**（`proto8` 的 py／sh／C++ 都沒 `git` 子行程）。
- **只在文件與兩個樣板檔**：搬家食譜 `cmd/aos-agent/docs/04-搬家/02-image保存與邊界.md` 的「git image」（專門 repo、orphan commit、`push --force-with-lease`、push 後 `reflog expire`＋`gc --prune`）；`cmd/aos-agent/stack.gitignore`、`stack.gitattributes`；`extras/image-move-check/` 是驗搬家的假腦試驗場。
- K7 的定案「知識庫要歷史就 `git init`」也只是文字，沒有工具。

## 對這條線可能卡住的地方

1. 知識庫只能讀：agent 沒有 `memory_write`，要寫只能給 `bash`／`write`（限 ws 內）或人寫。
2. 節點段名限 `[a-z0-9_-]`：arknights `lore/` 全是中文詞條，不能直接拿詞條名當路徑。
3. 規模：`find` 最多 20 筆、每次 `grep -r` 掃全庫；30 MB 級的庫還沒實測速度與命中量。
4. 嵌套 kernel 要自寫轉交函數，且 token 帳與每隊額度斷在中間一層。
5. 子 agent 上限分散在三處（`max_children`、判官 `max_running`、kernel `slots`），範本領班沒有判官＝不限。
6. 原始語料 `corpus/`（1.1 GB）不在 arknights 的 git 裡，`git clone` 只拿得到 `lore/` 等追蹤檔。

## 試驗場實跑（11-07 10:08～10:12，家機；全部 `nice -n 10`）

| 步 | 指令（在 `~/code/playground-ak`，先 `source env.sh`） | 輸出（節錄） |
|---|---|---|
| 0 語料 | `git clone -q --depth 1 ~/repo/narratives/arknights corpus/arknights` | `warning: --depth is ignored in local clones`；0.2 s、62 MB、HEAD `5d9bedd` |
| 1 起樹 | `aos-exec root`（背景）；`aos-daemon-ctl -d $PG/.stack ping` 等三台 | `replied in 53 ms`×3；根表 `_tick`、`llm_kernel`、`daemon` running、`# root daemon (no supervisor)` |
| 2 掛 agent | `cd ws && aos-exec ../agents/fsm_ak` | `…/ws/.stack/procs/fsm_ak`；`ctl ls` running |
| 3 假腦 | `aos-agent say --target fsm_ak "what time is it" && aos-agent listen …` | `FAKE ANSWER to: what time is it (tool said: 2026-11-07T02:08:29Z)`，3.9 s |
| 4 gpt（第一次） | `aos-agent llm --target fsm_ak set endpoint=gpt-luna-low`；say＋`listen --timeout-s 120` | fsm_ak `stopped`：`llm_http: error: EndpointFailed environment variable LITELLM_KEY (--key-env) is not set`；listen 印了「fsm_ak is stopped」仍等滿 120 s 才 `AnswerMissing`（不足 #1、#2） |
| 4' 修 | `env.sh` 加 `export LITELLM_KEY=${LITELLM_KEY:-none}`；根 SIGINT（全樹留 sleeping）→ 重 source、重起 → `aos-agent ctl start --target fsm_ak` | `started (same stack); 0 queued letter(s) will be answered next` |
| 5 gpt 答 | `aos-agent listen --target fsm_ak` | `It’s 02:10 UTC on November 7, 2026.`，6.3 s；history：assistant `tool_calls clock {}` → tool `2026-11-07T02:10:52Z` → 答 |
| 5' 查知識庫 | say「Using your memory tool, find out how an aos agent starts a child agent…」 | 腦叫 `memory {"op":"read","path":"agents/"}`，答出 `agents` op add／new，7.9 s |
| 6 嵌套 | 另起 `llm_team/`（kernel.json 只兩包、`exec: forward`，`forward/_entry` 十行轉交）；`AOS_LLM_KERNEL=$PG/llm_team aos-llm ask` | `FAKE ANSWER to: hi`（1.8 s）、`nested ok`（gpt，3.3 s）；`llm_team/used.json` tokens 0，主 kernel `senders` 記成 `../llm_team` 一格 |
| 7 收 | 對自己記的 root、team pid 送 SIGINT | 兩支都退 130；`pgrep -af "aos-(daemon|loop|fsm|llm-kernel|exec)"` 空（退 1）；各列留 `sleeping` |

用量：主 kernel 一天 9 次、17564 tokens（gpt-luna-low 6 次）。LiteLLM 對只說 `hi` 的請求也回 `prompt_tokens` 1636（proxy 端多塞的，非 aos）。
