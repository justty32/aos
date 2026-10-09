# 長任務實跑（r4 L 隊）：AI 用 wf 管自己，12 封信、中途 SIGKILL

← [play](../README.md)｜意圖卡 [longtask](../../intents/longtask.md)｜計畫 [r4 §2](../../plan-2026-10-09-r4.md)｜場景與腳本 [up/examples/longtask](../../../modules/up/examples/longtask/README.md)

2026-10-09 18:52～19:00，L 隊（Opus）寫。用的是 B5 進 main 後的版本（35c368ea），真 AI `chatgpt-gpt-6-sol-high`，所有呼叫都經 llmcall，三次實跑合計 **65 次呼叫**（上限 100）。程式一行都沒改。

## 一句話結論

正常跑或只有 brain 被殺時，**一封 12 節週報做了 13 回合，12 封信共 29 回合，2.5 分鐘全部結案**：STATE 每回合一行、open 做完歸零、PROGRESS 2 封、NEEDS-USER 2 封、DONE 10 封、被殺後接上沒有重問。**但 brain 連同它正在問 AI 的子程序一起被殺時，這封信會永遠卡住**：心跳照跳、status 看起來一切正常，後面 11 封信也全被擋住（見問題 1）。

## 怎麼跑的

12 封信放在 [letters/](../../../modules/up/examples/longtask/README.md)（`letters/*.txt`），開頭一次全寄出：
- 01：12 節週報，每回合寫一節，第 13 回合交全文。材料裡有一處故意對不上（I5 說「1000 項全綠」，FL 說「有 3 個偶發紅」）。
- 02～10：小件，其中 4 封指定分 2～3 回合。
- 11：「照你前面交的週報第 5 節寫三句話」，用來測 brain 換一封信之後還記不記得前一封。
- 12：故意缺 RV 的人數，B5 又有兩個對不上的數字，用來逼出 NEEDS-USER。

跑三次，差別只在 SIGKILL 怎麼殺：

| 跑 | 怎麼殺 | 結果 | 證據 |
|---|---|---|---|
| 1 | 01 做到第 7 回合、brain 正在問 AI 時，brain 和 llmcall 子程序一起 SIGKILL | **卡死**：第 7 回合那筆停在 intent、沒有 raw。llmcall 照規則不重送，brain 每回合都印「AI 還沒確定回沒回，下回合再看同一筆」，跑了 80 幾個心跳回合沒動，最後人工停掉 | [run1-kill-inflight/](run1-kill-inflight/) |
| 2 | 同一時間點，只殺 brain，llmcall 子程序留著 | 3 秒後孤兒 llmcall 拿到回覆、寫好回條；新的 brain 直接讀回條往下做。全程 146.6 秒 | [run2-kill-brain/](run2-kill-brain/) |
| 3 | 等 brain 沒在問 AI 時才殺（第 7 回合以後第一次抓到空檔，已經是第 12 回合） | 照常接上。全程 156.6 秒 | [run3-kill-idle/](run3-kill-idle/) |

每個資料夾裡有：`events.log`（驅動腳本紀錄）、`timeline.jsonl`（每秒取樣，只記有變化的：回合、open 行數、SESSION-LOG 和 journal 的大小、STATE 行數、回條數、you 信箱）、`status.log`（每 60 秒一次 `aos7-up status`）、`kill.json`、`calls.csv`（每次呼叫的 prompt／completion token）、`replies.md`（所有回信全文）、`summary.json`，以及 `house.tar.gz`（整個房子，包含 node 的 wf／brain／llmcall／compact／skills）。`summary.json` 和 `calls.csv` 由 `analyze.py` 從 tar 重算出來。

## 燈號（R3 §2，逐條）

下面的數字都以跑 2 為主，跑 3 幾乎一樣，有差才另外寫。

### 目標 1：wf 當腦

