# astra-kernel 的 fable 設計稿原樣：先用 kernel_gate 把門掛在 astra 身上、sol 的起停請求寄 astra、腦請求走隊問腦站、sol 做完「按門鈴」；目標是前面加規則站讓 astra 只看例外

← [astra-kernel-plan](../astra-kernel-plan.md)｜fable 只讀了 [01-備料](01-備料.md)。opus 讀程式核對後跟這份不同的地方見 [03-opus細化](03-opus細化.md) 第二節；下面原樣保留。

---

**一句話結論**：先用現成的 `kernel_gate` 把門掛在 astra 身上（不改 aos 程式），sol 的起停睡醒請求寄給 astra、腦請求走一個隊問腦站；sol 做完「按門鈴」叫 astra，astra 不再一直 say／listen 盯人。跑順後再在前面加一個規則站，讓 astra 只看例外。

```
使用者／隊長(opus)
   │ 起 astra、給圖紙；人的保底 aos-daemon-ctl 直寄 daemon
   ▼
astra（agent 兼門：kernel_gate）──自己的 add/rm 直寄──▶ ws daemon（手）
   ▲ 起停睡醒請求（sol 的 AOS_KERNEL                      ▲
   │ ＝astra 的 hooks/kernel_gate/requests）              │ astra pass 後機器轉寄
 sol-1  sol-2 …                                           │
   │ 問腦（sol 的 AOS_LLM_KERNEL＝隊問腦站）
   ▼
隊問腦站 llm-t1（規則、每隻 sol 額度、帳）─llm_forward─▶ llm-gpt（總額度）─▶ proxy
astra 自己問腦：直寄 llm-gpt，不經隊站
```

我只讀了備料。下面標「待驗」的，是備料沒寫明、我推出來的，要在階段 0 先確認。

## 1. 形狀

| 選項 | 做法 | 好 | 壞 |
|---|---|---|---|
| 甲 agent 兼門 | `kernel_gate` 掛在 astra 身上：規則先判，放行的留給 astra 表態 | 現成、活樹已有、不改程式 | astra 在回合中或睡著時沒人判；每封放行的信都花 astra 一輪腦 |
| 乙 子 daemon 當手 | 起一台子 daemon 管 sol，astra 當門 | sol 與外面隔開，父只看子活著沒 | 活樹現在不能起第二台 daemon（T33），今晚做不了 |
| 丙 兩層 | 前面一個機器規則站（loop proc，一直醒著），平常的信直接放給 daemon，例外才轉給 astra 的 `kernel_gate` | astra 忙也不卡；省 astra 的腦 | 多一個站要顧。規則站能不能當 loop proc 管掛 proc 請求，待驗 |

**推薦：先甲、目標丙。** 甲今晚就能跑，丙要先驗一件事才知道走不走得通。丙合使用者「雜事不要花 astra」的話：例外用 `after_verdict` hook（判完後跑的小程式，可替單封信指定下一站）轉給 astra。

哪種請求經過誰：

- **sol 的起停睡醒**（要幫手、自己睡／醒／停）：經 astra。甲是每封都經；丙是只有例外經。
- **sol 的問腦**：不經 astra 本人。`kernel_gate` 只管掛 proc，問腦那包也沒有「留著等人表態」的口，所以由隊問腦站照規則判。
- **astra 自己的請求**（add／rm sol、自己問腦）：不經自己的門，直寄 daemon 與 `llm-gpt`。這樣不會自己判自己。
- **人的 `aos-daemon-ctl`**：直寄 daemon，保底不變。

## 2. sol 怎麼掛

- **起 sol**：astra 照舊用 `subagent add`，多帶兩個 `envs`。`AOS_KERNEL` 指到 astra 的 `<stack>/hooks/kernel_gate/requests`，`AOS_LLM_KERNEL` 指到隊問腦站。名冊仍在 astra 的 stack。
- **誰准**：先過規則（`allowed` 只列 `sol-*` 這隊的名字、`max_running`）。規則拒的不問 astra；規則放的留給 astra pass／refuse；pass 後規則再判一次，所以 astra 放不過規則。
- **排程**：proc 格數用 `max_running`（建議 3，連同 `count_daemon`）；`queue` 先關，滿了就拒（排隊配寄件人 30 秒期限容易全部過期）；腦的格數沿用 astra 1、sol 2。
- **派工**：工單是隊夾裡的檔 `H/teams/t1/orders/<單號>.json`（內容、可動的檔、驗收法、狀態）。astra add sol 後只 `say` 一句「做哪張單」，就結束自己這一輪。
- **回報（按門鈴）**：
  1. sol 做完把結果寫進工單的回報欄。
  2. sol 用 `aos-agent ctl` 對自己寄「停」的請求，`--timeout-s 600`。
  3. 這封信會被留在 astra 的門上，astra 收到 `kernel_hold` 通知，等於被叫醒。
  4. astra 讀回報、驗收。合格就 pass（sol 停下，astra 再 rm）；不合格就 refuse，再 `say` 退件理由。

  這繞過 T3（子做完不通知母）、T24（ask 卡住母）、T28（一句閒話被當回報）。sol 有沒有工具寄這封信，待驗。
