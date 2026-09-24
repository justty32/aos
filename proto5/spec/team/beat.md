← [team](README.md)｜郵差：[post.md](post.md)｜問人：[ask.md](ask.md)

# 心跳：`aos-team beat`、`aos-team routine`

一支機械程式，kernel 反覆叫（`aos-team start` 登記，預設 60 秒一輪），**不叫模型**。照 `team/routines.json` 算誰到期，**以開單的方式**派出去。
程式：[`lib/aos_team_beat.py`](../../lib/aos_team_beat.py)。第 2 隊，2026-09-24 第 1 版。

## 兩個檔

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `team/routines.json` | **郵差**（申請 `kind: routine` 的處理函式 `on_routine`） | 例行的定義，`wf-table/1` |
| `team/beat.json` | **心跳** | 每條例行處理到哪一次、在途的那一次、上次結果 |

人不直接改 `routines.json`：用 `aos-team routine add/rm`（往 `team/outbox/human/` 放一份申請，郵差下一輪寫）。

**心跳有自己的身分 `beat`**（2026-09-24 使用者裁）：保留名（跟 `human`、`post` 一樣不能當成員名、不能當派工的負責人）；自己的寄件格 `team/outbox/beat/`；只能寄 `handoff`、`cancel` 兩種申請（不能替人答題、不能加例行）；寄的信信頭寫「心跳（定時器）」。成員都能回信給 `beat`（`team_say` 一定收這個名字），郵差只記下、不投。模型要加也是寄申請，而且要人批准（下面）。

```json
{"contract": "wf-table/1", "source": null,
 "columns": ["name", "every", "daily", "once", "tz", "to", "workflow", "goal", "done_when", "timeout_minutes",
             "retries", "added_by", "added_at", "q", "request"],
 "rows": [{"name": "count-md", "every": "2m", "daily": "", "once": "", "tz": "", "to": "worker-1", "workflow": "無",
           "goal": "數 p 裡的 md 檔數量寫進 notes/md-count.txt",
           "done_when": [{"kind": "file_exists", "path": "notes/md-count.txt"}],
           "timeout_minutes": "", "retries": "", "added_by": "human", "added_at": "2026-09-25T10:00:00+08:00",
           "q": "", "request": "1790000000000000000-5000-human"}],
 "removed_requests": []}
```

- 時間三選一：`every`（`30s`／`10m`／`6h`／`1d`，從 `added_at` 起算，登記當下就算第一次）、`daily`（`09:00`，照 `tz`，沒寫＝團隊的）、`once`（含時區的 ISO 時刻，一次性）。
  `tz` 要是認得的 IANA 名字（打錯＝`BadRoutine`，不默默變本機）；到期一律換成 UTC 比；夏令重複的那一小時取第一次，跳過的那一小時照 zoneinfo 往後推。
  （申請本身已經有 `at`＝寄出時間，所以一次性的叫 `once`；catalog 也已改成 `once`。）
- `done_when`：同任務單（[tasks.md](tasks.md)），**一定要有**——心跳派的單一樣走驗收。
- `timeout_minutes`：寫進那張單的 `deadline_minutes`，到了郵差把單子判 failed。`retries`：這一次失敗後重派幾次（0～5，預設 0）。

## 申請 `kind: routine`

`{"id", "from", "kind": "routine", "at", "op": "add"|"rm", "name", …上表的欄位}`。處理登記在 `aos_team_requests.KINDS`。

- `add`：人寄的直接生效（`added_by: human`）；**成員寄的**（模板 `may` 要有 `routine`）加一列 `added_by: <成員>`，同時開一題問人（`q-NNNN`，選項「批准／不要」）。
  名字重複＝`NameTaken`；欄位不對＝`FormatInvalid`／`BadRoutine`／`BadAssignee`（郵差退件給寄件人）。
- `rm`：人或提出的成員能拿掉；沒有這條＝`NoSuchRoutine`。
- 冪等：同一份申請（列的 `request`、`removed_requests`）再來不多做。

## 授權

只有兩種列會自動跑：`added_by: human`；或成員提的、那一題被人用 `aos-team answer q-NNNN 批准` 答了（答案是「批准／同意／好／可以／yes／y／ok／approve」之一）。
沒答、答別的（例「不要」）＝不跑，`routine ls` 會寫原因。

## 一輪

同一時間只有一個心跳（`team/.beat.lock`）。對每條有授權的例行：

