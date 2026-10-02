# 通用 tick：核心

← [整理區](README.md)｜[名詞](terms.md)｜[慣例](conventions.md)｜[hooks](tick/hooks.md)｜[tasks-blocked](tick/tasks-blocked.md)｜格式：[tick 協議](protocol/tick.md)｜[暫緩區](deferred/tick.md)

`aos-tick [<目標>]` 是一個定期被執行的程式。**程式與測試就是正本**：`proto6/src/py/lib/aos_tick*.py`（`aos_tick.py` 主流程、`aos_tick_table.py` 讀表、`aos_tick_run.py` 跑項、`aos_tick_record.py` 紀錄、`aos_tick_hooks.py` 掛點）；測試 `tests/test_tick_*.py`；說明 [docs/tick.md](../../src/py/docs/tick.md)。這裡只留設計原則。

**總原則：默認一切正常**。POC 不考慮邊緣狀況：紀錄讀得懂、寫得進去、斷電不倒退都不保證，出錯就讓程式自然丟錯、回 1。

## B-626：核心與系統級任務的界線

核心只做三件事：互斥鎖（B-602）、照任務表跑（B-620）、每項結束碼紀錄（B-633）；照表跑時另外只認 tasks-blocked 與擋板檔兩個檔。核心不靠 daemon、git、cgroup、helper，也不靠任何系統級任務；任務沒有 `user`，一律用 tick 自己的帳號（要換帳號只能在 daemon 設定檔做）。**任務能影響之後的項或之後的格，只有 tasks-blocked 與擋板檔這兩個檔，結束碼沒有特別意義。** 管轄權是約定、不是前提：碰不到的東西照各自規則失敗，tick 照樣跑完一格。

## B-602：同一資料夾一次一格

對 `<狀態資料夾>/tick.lock` 取非阻塞獨占 flock，取鎖在看擋板檔之前；拿不到印 `busy`、回 0、不寫紀錄、不加 `seq`。鎖 fd 不傳給任務，所以任務留下的後代不會佔住鎖。核心不清後代、不管逾時。人手要改工作資料夾，先停住排程（`aos-ctl pause`）。

## B-620：照表依序跑

任務表只有一個位置：`<狀態資料夾>/tasks.json`，**陣列位置就是順序**。目標只能是資料夾（給檔是用法錯），不給就用 cwd，不往上層找。一格：認資料夾 → 取鎖 → 看擋板檔 → 讀表並做極簡檢查 → 換新紀錄 → 逐項跑（每項前看 tasks-blocked）→ `after_all` → 刪 tasks-blocked → 回碼。

- **極簡檢查只查**：合法 JSON、有 `tasks` 陣列、每項是物件、合併頂層預設後有 `argv`、要展開的鍵展得開。不過＝`bad_table`、回 1、不開格。其餘（`id` 重複、`kind` 值、陌生鍵）一概不查，由建表的工具或人在 `aos-ctl resume` 前用 schema 驗。
- **先合併再展開**：頂層預設與該項淺層合併，成為一份 inst 才執行；項寫了的鍵整個蓋過。
- **任務結束碼完全不影響 tick**：成敗都照記、照跑下一項；沒跑成記 125／126／127（同 inst）。
- tick 只回 0 或 1（C-08）；stderr 代碼：`usage`、`busy`、`no_target`、`no_tasks`、`bad_table`、`exec_failed`。
- 環境變數見 C-10。

**tasks-blocked 與擋板檔**：tasks-blocked 擋「本格後面的項」，任務、hook 或人都能建，核心整格最後刪；內容 `{"kinds":[…]}` 時只跳過那些 kind。擋板檔擋「之後各格」，只由人手刪，核心取鎖後看到就直接回 0、一切不做。兩者都只看存不存在（kinds 除外）。daemon 不看它們，由 tick 自己擋。

## B-633：每項結束碼紀錄與格數

核心每格寫一份紀錄，讓後面的任務讀得到：跑了幾項、哪幾項結束碼不是 0（0 不記）。一格一個資料夾 `tick/current/`，上一格 `tick/last/`；常變的欄位拆成各自的小檔，`record.json` 用 `$ref` 指過去。格式看 [protocol/tick.md](protocol/tick.md) 與 schema。

- **格數 `seq`**：本資料夾第幾格，跨重啟、換 daemon、改 cron 都接著數；busy、被擋板擋、`bad_table` 的格沒有紀錄、不佔號。
- 換紀錄用「寫暫存資料夾再 rename」，不 fsync；`ended:true` 要等所有 hooks 跑完才寫，所以 tick 中途被殺，下一格看到 `last/` 的 `ended:false`。
- 核心除了算 `seq`，不拿紀錄做任何決定。人手刪紀錄，`seq` 重數，風險自負。

## B-627：直接跑一格：風險自負

`aos-tick` 誰都能直接跑。現行 daemon 只是定期叫 `aos-exec`，經它跑的格跟人手、cron 直接跑沒有差別：同樣互斥（互相碰到印 `busy`）、同樣寫紀錄加 `seq`。想經 daemon 立刻跑一格用 `aos-ctl wake`。
