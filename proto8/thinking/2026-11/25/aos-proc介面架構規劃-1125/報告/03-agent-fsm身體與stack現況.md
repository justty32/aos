盤點 agent-fsm（直接叫 API 的 agent）的 stack 裡每個檔誰寫誰讀、照新模型分成四類，並實測 kill -9 之後靠哪些檔接回；結論是 agent-fsm 今天沒有「記憶體裡的身體」，常駐的只有一支排班的 aos-loop，全部狀態都在檔裡，所以改義要做的是把一個夾拆成兩種壽命，以及不再拿 stack 路徑當身分。

# 03 agent-fsm 的身體與 stack 現況

← [架構規劃入口](../README.md)

寫的人：第 03 隻子 agent（fable）。只讀 repo 與活樹，實驗都在 `~/.aos/scratch/aos-proc-arch-1125/03/`。路徑沒特別說的都從 `proto8/` 算起。版本：repo HEAD `c196f9110` 加工作樹，`bin/` 是 11-25 09:44 裝的那份。

三種話分開寫：使用者的原話會寫明「使用者」、逐字放在「」裡；查到的附 `檔:行` 或實測編號（E1～E8，第 2.3 節）；我自己推的標「推論」。其餘的「」只是標名詞，檔案裡的字用 `這種字` 引。

名詞：**格**＝fsm 的一個狀態，每次跑是一支新的短命程式（agent-fsm 有 idle、think、wait、act 四格）。**覆蓋層**＝agent 自己改過的設定，只存跟定義不同的地方。**在途**＝事情做到一半才有意義的檔（例：問腦的信寄出去了、回信還沒收）。

## 1. 結論

1. **agent-fsm 沒有活在記憶體裡的身體。** 常駐的只有一支 aos-loop（活樹那隻佔 2.8 MB），它每 300 ms 起一支新的 Python 跑一格，格跑完就結束。所有狀態都在 stack 的檔裡。對這種身體，「stack＝活的身體」不是搬一個夾，是把今天混在同一個夾的四種東西拆開。
2. **stack 裡約 45 樣檔與夾**（活樹約 40 個 agent-fsm stack 的聯集）。照新模型分：要留的約 20 樣、活的約 20 樣；別人會來寫的不只信箱，有 9 處，另有 3 種是管理的人直接改檔；「說自己東西放哪」今天沒有一個集中的檔，散在五個地方。
3. **實測：kill -9 之後接回同一隻，靠的是 `history.jsonl`、`stage.txt`、`think/pending.txt` 加 `think/reply/`、`letters.json`，再加覆蓋層。** 各少一樣的後果都不同：回合卡住不答、多付一次模型費、問的人等不到回答、悄悄換了一顆腦（E4）。
4. **kill -9 只殺得到 aos-loop，正在跑的格和工具變孤兒照跑。** 馬上重起就是兩個身體同時寫同一份 history：實測工具跑了兩次、同一個呼叫出現兩則結果（E3）。「行程死了身體就消失」在 agent-fsm 是一整棵行程樹的事。
5. **`AOS_STACK` 今天身兼兩職：「我的檔在哪」與「我是誰」。** daemon 的表認人、信封的寄件人、llm kernel 的額度帳都拿 stack 路徑當身分。身體路徑如果每次重起都換，這幾處要先改。程式與設定裡提到 `AOS_STACK` 的有 174 檔 527 行（不含測試與文件），分九類用法，「當身分用」是另外的第十類。
6. **token 用量今天就是自己報的**：wait 格每問一次腦，在自己 stack 的 `observed.jsonl` 記一列；`/usage` 每次把整個檔重加一遍。kernel 那邊另有自己的帳。做成純文字檔要動兩支程式。
7. **等模型回覆時 pause、stop 都在一拍內生效**（實測 0.02 秒、0.10 秒），模型那次呼叫不取消，回信落在 `think/reply/` 等它回來收。跑工具時要等工具跑完（實測 11.6 秒）。
8. **agent-fsm 有兩層控制**：aos-loop 的 `ctl.json`（pause、resume、stop，一拍內）與寄進對話佇列的斜線信（`/compact`、`/clear`、`/status`、`/usage`、`/exit`，等回合結束）。新的 `ctl` 與 `status` 剛好可以把這兩層收成一套（推論）。

## 2. 查到的事實

### 2.1 一隻 agent-fsm 長什麼樣

| 項目 | 事實 | 出處 |
|---|---|---|
| 常駐的行程 | 只有 `aos-loop loop.json` 一支；活樹 `mine_paper/main` 那支 RSS 2824 KB | `ps -o rss,cmd -p 1696883` |
| 它站在哪 | 定義夾，不是自己的 stack；同一份定義的每一隻都站同一個夾 | `readlink /proc/1696883/cwd` → `…/templates/agents/agent-fsm` |
| 它的環境變數 | `AOS_STACK`（絕對、結尾 `/`）、`AOS_WS`、`AOS_CD`、`AOS_CF`、`AOS_DAEMON`、`AOS_LLM_KERNEL`、`AOS_CLOCK`、`AOS_HOME` | `/proc/1696883/environ` |
| 一拍做什麼 | 每隔 300 ms 起 `aos-fsm`，它讀 `stage.txt`、起那一格的 Python，照結束碼換格 | `templates/agents/agent-fsm/loop.json:1`、`fsm.json:1-11` |
| 跑工具時的行程樹 | aos-loop → aos-fsm → `act.py` → 工具 → bash → 指令，共六支，分屬四個行程群組、四個 session | E3、E9 |
| 記憶體裡有什麼 | aos-loop 只是定期跑一個目標的排班程式，不讀對話與佇列（`cpp/aos-loop/README.md:5`）。推論：對話、佇列、在途的請求都只存在檔裡 | 同左；2.8 MB 的大小 |
| 閒著時寫檔 | 沒有時鐘：5.7 秒 0 次。有時鐘（活樹）：60 秒內 `hookeds/context_wrap/` 兩個檔各 11 次、`hookeds/mail_notify/` 兩個檔各 1 次，其餘不動 | E1；`watch_mtime.py` 量 `mine_paper/main` |
| 知識庫怎麼教 | `stack = memory`、`RAM of one running proc: its state, history, mailbox` | `knowledge/aos/world.md:3,10` |

最後一列值得注意：給 agent 讀的知識庫今天就把 stack 比成記憶體，跟使用者的新說法同一個比喻；但實作是一個永遠留在硬碟上的夾，`ctl rm` 也留著它，`adding it again with the same stack picks it up`（`knowledge/aos/status.md:17`）。今天「接回同一隻」這件事是 stack 自己在做。

