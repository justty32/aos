← [入口](README.md)｜涵蓋：image 心智模型對到現況、image 裡有什麼／不屬於 image 的、WSL 拷貝實測｜上一份 [01-旅程對照](01-旅程對照.md)｜下一份 [03-絕對路徑盤點](03-絕對路徑盤點.md)

# image 模型：daemon＝硬體、stack＝記憶體、ws＝外置記憶體、定義＝source、daemon 下的 stack＝實例

使用者 11-05：「lisp可以做image，直接在程式執行中把狀態保存起來。在我們這邊，daemon就像是硬體，各stack就是各程序所佔據的記憶體空間。ws則是外置記憶體。各種定義資料夾則是類似source code，跑起來之後就是看其實例了(daemon下的stack)」。

## 對到現況（結論）

| 比喻 | 現況 | 搬家時 |
|---|---|---|
| 硬體＝daemon | `daemon/` 定義（`daemon.json`＝名單、硬體設定）＋ 一支 aos-daemon 行程 ＋ 它的 stack `ws/.stack/`（表 `procs_state.json`、自己的 `state.json`、信箱 `procs_ctl_mailbox/`） | 行程不搬；定義跟 image 一起搬；**image 裡的位址都相對這台硬體**（使用者 patch）＝相對 daemon 的 stack（[03](03-絕對路徑盤點.md)） |
| 記憶體＝各 proc 的 stack | 小格 `ws/.stack/procs/<名>/`：daemon 寫的 `loop.json`、子 loop 的 `state.json`（含 `paused`）、`stderr.txt`；P-42 三樣 `queue/`、`history.jsonl`、ctl／state；fsm 的 `stage.txt`；think／wait 的 `think/request.json`、`pending.txt`、`think/reply/`；工具小格 `tools/<名>/`；kernel 的 `mailbox/`、`queue.json`、`used.json` | 整塊搬。**實例不存 source 的副本**（使用者 11-05）：現在 aos-agent `tools` 第一次改會把定義的 `tools.json` 整份複製進 stack（path 改絕對）、`llm` 只存改過的鍵——前者要改（[05 衝突 2](05-衝突與方向題.md)） |
| 外置記憶體＝ws | `AOS_WS`；agent 寫成果的地方；**現在 daemon 的 stack 就長在 `ws/.stack/`**（N-57 預設） | 使用者的話把 stack 與 ws 當兩樣東西、「一起複製」；現況是一個資料夾。要不要維持＝[05 題 2](05-衝突與方向題.md) |
| source＝定義資料夾 | `agents/<名>/`（`_entry`、`loop.json`、`fsm.json`、`*.py`、`interfaces.json`、`tools.json`、`llm.json`）、`kernel/`、`daemon/` | 表的 `def`／`exec` 欄指向它；沒一起搬＝醒來 `aos-loop` 找不到 `exec` 的檔、退 1、列被拿掉（11-02「自己結束就下表」）——要 `add` 回來。[05 衝突 3](05-衝突與方向題.md) 建議 wake 失敗留列 |
| 實例＝daemon 下的 stack | 表上一列＋它的小格 | 同一份 source 可以掛好幾隻（11-04 aos-agent 已有「X 也用這份定義」提醒） |
| 存 image＝sleep＋Ctrl-C | Ctrl-C 走 `finish`：loop 型 SIGTERM（10 秒 KILL）、列 `sleeping`、最後一份表寫好才走 | 這一刻的 `ws/.stack/` 就是 image；**要在睡著時存**（跑著時 cp／commit＝半寫入的窗、認領中的 `cur/` 信，見 [04](04-跨電腦與git.md)） |
| 載回＝起 daemon | adopt：`sleeping` 的列用列上的 `stack` 再起（wake）；子 loop 讀自己 `state.json` 的 `paused` 接回暫停 | 全靠表上的路徑能在新位置解得開 |