| 燈號 | 結果 | 數字／依據 |
|---|---|---|
| 長任務 20～40 回合 | 🟢 | 共 29 回合有問 AI（01 號 13 回合，其他 11 封 16 回合）。總共 29 次呼叫，沒有多問 |
| 每回合 STATE 一行 | 🟢 | STATE.md 29 行，重複 0 行（跑 3 被殺後也是 0） |
| SESSION-LOG open 做完歸零 | 🟢（有附註） | `timeline.jsonl` 的 open 一直是 0 或 1，最後是 0。附註：brain 同時只開「正在做的那封」，還在排隊的 11 封不會出現在 SESSION-LOG |
| PROGRESS ≥2 | 🟢 | 01 號第 5、第 10 回合各寄一封 |
| NEEDS-USER 1（樣本缺資料） | 🟢 | 12 號：「請確認 RV 人數，以及 B5 交付項數該用 9 還是 6」，已知的幾隊也先算好了。另外 11 號也回了 NEEDS-USER，原因是 brain 跨信不記得（見問題 4） |
| DONE 1 | 🟢 | 01 號交出 12 節齊全的全文，第 4 節和第 9 節照實標了「待確認」（那處故意的矛盾）。其他 9 封也都是 DONE；09 號算錢 $4.56，我核過是對的 |
| 中途 SIGKILL 接續不重問 | 🟡 | 跑 2、跑 3：🟢（被殺的那筆 raw 只有 1 份，STATE 沒重複）。跑 1：🔴 卡死 |
| 旁觀者只看 status 與信箱就知道進度 | 🟡 | Haiku 正常跑時打 **5/10**：做到第幾節、哪兩件要你決定都看得出來；看不出總共幾件、做到幾成。卡死時打 **4/10**：只看出「心跳在跳，內容沒變」，看不出卡住。原文見兩份 `bystander-haiku.md` |

### 目標 2：compact／memory／skill

| 燈號 | 結果 | 數字／依據 |
|---|---|---|
| compact 觸發 ≥1、open 不丟 | 🟡 | 每次跑各觸發 1 次（原因是超過 max_bytes），journal 14 則摘成 1 則加最近 3 則。open 沒丟，但這條其實是自動成立的：journal 本來就沒有 open，SESSION-LOG 又沒被摘。**門檻是我改的**：預設 16384 bytes、保留 10 則，在這個長度的任務裡永遠不會觸發（journal 一回合只長約 300 bytes，29 回合才 6.5 KB），所以 run.py 把門檻寫成 6000、保留 3 則。跑 1 開跑後 20 秒我才發現，手動把 12000 改成 6000，`events.log` 有記 |
| 檔長降 ≥60% | 🔴 | 6500→2930（降 55%）；跑 3 是 6388→2861（55%）。而且摘要本身沒有內容（見問題 3） |
| skill pick ≥1 有紀錄 | 🟢（品質🔴） | `skills/.pick/log.jsonl` 有 17 筆，全部走本機、不花錢。但挑得不對：週報和數字表挑到 aos-test，FAQ、會議紀錄、英文摘要挑到 aos-inbox。分多回合做的信每封記兩筆（見問題 5） |
| 每回合 prompt 經 `$ref` 折疊、token 不隨回合數線性長 | 🟡 | 依 B5 代定**不用 `$ref`**（AI 沒有工具可以展開）。token 有上限：01 號的 prompt 從第 1 回合 4115 長到第 10 回合 4888，之後停在 4876～4898，因為「最近 8 回合」的軌跡有上限。所有呼叫平均 4166，其中約 1620 是 proxy 自己加的 Codex 系統提示。cached 只命中 9856／120815 |

### aos7-metrics 四個指標（跑 2／跑 3）

```text
bob：1 件工作｜每件用 127274 token｜同時最多 1 個在問模型｜花 145.107 秒｜重試 28 次
bob：1 件工作｜每件用 127736 token｜同時最多 1 個在問模型｜花 155.368 秒｜重試 28 次
跑 1：27339 token｜22.597 秒｜重試 6 次｜1 次還沒結帳（卡住的第 7 回合，預留 1,000,000 一直沒放掉）
```