### 2.2 stack 裡每一樣

分類欄的字：**身**＝活的身體（行程死了就該消失）；**留**＝persist（重起靠它接回同一隻）；**留（紀錄）**＝只往後加、掉了不影響接著做，但有人會回頭查；**設**＝說自己東西放哪；**信**＝別人會來寫的。「一回合」指 E1 那種最短的回合：一封信、腦叫一次工具、再回答，共四則訊息。

**A. aos-loop 與 aos-fsm 寫的（C++）**

| 檔 | 誰寫 | 誰讀 | 多常寫 | 掉了會怎樣 | 類 |
|---|---|---|---|---|---|
| `state.json` | aos-loop | daemon（判活著）、aos-agent（看暫停）、wait 格（拿 loop 的 pid）、hook（認「這次 loop」）；kernel 與 aos-comm 拿它認「這是 proc 的 stack」（`py/tools/aos/kernel_llm/budget.py:98`、`py/aos/comm/walk.py:17`） | 有變才寫：起來、暫停、恢復、結束 | 安靜重建；**暫停狀態丟掉**（E7） | 身；其中 `paused` 一個值要留 |
| `state_flux.json` | aos-loop | daemon（判卡住）、下 ctl 的人（等序號追上） | 每收一道新 ctl | 舊的 stop **再生效一次**，起來立刻退（E7） | 身；要跟 `ctl.json` 同生死 |
| `ctl.json` | 誰都能寫：daemon（stop）、`aos-agent ctl pause`（`py/aos/apps/agent/ctl/phase.py:252`）、人 | aos-loop 每拍讀 | 有人下指令才寫；loop 不刪它 | 沒有新指令 | 信 |
| `stop_cause.json` | daemon 送 SIGTERM 之前 | aos-loop 收工時 | 每次被收 | 收工原因記成 `signal` | 身 |
| `stage.txt` | aos-fsm | aos-fsm 每拍、人 | 換格才寫：一回合 7 次 | 從 idle 重來，**做到一半的回合卡住不答**（E4） | 留（在途） |
| `stderr.txt` | daemon 開檔，loop 與每格的 stderr 往後加 | daemon（取最後一行當 reason）、`listen` 的提示、人；aos-agent 拿它認「這是 agent 的 stack」（`py/aos/apps/agent/common.py:243`） | 有警告或錯才加 | 表上的 reason 空白 | 身（紀錄） |
| `exec.json`、`loop.json` | daemon，每次起它時重寫（帶環境變數掛的才有；活樹 38 個裡 30 個有） | aos-exec；`ctl who` 從裡面讀 parent、notify_box | 每次起 | 下次起寫回 | 設（daemon 寫的那一半） |

**B. 對話**

| 檔 | 誰寫 | 誰讀 | 多常寫 | 掉了會怎樣 | 類 |
|---|---|---|---|---|---|
| `history.jsonl` | idle、wait、act 各自往後加一行；`/compact`、`/clear`、`aos-agent history`（人、父 agent）整份重寫 | brain 每次想都整份讀（`py/aos/apps/agent_fsm/brain.py:242`）；外面等回答的人每 0.2 秒整份讀一次（`py/aos/ws.py:119`、`py/aos/apps/agent/listen.py:279`） | 每則訊息一行：一回合 4 次 | 什麼都不記得，等於換了一隻 | 留 |
| `letters.json` | idle（收了哪幾封）、wait（答完清掉） | 問的人靠它配「哪則回答是回我的」（`py/aos/ws.py:288`）；wait | 一回合 2 次；Python 這幾格自己寫的檔裡，只有它寫完會 fsync（`py/aos/ws.py:198`） | 回答不帶信名，**問的人等不到**（E4） | 留（在途） |
| `history_removed.jsonl` | 壓縮、清空、`aos-agent history` 把原文搬來 | 找被摺掉的回答（`py/aos/ws.py:276`）、agent 與人回頭查 | 每次壓縮；只加不刪，最大的檔（例子 1.7 MB） | 摺掉的原文查不到 | 留（紀錄） |
| `handoff.md` | 壓縮時加一節（`py/aos/apps/agent_fsm/compact.py:462`） | agent、人 | 每次壓縮 | 少一份累積摘要 | 留（紀錄） |
| `compact.json` | 壓縮流程（`compact.py:211`） | idle、brain、wait、`/status` | 每次壓縮 2 次 | 壓到一半時掉了會怎樣沒測 | 留（在途） |
| `goal.json` | 工具 goal、`aos-agent goal`、idle | idle 每拍看在不在 | 設目標、每次提醒 | 目標沒了 | 留 |
| `observed.jsonl` | wait 每次腦回信一列、act 每次工具一列 | `/usage` 整檔加總；context 讀數讀最後 256 KiB（有鐘時每 5 秒） | 每步一列：一回合 3 次 | **用量歸零** | 留（紀錄）；現行分類是「不帶走」 |
| `cooldown.json`、`quiet.json`、`mailbox_warning.txt` | wait、idle | wait、`ctl ls -l`、人 | 問腦失敗、等超過 10 分鐘、收到壞信時 | 不等冷卻就重試；少一個提示 | 身 |
| `interfaces.json`（stack 裡那份） | 第一次記帳時（`py/aos/observed.py:16-22`） | 父 agent 抄子的帳 | 一次 | 下次補回 | 設 |

**C. 問腦中（`think/`）**

| 檔 | 誰寫 | 誰讀 | 多常寫 | 掉了會怎樣 | 類 |
|---|---|---|---|---|---|
| `request.json` | brain 每次想整份重寫：整份對話加 system 加工具說明（空對話就 26 KB，例子 237 KB） | wait | 每步 1 次 | wait 回 think 重組 | 身 |
| `pending.txt` | wait 寄出後記下信名（`wait.py:495`） | wait | 每步寫 1 次、刪 1 次 | 已到的回信沒人認，**多問一次腦**（E4） | 留（在途） |
| `reply/` | **llm kernel 把回信投進來** | wait | 每步 1 封 | 同上；agent 死著時回信照樣落在這裡（E2） | 信 |
| `sent.json`、`brain_wait.json`、`wait_warned.txt` | wait | wait（算耗時）、context 讀數（找 kernel 公布的視窗） | 每步 | 耗時記 null、讀數暫時沒有 | 身 |

**D. 別人投信的地方**

