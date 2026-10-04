# daemon ↔ tick-tock 的交接

← [入口](../layer-interfaces.md)｜下一份：[tick-tock ↔ 任務](02-ticktock-task.md)

這一層是四層裡最「硬」的一層：daemon 和 tick／tock 之間只靠**程序呼叫、環境變數、stdout、退出碼**和幾個固定的檔案說話，而且每個判斷都照三態（是／否／不知道）。依據是 spec 第 1～3 節與 `lib/aos7_daemon.py`、`lib/aos7_daemon_timeline.py`、`lib/aos7_tick.py`、`lib/aos7_tock.py`、`lib/aos7_fs.py`。

## 1. 交接點清單

「通用」＝對任何任務都一樣，不是為了 agent／LLM 才有。這一層**全部是通用的**。

| 交接點 | 誰寫 → 誰讀 | 時機 | 格式 |
|---|---|---|---|
| 程序呼叫 `aos7-tick <root> <node-id>` | daemon 的時間線 thread → tick | 每回合第 3 步 | `python3 bin/aos7-tick`，stdout／stderr 用管線收 |
| 程序呼叫 `aos7-tock <root> <node-id>` | 時間線 → tock | 第 5 步；回合沒關上馬上補一次；開回合前發現上一回合還開著也先跑一次 | 同上 |
| 環境 `AOS7_GEN` | daemon → tick／tock | 每次呼叫 | daemon 這一世的世代號（字串） |
| 環境 `AOS7_EARLY` | daemon → tock | 每次 tock | `1`＝提前（early_tock 或被 wake 切掉），`0`＝沒有 |
| 環境 `AOS7_INCOMPLETE` | daemon → tock | 不正常收尾時 | `unclosed`（開回合前補收）／`tock`（剛才沒關上）／`tick`（tick 被逾時收掉）／`unregister` |
| stdout 最後一行 JSON | tick → daemon | tick 結束 | `{"round", "started": [run id], "tasks_rev"}`，或 `{"gone": true}`、`{"stale": true}`、`{"unknown": "原因"}` |
| stdout 最後一行 JSON | tock → daemon | tock 結束 | 回合總結；或 `{"skipped": ...}`、`gone`、`stale` |
| 退出碼 | tick／tock → daemon | 結束 | `0` 做了（含 gone／stale）、`1` 用法錯、`3` 不知道（什麼都沒寫）、`-9` 被 daemon 逾時收掉；Python 例外也是 `1` |
| stderr | tick／tock → daemon | 失敗時 | 收進 status 的 `last_error.err`（太長保留頭尾） |
| `.aosd/gen.json` | daemon 起來時寫 → tick／tock 拿鎖後讀 | daemon 拿到 `daemon.lock` 後 | `{"gen", "pid", "at"}` |
| `<node>/.aos/action.lock` | tick、tock 都拿 flock | 整個動作期間 | 空檔，不 unlink |
| `<node>/.aos/action.owner.json` | 現役的 tick／tock → 新 daemon 等鎖逾時時讀 | 確認世代後 | `{"pid", "gen", "starttime", "at"}` |
| `<node>/.aos/round.json` | tick 寫 `open: true`、tock 寫 `open: false` → daemon 每回合頭尾讀 | 第 1 步前、第 5 步後 | `{"round", "open", "tick_at", "tock_at", "started", "ctl", "mounts", "tasks_error", "reaped", "skipped", "tasks_rev", "notify_errors"}` |
| `<node>/.aos/last-round.json` | tock 寫 → tick（round.json 不在時接號）、tock 重播時讀 | 第 5 步 | 見 spec 第 3 節；daemon 本身不讀 |
| `<node>/.aos/timeline.json` | 人／kernel 寫 → daemon 每圈頂端讀 | 每回合開始前 | `{"interval_ms", "early_tock", "action_timeout_s"}`，可無 |
| 槽裡的 `birth.json`、`exit.json`、`pid.json` | tick／aos7-run 寫 → daemon 讀 | `early_tock` 時每 20 ms 看「本回合起的都結束了沒」；status 的 `live` 每 0.25 秒算一次 | 見 [02](02-ticktock-task.md) |
| 訊號 | daemon → tick／tock | 逾時、停機寬限（3 秒）過了 | SIGKILL；tick／tock 自己忽略 SIGTERM，做完才走 |

daemon 自己的檔（`nodes.json`、`paused.json`、`status.json`、`log.jsonl`）tick／tock 不碰；跟上層的交接放在 [04 跨層](04-cross-layer.md)。

## 2. 機制與協議

