# 自訂 kernel：今天自訂「記什麼」「怎麼分配」要寫什麼、放哪；最小實測（兩支 hook、零改程式就做到）與卡住的地方；七種自訂形式比一比

← [README](README.md)｜上一份：[02-記什麼-資源清單](02-記什麼-資源清單.md)｜下一份：[04-全域指標](04-全域指標-耦合度與掌控度.md)

## 先講結論

- **今天就能自訂，而且不用改程式**：在 llm kernel 的 `kernel.json` 掛兩支 hook，一支「記」（每封回信時按寄件人累計次數與 token）、一支「分配」（耦合度超過門檻時，角色是 planner 的寄件人的信改成 high），假腦實跑兩支都照做了。使用者的比喻「灌 kernel＝用現有的 kernel 定義，掛個 aos proc 上去」今天就成立：kernel 本來就是一份定義夾。
- **卡住的不是「能不能做」，是做了之後沒人看得懂、也不一定有效**：
  1. 記下來的東西沒有「宣告」——我記的 `tally.json` 是自己發明的形狀，htop、gdb 不知道它在、不知道欄位是什麼意思。
  2. 改優先級只在排隊時有效——格子沒滿時 high 跟 normal 一樣立刻跑；實測就看不出差別。
  3. 認人靠 `sender` 自報——角色名單以路徑當 key，誰都能冒充，搬家也會錯位。
  4. 只看得到經過它的信——工具呼叫、cpu、eca-claude 的花費都看不到。
  5. 沒有「每輪一次」的時機——三個 hook 都是「每封信」觸發；要讀全域指標、算彙總，只能搭在信上。
- **自訂形式至少七種**（json 旋鈕、hook、寫一包、當 kernel 的 agent、kernel.py 再編譯，加上 Argon 補的「前面串一站策略站」「策略 proc 算表、kernel 查表」），表達力與代價各不同；**跟 agent 那套比，kernel 今天停在「手寫定義夾＋hook」，還沒有對應 agent.py／編譯／std 的那一層**。要不要長出那一層是方向題（第 2 題），這裡只攤。

## 今天自訂一個 kernel 要寫什麼、放哪

| 自訂點 | 放哪 | 能做什麼 | 例 |
|---|---|---|---|
| kernel 定義夾 | 任何夾；`aos-exec --stack <stack> <定義夾>` 掛上 | 選範本、決定它是 daemon 的身體還是一列 proc | `templates/kernel/llm-kernel`、`llm-team`、`procs-kernel`、`daemon-kernel` |
| `kernel.json` 旋鈕 | 定義夾裡 | 格數、保留格、aging、三層額度與窗、端點表、下一站 | `slots`、`reserved`、`aging_cycles`、`budget`、`next` |
| hook | `kernel.json` 的 `hooks`，handler 是任何程式（經 `aos-exec` 跑） | `before_verdict` 改信的 body（含 `priority`）、`after_verdict` 改判決（pass／refuse／hold）與下一站、`before_reply` 看並改回信（含 `usage`） | 部門配額用完回 `BudgetMissing` 的 sh 範例（kernel_llm README） |
| 另寫一包 | Python，交給框架骨架 `round.run(pack)` | 整套收信、判、排、轉的規則都自己寫 | 問腦那一包 `kernel_llm` 就是這樣寫的 |
| 一隻當 kernel 的 agent | `kernel_gate` 工具，站掛在它的 on_clock | 規則放行的先 hold，agent（腦）逐封點頭 | knowledge `aos/kernel.json` 的 gate 節 |
| 串站 | 每站的 `next` 或 `after_verdict` 指定 | 多台 kernel 疊起來，各管一段 | agent → 隊 kernel → 主 kernel → daemon |

宣告的先例也有：`templates/kernel/llm-kernel/interfaces.json` 宣告了 `aos-ledger`（ledger 是給人看的）；agent 的 stack 也用 `interfaces.json` 的 `aos-observed` 宣告自己的觀察帳，`measure` 工具照宣告去讀。

## 最小實測

