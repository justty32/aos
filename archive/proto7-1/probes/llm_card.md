# aos7 操作卡（給只靠讀寫檔的 LLM）

一個 **daemon** 管一個空間根（root）。root 底下每個含 `.aos/timeline.json` 的資料夾是一個 **node**，node id＝相對 root 的路徑（`a`、`team/bob`；root 本身是 `.`）。每個 node 一條時間線：**tick**（開回合、起任務）→ 任務跑 → **tock**（收回合）→ 等滿 interval → 下一個 tick。所有狀態與控制都是 JSON 檔；寫檔就是操作。

## 你會讀的檔
- `.aosd/status.json`（daemon 每 ~20 ms 覆寫）：`{"pid","at","gen","stopping","stopped","nodes": {node id: {"round","phase","paused","pause_pending","interval_ms","live":[tid...],"last_error"?,"steps_left"?}}}`。`phase`：idle／tick／running／tock／paused／error／stopped。`at` 停更＝daemon 卡住或死了。`last_error`＝`{"prog","rc","round","at","err"}`，留到下次出錯才覆寫（**不會自己清掉**；拿它的 `round` 跟現在的 `round`、rounds.jsonl 最新幾行比，才知道是不是舊的）。
- `.aosd/log.jsonl`：daemon 流水帳（tick、tock、ctl、node+／node-、error）。
- `<node>/.aos/round.json`：`{"round","open","tick_at","tock_at", "tasks_error"?}`。
- `<node>/.aos/rounds.jsonl`：每回合一行總結 `{"round","started","alive","ended":[{"tid","name","code","by_ctl"?}],"ctl","tasks_error"?,"errors"?,"early"}`。
- **從沒開過回合的 node**（例如一出生就 pause）：status 的 `round` 是 0，還沒有 round.json、rounds.jsonl、tasks/，讀不到是正常的。
- `.aosd/status.json`、`paused.json`、`log.jsonl`、`gen.json` 是 daemon 寫的，**你寫了沒用**；要改狀態一律寫控制檔。
- `<node>/.aos/tasks/<tid>/`：一個任務。`birth.json`（定義）、`pid.json`、`out.log`、`exit.json`（有＝結束；`code` 負數＝被訊號殺）、`tock.json`（最近一次 tock）、`ctl-done.json`（控制回條）。tid＝`<name>-r<回合>`。結束超過 `keep_ended_rounds`（預設 20）回合的任務會被搬到 `.aos/tasks-old/<tid>/`：回合快時幾秒就搬走，`tasks/<tid>` 不在就去那裡找。

## 你會寫的檔（都寫完整 JSON；寫入是原子的）
- **daemon 控制**：寫一個新檔 `.aosd/ctl/<任意名>.json`（**檔名要以 `.json` 結尾**，否則回 ok: false）＝`{"op": ..., "node": "<node id>", "by": "<你是誰>"}`。op：
  - `pause`（node 不再開新回合；這回合會先收完，看 status 的 `pause_pending`→`paused`）、`resume`（可加 `"rounds": N`＝只再跑 N 回合後自動 pause）、`wake`（idle 的 node 馬上開下一回合）、`rescan`、`stop`（**整個** daemon 結束，不收 `node`；`"kill": true` 先 kill 所有任務）。daemon 控制**沒有 kill**；kill 單一任務寫那個任務的 ctl.json（下面）。
  - 同一批控制檔**依檔名排序**執行：換人時讓 pause 的檔名排在 resume 前面，或先 pause、等 status 看到停住再 resume。
  - 你比回合慢（一次思考好幾秒，回合幾百 ms）時，要精準只跑 N 回合請用 `resume` 帶 `rounds`，不要自己看到再 pause——等你看到已經多跑十幾回合。
  - daemon 處理後把檔搬到 `.aosd/ctl-done/<同名>.json` 並加 `"result": {"ok", "msg"}`。**ok 只表示接受**，真的停住要看 status。
  - pause 的清單存在 `.aosd/paused.json`，daemon 重開照樣有效。
