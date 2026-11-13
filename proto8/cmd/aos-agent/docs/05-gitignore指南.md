# gitignore 指南：自行選擇要帶走的狀態與只留本機的檔。

← [aos-agent](../README.md)｜[可選 stack 範本](../stack.gitignore)｜[逐類依據](../../../thinking/2026-11/10/two-machines/gitignore_classes.json)

你可以把 stack 放進自己的專案 repo，也可以分開管理、放在 repo 外。`defs/`、`stacks/` 都只是例子；名字、數量、位置由你決定。aos 不替你放 `.gitignore`，不替你操作 git，也不以這份指南或檢查工具擋住啟動。

## 要留什麼、擋什麼

`.gitignore` 只決定哪些尚未追蹤的檔不加入 git，並不刪檔，也不會讓已追蹤的檔自動退出 git。下表說的是用途；完整檔名、寫入者與實跑觀察見[分類表](../../../thinking/2026-11/10/two-machines/gitignore_classes.json)。

| 類別 | 例子 | 為什麼 |
|---|---|---|
| 帶走 `carry` | 定義、agent 記憶 `history.jsonl`、工具與腦設定、hook 清單 `hooks.json`、`state.json`、`state_flux.json`、`procs_state.json`、`stage.txt` | 下次從同一份設定與進度繼續；暫停狀態也要保留 |
| 帶走 `carry` | 未處理的 `new/`、`cur/`、agent `queue/`、歸檔信、`think/pending.txt`、`think/reply/` | 還沒處理完的工作與問腦回信；不能把所有 `reply/` 一起擋掉 |
| 帶走 `carry` | agent 自己記的進度：`goal.json`、待辦 `tools/todo/todo.json`、開著的任務 `tools/do_task/tasks.json` | 使用者 11-11「三個都進 git」：跟 history 一起走，換台後 goal 照常提醒、待辦接著做、do_task 的 end 照摺 |
| 帶走 `carry` | 跟子 agent 有關的帳：`subagents.json`（工具小格 `tools/subagent/` 的記帳、stack 根的配額設定）、fork 的分身紀錄 `tools/fork/children/<分身>/state` | 知道哪些子、哪些分身是我的，換台後還收得回來；分身自己的 stack 在 daemon 的 `procs/` 下，照一般 agent stack 帶走（代定） |
| 帶走 `carry` | `clock`、`ledger.jsonl`、`used.json`、`queue.json` | 時鐘、帳本、額度與隊序接著算；這些本來就可能每輪改動 |
| 帶走 `carry` | eca 的 `session.txt`、`tool.txt`、`ws.txt`、`stack.txt`、`last.txt` | 保留對話識別與小格狀態；`session.txt` 並不是 CLI 的整段原生對話資料 |
| 留本機 `local` | `.session_home` | 辨認這台的對話環境；換台不應沿用舊值 |
| 擋執行期檔 `runtime` | 鎖、socket、`cooldown.json`、`think/wait_warned.txt`、hook 的小格 `hooks/`、`hook_tools_seen.json`、ctl 呼叫者的回信箱 | 舊行程、舊等待者或這台牆上時間才有意義；帶過去無助於接續 |
| 擋可重建檔與暫存 `runtime`／`temp` | `think/request.json`、`think/sent.json`、stack 的 `endpoints.json` 觀測窗、MCP 設定、可執行檔工具的定義快取 `tooldef_cache.json`、`tmp/` 半封信、點開頭的原子寫入暫存、Python 快取 | 由仍保留的進度、設定或下一次操作重建；半封信尚未完成投遞 |
| 擋觀測與留證 `runtime` | `stderr.txt`、`stderr_archives/`、`sweeper_report.json`、`observed/`、`live.jsonl`、`turns.jsonl`、計數器、`*.bad-*` | 只留原機供人查看，避免每次存進一批無助接續的紀錄 |

不擋這些本機檔，常見結果是多出 log 與暫存的 diff、把舊絕對路徑帶到新機，或錯帶 `.session_home`。反過來，擋掉 history、在途信、pending 或帳本，會讓搬過去的進度不完整。`.gitignore` 不檢查檔案內容：定義、history、工具輸出、信與帳本裡若含金鑰或本機絕對路徑，仍可能被 commit；請把本機值與金鑰留在你自己選定的外部設定或環境變數。

