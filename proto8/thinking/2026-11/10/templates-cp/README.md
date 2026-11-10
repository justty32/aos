範本改成 AOS_HOME 寫法、自帶 .env、copy-out 拿掉的可行性調查（11-10 晚，只讀＋/tmp 實測，未改 repo 任何既有檔）。

← [11-10 日索引](../README.md)｜分檔：[01 現況盤點](01-現況盤點.md)｜[02 實測](02-實測.md)｜[03 .env](03-env.md)｜[04 刪 copy-out 前要解決的](04-刪copy-out前要解決的.md)｜[05 施工結果](05-施工結果.md)

# 結論

**最少只要 export 1 個（`AOS_HOME`）**：範本自帶 `.env` 給好其他預設、用 `cp -r` 抄出來，就能起根、掛 agent、假腦問一題、shutdown，整個資料夾 `mv` 到別處再起也照答。要是把 `AOS_HOME` 也寫進自己專案的 `.env`，一個都不用 export（實測過）。要用真模型的話，llms 那邊另外要 export 金鑰 `LITELLM_KEY` 這 1 個，金鑰不能寫進 `.env`。

- **做得到，而且不用改 lv1～lv4 的程式**。所有讀這些路徑的程式（aos-exec、aos-fsm、aos-loop／aos-daemon、aos-tools、aos-llm-kernel、memory 工具）**現在就收** `{"$env": "AOS_HOME", "$path": "/…"}`。copy-out 預設的 env 模式本來就是寫成這樣，而且已經有搬家測試跑過。所以「範本本身就寫成這樣」只差在範本檔怎麼寫，讀檔的程式不用動。
- **真正卡住的只有一件：範本裡的 symlink**。agent-fsm 和 eca-claude 各有 5 條，其中 4 條指進 `lib/`（`tools/memory*/_tooldef.json`、`_metainfo.json`）。`cp -r` 抄出去就斷，agent 起來後立刻停在表上（`ToolDefMissing`，訊息沒提到 symlink）。這些 symlink 也沒辦法換成 `$env` 寫法：`$ref` 的值只收字串，放不了 `$env`。**解法**：把範本的 `tools/` 夾整個拿掉，memory 直接登記 `lib/agent/memory` 那格，知識庫位置寫在 `tools.json` 那格的 `env` 裡（`AOS_MEMORY` 寫成 `$env` 寫法）。這樣範本裡 0 條 symlink，實測照答，知識庫的根也有進到問腦的請求。只動 lv5（範本）。
- **copy-out 能刪**。刪之前要先處理的有 9 項（[04](04-刪copy-out前要解決的.md)），**沒有一項擋得住**：大多是範本 JSON、測試的環境變數和文件。唯一碰到 lv3 的是 `lib/agent/agents`（工具 `agents` 的 `new`），它和 copy-out 共用 `lib/agent/copy_def.py`。不過對改好的範本，`copy_def` 改寫 0 處（實測），所以 lv3 可以先不動，等要刪 `copy_def.py` 時再小改（約 20 行加 2 支測試）。
- **沒設 `AOS_HOME` 時**，錯誤訊息本身看得懂（`aos-json: error: DirectiveBad environment variable AOS_HOME is not set`），但它寫在 `stacks/root/procs/ann/stderr.txt`。使用者在 `listen` 看到的只有 `RunFailed … fsm.json failed with exit code 1`。範本 `.env` 加一行 `AOS_HOME=${AOS_HOME}`，就會在起根那一刻直接報 `DotenvBad bad .env: …/defs/.env line N`（實測）。

## 三條路各一行（使用者已表態「copy-out 能刪就刪」，主線是 A）

| | 指令長相 | 要改的 | 照 C-85 一段白話 |
|---|---|---|---|
| **A（主線）** | `export AOS_HOME=…`；`cp -r $AOS_HOME/templates/agent-fsm defs/ann`；`aos-exec …`；`aos-agent …` | 範本 JSON（lv5，加上 kernel 範本的 JSON 資料）、刪 `tools/` 夾、約 12 支測試補 `AOS_HOME`、約 12 份文件、install.sh 拿掉一行；選做：lv3 的 agents new | 範本就是一般的資料夾：用 `cp -r` 抄走，設好 `AOS_HOME`（或寫進 `.env`）就能跑。 |
| B | 同 A；想要絕對或相對寫法時再跑 copy-out | 同 A，copy-out 留著 | 同 A，再加一句「想把 AOS_HOME 換成絕對或相對路徑就跑 copy-out」。其實 `.env` 寫 `AOS_HOME=/絕對` 或 `${AOS_WS}/…` 就能做到同樣的事，所以 copy-out 留著用處不大。 |
| C（現況） | `copy-out --template agent-fsm defs/ann` 加上兩個 export | 不用改 | 「copy-out 把範本抄出去，順便把指回 repo 的路徑改寫」，裝不下的有 7 樣（cli-sweep 03）。 |