在乾淨複本（`308443eaf`）抄出的假腦樹上，只改樹裡的 `llms/def/kernel.json` 與它旁邊放的檔；程式一行沒動。腳本與輸出在 `~/.aos/scratch/aos-htop-1119/exp/`。

```
llms/def/
  kernel.json      ← 加 "hooks": {"prio": before_verdict, "rec": before_reply（純通知）}
  hooks/prio       ← 「分配」：讀 roles.json、signals.json、rule.json，條件成立就把 body.priority 改 high
  hooks/rec        ← 「記」：回信時按 sender 累計 calls、tokens、last_at，寫進自己小格的 tally.json
  hooks/roles.json   {"<樹>/.stack/procs/pat": "planner"}
  hooks/signals.json {"coupling": 0.72, "measured_at": "…"}   ← 全域指標，實驗裡手寫
```

再掛一隻 `pat`（ann 的複本）當 planner，對 ann、pat 各說一句：

- 兩隻都收到假腦回答。
- `prio` 的決定紀錄（它自己寫的 `decisions.jsonl`）：pat 的兩封都是 `{"level": "high", "why": "coupling 0.72 > 0.60, role planner"}`，ann 的兩封 `null`（不動）。
- `rec` 的 `tally.json`：pat、ann 各 `calls: 2`、`tokens: 0`（假腦）。
- llm kernel 每輪照常退 0，ledger 照記。
- 順便看到：hook 的 `event.json` 留在 kernel stack 的 `hooks/<名>/` 裡，內容是**整份 prompt**（system 文字、對話）——記錄型 hook 天生看得到所有內容。這是代價不是好處（Argon A17）：每封信都把可能上百 KB 的對話寫一次磁碟，問腦頻繁時寫入放大，對話內容也留在 kernel 的 stack 裡。

## 卡在哪（照實寫，不設計解法）

| 卡點 | 實際情形 | 後果 |
|---|---|---|
| 沒有「我記了什麼」的宣告 | `tally.json` 的形狀我自己定；`interfaces.json` 有宣告慣例但只說「這是哪個檔」，沒說欄位、單位 | htop／gdb 只能寫死欄位，違反「記什麼要可自訂」 |
| 優先級只在擠的時候算數 | 實測格子沒滿，high 跟 normal 一樣馬上掛；`aging_cycles` 預設 3 格就升一級，別人等久也會追上 | 「規劃 agent 優先」平常看不出效果，擠的時候才有 |
| 認人靠自報 | `sender` 是信封上寄件人自己寫的路徑（體檢 P15） | 角色規則可被冒充；路徑當 key，整棵搬家就錯位（`budget.senders` 早就有這個提醒） |
| 只看得到經過的 | 工具呼叫在 agent 自己行程裡；eca-claude 不寄問腦信 | 這些要別人報給 kernel，或 kernel 去讀別人的檔 |
| 沒有每輪一次的時機 | 框架骨架只有 `before_verdict`、`after_verdict`、`before_reply` 三個事件 | 讀全域指標、彙總只能搭在信上；沒信就不更新 |
| hook 失敗會連坐 | 預設 `on_error: stop`：一支 hook 壞，這輪退 1，問腦全停 | 跟體檢 P5（used.json 壞了全停）同一類風險 |
| 每封多一個行程 | handler 每封經 `aos-exec` 起一次 | kernel 身體每 300 ms 一輪，信多時會拖慢 |
| 分配旋鈕分散 | 問腦先後在 llm kernel；誰能起在框架站；**誰先醒沒有任何 kernel 管** | 「行動優先級」要看是哪一種行動（見 04） |

## 自訂形式