定義裡的 `.env` 可能是必要設定，不能一概當垃圾。下面的寬規則因此只放在你選定的 stack 範圍。

## A：把樣板放在各 stack 根，推薦

選定一個 stack，把 [`stack.gitignore`](../stack.gitignore) 的內容手動放進它的 `.gitignore`。例如 `P` 是這台的 `proto8/`，`STACK` 是任意名稱、任意位置的 stack：

```sh
cp "$P/cmd/aos-agent/stack.gitignore" "$STACK/.gitignore"
```

如果已有 `.gitignore`，先合併你要的規則，保留自己的設定。aos 不會幫你放、更新或覆寫。另一個獨立 stack（包括另一個 `llms` 專案的 kernel stack）也由你決定是否放一份。若某個共同父資料夾只裝 stack，也可以只在那一層放，規則會涵蓋底下各層。

這個方法不看 `defs`、`stacks` 這些名字。改成 `d/`、`s/`，分成多份定義，或把 stack 放到專案外，規則仍從放置 `.gitignore` 的那層往下生效。**專案外的 stack 不會因此進入專案的 git**；要不要另存、存在哪個 repo，由你自己決定。

巢狀 stack 可以各有一份，相同排除規則疊起來有效。樣板的 `!**/.gitignore`、`!**/.gitattributes` 會保留子 stack 的規則本身；只寫 `!/.gitignore` 的話，只能保留放樣板那一層的檔。

代價是它有意在 stack 範圍內使用寬規則：

- `**/tmp/` 會擋所有深度的 `tmp/`；`**/.*` 會擋點開頭的檔與資料夾。一般 `.stack` 目錄、`.gitignore`、`.gitattributes` 已留例外；自訂持久點檔或其他點開頭的 stack 名稱，需自己補例外。
- 如果定義或專案成果也放在這個範圍內，裡面的 `.env`、自有 `tmp/`、定義 `endpoints.json` 也可能被擋。請縮小套用範圍，或為那些路徑補例外。樣板無法單憑檔名知道它是你的定義還是執行期產物。
- 自訂窗名、stderr 檔名或其他輸出，需按實際名稱補規則。例如把 `stderr.txt` 改成 `err.log`，相應封存夾 `err_archives/` 也要自己考慮。

不要直接把整份寬樣板放到同時存放程式與成果的專案根，否則專案自己的 `.env`、`tmp/` 也會一起隱藏。

## B：專案根只按 aos 檔名排除，可作起點

不想在各 stack 放檔，也可自行把較窄的規則放到自己的 repo 根。下面這組不依賴定義或 stack 的名字，並保留專案自己的 `.env`、`tmp/`、`state.json`；**它不是完整的 stack 排除樣板**：

```gitignore
**/.session_home
**/.flock
**/.sweeper.lock
**/.sweeper_pending.json
**/stderr.txt
# 11-10 以前的畫面 socket；之後放在 ${XDG_RUNTIME_DIR:-/tmp}/aos-tty-<uid>/，不在 stack 裡
**/tty.sock
**/lock
**/sender.flock
**/order.lock/
**/order.lock.releasing.*
**/claude/mcp.json
**/codex/mcp.json
**/tmux.conf
**/busy.txt
**/a2a.json
**/a2a_acks.jsonl
**/env.json
**/tools/run_python/main.py
**/tooldef_cache.json
**/procs_requests/reply/
**/daemon_reply/
**/think/request.json
**/think/wait_warned.txt
**/think/sent.json
**/cooldown.json
**/hook_tools_seen.json
**/live.jsonl
**/turns.jsonl
**/aos-mcp-logs.jsonl
**/mailbox_warning.txt
**/transcripts/
**/counter_*.txt
**/*.bad-*
**/stderr_archives/
**/sweeper_report.json
**/observed.jsonl
**/observed/
```

