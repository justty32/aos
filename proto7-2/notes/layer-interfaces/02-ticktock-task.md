# tick-tock ↔ 任務的交接

← [入口](../layer-interfaces.md)｜上一份：[daemon ↔ tick-tock](01-daemon-ticktock.md)｜下一份：[kernel ↔ agent](03-kernel-agent.md)

kernel 和 agent 對 tick-tock 來說都只是「任務」（S-16），所以這一節同時是 kernel 和 agent 接到核心上的那一面。任務能跟核心說話的入口只有六個：**tasks.json、ctl.json、mount-req/、環境變數、tock.json、槽裡的檔**。依據是 spec 第 4～8 節與 `lib/aos7_tick.py`、`aos7_tock.py`、`aos7_task.py`、`aos7_run.py`、`aos7_mount.py`、`aos7_ctl.py`。

## 1. 交接點清單

| 交接點 | 誰寫 → 誰讀 | 時機 | 格式 | 通用／專用 |
|---|---|---|---|---|
| `<node>/.aos/tasks.json`（＋`tasks.json.lock`） | 人、kernel、tick（once 的 `launch` 標記、刪起完的 once）、tock 與 tick（restart、retry_lost 加 once 項）→ tick | tick 第 4 步拿鎖讀（最多等 1 秒） | `{"tasks": [{name, mode, argv/inst, max_live, from_round, until_round, enabled, mounts, subroot, allow_stop, slot, retry_lost, ...}], "mount_allow"}` | 通用 |
| 槽資料夾 `.aos/tasks/<槽>/` | tick 建、tock 刪 | 第一次起；名字離開表、結束報過再一回合後刪 | 槽名＝`name` 或 `name.k` | 通用 |
| `birth.json` | tick → aos7-run、tock、daemon、kernel | 起 run 前寫，Popen 後補 `runner` | `{name, slot, run, round, node, argv/inst, mounts, once, restart_of, ctl_id, at, runner}` | 通用 |
| 程序呼叫 `aos7-run <槽> <fd>` | tick → aos7-run | 第 5 步 | 新 session、cwd＝tick 抓著的 node fd、stdin／stdout 接 /dev/null | 通用 |
| 環境變數 | tick → aos7-run → 任務 | 起 run 時 | `AOS7_ROOT`、`AOS7_NODE`（絕對路徑）、`AOS7_NODE_ID`、`AOS7_TASK`、`AOS7_TID`（＝槽名）、`AOS7_RUN`；子 daemon 另有 `AOS7_SUBROOT`、`AOS7_OWNER_NODE`、`AOS7_OWNER_TID`、`AOS7_ALLOW_STOP`；`PATH` 前面加 `bin/`。**其餘環境整份從 daemon 繼承** | 通用 |
| argv 裡的 `$AOS7_*` | aos7-run 展開 | 起任務前 | 只展開 `AOS7_` 開頭的 | 通用 |
| `pid.json` | aos7-run → tock、tick、daemon、kernel | 任務起來後 | `{run, pid, pgid, starttime, runner_pid, uid, at}` | 通用 |
| `out.log` | 任務的 stdout＋stderr | 整個 run | 這次 run 的，換 run 清 | 通用 |
| `exit.json` | aos7-run（lost 時是 tock 或 tick）→ tock → `last-round.json` 的 `ended` | 任務結束 | `{run, code, at, round}`；code 負數＝被訊號殺、127＝沒起成、lost 是 `{code: null, lost: true}`；報過補 `seen_round` | 通用 |
| `tock.json` | tock → 任務 | 每回合結束（總結提交之後） | `{run, round, at, early}`，覆寫；補寫的帶 `late: true` | 通用 |
| `aos7-wait-tock` ／ `aos7_fs.wait_tock` | 任務自己呼叫 | 任何時候 | 等 `round > --after` 且 `run` 相符，印回合數；逾時退出碼 1 | 通用 |
| `ctl.json` → `ctl-done.json` | 任何人 → tick／tock → 請求者 | **只在 tick 和 tock 時刻**執行 | `{op: kill/restart, by, why, run?, reload?, id?}`；回條加 `result: {ok, msg, at, run, ctl_id, diff?, replayed?}` | 通用 |
| `.aos/ctl-seen.json` | tick／tock（完成證據） | 執行後、寫回條前 | `{"slots": {槽: {ctl_id, op, ok, msg, run, at}}}` | 通用 |
| `mounts` 宣告 → `mnt/<名字>` | tasks.json → tick 建相對符號連結 | 每次起新 run 重建 | `{"名字": "空間裡的路徑"}` | 通用 |
| `mount-req/<名>.json` → `mount-done/<名>.json` | 任務 → **只有 tick** 審 → 任務 | 下一個 tick | `{name, path, why}`；回條加 `result` | 通用 |
| 任務自己的檔（`state.json`、`usage.json`、`progress.json`…） | 任務寫 → 同槽下一個 run、kernel 讀 | 任意 | 核心不管格式，換 run 不清，槽被刪才消失 | 機制通用；**內容是約定**（見 [03](03-kernel-agent.md)） |
| `last-round.json`、`round.json` | tock／tick → 任務讀 | 隨時 | 只留「上一次」 | 通用 |
| 訊號 | tick／tock／daemon → 任務 | 任務控制、node 消失、unregister、stop | SIGTERM，最多等 1 秒，SIGKILL；範圍是 Q1（群組、後代所在群組、NODE＋TID＋RUN 相符的程序） | 通用 |
| 可選的寫入紀錄 `AOS7_AUDIT` → `writes.jsonl` | aos7-run 的 sitecustomize | 整個 run | 只給 Python 任務；換 run 清 | 通用 |

