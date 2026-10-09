# routines／schedule 進階

← [README（日常用法）](README.md)

## 讓它自己定時跑

`ls --run` 是手動看一次；要它一直自己看，就讓 aos 的背景程式 daemon 每次心跳叫起 routines。`add` 只登記清單，**不裝任務**；`aos7-up` 起的 node 已裝好，自己 register 的 node 要用 `aos7-ctl add` 裝 keep 任務。在 repo 根貼上：

```sh
cd "$(git rev-parse --show-toplevel)"
P=$PWD/proto7-2; ROOT=$(mktemp -d); R="$P/modules/routines/aos7-routines"; N="$ROOT/n1"
python3 "$P/bin/aos7-ctl" daemon "$ROOT" register n1
python3 "$P/bin/aos7-ctl" add "$N" '{"name": "routines", "mode": "keep", "argv": ["python3", "'$R'"]}'
echo '{"interval_ms":200}' > "$N/.aos/timeline.json"   # 每 0.2 秒醒一次，示範用
printf '#!/bin/sh\necho hello\n' > "$N/hello.sh"; chmod +x "$N/hello.sh"
"$R" add "$N" hello --every 3r hello.sh                  # 每 3 回合一次
python3 "$P/bin/aos7-daemon" "$ROOT" > "$ROOT/daemon.log" 2>&1 & D=$!
sleep 3
"$R" ls "$N"
python3 "$P/bin/aos7-ctl" daemon "$ROOT" stop --kill; wait "$D"
```

2026-10-09 實跑 `ls` 輸出（回合數會不同）：

```text
routine hello  every 3r  last 10  code 0  next round 13
```

`last` 有數字就表示自己跑過了。register／add／stop 印控制檔或任務表的位置；daemon 跑時程式輸出在 `$N/.aos/tasks/routines/out.log`。`r` 型只有心跳來才算，`ls --run` 不跑它。

## 一覽

| 項目 | 內容 |
|---|---|
| 接法 | A 普通 keep 任務＋C 工具（add／ls／rm） |
| 預設 | 關；add 不裝任務，裝 keep 任務交 aos7-up 或 aos7-ctl add |
| 依賴 | Python 3.11+ 標準庫、核心 aos7_fs／aos_exec、工具包 task_env／wait_tock |
| 程式 | `aos7-routines` 是入口；`aos7_routines.py` 管理清單與 `step(node, round, now)`（round=None＝手動 ls --run） |
| 測試 | `tests/test_routines.py`：兩張表、CLI 錯誤與副作用、真 keep、SIGKILL 窗口 |

## 退出碼

| 碼 | 一句話與本包何時出現 |
|---|---|
| 0 | 做到了：add／rm／ls 成功；inst 不在仍已登記，警告不改成失敗 |
| 1 | 做不到：名字撞名、rm 找不到（含空清單） |
| 2 | 你給的不對：參數缺漏、間隔／時刻／timeout 格式錯、無子命令又缺任務環境；不寫表 |
| 3 | 不確定：讀寫故障、壞表或鎖忙；保留表與已有證據，依訊息修好後重試 |

全 aos 共用表見 [blueprint-errors](../../notes/blueprint-errors.md)。錯誤在 stderr 一行：`aos7-routines: 發生什麼。怎麼辦`；3 以「不確定：」開頭，鎖忙等一下照原樣重跑。`--help` 一屏、退 0。keep 任務的 step 遇 unknown 會印警告並留到下次心跳再試。

## 契約卡／規則
- **職責**：收到 tock（daemon 每回合給任務的通知）後判兩張表到期、同步跑 inst（要跑的程式）；外部指令只有 `add <node> <name> (--every 間隔 | --at ISO或+90s) <inst> [--timeout 秒]`、`ls <node> [--run]`、`rm <node> <name>`。`ls --run` 在本程序做一次不帶回合的 step：秒型 routine 與 schedule 照時間判，r 型跳過。
- **前置條件**：表遵守 wf-table/1，name 唯一、值都是字串、缺欄視為空；所有寫者用 edit_json 鎖。相對 inst 以 node 為準。
- **保證**：缺表無事；讀不到、壞表、非 rows 陣列＝整表 unknown，下回合重試；壞列印原因並跳過。退出碼 0 做到、1 撞名／找不到、2 用法／格式錯、3 不確定。add 只寫 wf/ 的表；rm 沒表不建任何檔。手動 `ls --run` 與 daemon 同時跑也由同一把鎖保證最多一次。
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

## 測試指令

從 repo 根跑（限制程序數，`-B` 不產生快取）：

```sh
systemd-run --user --scope -q -p TasksMax=300 python3 -B proto7-2/tests/run_all.py modules/routines/tests
```