**不屬於 image 的（暫存器／硬體狀態，醒來重建，不該讀）**：行程 id、`started_at_ticks`、`boot_id`（表與每扇 state 窗都有；現在就是「對不上＝沒在跑」，別台搬來一定對不上、剛好正確）；`mailbox/.flock`（kernel 的鎖，空檔，flock 不跨行程保存，複製無害）；eca 的 `tty.sock`（tmux socket，git 不收、cp 過去無效，醒來要重開畫面）、`lock`（fcntl）；`stderr.txt`（log）；`.`開頭暫存與 `tmp/`（半寫入的信）；kernel `queue.json` 的 `seen_at_runs`（排隊帳，重算也沒差）。**屬於 image 但綁機器的**：eca 的 `session.txt`（claude／codex 的對話 id，對話本體在那台的 `~/.claude`）、`transcripts/*.jsonl` symlink（指 `~/.claude/projects/…` 絕對路徑）——[04](04-跨電腦與git.md) 列成自擔。

**比喻不貼合的地方（天然差異，不追問）**：lisp image 連程式碼一起存，這裡 source（定義）在 image 外、靠路徑指；「記憶體」不會像真記憶體一樣被作業系統回收，`rm` 才清；兩個 daemon 能同時指同一塊「記憶體」（11-03 晚使用者「自己承擔」）；ws 這塊外置記憶體裝著 daemon 的記憶體（`.stack`），硬體在外接硬碟裡。

<a id="實測11-05wsl-tmp-拷貝"></a>
## 實測（11-05，WSL `/tmp` 拷貝；不碰 `~/code/playground`，沒改程式）

場地：`/tmp/pf-a/{daemon,kernel,agents/fsm_ann,ws}`（照試驗場，kernel／tools 指 WSL clone 的 `lib/base` 絕對路徑），`cd ws && aos-exec ../daemon`，`aos-agent add --ws . ../agents/fsm_ann`，假腦答一題、再寄一題 0.4 秒後 Ctrl-C。

| # | 做了什麼 | 結果 |
|---|---|---|
| A | 睡著後看 image | 表兩列 `sleeping`；image 15 個檔、13 個**空資料夾**（四個信箱各 `tmp/new/cur/`、`tools/clock/`）；寫死 `/tmp/pf-a` 的檔 3 個：`procs_state.json`、兩個小格的 `loop.json`；沒有 `+x` 檔、沒有 socket |
| B | `cp -a /tmp/pf-a /tmp/pf-b`，表**不改**，在 b 起 daemon | **回舊位置醒來**：log 兩列 `running`，`stack`＝`/tmp/pf-a/…`，子行程 `AOS_STACK`／`AOS_WS`／`AOS_CF` 全是 pf-a、只有 `AOS_DAEMON`／`AOS_KERNEL` 是 pf-b（殼設的）→ b 的 daemon 寫進 a 的小格（`stage.txt`、kernel `queue.json`、重寫 a 的 `loop.json` 成 b 的 exec），agent 寄信到 b 的 kernel 信箱、kernel 卻讀 a 的信箱＝那題永遠沒回；`aos-agent state` 印的全是 a 的路徑。**兩份互踩** |
| C | 重新 cp，`sed` 把 image 裡 `/tmp/pf-a`→`/tmp/pf-b`，再起 | 表、環境、小格全在 b；再寄一題正常答。（睡前半路那題丟了——因為 a 已在 B 被踩過、`pending.txt` 指到被刪的信箱；對照 D） |
| D | 對照：原地睡在 `think` 格、原地再起 | 醒來把那題答完、`listen` 拿到；sleep／wake 本身沒問題 |
| E | 整個 pf-b（定義＋daemon＋ws 含 `.stack`）`git init`＋commit，clone 到 pf-c，`sed` 路徑，起 daemon | git 收 32 檔、**沒有 755**；掉 13 個空資料夾；起來後 daemon `aos::post::init`、idle.py、wait.py、aos-tools 各自把 `tmp/new/cur/`、`tools/clock/` 建回來，say／listen 正常。git 也收進了不屬於 image 的 `.flock`、`stderr.txt`、兩扇 `state.json`（舊 pid）——無害但該擋 |
| F | 表上 `stack` 寫成相對 `procs/<名>`、`ws` 寫 `.` 再起 | daemon **不轉**、照字面從自己的 cwd（＝`daemon/` 定義資料夾，不是 stack）拼：小格長到 `daemon/procs/llm/`、fsm_ann 退 1 下表。證實今天的 adopt 只認絕對；「相對誰」要明定（[03](03-絕對路徑盤點.md)） |

收乾淨：pf-a～d 全刪、沒留行程；試驗場的 daemon 沒碰。
