# proto8/cmd/aos-clock-register — 時鐘登記表：每 N 個 cycle 寄一封信

← [cmd](../README.md)｜時鐘本體：[aos-clock](../aos-clock/README.md)｜紀錄：[thinking 11-10 clock-letters](../../thinking/2026-11/10/clock-letters/README.md)

使用者 11-10 晚「時鐘這塊幫我改成寄信好了，不要用跑任意aos函數。」「指令是aos-clock-register嗎？」：時鐘檔旁邊放一張**登記表**，每格寫「每幾個 cycle、寄到哪個箱子、寄什麼字」。`aos-clock` 每走一格，新數字除得盡的格就各寄一封（用 `aos-post send`）。最常用的是**定時叫醒一隻 agent**：箱子寫它的 `queue/`，信就當一則 user 訊息進它的對話。

```
aos-clock-register [-c CLOCK] add --every N --box BOX [--by WHO] [--replace] NAME TEXT...|-
aos-clock-register [-c CLOCK] rm NAME
aos-clock-register [-c CLOCK] ls [-j]
# aos-clock register … 跟 aos-clock-register … 完全一樣（11-10 深夜；時鐘檔真叫 register 的寫 ./register）
```

例：

```sh
aos-clock-register add --every 10 --box stacks/root/procs/ann/queue ann-wake "Check data/ for new files."
aos-clock-register ls          # ann-wake	10	procs/ann/queue	Check data/ for new files.
aos-clock-register rm ann-wake
```

給腦的是 [`clock_register`](../../lib/agent/clock_register/_tooldef.json)（純包裝；`box` 不給＝叫我的那隻自己的 queue），agent-fsm、eca-claude 兩個範本預設登記。

<details><summary>細節</summary>

- **時鐘檔**：`-c/--clock`（子命令前後都收，前後不同＝`ArgumentsBad`）＞ `$AOS_CLOCK`（根 `.env` 給的，agent 都繼承）；都沒有＝`ClockMissing`。
- **登記表**＝時鐘檔同資料夾的 `<時鐘檔名>_register.json`（根 daemon 的鐘是 `<根 stack>/clock` → `<根 stack>/clock_register.json`）。形狀：
  `{"description": …, "check_every": 100（可省）, "letters": {NAME: {"every": 10, "box": "procs/ann/queue", "text": "…", "by": "…"}}}`。
  - `box` 是字串＝路徑：相對路徑**從登記表所在資料夾**算；也可以手寫指示詞物件（`{"$env": "X", "$path": "/queue"}`，用 `aos-directive` 解，cwd＝登記表資料夾），同 tools／hooks 的寫法。
  - `add --box` 相對路徑從 cwd 算；存進表時，跟登記表同一個頂層資料夾＝存相對登記表資料夾（整棵搬走還對），否則存絕對（同 aos-post 的 `reply_to`）。
  - `by`＝誰登記的，給 `ls`／人看（預設 `$AOS_WS`＞`$AOS_STACK`＞`$AOS_CF`＞cwd；工具填 agent 名字）。
  - 搬家：登記表跟時鐘檔一起帶走（two-machines 分類 G094）；暫存 `.clock_register.json.PID` 不帶（G095）。
- **什麼時候寄**：`aos-clock` 寫好新數字 n 之後，`n % every == 0` 的格各寄一封。**對齊整數倍**（every 10＝cycle 10、20、30…），不是從登記那刻起算。
- **信的 body**（一份形狀兩邊都收）：
  `{"role": "user", "content": "TEXT (clock cycle N)", "from": "clock", "status": "PROGRESS", "title": "clock cycle N: NAME", "what": "TEXT", "cycle": N, "register": "NAME"}`
  - fsm 的 idle 格、`aos-eca-turn` 只看 `role`＋`content`，當一則 user 訊息收進 history（其他鍵不管）；
  - `aos-mailbox` 讀 `from`／`status`／`title`／`what`，其餘照印。信封是 aos-post 的（`sender`、`sent_at`、有 `AOS_CLOCK` 時 `sent_at_cycles`）。
- **時鐘不會被拖垮**：寄不到（箱子不在、不可寫）、表壞、某格形狀不對＝`aos-clock: warning: …` 一行（壞格跳過、其他格照寄），時鐘照樣走、退 0；每封最多等 5 秒。**沒有登記表＝跟以前完全一樣**。
- **誰能改**：寫得到登記表就能 add／rm（不另外擋）。寄不到的格每到那格就 warning 一次，`ls` 看得到、誰都能 `rm`。
- **時鐘自己清**（11-10 深夜，使用者「時鐘本身會每隔一定的cycle檢查自身。」）：新數字 % `check_every`（登記表頂層鍵，正整數，沒寫或壞＝100）== 0 時，箱子資料夾**已經不在**的格從表裡拿掉，各印一行 `aos-clock: warning: clock register: removed entry NAME (added by BY): its box BOX no longer exists`。資料夾還在、只是暫時寄不到（不是信箱、不可寫）的不算；指示詞解不開的判不了、不動。寫回前重讀一次表、只拿掉那幾格；寫不回只 warning。`check_every` 手改登記表設；`add`／`rm` 會照留。
- `add` 時箱子還不是信箱（沒有 `tmp/ new/ cur/`）＝warning、照加。同名＝`EntryExists`（`--replace` 換掉）；`rm` 沒有那格＝`EntryMissing`；表讀不懂＝`RegisterBad`；寫不了＝`WriteFailed`。錯一律 `aos-clock-register: error: 代號 原因`、退 1。
- 同時兩個人改表不管（後寫的整份蓋過先寫的）。
- 測試：`python3 cmd/aos-clock-register/tests/test_clock_register.py`、`python3 lib/agent/clock_register/tests/test_clock_register_tool.py`。

</details>
