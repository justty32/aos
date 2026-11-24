# 11-24 晚：開著背景 Bash 時新信叫不醒 eca 的畫面（只查不改）

← [核心程式位子筆記](notes.md)｜eca-aos 信 01795508350523352210.26746.2827974 第 3 件｜progress `eca-bg-mail-1124`

## 結論

- **aos 這邊會一直等下去，不會退回貼字**：畫面開著時，新信走 Claude Code 的 cross-session 收件 socket。aos 投出去之後，要等 CLI 的 UserPromptSubmit hook 寫回執。
  - 等的期間，只要 `busy.txt` 在（CLI 正在跑一輪），aos 就不判它「不吃這個格式」，也不退回貼字。
  - 範本 `timeout_ms` 是 0，也就是不限時，所以一直等。
  - 第一批沒有回執之前，後面來的信一封都不加投，全部留在 queue。
- **卡住的開關在 CLI 那頭（推測，沒實測）**：CLI 開著背景 Bash 時，收到的 cross-session 訊息沒有當成新的一輪送進對話，要等背景任務結束、task-notification 進來開新一輪才一起讀。這跟觀察對得上：sleep 被 kill 或結束才醒，醒來一次吃下幾封。
  - 開 Agent 背景子 agent 時照收，表示 CLI 對這兩種背景的處理不同。這點 aos 看不到，要實測。
- **-p 模式會不會卡**：aos 讀 `claude -p` 的 stdout 一直讀到 EOF、再等行程結束，不是讀到 `result` 那行就收（`cli_print.run_claude_stream`）。
  - 所以如果 `claude -p` 會等背景 Bash 結束才退出，那一輪就跟著卡住；`timeout_ms` 是 0 的話就沒有上限。
  - claude -p 到底會不會等，我沒實測（要叫模型）。
- **kb 收到過期的「有 2 封新信」**：mail_notify 是「看到新信就往 queue 寄一則通知」，寄出去就不再管。
  - 通知在 queue 裡排隊的期間（那隻在忙、或像上面那樣卡住），agent 可能已經在別的回合用 mailbox_read 把信讀掉了。
  - 通知送到時沒有人再對一次信箱，所以變成過期通知。這不是 bug 造成的錯數，是投遞時沒有重驗。

## 1. 新信到 eca 畫面的路

1. **mail_notify**（`py/tools/agent/mail_notify/_entry`，on_clock hook）：`aos-mailbox peek -j` 看到沒通知過的信名，就往 agent 的 `queue/` 寄一則 `{"role": "user", "content": "[aos] new_mail: N new letters from …"}`，信名記進 `notified.json`。
2. **aos-eca-turn**（每拍）：從 queue 拿這批信，交給 `cli_ask.ask`。
   - 先拿小格的 lock；拿不到時，yield 模式這拍就退讓，信留 cur/。
   - 畫面開著（`cell.alive()`）就走 `live`。
3. **`live` → `live_a2a`**（`cli_ask.py` 37～85 行）：小格的 `a2a.json` 記著 CLI 的收件 socket，就把整批包成 `<cross-session-message from="aos-<id>">` 寫進去，不看畫面忙不忙（11-13 使用者「馬上送」）。之後每 0.2 秒看一次：
   - 回執（`a2a_acks.jsonl`，CLI 的 **UserPromptSubmit** hook 看到信封就寫一行）全到，而且之後有一輪講完（**Stop** hook 寫 `turns.jsonl`），就算答完。
   - 一則回執都沒有、而且 `busy.txt` 不在（CLI 閒著）滿 30 秒（`ACK_GRACE_S`），就認定「這版不吃這個格式」：`a2a.json` 改成 off、這次改成貼字進 tmux。
   - **一則回執都沒有、但 `busy.txt` 在**：`idle_since` 歸零，繼續等，沒有上限，因為範本 `cli.json` 的 `timeout_ms` 是 0。
   - 加投後來的信（`more.take()`）只在第一批**有回執之後**才做。
4. **`busy.txt`**（`cli_hook.py` 287、318 行）：UserPromptSubmit 寫、Stop 刪。

所以「判斷畫面忙」只看兩樣：lock，加上 `busy.txt`；「投遞」是寫 socket 之後等 hook 的回執。

## 2. 背景 Bash 時卡在哪（推測，有兩種可能；都要 CLI 實測才分得出）

- **A：CLI 收著不送**。回合結束、Stop 已經刪了 busy.txt，畫面看起來閒著。aos 寫進 socket，CLI 收下，但有背景 Bash 在跑時，不把它當成新一輪的 prompt，所以沒有 UserPromptSubmit、也沒有回執。
  - 照第 1 節，30 秒後 aos 會 mark_off、改成貼字進 tmux。貼字理應叫得醒，但觀察是一直沒醒。
  - 所以單靠 A 解釋不了兩小時的空窗，除非貼字在那個狀態下也被 CLI 收著。
- **B：Stop 沒有刪掉 busy.txt**。開背景 Bash 的那一輪，CLI 在背景任務結束前不算這一輪結束：沒有 Stop，或 Stop 之後馬上又有 UserPromptSubmit。
  - busy.txt 一直在，aos 照第 1 節第 3 點的那一格無限等，也不退回貼字，後面的信全部排著。
  - 背景任務一結束，task-notification 開一輪，CLI 才讀到 socket 裡收著的信封、寫回執，一次答。
  - B 跟觀察完全對得上，我判斷比較可能。
