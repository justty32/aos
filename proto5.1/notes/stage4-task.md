# proto5.1 第 4 段任務書：照使用者拍板改六件事（2026-09-22）

接 [stage3-task.md](stage3-task.md)；先讀 `proto5/notes/2026-09-22-decisions.md`（**唯一決策來源**）、[findings.md](findings.md)（#1～#35）、`stage3-report.md`。
一樣只動 `proto5.1/`；問題接第 36 條記進 findings。**原則：保持 KISS**——能少一個欄位、一個分支就少。規範跟著改，格式（協議）一份、程式一份分開寫。

## 1. engine 只剩代號（llm cpu 1＋5）

- agent `info.json` 的 `engine` 變成 **`{"cpu": <llm cpu 資料夾路徑>, "model": "<代號>", "params": {...}}`**；`cpu` 必填（指示詞可解）、`model` 非空字串、`params` 可省（物件）。`endpoint`／`api_key`／`timeout_ms` 從 agent 這邊**拿掉**。
- **同步模式拿掉**：think 一律送 cpu；`aos_llm_ask` 的 `request_from_info`／同步呼叫路徑刪掉（`call(engine, body)` 留給 cpu 用）；相關測試改成搭一個 llm cpu 家、測試裡叫一次 tick。
- llm cpu 的 `info.json` 加 **`models` 表**：`{"<代號>": {"endpoint": url, "model": "<真名>", "api_key": <字串或 null>, "timeout_ms": <正整數，預設 120000>}}`，值可用指示詞（api_key 用 `$env`）。cpu 讀 info 時解。
- 請求 payload 變成 **`{"model": "<代號>", "body": {...}, "result": "<絕對路徑>"}`**；`body.model` 由 cpu 用表裡的真名填（agent 不寫）。代號不在表→`ok:false`、error 寫「不認識的模型代號」。
- 規範：`spec/llm-cpu.md`、`spec/aos-llm-cpu.md`、`spec/aos-llm-ask.md`（engine 那節整個改、同步 HTTP 拿掉）、`spec/agent.md`／`aos-agent.md` 提到 engine 的地方。

## 2. 連敗暫停用 consume（逾時 3）

- 引擎連敗 3 次→waits 加 `{"file": "continue.json", "consume": true}`（照 agent.md 的 waits 格式寫）；**拿掉封存舊 continue.json 那段**。門開了檔就被吃掉，第二次暫停自然有效。
- 規範 `spec/aos-agent.md` 連敗那段改。

## 3. 結果不明的固定文字（act 6）

- tool cpu 收屍／失聯時 agent 接給模型的 tool 訊息固定為 `{"ok": false, "error": "結果不明：工具可能已經跑了，也可能沒有"}`（content 是這個 JSON 字串）；不重試。逾時、非零退出等**已知**失敗照現在的寫法，不要混成結果不明。
- 規範 `spec/aos-agent.md`／`tool-cpu.md` 寫清楚哪幾種情況算「結果不明」。

## 4. act 並行不處理（act 5）

- 程式不動。`spec/aos-agent.md` 寫明：同一則 assistant 裡多個 `_run: cpu` 工具，訊息順序有保證、**執行順序沒有**；有先後關係的工具別標 cpu 或合成一個工具。

## 5. aos-run：run.json＋ctl.json，拿掉槽鎖與 status-fd（daemon/kernel 4）

- 新旗標 **`--home DIR`**（可省；沒給就不寫狀態、不讀 ctl）。有 home 時：
  - **`<home>/run.json`**（先寫 `.tmp` 再 rename）：`{"pid", "busy", "target", "runs", "last_exit", "last_kind", "last_ms", "held"}`。
    **順序固定**：每次要跑之前先寫 `busy: true, target: null` → 讀目標（`run_target` 讀 inst 之前，target 寫成目標的絕對路徑）→ 跑 → 寫 `busy: false` 與 runs／last_*。這個順序是 kernel 擋重疊的前提，規範要寫成「保證」。
  - **`<home>/ctl.json`**：每次跑之前（間歇結束後）讀一次。`{"op": "stop"}`→不再跑、正常退出（reason `ctl`）；`{"op": "hold"}`→不跑、`run.json` 寫 `held: true`，每 interval 再讀，直到 ctl.json 不見或 op 不是 hold 才繼續（`held: false`）。aos-run 不刪 ctl.json（誰寫誰刪）。壞 JSON／未知 op 當作沒有。