- **只有一個 daemon**：`.aosd/daemon.lock` 非阻塞 flock，拿不到退出碼 1。拿到之後才把 `gen` 加一。
- **世代擋住舊動作**：舊 daemon 起的 tick／tock 可能比 daemon 活得久。它們拿到 `action.lock` 後先比 `AOS7_GEN` 跟 gen.json，不同就什麼都不寫、印 `{"stale": true}`；gen.json 讀不懂就退出碼 3。人手直接跑 `aos7-tick`（沒有 `AOS7_GEN`）不比世代，只靠 action.lock 排隊。
- **action.lock 讓 tick 和 tock 不會同時改同一個 node**：daemon 在一個 node 上本來就是一個接一個跑，鎖是防「舊世代的動作還沒走」和「人手同時跑」。
- **逾時與接管**：動作最多 `action_timeout_s`（預設 30 秒），過了 SIGKILL。新動作等鎖逾時時讀 action.owner.json，只有「世代比較舊、pid 加 starttime 都對得上」才殺；認不出就不殺，`last_error.kind` 記 `stale-holder-unverified`。
- **抓目錄 fd**：tick／tock 用 `O_NOFOLLOW` 開 node，開到後 realpath 要等於登記的位置，不然印 `gone`。這樣 node 被換成符號連結也不會寫到空間根外面。
- **三態退出碼**：tick／tock 推定不了（round.json 讀不懂、上一回合還開著、列不出槽、gen.json 壞掉、看不到 node）就退出碼 3、什麼都不寫。daemon 收到 3 就退避（0.5 秒起加倍，最多 8 秒），status 的 `phase` 是 `error`、`round_open` 是 `null`。
- **回合的不變條件**：round.json 明確 `open: false`（或確定不存在）才開下一回合。這條 daemon 檢查一次，tick 自己再檢查一次。
- **原子寫**：所有 JSON 都是寫 `.<名>.tmp.<pid>` 再 rename；寫的人被殺留下的暫存檔，tick／tock 在拿著鎖時清。
- **全部是強制的**（不靠任務合作）：這一層沒有合作式的部分，因為兩邊都是核心程式。

## 3. 彼此的影響

### 上層（daemon）怎麼影響下層（tick-tock）

- **節拍完全由 daemon 決定**。interval 從 tick **開始**算（`aos7_daemon_timeline.py:268-269`），所以 tick 本身花的時間吃進 interval；tick 若比 interval 還久，tick 一結束就馬上 tock。
- **固定 interval（預設）下 `wake` 會切掉正在跑的回合**：實測 wake 寫下到任務收到 tock.json 只要 15～25 ms（2 秒 interval 的 node，見 [入口的實驗](../layer-interfaces.md#實驗)）。`early_tock: true` 的 node 回合中的 wake 不起作用，但這種 node 的回合通常很短（沒有本回合起的任務時 tick 完就 tock），回合後的等待照樣被 wake 打斷。
- **daemon 重開**：gen 加一，正在跑的舊 tick／tock 自己做完（它們已經過了世代檢查，拿著鎖）或看到世代變了就收手；新 daemon 看到 round.json 還開著，先 tock 收掉（總結標 `incomplete: "unclosed"`），回合數接著數。

### 下層（tick-tock）的故障怎麼傳上來

| tick／tock 的結果 | daemon 怎麼做 | 誰看得到 |
|---|---|---|
| tick 退出碼 3 | 不 tock、退避，下一圈重看回合 | status `phase: error`、`last_error` |
| tick 被逾時收掉（-9） | 照樣等完、tock 時帶 `AOS7_INCOMPLETE=tick` | 總結 `incomplete: "tick"` |
| tick 其他失敗（例外，退出碼 1） | **當成正常回合**：記 `last_error`，照樣等 interval、跑 tock；tock 看到回合已關印 `skipped`，daemon 判定「回合關上了」並扣 `rounds` 倒數 | 只有 `last_error`；**見缺口 G2** |
| tock 沒把回合關上 | 馬上補一次 tock；還是沒關就欠著，下一圈頂端走不變條件一（退避） | `round_open: true`、`recovery_pending`、事件 `round-unclosed` |
| tock 印 `stale` | 這條時間線直接結束（舊世代的時間線不該再跑） | 事件 `stale` |
| tick 印 `gone` | 等 20 ms 再來；daemon 主迴圈那邊會判 `missing` | `phase: missing` |

G2 是這次實驗確認的：把 node 的 `.aos/` 設成唯讀，tick 寫 round.json 失敗（退出碼 1），`resume --rounds 3` 只真的跑了 1 回合，剩下兩次倒數被失敗的 tick 吃掉，node 又被同一個 owner pause 回去。上層（kernel 用 `rounds` 做「只跑 N 回合」）會以為跑滿了。

### 延遲：請求從寫下到生效

| 請求 | 生效時機 | 實測（interval 2 秒） |
|---|---|---|
| 改 `timeline.json` | 下一回合開始前（時間線迴圈頂端重讀） | — |
| `pause` | daemon 下一圈（約 20 ms）收件、回條；**本回合照常收完**才真的停 | 回條 5 ms；status 變 `paused` 約 2.0 秒（等本回合的 interval） |
| `wake` | 約 20 ms 收件，固定 interval 的 node 馬上 tock、開下一回合 | 任務收到新 tock.json 15～25 ms |
| `resume`（讓 node 變成沒人 pause） | 同 wake | — |
| 回合不知道（round.json 壞掉）恢復 | 人寫回 round.json 後，下一次退避醒來（最多 8 秒） | — |
