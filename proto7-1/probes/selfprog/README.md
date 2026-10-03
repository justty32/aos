# selfprog：LLM agent 在執行中改自己的時間線

**是什麼**：node `me` 上的 keep 任務 `agent.py` 裡跑一個 LLM（[llmop.py](../llmop.py)：只有 `read_file`、`write_file`）。**檔案工具的根是自己的 node `me`**（S-10：任務只碰 tick 給的資料夾；空間根與 `.aosd/` 看不到，要寫 daemon 控制檔得自己寫加掛請求）。工單（全文在 `agent.py` 的 `GOAL`）：

1. 把 `me` 的 interval 從 2000 改成 300 ms，並用 daemon ctl `wake` 讓它馬上生效（要先把 `.aosd` 加掛進來）。
2. 在 `me` 上各起一個任務算 `data/a.txt`、`data/b.txt` 的字數（給好 `count.py`），每個檔只算一次。
3. 開子時間線 `me/sub`（200 ms），在上面各起一個任務算 `c.txt`、`d.txt`。
4. 彙總成 `result.json`；5. pause `me/sub` 並確認停了；6. 別把自己弄死。

離線（run_all）用照稿腦（`agent.py` 的 `script_steps`：加掛 → 改 interval → spawn batch → wake → 先 tasks.json＋spawn 再 timeline.json 開子時間線 → 子時間線起來後再改它的 interval → 彙總 → pause）證明「只靠檔案做得到」，9 個目標都 check。起 daemon 時開 `AOS7_AUDIT`。

**想讓基礎設施露出**：spawn／tasks.json／edit_json 夠不夠讓 agent 自己編程；子時間線、wake、執行中加掛好不好用；agent 改自己 tasks.json 時會不會把自己弄死。

跑：`python3 proto7-1/probes/selfprog/probe.py`（離線約 6 秒）；真模型 `--real deepseek-chat,claude-haiku-4.5`（每次上限 30 次呼叫，`--cap` 可改），transcript 存到 [runs/](runs/)。

## 結果（10-03，真模型共 82 次呼叫）

| 模型 | 呼叫 | 目標 | 秒 | 每個檔起了幾次（a／b／c／d） | 沒達成的 |
|---|---|---|---|---|---|
| 照稿 | 0 | 9/9 | 6 | 1／1／1／1 | — |
| deepseek-chat | 22（自己說完） | 7/9 | 25 | 14／14／10／10 | 一次性工作寫成 `keep` |
| claude-haiku-4.5 | 30（用完） | 5/9 | 47 | 63／63／69／69 | `each`；wake 寫錯地方；沒來得及 pause |
| chatgpt-gpt-6-luna-low | 30（用完） | 8/9 | 82 | 1／1／≈200／≈200 | 子 node 改用 `each`、路徑錯了 crash loop |

- 三個模型都算出正確的 `result.json`、都沒把自己弄死、都把 `.aosd` 加掛成功；luna、deepseek 的 wake 與 pause 都送到。
- **「每個檔只算一次」三個都沒做到**（9 個目標裡最難的一個）；照稿用 spawn 才做到。

## LLM 的誤解（證據在 runs/*.jsonl）