| 夾 | 誰寫 | 誰讀 | 掉了會怎樣 | 類 |
|---|---|---|---|---|
| `queue/` | 要它做事的人：`aos-agent say`／`ask`／`chat`、時鐘的信、它自己的 hook。`say` 會替還沒起來的 agent 先建這個夾（`py/aos/ws.py:105-106`） | idle 收進 history 就刪（`idle.py:228`） | 還沒收的話沒了 | 信 |
| `mailbox/` | 別的 agent（`mailbox_send`）、使用者專區、子 agent 的回報 | agent 自己用工具讀；hook 每分鐘看一次 | 沒讀的信沒了 | 信 |
| `daemon_reply/`、`tools/<工具>/daemon_reply/` | daemon 回它下的指令（`py/aos/daemon_ctl/post.py:97-102`） | 下指令的那支 | 那次指令等不到回音；10 分鐘沒領就清 | 信（短命） |

**E. 自己那份設定與小格**

| 檔 | 誰寫 | 誰讀 | 掉了會怎樣 | 類 |
|---|---|---|---|---|
| `tools.json`、`llm.json`、`system.txt`、`hookeds.json`、`subagents.json` | `aos-agent tools`／`llm`／`system`／`hook`（agent 自己的 self 工具、人、父 agent） | brain、act、wait 每格重讀 | **悄悄退回定義那份**（E4：腦換了） | 留 |
| `tools/todo/todo.json`、`tools/do_task/tasks.json`、`tools/subagent/subagents.json`、`tools/fork/children/` | 各工具 | 各工具 | 待辦、開著的任務、「哪些子是我的」沒了 | 留 |
| `hookeds/<名>/event.json`、`on_clock.json` | hook 引擎，每次發事件、每次看時鐘 | handler 自己 | 當成第一次，立刻跑一次 | 身 |
| `hookeds/mail_notify/notified.json`、`hookeds/context_wrap/state.json` | handler 自己 | 同 | 舊信再提醒一次、可能再寄一次 `/compact` | 身（現行分類）；其實影響重起後的行為 |
| `tools/run_python/main.py`、`tooldef_cache.json`、`hook_tools_seen.json`、各種鎖、`.` 開頭的暫存 | 工具、aos-tools、brain | 同 | 重建 | 身 |
| `board.json`、`comm/` | aos-comm（agent 自己貼的布告：在忙什麼） | 別的 agent、人 | 布告沒了 | 留 |
| `gdb/log.jsonl` | 另一隻觀察用的 proc | 人 | 少紀錄 | 信 |
| `notes_path` | 人 | 只有 eca 的壓縮 hook 讀，agent-fsm 不讀（→ [04](04-eca身體與stack現況.md)） | — | 設（今天唯一「一行路徑」的先例） |

**別人會寫進這個夾的，數起來有九處**：`ctl.json`（下指令的人）、`queue/`（說話的人）、`mailbox/`（別的 agent）、`think/reply/`（llm kernel）、`daemon_reply/`（daemon）、`gdb/log.jsonl`（觀察的 proc），加上 daemon 自己寫的三樣：`stop_cause.json`、`stderr.txt`、`exec.json`。另外有三種是**管理的人直接改檔**，不經過 agent：`aos-agent history` 改 `history.jsonl`、`aos-agent tools`／`llm`／`system`／`hook` 改覆蓋層、`aos-agent goal` 改 `goal.json`；父 agent 經 subagent 工具也走這條（`py/tools/agent/subagent/_entry:316`）。

量一下大小（`classify.py`，規則照上面的分類；活樹上有 `stage.txt` 與 `history.jsonl` 的夾，第一次數 38 個，量大小時多了一個）：

| | 留 | 信 | 身 | 留（紀錄） |
|---|---|---|---|---|
| `mine_paper/main` 一隻 | 206 KB（10 檔） | 4 KB | 248 KB（其中 `request.json` 237 KB） | 2.18 MB |
| 活樹 39 個 agent-fsm stack 合計 | 6.2 MB | 0.19 MB | 6.9 MB | 24 MB |

**今天已經有兩份分類**，跟上表大致對得上：
- `py/aos/apps/agent/stack.gitignore` 與 `py/aos/apps/agent/docs/05-gitignore指南.md`：把 stack 的檔分成「帶走」與「不帶走」（逐檔 102 列在 `thinking/2026-11/10/two-machines/gitignore_classes.json`）。「帶走」幾乎就是上表的「留」加「信」。
- `docs/NORMS/附錄4-持久檔.json`：70 列，每列有誰寫、誰讀、壞了怎麼反應（hook 那幾列還寫舊名 `hooks/`）。

對不上的三處：
1. 三扇窗（`state.json`、`state_flux.json`、`ctl.json`）現行是「帶走」，理由寫在 `stack.gitignore:7`：`paused 也要帶著醒`。照新模型它們是活的身體。
2. `observed.jsonl` 現行「不帶走」，但 `/usage` 的總數靠它。
3. hook 小格整個「不帶走」，但裡面兩個檔記著「提醒過哪些信」。

**今天混在一起的地方**（分開時會卡的）：
- **一個根**。每支程式都是 `$AOS_STACK/<檔名>`，檔名寫死在程式裡；定義的 `interfaces.json` 只宣告了 tools、llm、history、system、hookeds、observed 六個名字的位置。
- **`think/` 一個夾三種壽命**：可重建的請求（身）、信名（留）、回信箱（信）。
- **`tools/<名>/`、`hookeds/<名>/` 是 stack 裡的小 stack**：工具被叫時 `AOS_STACK` 被換成這個小格（`py/aos/apps/tools/main.py:399`）。待辦清單這種要留的，跟每次重寫的暫存放同一格。
- **三扇窗要同生共死**（E7）。
- **收件處的地址就是 stack 路徑**，而且已經寫進寄出去的信裡當回信地址。

### 2.3 實測

環境：自己起一個假腦的 llm kernel 加一隻直接跑的 agent-fsm（不掛 daemon、沒有時鐘），環境變數清到只剩 `AOS_HOME` 與 `PATH`。腳本 `harness.py`、`e1`～`e8` 在暫存夾（不保證留著）。每次跑完查過沒有留下行程。

