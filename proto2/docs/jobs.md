# jobs 工具包

把要跑很久的指令搬去另一個世界。父 agent 不必停在原地等。

| 工具 | 什麼時候用 |
|---|---|
| `run_long(command, name?)` | 指令可能跑超過一格時。當場回 job 名稱，做完會寄信。 |
| `jobs_list()` | 想看哪些 job 還在跑、做完或取消了。 |
| `job_peek(name, lines?)` | 想看一個 job 的最新輸出。預設看 stdout、stderr 各最後 20 行。 |
| `job_cancel(name)` | 不想讓一個 job 繼續跑。 |

job 放在 `<home>/jobs/<name>/`。`name` 不給就用時間戳。自己取名時只能用英數字、底線、減號。

`run_long` 會把 `command` 原樣存成 `cmd.sh`。job 有自己的鐘。它最多跑 3600 秒。做完後，完整輸出留在 `stdout.log` 與 `stderr.log`，摘要寫進 `result.json`，再寄一封信到父的 `inbox/jobs/`。

叫完 `run_long` 不要等。先回一句「已經開跑」並結束這一格。下一格看到新信，再用信箱工具讀結果。

## 設定

一定要有 `AOS_DAEMON_DIR`。沒有時 `run_long` 會直接說不能另開鐘，不會建立 job。

要啟用這包，在 `tools.json` 的 `packs` 加上 `jobs`。要讓 agent 讀完成信，也要載入 `mailbox`。

## 坑

- 同名 job 不會自動換名字。請換一個名字再叫。
- 取消會留下 `result.json`，狀態是 `cancelled`。
- 做完的資料夾不會自動清掉。
- 指令重跑、同時跑太多、超大 log，這版都不處理。
