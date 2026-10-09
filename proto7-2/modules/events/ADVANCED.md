# events 進階

← [README（日常用法）](README.md)

日常只要 README 的 pub／read／ack。這份給要讓 daemon 自動記、要用全部選項，或要維護本包的人。


## 讓 daemon 自動記（選讀）

不用自己 pub，讓 aos daemon 每回合把「這個 node 跑到第幾回合」記進 obs。這要先懂 aos 的 daemon／node／keep 任務（見 [modules](../README.md) 與 `aos7-ctl --help`）；只用 pub／read／ack 可以跳過。在 repo 根貼上（`cd "$(git rev-parse --show-toplevel)"`）：

```sh
P=$PWD/proto7-2; R=$(mktemp -d); EV=$P/modules/events/aos7-events
python3 $P/bin/aos7-ctl daemon $R register n1
python3 $P/bin/aos7-ctl add $R/n1 '{"name": "events", "mode": "keep", "argv": ["python3", "'$EV'", "--status"]}'
python3 $P/bin/aos7-daemon $R &
sleep 3; $EV read --events $R/n1/events --text --limit 5
python3 $P/bin/aos7-ctl daemon $R stop --kill
```

`read` 會看到 `1 round.observed n1 {"last_round": {...}}` 這類紀錄。取樣器加 `--daemon-log` 會連 daemon 流水帳 `.aosd/log.jsonl` 一起記；daemon 只在 `$R/.aosd/log.on` 這個空檔存在時才寫流水帳，所以要 `touch $R/.aosd/log.on`。要看發布者怎麼「保存確認後才推進」，裝 `examples/demo_pub.tasks.json`（`<路徑>` 換掉）當 once 任務。

## 一覽

| 項目 | 內容 |
|---|---|
| 分類 | 事件保存模組，單 node；細部規則 [spec.md](spec.md)、藍圖 [blueprint-ev1](../../notes/blueprint-ev1.md) |
| 接法 | C 工具 `aos7-events pub`、`aos7-events read`、`aos7-events ack`，函式 `aos7_events_pub.publish`、`aos7_events_read.read`；A keep 任務 `aos7-events`（取樣器） |
| 預設 | 關，不裝就不存在 |
| 依賴 | 工具包任務端函式、核心 `aos7_fs` |
| 程式 | `aos7-events`、`aos7_events_store.py`、`aos7_events_pub.py`、`aos7_events_read.py`、`aos7_events_cli.py`（一行錯誤與共用 ack CLI） |
| 範例 | `examples/demo_pub.py`＋`demo_pub.tasks.json`（once）；`examples/longrun/`（長跑，見下） |
| 測試 | `python3 proto7-2/tests/run_all.py modules/events/tests` |

## 工具

`aos7-events read …`／`aos7-events pub …`／`aos7-events ack …` 是子命令，選項與 `python3 aos7_events_read.py`／`python3 aos7_events_pub.py` 相同；ack 入口在 `aos7_events_cli.py`：

- read：`--events`、`--channel obs|must`、`--cursor`、`--kind`、`--source`、`--round`、`--run`、`--limit`、`--text`、`--ack`（舊寫法，下一輪移除；須搭 `--channel must`，成功時 stderr 多一行請改用 `aos7-events ack`）。
- pub：`--events`、`--kind`、`--payload`（必填）、`--event-id`、`--must`、`--source`、`--node`、`--create`；payload／source 用 JSON，預設 obs。CLI 預設不建夾；第一次加 `--create` 才建，已有夾照舊寫。`--event-id` 不給就自動產生（結果多印 `event_id`，不防重複）；events 夾還沒建 state 時，`--node` 不給就用夾的上一層資料夾名。
- ack：`--events DIR [--channel must] N`，N 是非負整數；例：`aos7-events ack --events /tmp/demo/events 1`。
- `aos7-events --help` 看日常三個子命令；`--help-sampler` 看取樣器的完整選項（含 `--keep`、`--segment-bytes`）。

## 退出碼

照 [統一錯誤路徑](../../notes/blueprint-errors.md)；失敗時 stdout JSON 照舊，stderr 另印一行人話。

| 工具 | 0 做到了 | 1 做不到 | 2 參數不對 | 3 不確定 |
|---|---|---|---|---|
| pub | 存好，含 dup | full（must 滿了）、no_events（確定沒夾且未加 --create；權限等讀不到算 3） | 用法／JSON 錯、too_large | unknown（鎖忙、讀寫錯，可能存了也可能沒） |
| read | 讀完（errors／gaps 仍列在結果） | 沒 events 夾（拼錯路徑不會看起來像空帳本；函式 `read()` 照舊回空） | 用法／游標／limit 錯，--ack 未搭 must | 僅舊 --ack：沒 state、鎖忙、讀寫錯 |
| ack | 累積確認完成 | 沒 events 夾，什麼都不建 | 用法錯、N 非非負整數、通道非 must | 沒 state 或 state.json 是壞連結（不建鎖）、鎖忙、讀寫錯 |
| 取樣器 | 指定回合結束；未知回合跳過並留 stderr，下回合再試 | 未使用 | 選項錯、缺或壞 AOS7_ 任務環境，什麼都不建 | 未使用（keep 任務逐回合重試） |