| 編號 | 做什麼 | 結果 |
|---|---|---|
| E1 | 一個最短的回合 | 4.9 秒。寫檔次數：`stage.txt` 7、`history.jsonl` 4、`observed.jsonl` 3、`letters.json` 2、`think/` 四個小檔各 2；閒著 5.7 秒 0 次 |
| E2 | 等腦（15 秒）時 kill -9 aos-loop | `state.json` 還寫 `running` 與死掉的 pid；15.6 秒後回信照樣落進 `think/reply/new/`；重起後接著收、答完，回答掛的信名是原來那封 |
| E3 | 跑 12 秒的工具時 kill -9 aos-loop，馬上重起 | 舊的 aos-fsm、`act.py`、工具、bash、sleep 五支照跑；新的 loop 又把工具跑一次（副作用發生兩次）；history 裡兩則 tool 結果、同一個 `tool_call_id` |
| E4 | 等腦時殺掉、等回信到了，給**新的空身體**不同的舊檔 | 下一張表 |
| E5 | 等腦時與跑工具時下 pause、stop、SIGTERM | 第 2.6 節 |
| E6 | idle 把信接進 history 之後、收掉信之前死掉（手工擺出那個狀態） | 重起後同一封信進了 history 兩次 |
| E7 | 三扇窗少一扇再起 | 再下一張表 |
| E8 | 讓 aos-loop 站在自己的 stack 裡 | 原樣起不來：`aos-exec: error: EntryMissing entry not found: fsm.json`；把 `loop.json` 的 `"exec": "fsm.json"` 改成經 `AOS_CD` 指過去，整個回合照跑，`/proc/<pid>/cwd/stage.txt` 讀得到 |
| E9 | 跑工具時看整棵行程樹的群組 | 六支行程分屬四個行程群組、四個 session：aos-loop 與 aos-fsm 一組，`act.py`、工具、bash 加指令各自一組 |
| 附 | 身體裡放一個 symlink 指到 persist 的檔 | 往後加的寫入到得了；「寫暫存檔再改名」會把連結換成一般檔，persist 那份停在舊內容 |

**E4：新身體拿到哪些檔**（殺之前有一個答完的回合；被殺的那一問，腦的回信已經到了）

| 新身體拿到 | 結果 | 這一問叫了幾次腦 |
|---|---|---|
| 只有 `history.jsonl` | 25 秒沒答，停在 idle。再寄一封新信才動，回答只掛新信的名字 | — |
| 加 `stage.txt` | 5.0 秒答完。已到的回信沒用上，重問；回答不帶信名；腦退回預設那顆 | 2（多 1 次） |
| 再加 `think/pending.txt`、`think/reply/`、`letters.json` | 3.0 秒答完。接上已到的回信，信名正確；腦還是退回預設 | 1 |
| 再加 `llm.json` | 8.7 秒答完，用的是原來那顆慢腦 | 1 |

**E7：三扇窗少一扇**

| 之前 | 重起時少了什麼 | 結果 |
|---|---|---|
| 用 ctl 停下（序號 3），`ctl.json` 還寫著 stop | 都在 | 正常跑（舊的 stop 不重做） |
| 同上 | `state_flux.json` | **立刻又停**，退 0 |
| 用 ctl 暫停（序號 5）後被 kill -9 | 都在 | 起來仍是暫停 |
| 同上 | `state.json` | **不暫停，直接跑** |
| 同上 | `state.json` 與 `state_flux.json` | 又暫停（把 `ctl.json` 那道當新的） |

最小重跑（E2 加 E4 的頭尾兩種；實際輸出在下面）：

```sh
nap(){ python3 -c "import time,sys;time.sleep(float(sys.argv[1]))" "$1"; }
mkdir -p $HOME/.aos/scratch; S=$(mktemp -d -p $HOME/.aos/scratch); P=$HOME/repo/aos/proto8; E="env -i HOME=$HOME AOS_HOME=$P PATH=$P/bin:/usr/bin:/bin"
pid(){ python3 -c "import json,sys;print(json.load(open(sys.argv[1]+'/state.json'))['pid'])" "$1"; }
cp -r $P/templates/agents/agent-fsm $S/def; mkdir $S/k $S/kd $S/ws $S/st; echo '{"model":"slow"}' > $S/st/llm.json
echo '{"exec":"'$P'/lib/tools/base/llm_fake","endpoint":"fake","endpoints":{"fake":{"tool":"peek_now_time"},"slow":{"exec":"'$P'/templates/kernels/llm-kernel/fake_slow","delay_s":6,"tool":"peek_now_time"}}}' > $S/kd/kernel.json
echo '{"interval_ms":100,"exec":{"argv":["aos-exec","'$P'/lib/tools/aos/kernel_llm","'$S'/kd/kernel.json"]}}' > $S/kd/daemon.json
(cd $S/kd && $E AOS_STACK=$S/k/ AOS_CD=$S/kd AOS_WS=$S/kd setsid aos-daemon daemon.json >$S/k.log 2>&1 &)                # 假腦的 llm kernel，一次 6 秒
go(){ (cd $S/ws && $E AOS_LLM_KERNEL=$S/k setsid aos-exec --ws $S/ws --stack $S/$1 $S/def/body.json >>$S/$1.log 2>&1 &); nap 2; }
go st; echo '{"role":"user","content":"hi"}' | $E aos-post send --ordered $S/st/queue >/dev/null; nap 2.5
echo "stage=$(cat $S/st/stage.txt)"; kill -9 $(pid $S/st); nap 8                                                         # 等腦時殺掉
echo "死後 phase=$(python3 -c "import json;print(json.load(open('$S/st/state.json'))['phase'])") 回信 $(ls $S/st/think/reply/new | wc -l) 封"
mkdir -p $S/b1 $S/b2/think; cp $S/st/history.jsonl $S/b1/
cp $S/st/history.jsonl $S/st/stage.txt $S/st/letters.json $S/st/llm.json $S/b2/; cp -r $S/st/think/pending.txt $S/st/think/reply $S/b2/think/
for b in b1 b2; do go $b; nap 12; echo "$b: history $(wc -l < $S/$b/history.jsonl) 行"; kill $(pid $S/$b); done
echo '{"cmd":"stop","seq":1}' > $S/k/ctl.json
```

```
stage=wait
死後 phase=running 回信 1 封
b1: history 1 行
b2: history 4 行
```

### 2.4 `AOS_STACK` 與拼 stack 路徑的地方

重數用的指令（bash；每行後面是我跑出來的數字）：

