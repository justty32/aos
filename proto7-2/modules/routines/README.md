# routines／schedule 事務包

← [modules](../README.md)｜對照：workflows heartbeat flavor 的 routines／schedule 工作流

**一句話**：一張「要做的事」清單。`add` 寫進去、`ls` 看清單、`rm` 刪掉；時間到就跑你給的程式。有兩種事：**routine** 每隔一段時間做一次，**schedule** 到指定時刻只做一次、做完就從清單劃掉。

## 第一次跑（約 1 分鐘，不用開任何背景程式）
只要一個空資料夾當 node（清單會放在它的 `wf/` 底下）。`<proto7-2>` 換成本資料夾上兩層的絕對路徑；以下已實跑（2026-10-09）。
```sh
P=<proto7-2>; N=/tmp/rt-demo/n1; R="$P/modules/routines/aos7-routines"
mkdir -p "$N"; printf '#!/bin/sh\necho hello\n' > "$N/hello.sh"; chmod +x "$N/hello.sh"
"$R" add "$N" hello --every 1m hello.sh   # routine：每 1 分鐘做一次（程式路徑相對 node）
"$R" add "$N" once --at +1s hello.sh      # schedule：1 秒後做一次
sleep 2                                   # 等 once 的時間到
"$R" ls "$N" --run                        # 把現在到期的立刻做掉，再列清單
"$R" ls "$N" --run                        # 再一次：hello 還沒滿 1 分鐘、once 已劃掉
```
預期輸出（時間會不同）：
```text
added routine hello every 1m
added schedule once at 2026-10-09 15:40:01
hello
routine hello code 0
hello
schedule once code 0
routine hello  every 1m  last 2026-10-09 15:40:02  code 0  next 2026-10-09 15:41:02
（現在沒有到期的事）
routine hello  every 1m  last 2026-10-09 15:40:02  code 0  next 2026-10-09 15:41:02
```
`hello` 是你的程式印的，`code 0` 是它的結束碼。看到這些就成功了。不要了就 `"$R" rm "$N" hello`。同一個資料夾重跑會說「名字已經在清單裡」，換個空資料夾就好。

## 讓它自己定時跑（下一步，可選）
`ls --run` 是你手動叫它看一次。要它一直自己看，就開 aos 的背景程式 daemon：daemon 每隔一小段時間醒一次（一次叫一**回合**），每回合都替你看一次清單。`add` 已經順手在 node 登記好這件事，你不用再設。
```sh
P=<proto7-2>; ROOT=/tmp/rt-daemon; R="$P/modules/routines/aos7-routines"; N="$ROOT/n1"
python3 "$P/bin/aos7-ctl" daemon "$ROOT" register n1             # 在 ROOT 底下建 node n1
mkdir -p "$N/.aos"; echo '{"interval_ms":200}' > "$N/.aos/timeline.json"   # 每 0.2 秒醒一次（示範用，平常不用設）
printf '#!/bin/sh\necho hello\n' > "$N/hello.sh"; chmod +x "$N/hello.sh"
"$R" add "$N" hello --every 3r hello.sh                          # 3r＝每 3 回合做一次
python3 "$P/bin/aos7-daemon" "$ROOT" > "$ROOT/daemon.log" 2>&1 & D=$!   # daemon 會一直跑，所以 & 放背景
sleep 3                                                          # 讓它跑 3 秒（約 15 回合）
"$R" ls "$N"
python3 "$P/bin/aos7-ctl" daemon "$ROOT" stop --kill; wait "$D"  # 叫 daemon 停，等它真的結束
```
`ls` 會印像 `routine hello  every 3r  last 13  code 0  next round 16`（數字看機器快慢）；register／stop 各印一行控制檔位置，是正常的。daemon 跑時程式的輸出寫在 `$N/.aos/tasks/routines/out.log`。`r` 型只有 daemon 開著才算，`ls --run` 不跑它。

---
**以下是給維護者與整合者的細節，第一次用可以不看。**

| 項目 | 內容 |
|---|---|
| 接法 | A 普通 keep 任務＋C 工具（add／ls／rm） |
| 預設 | 關；add 會安裝 `routines` keep 任務，同名已有就不動 |
| 依賴 | Python 3.11+ 標準庫、核心 aos7_fs／aos_exec、工具包 task_env／wait_tock |
| 程式 | `aos7-routines`；`aos7_routines.py` 的 `step(node, round, now)` 可同程序呼叫（round=None＝手動 `ls --run`） |
| 測試 | `python3 proto7-2/tests/run_all.py modules/routines/tests` |

## 契約卡／規則
- **職責**：收到 tock（daemon 每回合給任務的通知）後判兩張表到期、同步跑 inst（要跑的程式）；外部指令只有 `add <node> <name> (--every 間隔 | --at ISO或+90s) <inst> [--timeout 秒]`、`ls <node> [--run]`、`rm <node> <name>`。`ls --run` 在本程序做一次不帶回合的 step：秒型 routine 與 schedule 照時間判，r 型跳過。
- **前置條件**：表遵守 wf-table/1，name 唯一、值都是字串、缺欄視為空；所有寫者用 edit_json 鎖。相對 inst 以 node 為準。
- **保證**：缺表無事；讀不到、壞表、非 rows 陣列＝整表 unknown，下回合重試；壞列印原因並跳過。退出碼 0 正常、1 用法／重名／找不到、3 unknown。手動 `ls --run` 與 daemon 同時跑也由同一把鎖保證最多一次。
- **規則**：r 型看回合差、秒型看時間差，空值第一次到期；回合重來／時鐘倒退當到期。schedule 在 at ≤ now 到期；錯過很久只做一次。
- **最多一次**：鎖內重讀仍到期才寫證據，放鎖再跑；routine 寫現在與 running，結束才寫 code；schedule 先寫 claimed，結束刪列。中斷的 claimed 刪列並報「被打斷、不重跑」；routine running 等下一期。
- **明確不管**：補漏、執行中斷後的業務恢復、斷電持久性、時機分區。

## 表格式
兩張空表原文（wfnode init 可照抄；extracted 換成建立日期）：
```json
{"contract":"wf-table/1","source":"workflows/routines.md","extracted":"2026-10-09","columns":["name","every","inst","last_round","last_time","last_code"],"rows":[]}
{"contract":"wf-table/1","source":"workflows/schedule.md","extracted":"2026-10-09","columns":["name","at","inst","claimed"],"rows":[]}
```
欄位：name 是唯一名稱；every 是正整數加 r/s/m/h/d；inst 是目標路徑；last_round 是上次回合；last_time 是上次 ISO 本地時間；last_code 是結束碼或 running；at 是含日期的 ISO 絕對時刻（有時區或本地）；claimed 是本包寫的認領時間；timeout 是可選的正秒數，空＝600。contract 是表契約；source 是對照來源；extracted 是建立日期；columns 是欄名；rows 是列陣列。

## 界線
取樣：tock 漏掉就延後，不補跑。最多一次：被殺在跑前或跑中途就不重跑該期。routine 在 keep 任務裡同步跑，長的會延後其他項，timeout 預設 600 秒。「每天上班」那種時機分區留給 agent 的 tick 工作流。`.lock` 是 edit_json 的鎖，會留在 wf/。
