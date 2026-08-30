# 任務：做出會自我投遞的 `aos agent`（含 `aos llm`），並規劃「自我投遞能否埋進 loop」

> 交接書是唯一契約。協定見 [PROTOCOL](PROTOCOL.md)（**以它為準**）。派線規則 [dispatch](../README.md)、隊形 [aos-teams](../aos-teams.md)。

## 背景與唯一目標

使用者的成品想像（[top-down-cli](../../ideas/top-down-cli.md) §一～§三）：視窗 A `aos run` 持續推進世界；視窗 B `aos agent init` 往投遞匣塞一份**會把自己再投遞一次**的 agent 指令，然後 `aos agent talk` 跟它交流。
**LLM CPU 仍以 inst 為核心，只是多一支可被指令呼叫的 llm 程式**（使用者 2026-08-30 原話）——所以「思考」＝一條 `aos agent step` 指令在回合裡跑，它內部呼叫 `aos llm`。
**唯一目標**：使用者能 `aos agent init W --name bob`，開著 `aos run W --step 0` 後，用 `aos agent say`／`listen`／`talk` 跟 bob 對話，bob 每回合自我投遞、狀態可從 `aos agent state` 與 `state.json` 看到；另交一份規劃文件回答「自我投遞能不能埋進 loop」。

## 團隊（你是 Opus 隊長）

- **Fable 規劃者 ×1**：`Agent(model="fable")`。兩件事：(a) 開工前把 `agents/<name>/` 的檔案版面與 `aos agent` 各子命令的行為定成一頁 `core/agent/README.md`；(b) 最後寫 `wf/workflows/ideas/self-delivery-in-loop.md`（見工作 7）。**只規劃，不寫實作。**
- **gpt-5.6-sol ×2**：`codex exec -m gpt-5.6-sol -C <你的 worktree 路徑> --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`。一位做 `core/llm`，一位做 `core/agent`。codex 可自行派生 codex／terra／luna。**codex 不 commit。**
- **Sonnet ×2**：一位寫 ctest 與假 loop（工作 2）；一位做 pi 介面調查與 `talk --interface pi`（工作 6）。
- 隊長自己：任務書、審 diff、ctest、commit。**你不親自寫實作。**

## 工作

1. 讀 [PROTOCOL](PROTOCOL.md)、`core/inst/CMakeLists.txt`（小專案範本）、`core/llms/CMakeLists.txt`（libcurl 走 `PRIVATE_DEPS` 的既有寫法）、`wf/workflows/add-subproject.md`、`wf/workflows/common/conventions.md`、[top-down-cli](../../ideas/top-down-cli.md)。
2. **你拿不到隊 A 的 loop**（它同時在 main 上做）。先寫一支 `core/agent/tests/fake_loop.py`（python3，≤ 80 行）照 PROTOCOL §1／§5 忠實模擬：搬 inbox → 並行執行 argv → 寫 out → 寫 state.json → turn+1。所有測試與 smoke 靠它；隊 A 落地後直接換成 `aos run`，不改協定。
3. `core/llm`：`aos llm`（協定 §6）。libcurl 打 `/v1/chat/completions`，非串流，只取第一個 choice 的文字。**模型固定 `qwen/qwen3.5-9b`；禁止呼叫 LM Studio 的 load／unload API**（使用者要求換模型要手動 unload，這件事歸他）。先 `curl localhost:1234/v1/models` 確認伺服器在。
4. `core/agent`：
   - `agents/<name>/`：`persona.md`、`history.json`（messages 陣列）、`status.json`（協定 §4 的四欄）、`say/`（使用者的話，投遞匣形式：`.tmp`→rename）、`log.md`（agent 說的話與思考，append-only）。
   - `aos agent init <folder> --name N [--persona TEXT]`：建 `.aos/`（若無）與上面版面，然後投遞第一條 `{"id":"agent-N-0","argv":["aos","agent","step","<folder>","N"]}`。
   - `aos agent step <folder> N`：status→thinking；收 `say/*.md` 併進 history；呼叫 `aos llm`（exec 子行程或直接連 `aos::llm` 都可）；回覆寫 history 與 log.md；status→idle；**再投遞一條 step 給自己**（id 帶回合號 `$AOS_TURN`）。若 `say/` 空且上一回合也空，可以不呼叫 LLM、只自我投遞（省 token）——**這是你的裁決點，選簡單的**。
   - `aos agent say <folder> N <text>`、`aos agent listen <folder> N`（tail -f 式跟 log.md）、`aos agent talk <folder> N`（stdin 一行→say，背景印新 log）、`aos agent state <folder> N`（印 status.json）。
   - **工具（使用者 2026-08-30 追加，必做）**：`agents/<name>/tools.json` 是工具登記表（每項 `name`／`description`／`argv` 模板；init 建預設幾項）。LLM 以固定格式回工具呼叫 → agent 依模板組成指令、`aos deliver` 投進 `.aos/inbox/`（id `agent-<name>-tool-<turn>-<n>`）→ 下一回合 step 從 `batch/<turn>/out/<id>.json` 讀結果餵回 LLM。**呼叫工具＝把要求投進 inst。**