```sh
cd ~/repo/aos/proto8      # lib/ 是 py/ 裝好的複本，不要重複算
X=(-g '!*test*' -g '!tests' -g '!*.md' -g '!_index.json' -g '!third_party'); D=(py cpp templates frontend)
n(){ rg -c "$@" "${X[@]}" "${D[@]}" | awk -F: '{f++;s+=$NF} END{print f+0" 檔 "s+0" 行"}'; }
n -e 'AOS_STACK'                                                                      # 全部  174 檔 527 行
n -e 'environ(\.get\(|\[)["'"'"']AOS_STACK|getenv\("AOS_STACK|env_or_empty\("AOS_STACK|environ\(env\)\.get\("AOS_STACK'   # A  54 檔 62 行
n -e 'setenv\("AOS_STACK|\[["'"'"']AOS_STACK["'"'"']\]\s*=|AOS_STACK=[a-z(]'          # B  14 檔 16 行
n -e 'AOS_STACK_IN_CALLER'                                                            # C   7 檔 13 行
n -e '"\$env":\s*"AOS_STACK"'                                                         # D  16 檔 20 行
n -e 'os\.path\.join\(stack\b|Path\(stack\)|os\.path\.join\(self\.stack\b'            # E  60 檔 161 行
n -e '\ba\.stack\b|kid\["stack"\]|kid_stack\('                                        # F  23 檔 131 行
n -e '\.get\("stack"\)|\["stack"\]'                                                   # G  49 檔 102 行
n -e '["'"'"']--stack["'"'"']|--stack[ =]'                                            # H  42 檔 101 行
n -e '["'"'"'/]\.stack\b'                                                             # I  38 檔 67 行
```

另有測試 144 檔 428 行、文件 196 檔 462 行（→ [13](13-文件、測試與活樹的遷移衝擊.md)）。行數是「提到的地方」，不等於「要改的地方」；E、F、G 三類的樣式也會撈到 kernel 與 daemon 自己的 stack。

| 類 | 用法 | 規模 | 代表 | 身體與 persist 分開後 |
|---|---|---|---|---|
| A | 讀環境變數，當「我的檔在哪」 | 54 檔 62 行 | 四格各一行（`idle.py:116`、`brain.py:105`、`wait.py:195`、`act.py:87`）、`cpp/aos-fsm/src/main.cpp:64`、每支工具與 hook handler | 每個讀的人要知道它要的檔在哪一邊 |
| B | 設給下一層 | 14 檔 16 行 | daemon 給 proc（`cpp/aos-daemon/src/child/child.cpp:88`）、aos-exec（`cpp/aos-exec/src/env/env.cpp:52,72`）、aos-tools 給工具小格（`py/aos/apps/tools/main.py:399`）、父 agent 借用子的小格（`py/tools/agent/subagent/_entry:316`） | 小格是「這次呼叫的身體」還是「這支工具要留的東西」要分 |
| C | `AOS_STACK_IN_CALLER`：工具把路徑印給腦看時的換算 | 7 檔 13 行 | `py/aos/tool_io.py:266-300` | 跟著 B |
| D | 定義檔裡的 `{"$env": "AOS_STACK"}` | 16 檔 20 行 | 全在 kernel 與 daemon 的範本；**agent-fsm 範本一處都沒有** | agent-fsm 的定義不用改 |
| E | 拼自己 stack 底下的檔名 | 60 檔 161 行 | `idle.py` 10 行、`py/aos/ws.py`、`py/aos/agentlib/context_use.py` | 每個檔名歸到兩個根之一 |
| F | 拿別隻的 stack 去讀寫它的檔 | 23 檔 131 行 | `py/aos/apps/agent/listen.py` 21 行、`hints.py` 14 行、`ctl/rm.py` 12 行 | 對方死著時只剩 persist 那一半 |
| G | 從 daemon 的表拿 `stack` 欄 | 49 檔 102 行 | `py/tools/agent/subagent/_entry` 20 行、`py/aos/apps/agent/common.py:124-132` | 表上要兩欄，或這一欄改指 persist |
| H | `--stack` 旗標 | 42 檔 101 行 | aos-exec、`aos-mailbox -s`、`ctl add -s`、`ctl who --stack` | 人指定的是要接回的那塊 persist |
| I | 預設夾名 `.stack` | 38 檔 67 行 | `cpp/aos-exec/src/env/env.cpp:43`、`py/aos/apps/agent/common.py:244`、各指令的說明文字 | → [06](06-路徑、環境變數與命名現況.md) |

**第十類沒有單一樣式：拿 stack 路徑當「我是誰」。** 找到這些：

| 哪裡 | 怎麼用 | 出處 |
|---|---|---|
| 認自己的名字 | `$AOS_STACK` 落在表上哪一列的 stack 裡，那列的名字就是我 | `py/aos/apps/agent/ctl/who.py:38`、`py/aos/daemon_table.py:110-112` |
| 信封的寄件人 | `$AOS_STACK` 的絕對路徑 | `cpp/aos-util/src/proc.cpp:109`、`cpp/aos-llm/src/send/send.cpp:123` |
| llm kernel 的額度與帳 | `used.json` 的 senders、`ledger.jsonl` 的 sender 都是 stack 路徑 | `py/tools/aos/kernel_llm/budget.py:94-101`；E1 的 kernel 夾裡是 `"../stack"` |
| goal 是誰改的 | 呼叫者的 `AOS_STACK` 在不在對方的 stack 裡 | `py/aos/apps/agent/goal.py:120` |
| 守門 hook 的禁寫範圍 | 從 `AOS_STACK` 算 | `py/tools/agent/guard/scope.py:98-99` |
| 這支行程是誰的 | daemon 接回行程、清道夫都看 `/proc/<pid>/environ` 的 `AOS_STACK` | `cpp/aos-daemon/src/daemon/adopt.cpp:62-70`、`py/aos/sweep_proc.py:201` |
| 回信地址 | `<stack>/mailbox`、`<stack>/think/reply`、`<stack>/daemon_reply` | `wait.py:202,480`、`py/aos/daemon_ctl/post.py:99-101` |

### 2.5 `/status`、`/usage` 的數字從哪來

兩個都是寄進 `queue/` 的信，idle 格認出來、不叫腦、把回答寫進 history（`idle.py:287-312`）。

