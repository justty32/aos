← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

### `core/agent` 檔案表與分層

相依只往下看：`paths ← store`；`paths + store ← deliver／tools`；`init／step` 再組合這些下層；最上面的 `run` 只呼叫 `aos::agent` 公開 API。跨小專案方面，`core/agent` 公開相依 `aos::tool`（公開標頭直接使用 `aos::tool::Spec`），私有相依 `aos::exec`／`aos::llm`／`aos::loop`。箭頭右邊知道左邊，**下層不知道上層存在**。

| 檔案 | 負責什麼 |
|------|----------|
| `core/agent/include/aos/agent.hpp` | 公開資料型別與 API：世界／唯一 agent 解析、初始化、say／log／status／history／pending／tools、argv 展開、工具呼叫抽取及單步 `step()`；completion callback 讓測試可離線注入。 |
| `core/agent/src/internal.hpp` | 小專案內部契約：集中 `Paths`（含正典 `log.jsonl`）、journal／儲存、prompt、投遞等下層宣告；不安裝、不是跨小專案 API。 |
| `core/agent/src/paths.cpp` | 最底層路徑規則：`resolve_folder()` 從 cwd／`AOS_FOLDER` 找世界，`resolve_name()` 找唯一 agent；並正規化 world folder、驗 agent 名稱，推導 `.aos/inbox`、`.aos/every` 與 `agents/<name>/` 全部檔位。 |
| `core/agent/src/store.cpp` | 儲存層：文字讀取、tmp＋rename 原子寫入、正典 `log.jsonl` 追加與 `log.md` 重畫／竄改還原，以及 history／status／pending 的 JSON 讀寫與驗證；沒有 journal 的舊世界仍直接讀 `log.md`。 |
| `core/agent/src/deliver.cpp` | 投遞層：把已按登記展開的工具 argv、cwd、timeout 包成 instruction，原子寫入 world inbox。 |
| `core/agent/src/inbox.cpp` | 信箱儲存層：讀取並解析未讀訊息、按 id 排序，及把已讀訊息搬進 `read/`。 |
| `core/agent/src/inbox_cli.cpp` | `aos inbox ls／read` CLI：列信箱、由 `read` 消費訊息、支援唯一前綴，並在前綴歧義時列出候選。 |
| `core/agent/src/tools.cpp` | 工具層：讀世界 registry 並套用可選 agent 白名單、每工具一行的 system prompt、依 `list`／`string`／`none` 展開 argv，以及抽取、驗證 LLM 工具呼叫並回報未知工具／args 錯誤。 |
| `core/agent/src/step.cpp` | 回合編排層：收 say 與工具結果、把執行結果或呼叫錯誤包成固定 JSON `tool` message、更新 history／log／status、lmstudio 呼叫前取 provider 槽且等不到回 75、用 `engine.model` 覆蓋環境模型；LLM 成功後才刪 say，失敗寫 `error` 與 log 指引；無新事件時不耗 LLM token，也不自我投遞。 |
| `core/agent/src/init.cpp` | 初始化層：限制一個 world 只住一隻 agent，建立 agent 版面（含 `log.jsonl`）與必要的 world turn／state；世界 registry 為空才安裝 `sh`／`ls`／`cat`，不建立 agent 白名單；依 `AOS_BIN` → `/proc/self/exe` → PATH → `aos` 解析 every instruction 的 argv[0]。`say()` 也在這裡原子投遞訊息。 |
| `core/agent/src/user.cpp` | 使用者世界層：解析 `$HOME` 與 say 寄件世界，維護扁平的 `~/.aos/say/`／`log.md`，並投遞、彙整使用者信件。 |
| `core/agent/src/run.cpp` | `aos agent init／step／say／listen／talk／state` 完整 help 與 CLI 分派；init 省略 folder 時固定用 cwd，其他命令維持世界解析；共用 state 增加 unread／engine／model，listen 顯示未讀，talk 讀 stdin 前驗 runner 鎖。 |
| `core/agent/src/run.hpp` | agent CLI 內部介面：共用 `state_text()` 與 listen／talk 實作；pending 顯示規則、未讀區塊宣告都在這裡，不安裝。 |
| `core/agent/src/run_top.cpp` | 頂層 `aos say／listen／talk／state` 進入點與逐命令完整 help：解析 cwd 世界與唯一 agent；`say --to` 驗目標世界並印真正收件匣，`listen` 顯示未讀，`talk` 回報 pi 尚未內建並共用 runner 鎖檢查。 |
| `core/agent/tests/test_agent_cli.cpp` | CLI 回歸：全組 help、say 真實目的地與錯誤、state 未讀／engine／model、listen 未讀、talk runner 鎖與 pi 指引。 |
| `core/agent/tests/test_agent_lifecycle.cpp` | 生命周期回歸：lmstudio model、LLM／pi 失敗保留訊息、error／log 指引、journal 渲染／防竄改／舊世界相容，以及 every 的絕對 aos 路徑。 |
| `core/agent/tests/fake_loop.py` | 測試用 loop 替身：依協定搬入 inbox、複製 every、並行跑 instruction、寫 out／state、鏡射 agent status 並推進 turn。 |
| `core/agent/tests/smoke.sh` | 端到端 smoke：在 bob cwd 無參數初始化、驗 every 的 argv[0] 是可執行的 aos 路徑，再用替身推三回合，驗 every 每回合執行與 `state.json` 的 status 鏡射。 |
| `core/agent/tests/smoke_user.sh` | 手動端到端 smoke：離線驗 lmstudio step 搶槽、使用者 `~` 的 say／listen 與天然通訊錄列。 |
| `core/agent/README.md` | 回合 agent 的快速使用、工具往返節奏與函式庫入口。 |
| `core/agent/docs/pi-interface.md` | pi 0.84.2 實測、三種接法與尚未內建的 extension adapter 規劃；不是目前已完成的 CLI transport。 |

### `agents/<name>/` 版面

| 路徑 | 存什麼、誰寫 |
|------|--------------|
| `persona.md` | agent 人格；`aos agent init` 寫初值，使用者可直接編輯。 |
| `history.json` | 送給 LLM 的 user／assistant／tool messages；init 建空檔，`step` 讀寫。 |
| `status.json` | `status`／`detail`／`updated_at`／`turn`；init／step 原子寫，loop 唯讀鏡射進 world `state.json`。 |
| `say/*.md` | 等 agent 收取的使用者訊息；`say` 每則寫一個排序檔，`step` 讀入 history 後刪除。 |
| `log.jsonl` | 正典稽核紀錄；一行一則 `turn`／`role`／`content`，role 為 user／assistant／tool／note；init 建空檔，所有追加先寫這裡。 |
| `log.md` | 從 `log.jsonl` 完整重畫的可讀 transcript；listen／talk 讀取時若與 journal 不符會警告並還原。舊世界沒有 journal 時仍直接讀本檔。 |
| `tools.json` | 工具**白名單**，可有可無；不存在＝世界 `.aos/tools/` 登記的工具全部可用，空陣列＝全部停用。接受字串陣列，並相容含 `tools` 陣列的物件及帶 `name` 的舊物件項；init 不建立它。 |
| `pending.json` | 已投遞但尚未回收的工具 call ID、工具名、args 與投遞回合；init／step 寫，step 依它找結果。 |