本包不用 4。舊寫法 `read --ack` 成功時 stderr 多印一行「改用 aos7-events ack」（成功不印 stderr 的唯一例外，下一輪連同 --ack 移除）；失敗時仍只有那一行錯誤。pub unknown 用同 event_id 加 `--event-id` 照原樣再跑一次會接續；自動產生的 id 在結果裡。ack unknown 照同值重跑。

游標＝下一個要讀的 seq；把 `next_cursor` 帶回 `--cursor` 接續。ack 是累積確認，處理完才送。

## 檔案與檔數

`events/` 只放 `obs.active.jsonl`／`must.active.jsonl`、`<ch>.<12位段首seq>.jsonl` 封存段、`state.json`、`state.json.lock`；原子寫瞬間另有 `.state.json.tmp.<pid>`。恢復會清暫存；別刪鎖檔。

預設 keep 4：兩通道各一個 active＋四個封存，清完最多 12 檔。obs 超過刪最舊；must 只刪「整段都已 ack」的段，未 ack 而滿了就拒收新的（退出碼 1）。已發生的事不因拒收當沒發生，來源要自留證據。ack 本身不刪段，下次輪替才清。

`--keep`（≤4）、`--segment-bytes`（預設 1 MiB）只在初建 state 生效，之後以 state 為準。

## 契約卡

**保存端 `aos7_events_store`（append／ack／recover）**

- **職責**：持鎖 append／recover／ack、輪替清理；既有夾沒有 state 時 ack 回 0，不拿鎖、不建 state.json.lock。
- **前置條件**：node 一致，寫者走保存端，輸入合 spec。
- **保證**：完整換行、seq 只增；壞 state 不覆蓋；同通道窗口內重送回原 seq、dup。保存確認＝append 成功（含 dup），消費確認＝ack，讀到／LLM 看過不算；SIGKILL 後可恢復。
- **明確不管**：來源效果、窗口外去重、斷電。

**取樣器 `aos7-events`（keep 任務）**

- **職責**：取樣與續讀 log，寫 obs。
- **前置條件**：任務環境齊；單取樣器；來源 round 合法。
- **保證**：預設自身 node，`--src` 可重複；成功才推進進度；跳號／倒退記 gap，log 不裁改；未知跳過、下回合重試。
- **明確不管**：補漏、全系統逐件記錄、來源 log 大小。

**發布者 `publish`／`aos7-events pub`**

- **職責**：逐件 published 交保存端。
- **前置條件**：合法 kind／event_id／JSON、有效 node；同件沿用 id。
- **保證**：用法錯不寫；預設 obs；CLI 預設不建夾，--create 才允許初建（publish 函式沿用原行為）；full 未寫，unknown 未確定保存。
- **明確不管**：業務執行與回滾、來源進度、自動重送。

**確認者 `aos7-events ack`（與 `read --ack` 共用）**

- **職責**：確認 must 到 N 都已處理完，輸出 acked_upto。
- **前置條件**：既有 events 夾與 state、must 通道、非負整數 N。
- **保證**：沒夾不建；沒 state 回 unknown，不建鎖；成功累積確認，unknown 留證據、照同值重跑。
- **明確不管**：讀事件、判斷業務完成、當場清段。

**讀者 `read`／`aos7-events read`**

- **職責**：讀事件；CLI 的舊 --ack 與 ack 子命令共用確認流程。
- **前置條件**：合法游標與 limit；處理完才 ack。must 只有一個累積確認值：同一通道多個消費者時，各自只確認自己的事件、遇別人沒確認的就停（author、mail 都照這條）。
- **保證**：無鎖讀完整行，回 records、next_cursor、earliest_cursor、coverage、gaps、errors；不跨無法解釋的 seq 洞，不自動確認。
- **明確不管**：修壞紀錄、補漏、存游標、判斷業務完成。

## 已知限制

- 一個 events/ 只能一個取樣器。
- 取樣會漏，看得出缺號（gap）但補不回。
- status 去重只比最近一筆（A→B→A 記三筆）；保存失敗（如 too_large）的事件下回合重試。
- event_id 去重只在留存窗口內，需掃描。
- 單消費者。
- log 同 inode 截短又長回舊 offset 認不出。
- 不 fsync，只抗程序 SIGKILL、不抗斷電。
- 不做集中收集、多消費者、跨 node 查詢、三包接線、history 合併或核心出口。

## 長跑

[`examples/longrun/`](examples/longrun/README.md) 用真 daemon 掛取樣器＋發布者＋讀者三個 keep 任務跑 300 回合（段開小到 8 KiB）。10-09 實跑：有讀者時 events/ 最多 9 檔、obs 刪了 29 段、must 已 ack 段隨輪替清掉（`dropped_upto` 293）、讀者 300 件連號無錯；不裝讀者時 must 滿 4 段後拒收 205 次、未 ack 段一段沒刪、檔數停在 12；兩種 RSS 250 回合內漲 <100 KB、開檔數不累積、收掉後無殘留程序。