- **備援**：astra 用 `clock_register` 每幾分鐘叫醒自己，巡一次工單狀態。

## 3. 跟現在 subagent 做法比

| 項目 | 現在（say／listen） | astra-kernel |
|---|---|---|
| astra 的腦花費 | 高，一直盯（是 sol 的 2～8 倍） | 預期降：只在門鈴與巡邏時動。要真腦才量得出 |
| 回報 | 靠 listen，T3／T24／T28 都撞過 | 門鈴＋工單檔，有憑有據 |
| sol 想要幫手 | 做不到或各走各的 | 寄給 astra 判，有規則擋 |
| sol 的腦額度 | 混在 `teams/t1` 一格 | 隊站分每隻 sol（要等活樹換執行檔） |
| astra 忙時 | sol 只是沒人理 | 請求過期（`SlotMissing`），要有重試規矩 |
| astra 死掉 | sol 繼續做，沒人收 | 一樣，再加請求全過期；門死了沒人知道 |
| 換指揮（改 sol 當門） | 要重寫流程 | 只是把 `kernel_gate` 換到另一隻身上 |
| 複雜度 | 低 | 多一個門、一個隊站、兩個環境值 |
| 防繞過 | 不適用 | 環境變數只是指路，要靠守門與沙箱擋 |

## 4. 權限與額度

**astra 能做**：add／say／state／stop／rm 自己隊的 sol；對留著的請求 pass／refuse；寫隊夾（工單）；選配：改隊問腦站裡每隻 sol 的額度（見裁題 4）。

**astra 不能做**：改門的規則、改 `llm-gpt` 的總額度；改 sol 的工具／腦／system／hook（沿用現在的守門）；用 `self` 包。因此 `kernel_gate` 要由隊長寫進新定義 `gpt-lead-k`，不讓 astra 自己掛。「定義裡直接列這個工具」行不行，待驗。

**腦額度分兩層**：上層 `llm-gpt` 管全隊一天的總數，只有使用者與隊長能改，這是總閘；下層隊站 `llm-t1` 分給每隻 sol（例：每隻 150 次／天），`ledger.jsonl` 記帳；astra 自己的腦直走上層，另列一格；用完設 `spent: refuse`（設成 wait 會掛到期限外）。

**防 astra 放過頭**：規則在 astra 前後各判一次；`max_subagents` 由隊長定（建議 2～3）；上層總額度 astra 碰不到；隊長收 DONE 後照舊重驗。

**防 sol 繞過 astra**：sol 的守門不放行 `aos-daemon-ctl`；sol 的沙箱不讓它寫 daemon 的 ctl 信箱與 `llm-gpt` 的信箱（現在的沙箱擋不擋得到，待驗）；sol 不給 `self` 包，改不了自己的環境值；工單寫明「被拒就是決定，不重試、不改名」。

kernel 不驗寄件人（#8），所以這些都是「擋路」不是「驗身」，試驗時要記下來。

## 5. 失敗與卡住

| 狀況 | 處理法 |
|---|---|
| astra 在回合中，請求沒人判 | sol 寄請求一律 `--timeout-s 600`。astra 的規矩：短回合、手上有 sol 時不用長 listen／ask。`SlotMissing` 是「沒人應門」不是拒絕，准 sol 隔一分鐘重寄，最多 2 次，再不行寫進工單狀態後停手。根治靠丙 |
| astra 睡著 | 規矩：手上有 sol 時不准睡，只能閒著等。要睡先收完 sol |
| astra 死掉 | daemon 只標 stopped。由隊長（opus）每輪看 astra 的 phase 當看門人；死了由隊長 start 或用 `aos-daemon-ctl` 收 sol。sol 的腦不靠 astra，手上的單可做完並寫進工單，不會丟 |
| sol 卡住 | astra 巡邏看 `subagent state` 與工單狀態，超過工單寫的時限就 stop、rm、重派。腦請求有 600 秒逾時 |
| 腦掛掉 | sol 收到 `EndpointFailed` 就把狀態寫進工單後停。astra 的腦掛了等同 astra 死掉，走上一條 |
| 自己判自己 | astra 的 `AOS_KERNEL` 永遠不設（直走 daemon）。`allowed` 不列 astra 自己的名字，sol 也就不能叫門去停 astra |
| 額度用完 | `BudgetMissing` 是決定。sol 寫「卡額度」進工單、按門鈴停。astra 只能在隊站內挪，挪不動就報隊長。上層只有使用者能加 |
| 隊問腦站死掉 | sol 收 `LlmKernelMissing`，同「腦掛掉」。隊站是 loop proc，由 daemon 重起 |

