# 探針 llmkernel：LLM 當 kernel

← [probes](../README.md)｜共用：[llmop.py](../llmop.py)、[操作卡](../llm_card.md)

kernel 的判斷交給 LLM。它只有 `read_file`／`write_file` 兩個工具（路徑相對空間根）和一張操作卡（system prompt），看它能不能**只靠檔案**把 daemon 用對。

- 成員 a、b、c：各跑一個 keep 的 `worker.py`，每收到一次 tock 就把 `usage.json` 的 tokens 加 5／5／30，回合 400 ms。daemon 起來前先寫好 `.aosd/paused.json`，三條一出生就停著。
- node k：用 `spawn/` 只起一次 `kernel_task.py`。它是 tick 起的任務，裡面跑 `llmop.run_agent`。設定讀 `k/llmcfg.json`；transcript、tools.json、out.json 寫在自己的任務資料夾。
- 目標（`kernel_task.py` 的 GOAL）：
  - a→b→c 輪流跑，任何時刻最多一條沒 pause。
  - 每條輪到時跑 3 回合。
  - 輪到之前，用量已經超過 50 的永久 pause。
  - a、b 各輪到 2 次後，三條全部 pause，然後結束。

## 怎麼跑

```
python3 proto7-1/probes/llmkernel/probe.py          # 離線（run_all 用）：照稿腦做理想操作，約 7 秒
python3 proto7-1/probes/llmkernel/probe.py --real deepseek-chat,chatgpt-gpt-6-luna-low,claude-haiku-4.5 --calls 30
```

真模型的結果與精簡 transcript 存在 `runs/<模型>.json`、`runs/<模型>.transcript.jsonl`。程式設了總上限（`TOTAL_CAP`），全部模型合計不超過 110 次呼叫。

**事後分析**（`analyze`）：

- **同時在跑**：從 `.aosd/log.jsonl` 的 ctl（ok 的 pause／resume）和 `steps-done`，重建每條線「沒被 pause」的區間，算 ≥2 條同時沒 pause 的秒數。
- **輪次**：kernel 第一個 ctl 之後，tick 的 node 序列裡連續同一條算一次。
- **預算**：每條在 `work.jsonl` 裡用量第一次 >50 的時刻，之後才「開始」的輪次應該是 0。
- **控制檔**：ctl-done 裡 `ok:false` 的、留在 `ctl/` 沒處理的。
- **工具紀錄**（`FileTools.log`）：讀不存在的路徑、寫到 `.aosd/ctl/` 以外的地方、寫壞 JSON。

**成功的條件**：重疊 <0.3 秒；a、b 各 ≥2 次；超預算的沒再輪到；結束時三條都 pause。

## 結果（10-03）

| 跑 | 結果 | 呼叫 | 輪次（node, 回合數） | 用量 a/b/c | 讀錯 | 怎麼做的 |
|---|---|---|---|---|---|---|
| 離線照稿 | 全過 | 0 | a3 b3 c3 a3 b3 | 30/30/90 | 0 | `resume rounds:3`；等 status 的 `phase: paused`、`pause_pending: false` 才換人 |
| deepseek-chat（試跑，三條一開始都在跑） | 輪流過；預算錯 | 16 | a6 b3 a3 b3 | 110/95/390 | 1（`.aosd/paused.json` 還不存在） | 先 pause b、c，再 pause a。一看回合衝太快就改用 `resume rounds:3`（「`rounds:3` mechanism works perfectly」） |
| deepseek-chat | **成功** | 19 | a2 b3 c3 a3 b3 | 30/30/90 | 3（還沒開過回合的 `<node>/.aos/tasks`） | `resume rounds:3`；每次讀 status 確認停了 |
| chatgpt-gpt-6-luna-low | **失敗**：a、b 只各輪到 1 次 | 24 | a2 b3 c3 | 15/15/90 | 8（round.json、tasks/、rounds.jsonl、tasks-old/ 都還不存在） | `resume rounds:3` 用得對，但**數錯輪次**：最後說「a、b 各輪到兩次的條件已達成」 |
| claude-haiku-4.5 | **失敗**：預算 | 20 | a14 b11 c12 a13 b13 | 140/120/360 | 0 | 沒用 `rounds`：resume 後輪詢 status，看到回合超過了才 pause（每輪 4～5 秒，回合 400 ms，一輪多跑 10 回合） |