- **任務表** `<node>/.aos/tasks.json`＝`{"tasks": [項目...]}`，每次 tick 讀。項目：`{"name", "mode": "keep"|"each", "argv": [...]}`（`keep`＝沒有同名活任務才起；`each`＝每回合起一個），可選 `from_round`、`max_live`、`mounts`（`{"名字": "空間路徑"}`，在任務資料夾建 `mnt/<名字>` 連結）、`subroot`（要在那裡開子 daemon 的空間路徑）、`allow_stop`（true＝允許別人用路二 stop 這個子 daemon，預設 false）。argv 相對路徑以 node 為 cwd。壞掉的一項只跳過那項（記在 `tasks_error`），整份讀不懂當空表。
- **只起一次的任務**：寫 `<node>/.aos/spawn/<任意名>.json`＝一個項目（或 `{"batch": [項目...]}`），下個 tick 起它、然後刪掉這個檔。**做一次就好的工作用 spawn，不要寫進 tasks.json**（tasks.json 的 `each` 每回合起一份，`keep` 結束了又起）。spawn 一樣看 `mode`／`max_live`：寫 `keep` 而同名已有活的就不起（回合總結的 `tasks_error` 會說）。常駐的任務只改 tasks.json，不要再補 spawn。
- **任務控制**：寫 `<node>/.aos/tasks/<tid>/ctl.json`＝`{"op": "kill"|"restart", "by", "why"}`。**下一個 tick 或 tock 才執行**，回條在同資料夾 `ctl-done.json`。restart＝照 **birth.json 原本的定義**再起一份（不是照現在的 tasks.json）。**改了 tasks.json 的定義（argv、mounts）想照新的重起，寫 `{"op": "restart", "reload": true}`**：照 node 現在 tasks.json 的同名項目起，回條 `result.diff` 列出舊→新（找不到同名項目就整個不執行、也不 kill，回條 `ok: false` 說原因）。keep 任務直接 kill，下個 tick 也會照現在的 tasks.json 再起。
- **時間線設定** `<node>/.aos/timeline.json`＝`{"interval_ms": 300}`（可選 `keep_ended_rounds`、`action_timeout_s`）。改了下一回合生效（想馬上生效再寫 `wake`）。tick／tock 超過 `action_timeout_s` 會被收掉、記在 `last_error`：先找它卡在哪（tasks.json、spawn、ctl.json 是不是正常的檔），**不要只把逾時調大**。
- **新 node**：先寫 `<新node>/.aos/tasks.json`，最後寫 `<新node>/.aos/timeline.json`；daemon 1～2 ms 內就會開始。拿掉 timeline.json＝node 消失，上面的活任務會被 kill（要暫停請用 pause）。

## 任務那邊
- 任務的環境變數：`AOS7_ROOT`、`AOS7_NODE`、`AOS7_NODE_ID`、`AOS7_TASK`（任務資料夾）、`AOS7_TID`。cwd＝**任務所在的 node**：寫在子 node `me/sub` 的 tasks.json 裡的任務，cwd 是 `me/sub`，相對路徑從那裡算。argv 裡的 `$AOS7_*` 會展開。
- 掛載點在**任務資料夾**底下：`$AOS7_TASK/mnt/<名字>`（不是 node 底下的 `mnt/`）。經掛載點寫控制檔後，看回條（ctl-done）確定送到了。
- 任務只該碰自己的 node 與掛載點；自己開的子 node（裡面有 `.aos/timeline.json`）也算別的 node，要改它先把它加掛進來。
- 任務靠輪詢 `$AOS7_TASK/tock.json` 知道回合結束；任務可以跨回合活著。
- 子 daemon（路一）：在 tasks.json 加一個任務 `{"name": "subd", "mode": "keep", "argv": ["aos7-daemon", "$AOS7_SUBROOT"], "subroot": "<自己 node 底下的空間路徑，例如 lab/sub>"}`。`subroot` 要在自己的 node 底下；`$AOS7_SUBROOT` 會展開成子根的絕對路徑。**等 `<子根>/.aosd/status.json` 出現之後再建子 node**，不然父 daemon 會先把它們當自己的。子根底下的 node 歸子 daemon 管，父 daemon 看不到。
- 管別的 daemon（路二）＝寫它的 `<子根>/.aosd/ctl/*.json`。**子 daemon 歸起它的 node**（看 `<子根>/.aosd/owner.json`）：那個 node 沒設 `allow_stop: true`，路二的 `stop` 會被拒（回條 `ok: false` 說它屬於誰）；pause／resume／wake 不受影響。允許時 stop 會留 `<子根>/.aosd/stopped.json`，父 node 的 keep 就不再起它，**刪掉 stopped.json 才會再起**。擁有者要停自己的子 daemon：kill 那個任務（keep 的先從 tasks.json 拿掉，不然下個 tick 又起）。寫給已經停掉的 daemon 的控制檔沒人處理，會留到它下次起來才執行。
