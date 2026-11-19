# 窗口：htop 與 aos-gdb 是讀 kernel 紀錄的兩扇窗——htop 的精神搬過來是什麼、CLI 與網頁、三個方向的草圖、gdb 怎麼看一隻的資源、跟「兩者解耦合」對不對得上

← [README](README.md)｜上一份：[04-全域指標](04-全域指標-耦合度與掌控度.md)｜原型：[原型-aos-top.html](原型-aos-top.html)

## 先講結論

- **窗口不能寫死欄位**：它顯示的是「每台 kernel 自己宣告它記了什麼」，再加 daemon 表那幾欄當共通底。原型頁就是這樣做的：欄位從假資料裡的 `declares` 長出來，勾選要看哪些。
- **分工**：htop 看全部、淺、即時、可排序可摺；gdb 看一隻（或它底下一棵）、深、看歷史到每一次問腦與工具呼叫。htop 每列的「下手」裡有一個是「進 aos-gdb」。
- **gdb 向 kernel 要資源，兩種做法**：`a.look.usage()` 直接讀 kernel 宣告的帳檔、只挑自己這隻（符合「讀檔的收進 a.look」）；或寄一封問句信給 kernel（照今天 `{"procs_state_path": true}` 那個先例）。後者是 a.xxx 的第三種東西——既不是 aos-agent 的薄殼、也不是讀檔——要不要開這個口子，列在下面。
- **gdb→kernel 單向讀，不破壞「兩者解耦合」**：kernel、aos-agent、daemon 都不必知道 gdb。會破的是反方向：如果有人寫的 kernel 策略去讀 gdb 的字條（例如「被扣住時不算等待時間」），kernel 就認得 gdb 了。
- **誰彙總**：三個選項都不碰 daemon——窗口自己讀檔、一列量測 proc 定期寫總表、kernel 自己的策略順手寫。刷新頻率分兩檔：狀態類 1～2 秒，量測類（耦合度、git、du）幾分鐘到一天。

## htop 的精神搬過來

| htop | aos 對應 |
|---|---|
| 一眼看全部 | 每列一個 proc（daemon 表的一列），共通欄＋各 kernel 宣告的欄 |
| 上方條狀儀表 | 今天的額度條（剩多少、幾點重置）、今天花多少（有價目表才有錢）、幾隻在等你、幾隻卡住、全域指標小條 |
| 排序 | 依任何宣告的欄（token、排隊、重起次數、多久沒看） |
| 樹狀（F5） | daemon 巢狀（根 → 隊 daemon → 隊員）＋子 agent 掛在生它的那隻下面。子樹合計**不能**用 stack 路徑前綴加總（Argon A17，核過）：`subagent` 工具是用 `ctl add` 把子 agent 掛上 daemon，stack 由父指定，不一定在父的路徑底下；父子關係要讀父的 `tools/subagent/subagents.json`（記 `{name, stack}`） |
| 即時跳動 | 狀態類每 1～2 秒重讀；ledger 只讀新長出來的尾巴 |
| 對一列下手（kill、renice） | stop、pause／resume、sleep／wake、看信箱、看它最後說什麼、對它說一句、進 aos-gdb；**renice 的對應**＝改那台 kernel 的策略輸入（把它加進角色名單、調它的額度），不是窗口自己有特權 |
| F2 設定欄 | 勾選要看哪台 kernel 的哪些欄 |

列也可以不是 proc：可以是「一條線」（一個隊長帶一群隊員，跨好幾個 daemon），那是使用者腦中的單位。窗口排在 kernel 後面，這題先不問；原型用 proc＋樹＋篩選先頂著，他看了覺得不對再說。

## CLI 與網頁