| 形式 | 記什麼怎麼寫 | 怎麼分配怎麼寫 | 表達力 | 代價 | 今天 |
|---|---|---|---|---|---|
| A. json 旋鈕 | kernel.json 多幾個欄（例：`record: ["tokens", "cached"]`） | 多幾種規則鍵（例：`budget.senders` 那樣的表） | 低：只能選 kernel 作者預先做好的 | 每多一種都要改 kernel 程式 | 有（只有額度與排隊那些） |
| B. hook | 一支程式，看信、寫自己的檔 | 一支程式，改 body／判決 | 中高：任何程式 | 每封一行程；失敗連坐；沒宣告 | 有，實測過 |
| C. 寫一包 | Python 包裡想記什麼記什麼 | 自己寫 order／admit | 全部 | 等於寫一台新 kernel；要懂骨架的五個函式 | 有（kernel_llm 就是） |
| D. 當 kernel 的 agent | 讓腦看信、自己記筆記 | 腦逐封判（hold 後點頭） | 最彈性、能講道理 | 慢、花 token、會被信裡的話騙；agent 長回合時整站停（knowledge gate 節） | 有（kernel_gate） |
| E. kernel.py 再編譯 | 一支 `kernel.py` 宣告 RECORD（欄位、單位、從哪個事件取） | 宣告 POLICY（函式或 hook）、KNOBS | 高，而且**宣告天生就在**（編譯時順手寫進 interfaces.json） | 又一套編譯器；跟 `agent_spec` 共用多少要想 | 沒有 |

Argon 補的兩種（核過，列進來）：

| 形式 | 記什麼 | 怎麼分配 | 表達力 | 代價 | 今天 |
|---|---|---|---|---|---|
| F. 前面串一站策略站 | 那站自己記 | 那站改 priority、扣隊額度，再轉 `next` | 中高；主 kernel 不用動 | 多一站多一輪延遲；**跟使用者說「不太對」的「專門記帳的 kernel 站」長得很像**——差別只在它也握分配權，算不算他要的，由他看 | 有（`llm-team` 就是這個形狀） |
| G. 策略 proc 算表、kernel 查表 | 一列量測 proc 定期讀指標與帳、算好每個寄件人的權重或額度寫成 json | kernel 每輪只查表（像今天的 `budget.senders`） | 中；規則在 proc 裡隨便寫，kernel 端只認表 | 表是幾分鐘前算的（延遲）；表的格式要先定 | 半有：查表那半就是 `budget.senders`，只是今天只能放上限 |

G 正好繞開 B 的兩個卡點（每封一行程、沒有每輪時機），代價是延遲。B 和 G 怎麼選，跟「優先要多即時」綁在一起，放進第 2 題。

跟 agent 那套對一下：

| | agent | kernel 今天 |
|---|---|---|
| 原始碼 | `agent.py`（SYSTEM／TOOLS／LLM／FSM） | 沒有；直接手寫定義夾 |
| 編譯 | `agent.py` → 定義夾 | 沒有 |
| std | `lib/packs`、`lib/tools`、`templates/*` | `templates/kernel/*` 四個範本、框架骨架 |
| 執行期改自己 | `self_*` 工具 | 沒有；改 kernel.json 下一輪就生效（每輪新行程） |
| 宣告給別人讀 | `interfaces.json`（aos-observed 等） | `interfaces.json`（aos-ledger），只到「哪個檔」 |

所以 E 是「讓 kernel 也走 agent 那條路」，B＋宣告慣例是「維持手寫定義夾，只補一個讓人讀得懂的宣告」。兩條都說得通，由他定（第 2 題）。

## 內建只剩機制

不管走哪種形式，aos 內建的東西可以只剩兩類，其餘都是「某人寫的策略」，範本只當例子：

- **kernel 看得到哪些事件**：今天是「每封信的三個時機」。想得到可能缺的：每輪一次、proc 起來／停了、有人來問紀錄（像今天 `{"procs_state_path": true}` 那種問句信）。
- **kernel 能動哪些旋鈕**：今天是 priority（先後）、slots／reserved（格子）、budget（額度、拒或等）、verdict（放、拒、扣著等表態）、next（轉哪一站）、limits 夾值（起 proc 時）。想得到可能缺的：喚醒先後、給某隻的額度比例。

這兩張清單長什麼樣是 kernel 架構的事，屬於使用者的大方向；本線只列出來，不往下設計。