「1 件」「重試 28」是讀錯了：metrics 把 12 封信、29 個回合都當成同一張需求，每多一回合就算一次重試（見問題 6）。比較可信的讀法是：29 次呼叫、平均每次約 4.4k token、每回合 3～12 秒（交全文那回合 12 秒）、全程 2.5 分鐘、真正的重試 0 次。

## 發現的問題（回報頂層，都沒有修）

1. **〔嚴重，brain＋llmcall〕送出請求後被殺，就永遠卡住。** 跑 1 的 brain 和 llmcall 在「intent 已記、raw 還沒到」之間一起被 SIGKILL。llmcall 照 spec 不重送（「無 raw 的 intent 不重送、留 R」），每次都退出 3；brain 把 3 當成「下回合再看」（`aos7_up_brain.py` 的 `Later`），沒有次數上限。結果是這封信永遠不結案，FIFO 後面的 11 封也全被擋住，預留的 1,000,000 token 一直不放；grant 是 1000 萬，殺 10 次就用完了。brain 大部分時間都在等 AI（跑 3 從第 7 回合等到第 12 回合才抓到空檔），所以隨機殺下去最可能就是殺在這裡；子程序會不會一起死，則看是怎麼殺的（整組殺、OOM、關機）。現在唯一的出路是 `aos7-llmcall adopt` 補一份遲到的回覆，可是這份回覆根本拿不到。**要頂層決定**：brain 對同一筆連續 N 回合退 3 要怎麼辦？(a) 回 NEEDS-USER／BLOCKED，附上怎麼辦；或 (b) 換一個新的 call id 重問，接受可能多付一次錢。
2. **〔人類面〕status 看不出卡住，也看不出總量。** 卡死時 status 照樣印「心跳：活著，第 N 下」，停在哪那行一直不變，「AI 還沒確定」只寫在 `.aos/tasks/brain/out.log` 裡。「信：未讀 12 封（要回 12 封）」說的是 bob 的待辦，旁觀者卻讀成要 you 回的信。status 也不算有幾封 NEEDS-USER 在等人，結案以後還顯示「還有 0 件事沒做完」。另外跑 3 中途兩次出現「體檢 有問題」，15 秒後自己變回 OK，原因沒查（事後 `aos7-wfnode check` 是 OK，只有 STATE.md 29 行的 BIGLIST 警告）。
3. **〔compact〕jsonl 的本機摘要沒有內容。** 摘要那一則是把每行原始 JSON 的前 40 字串起來，內容全是 `{"by": "brain", "re": "you-…", "s`，看不出做了什麼。這也讓檔長只降 55%。而且 journal 根本不在 brain 的提示裡，所以 compact 對 AI 的記憶和 token 都沒有影響。STATE.md 每回合加一行，又不在 compact 的檔案清單裡，會一直長下去。
4. **〔目標 1 的缺口〕brain 換一封信就忘了前一封。** 提示裡只有 AGENTS、SESSION-LOG、NEXT-SESSION、這封信，再加上這封信自己的軌跡。一封信做完，它的成果就不會再出現在提示裡。11 號信 AI 老實回「請貼上第 5 節原文」，這個行為是對的，但「用 wf 記事」目前只在同一封信裡有效。01 號能交出 12 節齊全的全文，靠的是每回合都重附整封信的材料，不是靠記憶。
5. **〔skills〕本機挑技能不準，而且記兩次。** 只靠關鍵字，「回信」「整理」都會被挑到 aos-inbox，名字裡有「測試」就挑到 aos-test。另外 `request()` 和 `step_on()` 在第 1 回合各呼叫一次 `pick_skill`，所以分多回合做的信每封記兩筆。
6. **〔metrics〕不認得 brain 的多回合。** logical 全是 `up/brain`，所以 12 封信算成 1 件；同一封信的第 2 回合以後（`-s<k>`）又被算成重試。用它來量 brain 會把「件數」和「重試」量錯。

## 給 R3／之後重跑

場景、驅動和分析腳本都留在 `modules/up/examples/longtask/`，假 AI 跑一次約 30 秒，真 AI 約 29 次呼叫、2.5 分鐘。要重現問題 1 用 `--kill-mode tree`，`--stuck-minutes` 會在卡住後自己停下來。