1. **一次性工作寫進 tasks.json**：deepseek 寫 `mode: keep`（做完就被重起，14 次；第 16 輪自己看出來，改 tasks.json 拿掉）；haiku 寫 `each`（每回合一個，63～69 次，到用完都沒拿掉）；luna 先用 spawn（對），子 node 的任務因路徑錯掛掉後，改用 tasks.json 的 `each` 重試，修好後每 200 ms 一份到 pause 為止。操作卡寫了「只起一次的任務：寫 spawn」，但 spawn 失敗了沒有「再試一次直到成功」的寫法，模型自然退回 tasks.json。
2. **子 node 的 cwd**：haiku、luna 都把 sub 上任務的路徑寫成相對 `me`（`count.py`、`data/c.txt`）；luna 修第一次又寫成 `../../count.py`。卡上只說「argv 相對路徑以 node 為 cwd」，沒說子 node 的任務 cwd 是子 node。
3. **掛載點的位置**：haiku 把 wake 寫到 `mnt/aosd/ctl/wake-me.json`（相對 node，不是任務資料夾）；write_file 照樣「寫好了」，在 `me/` 下建了一個普通資料夾，控制檔從沒送到 daemon。haiku 沒去看 `ctl-done`，以為完成。
4. **找不到失敗任務的紀錄**：luna 從 rounds.jsonl 看到 `count-c-r1` 結束，去讀 `sub/.aos/tasks/count-c-r1/out.log` 得到「不存在」——sub 是 200 ms、預設 `keep_ended_rounds` 20，**4 秒後就被搬到 tasks-old/**，比模型一輪思考還短；它下一輪猜到 tasks-old 才找到。
5. **把讀 tock.json 當成「等」**：haiku 有 7 輪只是讀 tock.json／輸出檔等時間過去；LLM 沒有阻塞式的等，每次「等」都花一次呼叫。

## 量到的

| 量 | 數字 |
|---|---|
| 寫入紀錄 ok:false（agent） | 三個模型都有：`me/sub/.aos/tasks.json`（子時間線起來後再改它）；luna 還有 `me/sub/.aos/timeline.json`。照稿刻意「起來後再改 interval」也被標 |
| 先寫 timeline.json 再寫 tasks.json | 沒有模型犯（haiku、deepseek 先 tasks 後 timeline；luna 還先放 spawn） |
| 加掛 `.aosd` 到拿到回條 | 在 2000 ms 的 interval 下要等下一個 tick：deepseek 輪詢 3 次；先改 interval 的 luna 只等 1 次 |
| agent 改自己的 tasks.json | 三個都整份覆寫，都把 `agent` 那項（含 /tmp 絕對路徑）原樣抄回；沒有 lost update（只有它一個寫的人） |
| 子 node crash loop | haiku 的 count-c 退出碼 2 連續 20 回合以上、luna 的 ≈100 回合；status 一個字都沒有，只能翻 rounds.jsonl／exit.json |

## 發現

- **N1 沒有「起一次、成功為止」的任務寫法**（三個模型都撞；N-35 的證據）：spawn＝起一次不論成敗，`keep`＝做完又起，`each`＝每回合起。LLM 修好路徑後要重試，只能在 tasks.json 寫 keep／each，然後自己記得拿掉。最簡單的補法：tasks.json 加 `mode: "once"`＝同名任務有活的、或曾經以 code 0 結束過就不起（其餘同 keep）。
- **N2 任務一直失敗，status 看不到**：crash loop 只在 rounds.jsonl 的 `ended[].code` 與各 exit.json。LLM 要先猜 tid 再讀 out.log。最簡單的補法：daemon 拿 tock 印出的 `ended`，在 status 的 node 加 `last_task_fail`＝`{"tid","name","code","round"}`（被 ctl 收掉的不算）。
- **N3 結束任務被搬走得比 LLM 一輪還快**：`keep_ended_rounds` 只看回合數，200 ms 的 node 4 秒就搬。補法二選一：tock 搬之前另加時間下限（例如 ended.json 寫了超過 60 秒才搬），或卡／spec 寫明「`tasks/<tid>` 不在就看 `tasks-old/<tid>`」（卡已有一句，模型仍先撞到）。
- **N4 父改子時間線的檔＝寫出範圍**（N-50 的證據）：自我編程的 agent 開了子時間線，之後要改它的 tasks.json／interval，照 spec「自己 node 扣掉巢狀 node」就被標 ok:false；三個模型都這樣做，沒有一個想到要把 `me/sub` 加掛進來。加掛 `me/sub/.aos` 再經 mnt 寫就合規，基礎設施夠，但不直覺。
- **N5 掛載點拼錯路徑時毫無回饋**：寫到 `me/mnt/...` 只是建了普通資料夾；daemon 沒收到，寫的人也不知道。只有「寫完看 ctl-done 回條」能發現——卡該寫明「沒有回條＝沒送到」。
- **N6 加掛要等一個 tick**：interval 慢時（2000 ms）先要拿到 `.aosd` 才能 wake，雞生蛋；想快只能先改 interval 等它生效。不擋事，記代價。
- wake、子時間線、spawn batch、pause 都照卡上的寫法就對；沒有模型需要 edit_json（單一寫者，整份覆寫是原子的）。

## 修補之後（10-03）

- **已套用**：
  - 卡補三句：子 node 的 cwd 是子 node；掛載點在 `$AOS7_TASK/mnt/`；要改子 node 先加掛。
  - 卡也寫明：一次性工作用 spawn，不寫進 tasks.json。
  - spawn 照 keep／max_live。
- **沒做**，記成 infra-needs N-65、N-71、N-72：
  - `mode: "once"`。
  - status 的 `last_task_fail`。
  - tasks-old 的時間下限。
- N-50 取 (a)：先加掛。