- **拿掉** `--status-fd` 與所有 status 事件；**拿掉** `TARGET.lock` 槽鎖與 `Y` 讓位標記那整套（aos_run／aos_kernel／spec 都清乾淨）。
- 訊號：第一次 TERM／INT＝跑完這次就停（**不砍子程式**）；第二次＝TERM 直接子程式那一組（不找後代）。開 **`--kill-tree`** 時第一次 TERM 就走 `aos_exec.terminate`（/proc 找後代、TERM→2 秒→KILL）。`--kill-tree` 預設不開。
- 規範 `spec/aos-run.md` 整份改；run.json／ctl.json 是格式，寫進同一份的「家」一節就好（aos-run 沒有其他家檔）。

## 6. daemon：runner 家＋kill_tree（daemon/kernel 4、5）

- add 請求多兩格：`kill_tree`（bool，預設 false）；daemon 啟動 aos-run 時給 `--home <daemon home>/runners/<名>/`（daemon 建資料夾）、`kill_tree` 真就加 `--kill-tree`。
- state entry 多一格 **`home`**（給 kernel 找 run.json）；`ready`／`running`／`runs`／`last_exit`／`last_kind` 這幾格改成**從 run.json 讀**（daemon 不再靠 status-fd），或直接拿掉、叫人去讀 run.json——選較少程式的那個，規範說清楚。
- stop：kill_tree 沒開→TERM（跑完這次就停）→等 5 秒→再 TERM 一次（砍直接子程式那組）→再等 5 秒→KILL aos-run group；開了→TERM→5 秒→KILL。
- 規範 `spec/daemon-home.md`、`spec/aos-daemon.md`。

## 7. kernel：拿掉槽鎖，改看 run.json（daemon/kernel 4、5）

- config 加 `kill_tree`（bool，預設 false），開 cpu 時傳給 daemon add。
- 換人＝直接 rename `cpus/<n>.json`，隨時可換，不等 runner。
- **排程規則只加一條**：要把行程 X 放進任何 `cpus/<n>.json` 之前，先換掉目標檔（如果是換人），再讀每顆 cpu 的 run.json（路徑從 daemon state entry 的 `home`）；哪顆 `busy` 為真且 `target` 是 X 或 `target` 是 null，X 這一格就不排、下一格再看。這條規則跟 aos-run 的寫入順序合起來就擋住重疊，規範要把這個推論寫出來（兩三句就好）。
- `cpus/<n>.json.lock`、yield 意圖、等 runner 停妥那些**全部拿掉**。
- 規範 `spec/kernel-home.md`、`spec/aos-kernel.md`。

## 測試、真跑、文件

- 每一段對應的測試改到綠；擋重疊要有一條測試：短 interval（0）＋一個跑 2 秒的 inst，kernel 換人後把 X 排去另一顆，驗證 X 沒有同時在兩顆跑（看 run.json）。ctl hold／stop 各一條。kill-tree 開／不開各一條（不開時孫程式活著，開時死掉）。
- 真跑：同第 3 段那套（daemon＋3 顆 cpu：agent／llm cpu／tool cpu，LM Studio `http://127.0.0.1:1234/v1` 模型 `qwen/qwen3-1.7b`，agent 的 engine 只寫代號），貼 ls、最後記憶、stop 後 `pgrep -f aos-` 空。
- 文件：`README.md`（分段表第 4 段「做完」、規範表更新）、`lib/README.md`、`notes/stage4-report.md`（檔案清單、測試數字、真跑紀錄、findings 新增幾條＋最重要 5 條）。
- 只動 `proto5.1/`；不 commit／push／stash／checkout。