## 2. 機制與協議

- **once 不重起也不消失**：tick 在寫 birth.json **之前**先在那項寫 `launch`（槽＋run），起成後再拿鎖照標記刪項。下一個 tick 看到還有 `launch` 的項，比對槽裡的 run 判斷「已起／確定沒起／不知道」。
- **run 號與身分**：run＝起它的回合數，同槽一定遞增。身分掃描比對 `AOS7_NODE`＋`AOS7_TID`＋`AOS7_RUN` 三個環境變數；同槽上一個 run 留下的孫程序不會被算成這次的。
- **三態判定**：槽的狀態只有空／活／結束／疑似 lost／不知道。讀不到、不是一般檔、/proc 讀不完整都是「不知道」：不起新 run、不判 lost、不刪槽，記進總結 `errors` 與 status `uncertain`。
- **任務控制的重播只生效一次**：每份請求有 `ctl_id`（帶 `id` 就用它，沒帶就用槽＋inode＋mtime＋內容的雜湊）。先記 `ctl-seen.json`，再寫回條，再刪請求；同一個 ctl_id 再出現就只補回條。restart 是「先加 once 項、再 kill」，新 run 仍由下一個 tick 起（S-10）。
- **tock.json 有 run 過濾**：`wait_tock` 只認 `run` 等於自己 `AOS7_RUN` 的通知，所以槽重用時新 run 不會被上一個 run 的 tock.json 騙。
- **合作式 vs 強制**：kill 的範圍、run 身分、槽的生死判定是強制的（核心自己做）；「任務只碰給的資料夾」（S-10）、「改 tasks.json 要拿鎖」、「交付物寫到槽外」、tasks.json 誰能改什麼，**全部是合作式**。任務拿得到 `AOS7_ROOT`，技術上可以寫空間裡任何地方（spec 第 11 節已接受）。

## 3. 彼此的影響

### 上層（任務）怎麼影響下層（時間線）

- **任務卡住不會卡住時間線**：固定 interval 下回合照走；任務只是漏看 tock，回來時只看得到最新一個（中間的回合被併掉）。`early_tock: true` 時只等「本回合起的任務」，所以一個常駐 agent 只會在它被起的那一回合拖住提前 tock。
- **each 的任務還在跑就跳過**，總結 `skipped` 記 `busy`；keep 的槽活著就不補。
- **不理 SIGTERM 的任務會拖慢 tick／tock**：kill 是在 tick／tock 拿著 action.lock 時做的，每個槽最多等 1 秒再 SIGKILL，再等 0.5 秒看 exit.json。一回合要收很多槽時，整個動作可能逼近 `action_timeout_s`（讀碼推論，沒實測）。
- **拿著 tasks.json.lock 太久會讓回合空轉**：tick 最多等 1 秒，等不到這回合就不從表上起任何東西（`tasks_error`）；同時，restart 請求等不到鎖會回 `ok: false` 並**刪掉 ctl.json**，請求者要重送。kernel 若在 `edit_json` 的回呼裡做慢事（例如問 LLM），兩件都會發生。
- **改 tasks.json 的效果**：加一項 → 下一個 tick 起（實測 2 秒 interval 下 1.5 秒看到 birth.json）；拿掉一項 → 跑著的不殺，結束報過後再一回合槽連同任務自己的檔一起刪；`enabled: false` → 不起但槽留著；`until_round` → 到期不再起、跑著的不殺。

### 下層的故障，任務看到什麼

| 下層發生 | 任務看到的 |
|---|---|
| tick 被殺在起任務途中 | 可能還沒起、或起了但 birth.json 沒記到 runner；核心照 5.4 判，等不到就判 lost。once 預設不重跑（`retry_lost` 可改） |
| tock 沒寫進某個 tock.json | 這回合沒收到通知；round.json 記 `notify_errors`，下一個 tick 補寫（帶 `late: true`） |
| 回合卡在「不知道」（round.json 壞掉、gen.json 壞掉） | **完全安靜**：沒有新 tock.json，任務照跑；`wait_tock` 沒設逾時就一直等 |
| node 被 pause | 同上：沒有 tock、`ctl.json` 不執行、mount-req 不審 |
| node 確定消失／搬走／換成符號連結 | 被收掉（SIGTERM→SIGKILL）；新位置要另外 register |
| node 看不到（EIO 等） | 不收、時間線退避：等於安靜 |
| daemon 被 kill -9 再起來 | 任務不受影響（自己的 session）；新 daemon 先收舊回合（`incomplete: "unclosed"`），之後的 tock.json 照常、回合數接著數 |
| `unregister` 帶 `kill: false` | 任務留著，**從此收不到 tock**，由下指令的人負責 |

任務分不出「回合被 pause」「回合卡在不知道」「daemon 死了」這三種安靜，只能自己讀 `.aosd/status.json`（要經掛載才合 S-10）。

### 延遲

| 請求 | 生效時機 | 實測（interval 2 秒） |
|---|---|---|
| 改 tasks.json | 下一個 tick | 加 once 項到 birth.json 出現 1.5 秒 |
| ctl.json kill／restart | 下一個 tick **或** tock，看哪個先到 | kill 到回條 1.7 秒 |
| restart 的新 run | 收到請求那次動作之後的下一個 tick | 最多約兩個動作 |
| mount-req 加掛 | 只在下一個 tick | — |
| 任務結束 → 出現在總結 | 下一次 tock（tock 之後才結束、下一個 tick 又重用槽的，tick 先記進 `reaped`） | — |
| 回合結束 → 任務知道 | tock 寫 tock.json 那一刻；任務自己輪詢（`wait_tock` 預設 20 ms） | — |
