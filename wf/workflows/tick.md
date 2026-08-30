# tick — 單次定期心跳（機械判定與派發）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

`aos run` 就是引擎：它持續推進資料夾的回合；`.aos/every/tick.json` 是心跳，
每到週期便讓 loop 在回合中執行一次 `aos tick`。`aos tick` 只做機械判定、投遞、
更新清單與寫 log，自己不叫 LLM、不動腦。

本工作流刻意極薄：判定與派發已機械化；只有真的需要判斷的內容才用 `ask` 進入
資料夾裡的 agent。常規清單見 [routines](routines.md)，一次性清單見 [schedule](schedule.md)。

**何時用**：心跳自動執行；或你要手動判定一次時跑 `aos tick [folder]`，先預覽則加 `--dry-run`。
**何時不用**：要登記常規事務 → `aos routine add`；要登記一次性行程 → `aos schedule add`。
心跳裡也不跑深度巡檢、調查、批次改檔等重活。

## Done when

- 本次到期項已投遞、兩張清單已按規則更新，且 `.aos/heartbeat/log.md` 有一行摘要。**沒有到期項的心跳不寫 log**——心跳活著的證據在 loop 的回合結果，不必用空行淹掉有用的。

## 流程

1. `aos run` 推進一回合；loop 依 `.aos/every/tick.json` 的週期把 `aos tick` 複製進本回合執行。
2. `aos tick` 掃 `.aos/heartbeat/routines.json` 與 `.aos/heartbeat/schedule.json`，依當地時間機械判定到期項。
3. 到期項的 `run.argv` 投進 inbox，交給後續回合執行；`run.ask` 則透過 `aos say` 投給資料夾裡的 agent。
4. tick 更新 routine 的 `last_run`、刪除已投遞的 schedule；錯過超過門檻的 schedule 改投「補做或跳過」的 `ask` 後刪列。
5. tick 在 `.aos/heartbeat/log.md` 寫一行結果。`--dry-run` 只印會做什麼，不投遞、不改清單、不寫正式結果。
6. 人與 agent 多半什麼都不用做；agent 只在收到 `ask` 時判斷並處理，argv 不需要 agent 介入。

## 怎麼開這個 repo 的心跳

在 repo 根目錄先初始化：`aos heartbeat init --interval 30m`。
再到另一個視窗執行：`aos run --step 0`。
要停就中止該程序；**不要由工作流自行留下常駐程序，是否開常駐是使用者自己的決定。**
`[folder]` 都可省略；省略時從 cwd 往上找最近含 `.aos/` 的目錄。

## 交接

- 到期項需要使用者決定 / 親自做 → [WAIT_USER](../WAIT_USER.md) 一行，心跳不卡在那裡。
- 到期項是重活 → [SESSION-LOG](../SESSION-LOG.md) 一行 open，另開 session 做。
- 心跳不自行推外部通知；只有登記的 argv 或 agent 收到的 `ask` 會繼續處理。