## 6. 怎麼試

只新增活樹的夾，不改 aos 程式：新定義 `H/defs/gpt-lead-k`、`gpt-worker-k`；新隊站夾 `H/kernels/llm-t1`（照 `llm-team` 範本）；把 `llm-gpt` 掛回去。唯一可能要動程式的是丙的規則站，放到階段 4，驗過才決定。

| 階段 | 做什麼 | 腦 | 一句驗收 |
|---|---|---|---|
| 0 接線 | 新定義掛得上 `kernel_gate`；`on` 印出信箱；sol 的兩個環境值帶得進去 | 假腦 | sol 寄一封「停自己」，信出現在 astra 的門上 |
| 1 門的機關 | pass、refuse、規則拒、過期、名字不在白名單、sol 直寄 daemon 被擋、隊站額度用完 | 假腦 | 七種情況的回信都對，且都回到寄件的 sol |
| 2 真跑小單 | 1 astra＋2 sol，跑 G 那張假工單，再跑一張真單 | 真腦 | 單子做完，且 astra 的次數與 token 低於 G 的紀錄（29 次／37.5 萬；31 次／52 萬） |
| 3 分額度、換指揮 | 活樹換執行檔後，隊站分每隻 sol 的額度；把門改掛在一隻 sol-high 身上跑同一張單 | 真腦 | 帳上分得出每隻 sol；sol 當門也能收完單 |
| 4（選做）規則站 | 前面加機器規則站，例外才到 astra | 假腦→真腦 | astra 在回合中時，平常的請求照樣通過 |

**假腦驗得到**：信的路、規則、留著與表態、期限、額度拒絕、繞路被擋。**一定要真腦**：astra 判得合不合理；astra 守不守「短回合、不長 listen」；sol 懂不懂按門鈴；花費到底有沒有降。

## 7. 預見會撞到的 aos 問題（只記不改）

1. 門在回合中或睡著時 `on_clock` 不跑，請求過期（#49、eca-as-kernel 第五節）。
2. 進來的請求叫不醒睡著的門。
3. `kernel_gate` 每封放行的信都留給 agent，沒有「規則放行就直接過」的檔位，花 astra 的腦。
4. 問腦那包沒有 `held` 口，agent 沒法對單封腦請求表態。
5. `kernel_gate` 不在任何範本、要 `self_tools add`，但隊長定義不給 `self` 包，兩邊打架。
6. 門死了沒人知道，留著的請求下落不明。
7. kernel 不驗寄件人，`from` 自報（#8）；環境變數只指路、擋不了直寄。
8. 活樹執行檔沒換前，所有 sol 的腦寄件人都是同一個工作區，隊站分不出誰。
9. `llm_forward` 轉寄時拿掉 `AOS_STACK`，上層看不到是哪隻 sol，上層只能管隊的總數。
10. 用「請求停自己」當回報是借用，aos 沒有正式的「子通知母」（#19、#40）。
11. `SlotMissing` 分不出「門忙」還是「門死」。
12. sol 做完不自己退（#17）；母 rm 不連子（T25）；同名再 add 接舊 history（T26）。
13. `llm_http` 沒讀逾時、沒重試（#23）；沒有總 token 上限與金額（#18、T13）。
14. 活樹不能起第二台 daemon（T33），乙案整個試不了。
15. 規則站能不能當 loop proc 管掛 proc 請求，備料沒有例子。

## 8. 要使用者裁的題

1. **形狀**：甲先跑、目標丙（推薦）／直接做丙／等能起子 daemon 再做乙。
2. **誰起 sol**：astra 自己 add、直寄 daemon（推薦，不會自己判自己）／隊長 add、astra 只當門。
3. **回報方式**：按門鈴為主、巡邏備援（推薦）／只巡邏／照舊 listen。
4. **astra 能不能改隊站裡每隻 sol 的額度**：能，上層總閘不給碰（推薦）／不能，全由隊長寫死。
5. **`kernel_gate` 怎麼掛上 astra**：隊長寫進新定義（推薦）／臨時給 astra `self` 包自己掛。
6. **沒人應門時 sol 重寄幾次**：2 次、隔一分鐘（推薦）／不重寄直接停手／一直等。
7. **階段 3 要不要等活樹換執行檔**：等（推薦，否則分不出每隻 sol）／先用隊總額度頂著跑。
8. **換 sol 當門的時機**：階段 2 花費降了再試（推薦）／階段 2 就兩種都跑來比。