| 數字 | 來源 | 出處 |
|---|---|---|
| model、思考程度 | 定義的 `llm.json` 疊 stack 那份 | `py/aos/apps/agent_fsm/slash.py:37-44` |
| history 幾則 | 數 `history.jsonl` 的行 | `slash.py:47-52` |
| goal、壓縮狀態、冷卻 | `goal.json`、`compact.json`、`cooldown.json` | `slash.py:75-88` |
| 幾封信等著 | 數 `queue/new` 與 `queue/cur` | `slash.py:55-62` |
| 問腦幾次、各欄 token 加總、最後一次 | `observed.jsonl` 整檔讀一遍，取 kind 是 think 或 compact 的列，把 usage 最上層的整數欄照原名相加 | `slash.py:95-130` |
| context 用了幾成 | `observed.jsonl` 最後一則有用量的 think，除以 kernel 公布的視窗 | `slash.py:131-133`、`py/aos/agentlib/context_use.py:264-317` |
| `observed.jsonl` 那一列 | wait 用 `aos-llm recv --full` 收回信，把 usage 原樣記一列 | `wait.py:409-410,541-549` |

活樹例子：432 次問腦，`prompt_tokens` 22,647,423、`completion_tokens` 105,850。巢狀的欄（`cached_tokens`、`reasoning_tokens`）今天不加總。

kernel 那邊另有自己的帳：`<kernel>/ledger.jsonl` 每次呼叫一列（信名、寄件人、usage），`<kernel>/used.json` 是額度計數（E1 的 kernel 夾裡看到的）。`9p-proc-1125.md`「定了的」那條（kernel 發出去多少記在 kernel 自己的目錄）今天已經是這樣。

**做成身體目錄裡的一個純文字檔，要動的地方**（推論）：
1. `wait.py` 的 `observe()`：記完那一列之後，把累計更新進一個小檔（寫暫存再改名）。讀的人就不必每次整檔重加。
2. `slash.py` 的 `usage()`：改成讀那個檔，或保留整檔加總當對帳。
3. 測試 `templates/tests/agent-fsm/test_slash_cmds.py`。
4. 兩件要先定：累計從什麼時候算起（第 5 節第 5 題）；欄名照端點原樣，還是 aos 定一套。

已有先例：stack 裡的通用檔 `context_usage.json`，檔頭說明寫 `任何腦都可以在每輪結束時寫 {"used": 整數, "window": 整數, "turn": 字串}`（`py/aos/agentlib/context_use.py:12,40`）；agent-fsm 自己今天不寫它。

### 2.6 狀態機、status 與 ctl

**今天「我現在怎樣」散在這些地方**（做 `status` 的原料）：

| 能報的 | 今天在哪 | 誰寫 |
|---|---|---|
| running、waiting、paused、stopped、done | `state.json` 的 phase | aos-loop |
| stopped、sleeping、stopping、stuck 與原因 | daemon 的表 | daemon，不在 proc 自己手上 |
| idle、think、wait、act | `stage.txt` | aos-fsm；名字是定義的 `fsm.json` 取的，別的定義可以不同 |
| 等腦多久、等哪一封 | `think/pending.txt` 的時間與內容、`quiet.json` | wait |
| 冷卻到幾點、第幾次失敗 | `cooldown.json` | wait |
| 壓縮中沒、目標 | `compact.json`、`goal.json` | 各自的流程 |
| 幾封話等著、幾封信沒讀 | `queue/`、`mailbox/` 裡有幾項 | **寄的人**一寄就變 |
| 用哪顆腦 | 兩份 `llm.json` | 改設定的人 |
| 在忙什麼（自己寫的一句話） | `board.json` | agent 自己 |

推論：
- 這些值有三個寫的人（aos-loop、aos-fsm、各格），外加「別人寄信就會變」的計數。落檔的 `status` 要保持新，只能每次有變就重寫。aos-loop 的窗有一條「有變才寫」的規矩（`cpp/aos-loop/docs/02-窗.md:13`），`status` 也得照這條，不能放每拍都變的值。
- 信有幾封這種值，讀的人自己數資料夾就有，不必進 `status`。
- 四個格名可以原樣當一行。要跟 eca 共用一組字，得另定對照（idle＝閒著，think 與 act＝在忙，wait＝等腦）。→ [18](18-ctl、status、settings的候選寫法.md)

**ctl 遇到正在等模型回覆的一輪**（E5；設計寫在 `wait.py:3`：`loop 照跑、不卡著等：每拍一下就退，ctl 的 pause／stop 每拍都看得到`，與 `templates/docs/02-agent-fsm.md:69`）

| 當下 | 下什麼 | 結果 |
|---|---|---|
| 等腦 | pause | 0.02 秒內回音。模型那次呼叫照跑完，回信 6.8 秒後落進 `think/reply/new/`，history 不動 |
| 等腦，暫停中 | resume | 0.40 秒後接上那封回信 |
| 等腦 | stop | 0.10 秒後 loop 退 0。`stage.txt` 停在 wait、`pending.txt` 留著。再起就接著收、答完 |
| 跑 12 秒的工具 | pause | 11.6 秒後才回音：正在跑的那一格不打斷 |
| 跑工具 | SIGTERM（daemon 的 sleep 送的） | 0.11 秒收掉整群、退 143、不留半則結果。再起後工具從頭重跑 |

- **沒有「取消那次模型呼叫」**：有 `aos-llm regret` 這個指令（抽回 kernel 還沒開始跑的信），但四格沒有任何地方叫它。停下來時 token 照花，回信等它回來。
- **等腦沒有期限**：每滿 10 分鐘 stderr 一行警告、寫 `quiet.json`，照樣等（`wait.py:294-330`）。
- **ctl 只有三個字**：pause、resume、stop（`cpp/aos-loop/include/aos/loop.hpp:53-61`）。sleep 是訊號；start、wake、rm 是寄給 daemon 的信。
- **另一層控制走對話佇列**：`/compact`、`/clear`、`/status`、`/usage`、`/exit` 是信，idle 格處理，所以要等這一輪答完（`/compact` 例外）。

## 3. 對新介面的含意

對著 `9p-proc-1125.md`「定了的」逐條。除了標出處的，這一節都是推論。

