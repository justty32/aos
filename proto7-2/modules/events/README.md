# events 事件保存包（第一版）

← [modules](../README.md)

**一個 `events/` 夾就是一本帳：`pub` 寫一筆、`read` 讀出來。檔數固定，舊的自己清。**

## 先懂這五個詞（照第一次跑出現的順序）

1. **events 夾**：放事件的資料夾，`pub` 第一次寫時自動建。
2. **seq**：每筆的編號（1、2、3…）。`read --text` 最後一行 `# next_cursor 2` 是「下一個要讀的 seq」，想接著讀時帶給 `--cursor`，不接著讀就不用管。
3. **obs／must**：夾裡兩本帳。obs＝一般紀錄，滿了丟最舊的（預設寫這本）；must＝一定要有人處理完的，用 `--must` 寫、`--channel must` 讀。
4. **ack**：對 must 說「seq 到這裡都處理完了」。讀到不算，ack 了才算；沒 ack 的一直留著，滿了 must 就拒收新的。
5. **event_id**：一件事的身分。同 id 再 pub 一次不會多一筆（回 `dup true`），所以失敗了可以放心重送。不給 `--event-id` 就自動產生一個（印在結果裡，這種不防重複）。

## 第一次跑（不用 daemon，約 1 分鐘）

在 repo 根貼上就能跑（`P`、`E` 自動帶好，不用改）。

**一、寫一筆、讀出來（obs）**

```sh
P=$PWD/proto7-2; E=$(mktemp -d)/n1/events; EV=$P/modules/events/aos7-events
$EV pub  --events $E --kind hello --payload '{"msg": "hi"}'
$EV read --events $E --text
```

```text
{"ok": true, "seq": 1, "dup": false, "why": null, "event_id": "auto/3f0c…"}   # 存好了，編號 1；event_id 是自動給的（每次不同）
1 hello n1 {"msg": "hi"}      # seq kind 誰寫的 內容（「誰寫的」n1 取自路徑，不用管）
# next_cursor 2               # 下一個要讀的 seq
```

**二、一定要處理的事（must）：寫、重送、讀、ack**

```sh
$EV pub  --events $E --kind job.done --payload '{"id": 7}' --event-id job/7 --must
$EV pub  --events $E --kind job.done --payload '{"id": 7}' --event-id job/7 --must
$EV read --events $E --channel must --text
$EV read --events $E --channel must --ack 1
ls $E
```

```text
{"ok": true, "seq": 1, "dup": false, "why": null}
{"ok": true, "seq": 1, "dup": true, "why": null}   # 同 event_id 重送：還是 seq 1，沒多寫
1 job.done n1 {"id": 7}
# next_cursor 2
{"acked_upto": 1}                                  # 1 號處理完了
must.active.jsonl  obs.active.jsonl  state.json  state.json.lock
```

看到兩本帳各一筆、重送 `dup true`、`acked_upto 1` 就成功了（10-09 實跑）。完整選項：`$EV pub --help`、`$EV read --help`。

---

以下是進階參考，第一次跑用不到。

## 讓 daemon 自動記（選讀）

不用自己 pub，讓 aos daemon 每回合把「這個 node 跑到第幾回合」記進 obs。這要先懂 aos 的 daemon／node／keep 任務（見 [modules](../README.md) 與 `aos7-ctl --help`）；只用 pub／read 可以跳過。在 repo 根貼上：

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
| 接法 | C 工具 `aos7-events pub`、`aos7-events read`，函式 `aos7_events_pub.publish`、`aos7_events_read.read`；A keep 任務 `aos7-events`（取樣器） |
| 預設 | 關，不裝就不存在 |
| 依賴 | 工具包任務端函式、核心 `aos7_fs` |
| 程式 | `aos7-events`、`aos7_events_store.py`、`aos7_events_pub.py`、`aos7_events_read.py` |
| 範例 | `examples/demo_pub.py`＋`demo_pub.tasks.json`（once）；`examples/longrun/`（長跑，見下） |
| 測試 | `python3 proto7-2/tests/run_all.py modules/events/tests` |

## 工具

`aos7-events read …`／`aos7-events pub …` 是子命令，選項與 `python3 aos7_events_read.py`／`python3 aos7_events_pub.py` 完全相同：

- read：`--events`、`--channel obs|must`、`--cursor`、`--kind`、`--source`、`--round`、`--run`、`--limit`、`--text`、`--ack`。
- pub：`--events`、`--kind`、`--payload`（必填）、`--event-id`、`--must`、`--source`、`--node`；payload／source 用 JSON，預設 obs。`--event-id` 不給就自動產生（結果多印 `event_id`，不防重複）；events 夾還沒建 state 時，`--node` 不給就用夾的上一層資料夾名。
- pub 退出碼：0 成功（含重送 dup）／2 用法（含超限）／3 full（must 滿了被拒）／4 unknown（可能已保存，照同 event_id 重送）。
- read `--ack` 要搭 `--channel must`：0 成功／4 unknown（照同值重送）；用法錯退出 2。

游標＝下一個要讀的 seq；把 `next_cursor` 帶回 `--cursor` 接續。ack 是累積確認，處理完才送。

## 檔案與檔數

`events/` 只放 `obs.active.jsonl`／`must.active.jsonl`、`<ch>.<12位段首seq>.jsonl` 封存段、`state.json`、`state.json.lock`；原子寫瞬間另有 `.state.json.tmp.<pid>`。恢復會清暫存；別刪鎖檔。

預設 keep 4：兩通道各一個 active＋四個封存，清完最多 12 檔。obs 超過刪最舊；must 只刪「整段都已 ack」的段，未 ack 而滿了就拒收新的（退出碼 3）。已發生的事不因拒收當沒發生，來源要自留證據。ack 本身不刪段，下次輪替才清。

`--keep`（≤4）、`--segment-bytes`（預設 1 MiB）只在初建 state 生效，之後以 state 為準。

## 契約卡

**保存端 `aos7_events_store`（append／ack／recover）**

- **職責**：持鎖 append／recover／ack、輪替清理。
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
- **保證**：用法錯不寫；預設 obs；full／unknown 不算保存。
- **明確不管**：業務執行與回滾、來源進度、自動重送。

**讀者 `read`／`aos7-events read`**

- **職責**：讀事件；CLI 另可 ack。
- **前置條件**：合法游標與 limit；must 單消費者，處理完才 ack。
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
