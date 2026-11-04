# jobs 工具包

把要跑很久的指令搬去另一個世界。父 agent 不必停在原地等。

| 工具 | 什麼時候用 |
|---|---|
| `run_long(command, name?)` | 指令可能跑超過一格時。回 job 名稱，並睡到完成。 |
| `jobs_list()` | 想看哪些 job 還在跑、做完或取消了。 |
| `job_peek(name, lines?)` | 想看一個 job 的最新輸出。預設看 stdout、stderr 各最後 20 行。 |
| `job_cancel(name)` | 不想讓一個 job 繼續跑。 |

job 放在 `<home>/jobs/<name>/`。`name` 不給就用時間戳。自己取名時只能用英數字、底線、減號。

`run_long` 把 `command` 原樣存成 `cmd.sh`。job 有自己的鐘，最多跑 3600 秒。
完整輸出留在兩個 log；共用層收結果到 `<home>/side/jobs/` 後喚醒 agent。

## 設定

一定要有 `AOS_DAEMON_DIR`。沒有時 `run_long` 會直接說不能另開鐘，不會建立 job。

要啟用這包，在 `tools.json` 的 `packs` 加上 `jobs`。

## 坑

- 同名 job 不會自動換名字。請換一個名字再叫。
- 取消會留下 `side/jobs/<id>.json`，錯誤種類是 `cancelled`。
- 做完的資料夾不會自動清掉。
- 指令重跑、同時跑太多、超大 log，這版都不處理。