| 定了的 | 對 agent-fsm 的含意 |
|---|---|
| **stack 的意思換了**。使用者：「我的想法是.stack就沒有了，它本身就是指向"一個活著的proc的身體所在"，只是我們現在的實作將其放在硬碟上」 | agent-fsm 的格每次都是新行程、每次從檔重讀，所以**要留的檔可以直接開在 persist，不必經過身體**。這樣沒有「多久存一次」的問題，跟今天一樣穩。身體那一半（約 20 樣，例子那隻約 250 KB，幾乎都是 `think/request.json`）整個放 tmpfs 也不怕丟。要動的是第 2.4 節 E、F 兩類：每個檔名歸到兩個根之一 |
| 使用者：「/proc/<PID>就是他的stack，並且直接對應到記憶體內他的stack」 | 這句只有把 agent-fsm 改寫成一支常駐行程（四格變成函數、對話在記憶體）才字面成立。今天的 aos-loop 記憶體裡沒有對話。要不要走到這一步，見第 5 節第 1 題 |
| **persist 在哪以 proc 自己說的為準**，daemon 從它的目錄讀 `settings` | 今天「我的東西放哪」散在五處：環境變數、定義的 `interfaces.json`、daemon 表上那一列（`ctl who --json` 印的）、stack 裡的 `exec.json`、資料檔裡順手記的路徑（`think/brain_wait.json`、`observed.jsonl` 第一列）。aos-loop 起來時這些值都在手上，寫一個 `settings` 不難。但 aos-loop 不知道自己跑的是 agent，信箱在哪這種行要由懂 agent 的那一層寫（起來時那個 hook 點，或第一格） |
| **ctl 吃純文字，寫回來＝收到** | 落檔的 ctl 永遠寫得進去：E2 裡行程死了，`state.json` 還寫 running。今天靠 `state_flux.json` 的序號回音判斷收到沒。要做到「寫回來＝收到」，得有人當場回答；agent-fsm 唯一常駐、答得了的是 aos-loop |
| （同上） | 字表可以把兩層收在一起：stop、pause、resume（今天的 ctl），加 compact、clear、exit（今天的斜線信） |
| **status 一行一個「名稱: 值」** | 原料在第 2.6 節。`/status` 那封信今天做的事，就是 `status` 檔要做的事：改成讀檔之後，不必寄信、不佔對話、不用等這一輪答完 |
| **token 用量自己報** | 已經是這樣，差在今天要寄 `/usage` 才看得到。動兩支程式（第 2.5 節） |
| **活著走 unix socket，掛了走寄信** | 對 agent-fsm 兩條路會匯到同一處：socket 那頭是 aos-loop，但處理訊息的是下一拍才起的 idle 格，它只會讀 `queue/`。所以 aos-loop 收到 socket 訊息還是得落成一封信。好處：eca-aos 攤的那條邊緣（socket 那條不落檔，收到了還沒處理就死掉，那封就沒了）對 agent-fsm 不存在。socket 多給的是當場回一聲收到，以及不必等下一拍 |
| **問 daemon 信箱在哪** | agent-fsm 今天有三個收件處，意思都不同：`queue/` 是要它做事的話，直接進對話；`mailbox/` 是 agent 之間的信，不自動進對話；`think/reply/` 是它自己問別人的回信。標準位置的「信箱」對到哪一個要定（第 5 節第 2 題） |
| （同上） | 回信地址今天是 stack 裡的路徑，寫在寄出去的信上。身體路徑如果是 `/proc/<PID>/…`，回信在它死後就沒地方去，那次模型費白花（E4 第二列）。回信箱一定要開在 persist |
| **daemon 的 procs 夾連到各 proc 的目錄**；每個 proc 站在自己的身體裡 | 今天同一份定義的每一隻都站在同一個定義夾。E8：範本只有 `loop.json` 的 `"exec": "fsm.json"` 一處靠「站在定義夾」，改一行就能站在自己的夾裡跑完整個回合 |
| **kernel＝普通 aos proc**，自己記帳 | llm kernel 拿寄件人的 stack 路徑記額度。身體路徑一換，同一隻 agent 在 kernel 眼裡變成另一個人，額度重算。要改認名字或 persist 的路徑（第 5 節第 4 題） |
| **重起＝新的身體接回舊的 persist**（eca-aos 攤的） | E4 給了 agent-fsm 的最小清單，見下 |

**agent-fsm 要放 persist 的最小清單**（依 E4、E7 與第 2.2 節）：

| 什麼時候寫 | 哪些 | 少了會怎樣 |
|---|---|---|
| 直接開在 persist，不是「存」過去 | `queue/`、`mailbox/`、`think/reply/` | 寄的人把信改名進 `new/` 就當寄到了；kernel 那封還付過錢 |
| 每一格結束（今天就是） | `history.jsonl`、`letters.json`、`stage.txt`、`think/pending.txt`、`compact.json` | 少一步就是重問一次腦，或重跑一次工具 |
| 改的當下（很少改） | 覆蓋層五檔、`goal.json`、待辦、開著的任務、子 agent 的帳 | 悄悄換腦、忘了目標與子 |
| 幾分鐘一次，或停下時 | `observed.jsonl`、`history_removed.jsonl`、`handoff.md` | 只影響統計與回頭查 |
| 不放 | `think/request.json`、hook 小格、各種快取、`state.json` 裡的 pid | 都能重建 |

「多久存一次才不痛」：
- 使用者 11-24 說過「持久性/單點故障沒差，我們可以定期保存。」。對 agent-fsm，定期保存的代價是工具重跑：`shell` 工具的說明自己寫著不能重做（`py/tools/base/shell/_metainfo.json` 的 `idempotent: false`）。死在兩次保存之間，那段的工具會再跑一次。
- 每格都寫的成本很低：一回合約 25 次小檔寫入，除了 `letters.json` 都沒有 fsync。進度檔 `fs-tmpfs-1124` 量過寫入加 fsync 加改名，ext4 約 8 ms、tmpfs 約 0.02 ms；對比一次問腦幾秒到幾十秒，可以忽略。
- 所以對 agent-fsm，身體放記憶體省不到多少寫入。省得到的是閒著時每拍起行程與重讀（→ [11](11-閒置成本、時鐘與等待.md)）。

## 4. 邊緣狀況