1. **有在途的那一次**：找那份派工申請開出的單（`find_by_request`）——
   - 還沒開單（申請還在 outbox 或郵差剛收）＝等；申請檔不見了＝補寫同一份（不覆蓋）；
   - 單子 `done`＝這一次完成：記 `handled`（處理到哪一次）、`last_run`（現在）、`last_result: done`；一次性的標成 `finished`；
   - 單子 `failed`／`cancelled`，或郵差退了申請＝這一次失敗：還有 `retries` 就重派同一個時刻（第 n 次），用完＝記 `last_result: failed`，寄報告；
   - 其他＝在途，**不重派**。
2. **沒有在途**：算「現在以前最近的一次到期」；比 `handled` 新就派這一次。中間漏掉的（`handled` 之後、這一次之前）**不補**，漏了 2 次以上寄一封報告「到 … 為止有 N 次沒跑，只補最近一次」。

**派出**＝先把在途寫進 `beat.json`，再往 `team/outbox/beat/` 放一份 `handoff` 申請（寄件人 `beat`；授權來源仍是「人登記或人批准」這一列）：
id＝`<那一次的 epoch 秒×10⁹＋第幾次>-<「名字｜登記它的申請 id」的 crc32>-beat`，重跑算出來一樣、不覆蓋；刪掉再重加同名的是新的一條，不會沿用舊單；`goal` 前面加 `〔例行 名字 @ 09-25 10:00〕`，`workflow` 沒寫＝`無`。
郵差開單、派給 `to`；單子的開單人是 `beat`，派工信多一行「這張單是心跳（定時器）照例行派的」，叫負責人做完回 DONE 給 `beat`。
**做完不寄信給人**（2026-09-24 使用者裁）：只有異常才寄——單子 failed（驗收三次沒過、負責人回 FAILED）、逾時（`timeout_minutes` 到）、檢查器壞（[verify.md](verify.md)）、重派用完、漏跑、卡住等人（負責人回 BLOCKED／NEEDS-USER 給 `beat` 時，郵差另寄一封給人；原信就是寄給人的不重複）。

**報告**（漏跑、失敗）：先記進 `beat.json` 那條的 `reports`（跟「放棄這一次」「派出」同一次寫），再寫進 `team/outbox/beat/`（一封給每個領隊、一封給人，`from: beat`、`PROGRESS`；id＝`<crc>-<crc>-beat`，由事件、這條例行、收件人算出來、不覆蓋），全寫好才從 `reports` 拿掉；崩在中間下一輪照寄。郵差投。

## 指令

| 指令 | 做什麼 |
|---|---|
| `aos-team routine add NAME (--every 2m｜--daily 09:00｜--once ISO) --to 成員 --goal "…" (--done-file 路徑…｜--done-when JSON) [--workflow W] [--tz TZ] [--timeout 分] [--retries N]` | 驗過就寄申請，印「已交給郵差」 |
| `aos-team routine rm NAME` | 寄拿掉的申請 |
| `aos-team routine ls [--json]` | 一行一條：`count-md  every 2m → worker-1  人登記的  上次 09-25 10:04（done）  下次 09-25 10:06`；在途的寫「在途：… 那一次」 |
| `aos-team beat [--quiet]` | 走一輪（kernel 反覆叫） |
| `aos-team start`／`stop`（第 1 隊） | 會叫 `aos_team_beat.start(團隊資料夾)`：登記 `team-beat-<資料夾名>`，60 秒一次 |

`routine import`（把 workflows 的 `routines.md`／`schedule.md` 表抄過來）這一版沒做。

## 模型端：`routine_propose` 工具（第二波 C 隊補）

第一波這裡只寫好郵差怎麼處理成員提的 `add`（開一題問人），但沒有模型能叫的工具——第二波 C 隊補上
[`tools/task/routine_propose`](../../tools/task/routine_propose)：領隊（模板 `may` 要有 `routine`，`templates/lead/template.json` 已加）
填跟 `aos-team routine add` 一樣的欄位（`name`、`every`／`daily`／`once` 三選一、`to`、`goal`、`done_when`…），
工具只做輕量的本地檢查（缺欄位、格式明顯不對）就寄出 `kind: routine, op: add` 申請；郵差那邊的 `on_routine`
沒有變——照樣加一列 `added_by: 領隊名`、開一題問人，人 `aos-team answer q-NNNN 批准` 才會被心跳排進去。
也支援 `op: rm`（拿掉自己提過的那條；人或提出的成員都能拿掉，郵差驗）。