5. 每個小專案 `README.md`；`wf/workflows/common/code-map.md` **在檔尾另起「core/llm、core/agent」一節**（避免跟隊 A 的段落衝突）。
6. **pi 介面層（使用者：「可以的話試著弄」）**：本機有 `pi` 0.84.2（`which pi`；先 `pi --help` 與它的文件搞清楚它是什麼、能不能掛自訂 provider／工具／stdin-stdout）。目標是 `aos agent talk <folder> N --interface pi`：把 pi 當「好用的終端機介面」，底下仍是 say/listen。做得到就做最小版；做不到就寫一頁 `core/agent/docs/pi-interface.md` 說明試了什麼、卡在哪、建議怎麼接。**上限：一位 Sonnet 的額度，不擴大。**
7. Fable 寫 `wf/workflows/ideas/self-delivery-in-loop.md`（≤ 2 頁）：純投遞式自我複製做得到什麼、做不到什麼（靜默死亡、停不下來、狀態新舊、跟 `state.json` 的關係），提出 1–2 個「loop 原生支援」方案（例如 `inbox/` 之外加 `agents/*/next.json` 由 loop 每回合自動投遞；或 state.json 的 `agents` 段反向驅動），各附代價。**只規劃，等使用者拍板；不實作。**
8. commit 到你的 worktree 分支。**不 rebase 進 main**——收線時調度者會指示。

## 硬性限制

- **禁區**：`core/inst/`、`core/llms/`、`core/tooljson/`、`core/exec/`、`core/wire/`、`core/loop/`、`reference/`、`app/`；`wf/` 只能寫 `wf/workflows/common/code-map.md`（檔尾新節）、`wf/workflows/ideas/self-delivery-in-loop.md`、本資料夾的 `reports/B.md` 與本檔「隊長裁決」段。
- **`git add` 只加明確路徑**，不 `-A`。**不 push。**
- 不取任何鎖、不開 GUI／瀏覽器、不裝系統套件、**不 load／unload LM Studio 模型**、不用 `claude`／`codex` CLI 當思考引擎（那是隊員，不是引擎）。
- 邊緣狀況一律跳過（agent 死了怎麼辦、say 撞車、多視窗 listen…）：**不實作，全部丟進工作 7 的文件**。
- 卡在設計選擇 → 選最簡單的、記「隊長裁決」、繼續。只有協定本身要改才 BLOCKED。
- 暫存物放 `/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/8f4f80fb-1793-4431-92e8-09478f666f76/scratchpad/team-b/`。

## 交付

| 產物 | 路徑 |
|---|---|
| 兩個小專案 | `core/llm/`、`core/agent/`（各含 README、tests；agent 另含 `tests/fake_loop.py`） |
| 登記 | `core/CMakeLists.txt` 加兩行 |
| 規劃文件 | `wf/workflows/ideas/self-delivery-in-loop.md` |
| pi 介面 | 程式或 `core/agent/docs/pi-interface.md` |
| code map | `wf/workflows/common/code-map.md` 檔尾新節 |
| 回報 | `wf/workflows/dispatch/proto/reports/B.md` |

## 驗收（就這 7 條）

1. worktree 根目錄 `cmake --build --preset default && ctest --preset default` 全綠。
2. `echo '只回一個字：好' | aos llm` 印出含「好」的回覆（真的打到 LM Studio）。
3. `aos agent init W --name bob` 後 `W/.aos/inbox/` 有一條 step 指令、`W/.aos/agents/bob/status.json` 存在。
4. 用 `fake_loop.py W --step 3` 跑三回合：每回合 inbox 都再出現一條新的 step（自我投遞成立），`state.json.agents.bob` 有值。
5. `aos agent say W bob "你叫什麼名字"` → 再跑一回合 → `aos agent listen`（或 log.md）出現 LLM 的回覆。
6. `self-delivery-in-loop.md` 存在且含「做不到什麼」與至少一個 loop 原生方案＋代價。
7. `aos agent say W bob "看看目前資料夾有哪些檔案"` → 跑兩回合 → log.md 出現投進 inbox 的工具指令，以及引用其結果的回覆。

## 回報

最後一則訊息＝ `reports/B.md` 摘要（≤ 30 行）＋終局 STATUS（`DONE`／`BLOCKED`／`FAILED`）＋你的 worktree 路徑與分支名。

## 隊長裁決

（隊長追加）