1. **孤兒格**（E3）。新模型說身體跟著行程沒，但 agent-fsm 的身體是一棵樹。只殺得到樹根時，樹枝還在寫 persist。這棵樹不是一個行程群組：跑工具時分成四組（E9），殺 aos-loop 那一組只收得到它和 aos-fsm。樹根一死，樹枝的父行程就換人，順著父子關係也找不回來；今天 daemon 接回行程與清道夫是看 `/proc/<pid>/environ` 的 `AOS_STACK` 認的（第 2.4 節第十類）。誰來收、怎麼認 → [08](08-Linux機制實測.md)。
2. **同一封信進 history 兩次**（E6）。收信是四步：記進 `letters.json`、接進 history、收掉信、清 `letters.json`，不是一次完成。兩個夾分開之後，這四步不要橫跨兩個根。
3. **一檔一個 symlink 是陷阱**（第 2.3 節附）。`letters.json`、`state.json`、`compact.json`、`goal.json`、待辦、覆蓋層都是「寫暫存再改名」，壓縮時連 `history.jsonl` 也是。要用連結就連整個夾。
4. **三扇窗要嘛都留、要嘛都不留**（E7）。只留一部分會出現「舊的 stop 又生效」或「暫停悄悄沒了」。ctl 改成當場有人回答之後不需要序號，這組問題消失；但「暫停中的 agent 被重起，起來還暫不暫停」要定。今天是暫停。
5. **認「這是一個 proc 的 stack」靠的是身體類的檔**：aos-agent 認 `stderr.txt`，kernel 與 aos-comm 認 `state.json`。persist 裡沒有這兩個檔，這幾處會認不得。
6. **替別人建信箱**。`aos-agent say` 發現對方沒有 `queue/` 會幫它建；直接用 `aos-post send` 則報 `MailboxMissing`（做 E2 時撞到：agent 的第一格還沒跑，夾還不在）。信箱由誰建、什麼時候建要定；推論：daemon 給預設那塊 persist 時一起建最單純。
7. **覆蓋層不見不會報錯**（E4）。少了 `llm.json` 只是換一顆腦繼續答，沒有任何提醒。
8. **路徑已經寫進資料裡**：寄出去的信的 `reply_to` 與 `sender`、子 agent 帳的 `{name, stack}`、父給子的 `notify_box`、`think/brain_wait.json` 裡 kernel 的絕對路徑。persist 搬家之後這些是舊的。
9. **壓縮會整份重寫 history**。如果 persist 是「只抄新增的行」那種同步，壓縮那次要整份換。
10. **hook 小格裡兩個檔會影響重起後的行為**（提醒過哪些信、壓縮過沒）。現行分類是不帶走；放進身體就是每次重起再提醒一次舊信。
11. **格裡的寫入多半沒有 fsync**。history 往後加的那一行，行程死了不會丟，機器死了可能丟。今天就是這樣；persist 放 `/tmp` 的預設位置時更是整個跟著開機沒了。
12. **`stderr.txt` 是 daemon 開的檔**，不是 proc 自己寫的。歸身體的話，proc 死了之後「它為什麼死」那一行跟著沒了；今天表上的 reason 就是從這裡取的。

## 5. 要問使用者的

**1. agent-fsm 要不要改成一支常駐行程，讓對話真的在記憶體裡？**
- a. 不改。維持短命的格與落檔，只把檔分到身體與 persist 兩個夾，補上 `ctl`、`status`、`settings`。
- b. 改寫成常駐行程，格變成函數，對話在記憶體、定期存 persist。
- c. 兩種都留：a 先做，b 當另一種身體以後再寫。

推薦 c，先做 a。理由：a 改得最少、照樣能拿來驗介面；b 才字面符合使用者說的「/proc/<PID>就是他的stack」，也順手解掉每拍起行程，但等於重寫 agent-fsm。

**2. 活著時從 socket 送來的訊息，對 agent 是「直接進對話」還是「進信箱等它自己讀」？**
今天這是兩個不同的夾：`queue/`（say，進對話）與 `mailbox/`（信，不自動進對話）。
- a. 進信箱。活著與掛掉意思一樣，只差快慢；`queue/` 留給人直接說話。
- b. 進對話。那麼掛掉時走的寄信，跟活著時的意思就不一樣。
- c. 訊息自己帶種類，兩種都收。

推薦 a。理由：送的人不必先知道對方活著沒，兩條路才能互相替代。細節 → [20](20-送訊息兩條路的細節.md)。

**3. 要留的東西是「直接寫在 persist」還是「寫在身體、定期抄過去」？**
- a. 直接寫在 persist（上一節那張清單）。身體只放活的那一半。
- b. 全寫在身體，每回合結束抄一次。中途死掉，這一回合做過的要重來，工具會重跑；信今天是收進 history 就刪，得改成答完才刪。
- c. 全寫在身體，每幾分鐘抄一次。死掉丟幾分鐘，可能重跑好幾個回合的工具。

推薦 a。理由：agent-fsm 的格本來每次都從檔重讀，直接寫 persist 不多花什麼；b、c 省不到多少寫入，卻換來工具重跑。

**4. 身分改認什麼？** 今天拿 stack 路徑當「我是誰」（第 2.4 節第十類）。
- a. daemon 底下的名字那條路（`procs/<名>`）。
- b. persist 的路徑。
- c. 另發一個不變的代號，寫在 `settings`。

推薦 a。理由：跟使用者 11-25 說的錨點「離自己最近的頭上的那個daemon的stack」一致；kernel 的額度帳要從路徑改成名字。→ [06](06-路徑、環境變數與命名現況.md)、[15](15-權限過去的規劃對照新模型.md)。

**5. token 用量檔從什麼時候算起？**
- a. 這個身體這次活著以來，死了歸零（像 Linux 行程的計數）。
- b. 這隻 agent 有生以來（今天 `/usage` 是這個；累計要放 persist）。
- c. 兩組都給，各幾行。

推薦 c。理由：一行一個「名稱: 值」多幾行就有，上層 kernel 要哪一組都拿得到。

## 6. 沒查到、沒把握的

- **實測的條件比活樹單純**：直接跑、不掛 daemon、沒有時鐘、假腦。掛在 daemon 底下時 kill -9 之後 daemon 怎麼反應（自動重起、接回）沒測（→ [02](02-aos-daemon現況.md)）。
- **重複的 tool 結果真模型收不收**沒試。憑記憶：OpenAI 相容的端點多半會拒絕，未驗。
- **壓縮進行中被殺**的接續沒測，只讀了程式。
- **閒著一拍讀幾個檔**沒量到（這台沒有 strace）。
- **活樹的寫入頻率**只量了一隻閒著的 60 秒。
- **計數是 rg 的行數**，不是要改的處數。同一組指令連跑多次，有兩次個別類別多出一檔幾行，再跑又回到表上的數字；沒查出是哪個暫時的檔（當時有別的 agent 在同一棵工作樹做事）。
- **eca 的 stack、aos-loop 內部、daemon 的表**只在碰到 agent-fsm 的地方帶過（→ [04](04-eca身體與stack現況.md)、[01](01-aos-loop現況.md)、[02](02-aos-daemon現況.md)）。
- **`aos-idle`（閒置閘，工作樹裡還沒交）**掛上之後會多寫 `idle_gate.json` 與 `hookeds/on_clock_next.json`，只照它的 README 列進身體類，沒跑。
- **`board.json`、`gdb/`、`comm/`** 只確認在哪、誰寫，沒細看。