| | CLI（`aos-top`） | 網頁 |
|---|---|---|
| 適合 | ssh 進去、快速看一眼、在 tmux 一格常駐 | 圖多、細節摺疊、手機看；使用者偏好這種 |
| 下手 | 按鍵直接跑指令（照 htop） | 先只顯示指令、按了才跑（避免誤點）；網頁要能跑指令就得有個本機小伺服器 |
| 資料怎麼來 | 都是讀 json；誰負責讀見下 | 同左 |

資料來源三選（都不碰 daemon；體檢說 daemon 是單一管理員，別加重活）：

1. **窗口自己讀**：每次刷新讀 `procs_state.json`、各 kernel 宣告的檔、各 stack 的尾巴。沒有新行程；隻數多時讀得慢。
2. **一列量測 proc**：掛在 daemon 表上（像 `_sweeper`），定期寫一份總表 json，窗口只讀它。多一個行程，但窗口很輕，也順便是全域指標的量測者。
3. **kernel 的策略順手寫**：記錄型 hook 每封信更新彙總（實測的 `tally.json`）。最即時，但只有經過那台的。

## 三個方向的草圖

### A. 一張大表（htop 本體）

```
 額度 llm [|||||||||||||||||       ] 67%  重置 00:00   今天 $3.20(假價目)   等你 3   卡住 1
 耦合度 0.72 ▲(昨天量)   掌控度：最久沒看 95 分（kf-captain，之後 41 個 commit）
 kernel 偏向：pat（planner）← 耦合度 0.72 > 0.60［策略 coupling-planner，使用者自訂］
 ─────────────────────────────────────────────────────────────────────────────
  名字            狀態     格     token(今天)  快取  排隊   重起  沒看   最後一句
 ▾ .stack         running  -
   ├ ann          running  think    120k       61%   0.4s   0    12m   "已改好 README…"
   ├ pat ★planner running  wait      88k       70%   0.1s   0     3m   "拆成三刀…"
   ├▾ kf (隊)     running  -
   │  ├ kf-captain running idle      40k        -     -     0    95m   "等使用者裁…"
   │  ├ kf-sol-2  stuck    act       12k        -     -     0    95m   (stderr) Timeout…
   │  └ kf-rev ⓔ  running  -        (不經 llm kernel) $1.10 等值
   └ dex          running  act       30k       58%   0.0s   0     8m   "改 a.py 第 3 處…"
 F2 欄  F5 樹  F6 排序  F9 下手
```

一眼看全部，但欄一多就是「一面牆」——最容易做成沒人看的儀表板。Argon 補一刀：各台 kernel 各宣告各的欄、eca 又走另一套，大表會滿是 `-`，按那欄排序時一大半列沒數字。它建議大表只留每列都有的欄，自訂欄移進「點開這列」；這跟「欄位來自 kernel 宣告」不衝突，只是預設放哪，原型保留勾選、預設少開幾欄。

### B. 以錢為主軸

```
 今天 $3.20／預算 $10   照這速度 21:40 用完    快取命中 64%（昨天 71% ▼）
 ┌ 誰在燒（今天） ──────────────────────┐  ┌ 燒的速度（每 10 分） ───────┐
 │ bob-sub-1  ███████████  $1.40  ▲急升  │  │  ▁▂▂▃▅▇█▇▅               │
 │ kf-rev ⓔ   ███████      $1.10 等值   │  └──────────────────────────┘
 │ ann        ███          $0.40        │   不經 llm kernel 的：kf-rev、gus（eca）
 └──────────────────────────────────────┘
```

回答「錢去哪了」最快；但要先有價目表，而且 eca 的「等值金額」不是帳單，混在一起會誤導。Argon 說得更重：訂閱制卡的是 5 小時滾動窗、API 卡的是 token 窗，兩者不能相加、也不會同時用完，「照這速度 21:40 用完」是假的。沒有真帳單之前，這個方向只能顯示「各個額度窗剩幾成、幾點重置」，不能顯示錢。

### C. 以「哪裡需要你」為主軸

