# routines／schedule 事務包

← [modules](../README.md)｜對照：workflows heartbeat flavor 的 routines／schedule 工作流

**引擎是 aos tick**：keep 任務每回合醒來看一次表；本包只決定醒來做什麼，沿用 workflows heartbeat 的分工，不是 cron。

| 項目 | 內容 |
|---|---|
| 接法 | A 普通 keep 任務＋C 工具（add／ls／rm） |
| 預設 | 關；add 會安裝 `routines` keep 任務，同名已有就不動 |
| 依賴 | Python 3.11+ 標準庫、核心 aos7_fs／aos_exec、工具包 task_env／wait_tock |
| 程式 | `aos7-routines`；`aos7_routines.py` 的 `step(node, round, now)` 可同程序呼叫 |
| 測試 | `python3 proto7-2/tests/run_all.py modules/routines/tests` |

## 契約卡／規則
- **職責**：收到 tock 後判兩張表到期、同步跑 inst；外部指令只有 `add <node> <name> (--every 間隔 | --at ISO或+90s) <inst> [--timeout 秒]`、`ls <node>`、`rm <node> <name>`。
- **前置條件**：表遵守 wf-table/1，name 唯一、值都是字串、缺欄視為空；所有寫者用 edit_json 鎖。相對 inst 以 node 為準。
- **保證**：缺表無事；讀不到、壞表、非 rows 陣列＝整表 unknown，下回合重試；壞列印原因並跳過。退出碼 0 正常、1 用法／重名／找不到、3 unknown。
- **規則**：r 型看回合差、秒型看時間差，空值第一次到期；回合重來／時鐘倒退當到期。schedule 在 at ≤ now 到期；錯過很久只做一次。
- **最多一次**：鎖內重讀仍到期才寫證據，放鎖再跑；routine 寫現在與 running，結束才寫 code；schedule 先寫 claimed，結束刪列。中斷的 claimed 刪列並報「被打斷、不重跑」；routine running 等下一期。
- **明確不管**：補漏、執行中斷後的業務恢復、斷電持久性、時機分區。

## 五個概念
1. routine 是隔幾回合或幾秒重做的例行事。
2. schedule 是指定時刻只做一次的事。
3. 兩張表放在 node 的 wf/，記錄要做的事和執行證據。
4. inst 是要跑的東西，可以是可執行檔、inst.json 或資料夾。
5. 引擎＝tick，負責讓 keep 任務醒來。

## 第一次跑
`<proto7-2>` 換成絕對路徑，`<root>` 換成一個空資料夾。以下已實跑（2026-10-09）。
```sh
P=<proto7-2>; R=<root>
python3 "$P/bin/aos7-ctl" daemon "$R" register n1
mkdir -p "$R/n1/.aos"; echo '{"interval_ms":200}' > "$R/n1/.aos/timeline.json"
printf '#!/bin/sh\necho hello\n' > "$R/n1/hello.sh"; chmod +x "$R/n1/hello.sh"
"$P/modules/routines/aos7-routines" add "$R/n1" hello --every 3r "$R/n1/hello.sh"
"$P/modules/routines/aos7-routines" add "$R/n1" once --at +2s "$R/n1/hello.sh"
python3 "$P/bin/aos7-daemon" "$R" > "$R/daemon.log" 2>&1 & D=$!
sleep 3
"$P/modules/routines/aos7-routines" ls "$R/n1"
grep -c code "$R/n1/.aos/tasks/routines/out.log"   # 跑過幾次（每次一行 routine／schedule … code N）
python3 "$P/bin/aos7-ctl" daemon "$R" stop --kill; wait "$D"
```
已實跑輸出（register／stop 另印控制檔位置）：
```text
added routines hello next tock (every 3r) keep installed
added schedule once next 2026-10-09T14:37:55.787797+08:00 keep existing
routine hello  every 3r  last 13  code 0  next round 16
5                                    # 4 次 routine（回合 1、4、7、10…）＋1 次 schedule；schedule 那列做完已刪
```
## 表格式
兩張空表原文（wfnode init 可照抄；extracted 換成建立日期）：
```json
{"contract":"wf-table/1","source":"workflows/routines.md","extracted":"2026-10-09","columns":["name","every","inst","last_round","last_time","last_code"],"rows":[]}
{"contract":"wf-table/1","source":"workflows/schedule.md","extracted":"2026-10-09","columns":["name","at","inst","claimed"],"rows":[]}
```
欄位：name 是唯一名稱；every 是正整數加 r/s/m/h/d；inst 是目標路徑；last_round 是上次回合；last_time 是上次 ISO 本地時間；last_code 是結束碼或 running；at 是含日期的 ISO 絕對時刻（有時區或本地）；claimed 是本包寫的認領時間；timeout 是可選的正秒數，空＝600。contract 是表契約；source 是對照來源；extracted 是建立日期；columns 是欄名；rows 是列陣列。

## 界線
取樣：tock 漏掉就延後，不補跑。最多一次：被殺在跑前或跑中途就不重跑該期。routine 在 keep 任務裡同步跑，長的會延後其他項，timeout 預設 600 秒。「每天上班」那種時機分區留給 agent 的 tick 工作流。`.lock` 是 edit_json 的鎖，會留在 wf/。