從零到問一題的完整幾行，見 [04 § 指令長相](04-刪copy-out前要解決的.md#指令長相)。

## 要使用者選的（3 題）

1. **範本裡的 symlink怎麼處理？**
   - **(a) 拿掉 `tools/` 夾，memory 直接登記 lib 那格，知識庫寫在工具格的 `env`（推薦）**：0 條 symlink，`cp -r` 就通（實測）；每隻 agent 的知識庫設定從 `_memory.json` 搬到 `tools.json`。
   - (b) 換成真檔複本：`cp -r` 也通，但 repo 裡同一份 tooldef 會有兩份，lib 改了範本不會跟著變。
   - (c) 留著 symlink，文件教 `cp -rL`：實測通，但打成 `cp -r` 就壞，錯誤訊息也不提 symlink。
2. **範本 `.env` 要帶什麼？**
   - **(a) 帶 `AOS_CLOCK`（現有）、`AOS_LLM_KERNEL=${AOS_WS}/../llms/stacks/llm` 預設、`AOS_HOME=${AOS_HOME}` 必填檢查（推薦）**：使用者只要 export 1 個；llms 放在別處時，在殼裡 export 就會蓋過預設。
   - (b) 只帶 `AOS_CLOCK` 加必填檢查：`AOS_LLM_KERNEL` 照舊每次 export，變成 2 個。
3. **`lib/agent/copy_def.py`（工具 `agents` 的 `new` 也在用）要不要一起拿掉？**
   - **(a) 一起拿掉，`agents new` 改成單純整夾複製（推薦）**：lv3 小改，約 20 行加 2 支測試；之後 `new` 從範本生子 agent 跟人手 `cp -r` 一模一樣。
   - (b) 先留著：lv3 完全不碰；`copy_def` 對新範本改寫 0 處，等於留下一段沒在做事的程式。

我自己代定的細節列在 [04 § 代定](04-刪copy-out前要解決的.md#代定的細節)。

## 沒實測或拿不準的

- eca-claude、reviewer、judge-llm、llm-team、daemon-judge、procs-kernel 只驗了「cp 出來後指示詞解得開、`aos-tools ls` 列得出來」，**沒有實際跑**（eca 要真的 claude）。去掉 symlink 的寫法只在 agent-fsm 上跑過，eca-claude 是同一個結構、照推。
- `cmd/aos-sandbox/examples/thought-boxed`：沙箱裡唯讀掛了 `templates/agent-fsm` 和 `lib`，`AOS_HOME` 進不進得了沙箱、路徑對不對，沒驗。
- `kernel/docs/03` 的 demo 在原地 `ctl add $P/templates/agent-fsm`，範本改寫後要先 export `AOS_HOME`。沒有實際跑那份 demo。
- `interfaces.json` 的 `"memory": "tools/memory/_memory.json"` 這個 key，grep 沒找到哪個程式在讀，去掉 `tools/` 時一起刪；施工前請施工隊再確認一次。
- 實測用的是「假 proto8」：`lib/`、`py/` 等是 symlink 到這份 clone，`templates/`、`kernel/` 換成手改的版本。這份 clone 同時有兩隊在改（`AOS_PROTO8→AOS_HOME` 改名已經在工作樹裡、還沒 commit），所以測到的是當下工作樹的程式。
- `/mnt/c` 和 Windows 沒有測。`llm.json` 留 `{}`、讓 kernel 用預設端點這條沒測（實測都寫了 `{"endpoint": "fake"}`）。

## 使用者已答（11-10 收工前，頂層轉達；只記裁定、明天施工）

- 「copy-out能刪就刪」＝走選項 A：範本全改 `AOS_HOME` 寫法、copy-out 整支刪、文件教 `cp -r`。
- 三題快選都選推薦：
  1. 範本不再帶 symlink：拿掉範本的 `tools/` 夾，memory 直接登記 lib 那格（`AOS_HOME` 寫法），知識庫位置寫在工具格的 env。
  2. 範本 `.env` 帶 `AOS_CLOCK`、`AOS_LLM_KERNEL` 預設（工作區旁的 llms 專案）、`AOS_HOME=${AOS_HOME}` 必填檢查；使用者只需 export `AOS_HOME` 一個。
  3. `lib/agent/copy_def.py` 跟 copy-out 一起拿掉，`agents new` 改成單純整夾複製（lv3 小改，使用者已點頭）。
- 明天排在 two-machines B01 剩下那半之後施工。