```
 現在有 3 件要你、2 件可以等
 ① kf-captain 等你裁一題，已等 95 分           [看題]
 ② kf-sol-2 卡住 12 分（act 格，最後一行 Timeout）[看它最後說什麼] [stop]
 ③ bob 你 95 分沒看，之後它改了 41 個 commit     [看它做了什麼]
 ── 可以等 ──
 ④ 未 push 7 個 commit   ⑤ bob-sub-1 花費急升
```

最貼近「董事長看全景」，也最不像 htop；排序規則（什麼算急）本身又是一條要能自訂的策略。

原型做了 A 和 C 兩頁，頂上的儀表與「kernel 偏向誰」卡兩頁共用，B 的幾個數字放進儀表。

## aos-gdb 看資源

今天 gdb 的通則：`a.xxx`＝`aos-agent xxx` 的薄殼；讀 stack 檔的收進 `a.look`（where、history、observed、request、queue、stderr、file）。

| 做法 | 長相 | 合不合通則 | 代價 |
|---|---|---|---|
| G1. 讀檔 | `a.look.usage()`：讀 kernel 宣告的帳檔（ledger 等），只挑 `sender` 是這隻 stack 的；`a.look.usage(tree=True)` 照 `subagents.json` 加總子樹 | 合：讀檔收進 a.look | 要知道 kernel 在哪（`observed.jsonl` 的 self 行有 `llm_kernel` 路徑）；各台 kernel 宣告的格式要一致才讀得懂 |
| G2. 問 kernel | `a.kernel.usage()` 寄 `{"usage_of": <stack>}` 給 `$AOS_LLM_KERNEL`，kernel（或它的策略）回這隻的紀錄；中間站照今天的規矩把不認得的鍵轉下去 | 不合現有兩類：是新的第三類 | kernel 要多一種「被問」的事件（[03](03-自訂kernel-形式與最小實測.md) 末節「可能缺的」）；kernel 慢或長回合時問不到（knowledge 已寫 kernel_gate 會讓 3 秒問句失敗） |
| G3. 經 aos-agent | 先有 `aos-agent usage`，`a.usage()` 是它的薄殼 | 合：a.xxx 薄殼 | aos-agent 要認得 kernel 的帳（不是認得 gdb，所以不違反解耦） |

跟「兩者解耦合」核對：

- **gdb 去讀或去問 kernel**：單向，kernel 不知道問的是 gdb（任何寄件人都能問），aos-agent、daemon 不變 → 不破壞。
- **kernel 策略讀 gdb 的字條**（例：扣住期間不算排隊時間、不扣額度）→ kernel 就認得 gdb，**會破**。這是寫策略的人可能自然想做的事，列出來。
- **htop 顯示「被 gdb 扣住」**：htop 不是 aos-agent 也不是 daemon，字面上沒違反；但使用者那句是「表上不要看得出來」，htop 也是一張表——照原話不顯示。初稿原型有這一欄，Argon 指出後已拿掉。
- **反過來的車禍**（Argon A19，核過一半）：gdb 扣住一隻除錯十分鐘，daemon 與 kernel 因為解耦不知道。若那列設了 `stuck_after_ms`（範本的 agent 列沒設，`_clock`、`_sweeper` 才有）且開了 `restart_on_stuck`，daemon 會把現場重起掉；自訂 kernel 策略若用「多久沒問腦」當訊號（例如閒著就降級），也會把扣著的那隻當成閒著。這是解耦的代價，不是 bug；寫策略的人要知道。
- **G2 的問句信會撞到自訂 hook**：問「ann 用了多少」的信也是一封信，會經過 `before_verdict`；記錄型 hook 若不分辨，就把問句也記成一次問腦，或因為缺 `request` 欄而失敗（失敗又連坐整輪）。
- **G3 讓 aos-agent 認得 kernel 的帳檔格式**：不違反「不認得 gdb」，但自訂 kernel 換了記法，aos-agent 就讀不懂；所以三種做法都繞不開「kernel 宣告自己記了什麼」那一步。