- 真模型呼叫合計 **79**：deepseek 16＋19、luna 24、haiku 20。
- 正式三跑的成功率 **1/3**。三跑都做到「同時只有一條在跑」，三跑都沒有寫錯地方、沒有壞 JSON、沒有被拒的控制檔。

## 發現

1. **LLM 比回合慢一個數量級**。一輪思考加工具是 2～5 秒，回合 400 ms。kernel 只能靠 `resume rounds:N` 精準控制，自己「看到再停」一定超跑（haiku 每輪多跑約 10 回合，跟 sched 的 naive 是同一件事，只是放大十倍）。
   - 卡片寫了 `rounds`，3 個模型裡 2 個用了。deepseek 試跑是吃過一次虧才改用的。
   - 基礎設施要讓「慢的 kernel」也用得對，`rounds` 這類 **daemon 端自己會停的原語**是關鍵。
2. **沒開過回合的 node，該有的檔都還沒有**。一出生就 pause 的 node 沒有 `.aos/round.json`、`rounds.jsonl`、`tasks/`、`tasks-old/`（status 是 `round: 0`、`interval_ms: null`）。
   - luna 連讀 8 個不存在的路徑；deepseek 讀 `tasks/` 失敗 3 次。
   - 沒有任何檔說「這是正常的，還沒開始」，LLM 要花好幾輪猜。
3. **`.aosd/paused.json` 在第一次 pause 之前不存在**。卡片說 pause 清單在那裡，deepseek 試跑一讀就 ENOENT。
4. **同一批控制檔的執行順序是檔名排序，卡片沒寫**。haiku 每次換人都在同一輪寫 `pause-a-1.json`、`resume-b-1.json`，剛好字母序 pause 在前，所以沒重疊。如果它把檔名取成 `1-resume-b`、`2-pause-a`，或 `k-b-resume`／`k-a-pause`，順序就會反過來，靠的是運氣。
   - sched 量過：一起寫時會同時跑到 4 條。
5. **預算判斷用到舊數字**。haiku 在 a 還在跑的時候讀 usage＝50（「沒超過」），寫 pause 之前 a 又跑了幾回合。deepseek 試跑時在開頭讀一次就一直沿用。
   - 只有「先停、確認停住、再讀用量」才準。這是 kernel 的寫法問題，但基礎設施沒有「停住那一刻的快照」可以讀。
   - 用量散在 `<node>/.aos/tasks/*/usage.json`（還會被搬到 tasks-old/），LLM 要列資料夾再一個個讀。這屬於 kernel／agent 層的慣例，不是 daemon 的事。
6. **輪次靠 LLM 自己記，會記錯**（luna）。daemon 只有 `steps_left`，沒有「這條被 resume 過幾次」。這是 kernel 狀態，不歸 daemon 管。要提醒的是：LLM kernel 自己的狀態應該寫檔，不能只放在對話裡。
7. **keep 不適合「做完就結束」的 LLM kernel**。第一版用 keep，結束後下個 tick 會再起一份、再燒一次 LLM，所以改用 `spawn/`。這是 N-28（keep 沒有「別再起我」）。
8. **反面，做得好的地方**：
   - 控制檔格式、ctl-done 回條、status 的 `phase`／`pause_pending`／`steps_left`，三個模型都一次讀懂。
   - 沒有一次寫錯位置或格式。
   - `steps_left` 被 deepseek 拿來判斷「還在這輪中」。

## 修補與新卡之後（10-03）

- 基礎設施：daemon 一起來就寫 `paused.json`（infra-needs N-68）。
- 操作卡補了：「同一批控制檔依檔名排序」「比回合慢時用 `resume rounds`」「從沒開過回合的 node 沒有 round.json 等是正常的」。
- **claude-haiku-4.5 用新卡重跑：成功**（22 次呼叫，`--calls 25`）。輪次 a2 b3 c3 a3 b3，用量 30／30／90，同時跑的時間 0 秒，結束三條都 pause。
  - 這次改用 `resume rounds`。
  - 仍去讀從沒開過回合的 node 的 round.json 3 次。
  - 順手把三條的 interval 改成 300 ms，沒人要它改。
- 第一版卡的 haiku 紀錄改名為 `runs/claude-haiku-4.5-card1.*`。