- **為什麼 Agent 背景子 agent 照收**：子 agent 在 CLI 裡是另一種「背景」，主對話的回合有正常結束（Stop），所以 busy.txt 被刪，A、B 都不成立。這是推的，沒驗。

**要分出 A 或 B**，看 main 的 claude 小格裡這幾個檔的時間就知道。這次我只被准看 history.jsonl，所以沒看。另外，13:29～15:45 那段已經在 16:05 被 /compact 搬到 history_removed.jsonl，history.jsonl 裡只剩摘要；摘要記了兩段空窗：13:29～15:25，以及 15:25 到 15:44 被 kb kill 為止。
- 13:29 之後 `busy.txt` 有沒有一直在（它的 mtime）。B＝在。
- `a2a.json` 有沒有變成 `{"off": "no receipt 30 s …"}`。A＝會變。
- `a2a_acks.jsonl` 在 13:30～15:25 有沒有行。兩種都應該沒有。
- main 的 `stderr.txt` 有沒有 `no receipt 30 s after delivering … typing into the screen instead`。A＝有。

## 3. -p 模式

- `cli_print.run_claude_stream`：`for line in p.stdout` 讀到 EOF，`p.wait()`，期限是 `timeout_ms`（0＝不限）。拿到 `result` 那行不提早收。
- 所以 `claude -p` 只要在背景 Bash 結束前不退出，或背景行程還握著 claude 的 stdout，那一輪就卡到 sleep 結束；這段時間 lock 一直被佔，新信全排著。
- claude -p 會不會這樣，沒實測，要一次真的模型呼叫：例如 haiku，一個「`sleep 60` 開背景就結束」的題目，量 `claude -p` 幾秒退出。

## 4. kb 收到的過期通知

- mail_notify 寄出通知時只記信名，不把信名寫進通知本身。通知在 queue 排著的時候沒有人再看信箱。
- 在 eca 上，這隻在忙（lock 佔著、busy.txt、或第 2 節的卡住）時，通知最多排很久。期間 agent 自己用 mailbox_read 讀掉了那兩封（mailbox_read 會刪），通知才送到，就是「有 2 封新信」，但信箱是空的。
- kb 那則是不是這樣，我沒看 kb 的 stack（不准）；照程式只有這一條路會出過期通知。

## 5. 修法選項（只列、不選）

| # | 做什麼 | 改哪 | 代價 |
|---|---|---|---|
| 1 | `live_a2a` 給「沒回執」也設上限：投了之後 N 分鐘都沒回執，**不管 busy.txt**，就改貼字或把信退回 queue、記 warning（busy.txt 卡住也救得回來） | `py/aos/agentlib/cli_ask.py` | 貼字在 CLI 收著不送的狀態（A）下可能一樣進不去；要配 3 實測 |
| 2 | 範本 `timeout_ms` 不用 0，給一個大值（例 2 小時），卡住至少會報 `ReplyMissing`、信留著、上層看得到 | 三份 eca 範本 cli.json（範本位子） | 真的長回合會被誤殺；`-p` 也一起受影響 |
| 3 | 先實測分出 A／B 與 -p 的行為（我做；要叫一次模型，或准我看 main 小格那幾個檔） | 不改程式 | 要使用者點頭花一點模型額度，或給讀檔許可 |
| 4 | 過期通知：mail_notify 把信名放進通知（例 body 的 `aos.new_mail: [信名]`），aos-eca-turn／fsm 的 idle 送出前再對一次信箱，全讀掉了就丟，部分讀掉就改寫封數 | `mail_notify/_entry`、`apps/eca`、`apps/agent_fsm/idle.py` | 兩邊都要改；通知變成不是純文字 |
| 5 | 說明：eca 的知識庫寫「不要用 Claude Code 的背景 Bash 排定時，要定時用 `clock_register`」（main 已經自己記成 memory 了） | 知識庫（kb 位子） | 只防不治 |
| 6 | 看得到延後：aos-agent ctl ls -l／state 顯示「投了 N 分鐘沒回執、等 busy.txt」 | `apps/agent/ctl/ls.py`、`state.py` | 只讓人看得到，不解決 |

建議的順序（給 eca-aos 參考，不是決定）：3 先做（分出原因），再 1＋5；4 跟它獨立，可以一起排。

## 6. 附：畫面 socket 搬家題（已另回 PROGRESS）

- socket 名＝`sha256(小格的 realpath)[:16]`（`cli_cell.tty_socket`）。搬家後舊路徑是 symlink，realpath 變了，雜湊就變了；新的 loop 找不到舊畫面。
- 舊畫面若還活著，loop 會當成沒畫面、起 `claude -p --resume` 接同一段對話，兩支撞在一起。
- 16:19 查的現況：eca-aos 的舊 socket `767fb7812c4b71e2` 沒有 server，新的 `9db3a6cf7b61f650` 在跑；repo-aos 底下其他各隻，用舊路徑算的 socket 一個都沒活著。
- 以後搬家前要先關畫面，或讓 `tty_socket` 也認搬家前的路徑（例如小格裡記一份開畫面時的 socket 路徑）。