B 有兩個檔名無法解決的界線。其一，`endpoints.json` 在 kernel stack 是重建的觀測窗，在定義裡卻是要保留的設定；專案根加 `**/endpoints.json` 會兩者一起擋。其二，半封信所在的 `tmp/`、動態原子寫入暫存與 Python 快取，並沒有全域唯一的 aos 檔名；為了不隱藏專案自己的檔，上面沒有全域擋掉它們。

此外，只認檔名仍可能撞名：專案自己的 `app/stderr.txt` 也會被 `**/stderr.txt` 擋。專案根的規則也管不到 repo 外的 stack。要補齊 B，必須由你依實際位置與自訂名稱補規則或例外；能選出純 stack 範圍時，A 較容易完整。

這兩種擺法已用五種獨立 git 測試樹驗過：原名、改名、多定義與巢狀 stack、外置 stack、外置定義。A 保留測試中的所有持久檔、定義與專案檔；B 保留 `.env`、`tmp/`、`state.json`，同時重現上述漏擋與 `stderr.txt` 撞名。這是 git 規則測試，daemon 真正跑動與 clone 接續另由可選的[開發者回歸工具](../../../extras/gitignore-check/check.py)驗證；它不是日常使用必跑的一步。

## 存下來與換台

要保存一致的狀態，先讓使用中的 daemon 整棵 shutdown，再由你自行檢查、commit、push。根 daemon 與另一個專案的 llm kernel 各自保存；`AOS_LLM_KERNEL` 由你在新機指向那邊已啟動的 kernel，aos 不替你安排兩個 repo 的同步。

kernel 收件匣裡排隊、在途的信（`requests/new/`、`requests/cur/`）**樣板與指南都不擋、照帶**（使用者 11-10 裁「都按照推薦」）：避免只因寄件人此刻不在就靜默丟工作。代價：換台前最好讓 kernel 把它們處理完，否則接受重寄——帶走的信在另一台被答時，回信地址可能指向舊位置、**回信可能沒人收**；寄件那邊的 agent 發現信不在 kernel 了會自己重寄一次（wait 格會認）。帶走信件不等於另一個 repo 已同步；兩份 repo 分開搬時，請一併確認尚未完成的工作與路徑。

git 不保存空資料夾。本次 clone 實跑，一般 daemon 控制信箱、已進入初始化流程的 agent 信箱與 kernel `requests/` 會建回；未使用的領班 ctl 回信箱、尚未進入 idle 的子 agent `queue/` 則按需建立。

子 agent 保留 `think/pending.txt`、空的 `think/reply/` 沒被 git 保存時，wait 會先補回信箱再續收。

任意自行建立的信箱仍須按 `aos-post init` 的契約準備；單獨實跑確認，一般 `aos-post send` 不會替缺少的空信箱補好。新機上的執行檔、路徑與 CLI 登入，也仍由你準備。

## 追蹤檔裡的本機路徑，什麼算外洩

開發用的整棵實跑檢查 [`extras/gitignore-check`](../../../extras/gitignore-check/check.py) 會在 commit 前找追蹤檔裡的本機記號（暫存根、HOME、使用者名、主機名、repo 位置、`sk-` 金鑰開頭）。使用者 11-11 選「改檢查的標準」（two-machines B05／B06），下面三種**不算**外洩、不動 C++：

- **使用者自己寫的絕對路徑**：`defs/` 底下的定義與設定整份；daemon 表上原樣存的 `as_written`；程式從定義原樣抄到別處、跟定義裡一字不差的同一個字串。
- **帳本**：`ledger.jsonl`（只記當時路徑、不拿來解路徑）。
- **信封的 `sender`**（寄件人＝工作區路徑）。

`sk-` 金鑰開頭不在放過之列，哪裡出現都算。其餘照查；命中時結果檔的 `where` 印出是 JSON 裡哪一格與它的值。另外兩格**程式自己記的**絕對路徑也不算（使用者 11-11 再裁「放過」）：子 daemon 公開 state（`procs_state.json`、`state.json`）的 `daemon` 欄（上一層 daemon 的 stack），以及 kernel 在途信小格 `proc.json` 的 `exec`（定義裡寫的相對入口被轉成的絕對路徑）。只放過這兩格，同一檔的別格照查。
