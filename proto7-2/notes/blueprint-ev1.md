# 事件保存第一版藍圖（ev1）：每 node 一個 `events/`、兩條通道、檔數固定

依據：[event-store 報告](reviews/2026-10-05/event-store.md) §6.1／§7／§11、[prior-art](reviews/2026-10-05/prior-art.md) §11.4／§11.5、[r5 統整](../../proto7/notes/thinking/2026-10-04-r5-synthesis.md)第 1 題、[下午計畫](plan-2026-10-09-pm.md) §4、[代定清單](decisions-2026-10-09.md)。接法仿 [history.py](../modules/history.py)（不改）。E0 隊 10-09。

逐件工作項已抽到 [blueprint-ev1-items.json](blueprint-ev1-items.json)（欄位 id、lane、title、files、how、test）。

## 1. 一句話

新模組 `modules/events/`：每 node 一個 `<node>/events/`，分**觀測（obs）**與**必讀（must）**兩條通道。寫者在鎖內追加、輪替、清垃圾；讀者不拿鎖、只讀完整換行的紀錄。

## 2. 硬約束（使用者 user-advice）

- **檔數固定**：`events/` 內只有 `obs.active.jsonl`、`obs.<首 seq 12 位>.jsonl`（≤N）、`must.active.jsonl`、`must.<首 seq>.jsonl`（≤N）、`state.json`、`state.json.lock`（`locked` 的 sidecar）。上限 2(N+1)+2＝12 檔（每通道各一套，見 §8 ①），寫 state 當下另有 1 個暫存；不每回合新檔、不開子夾。只有持鎖者寫 state，所以拿鎖後殘留的 `.state.json.tmp.*` 一律刪（不靠 pid 判斷）。
- **垃圾由寫的人清**：輪替當下做。obs 封存超過 N 刪最舊；must 只刪「整段都已確認」的封存段，未確認的永不刪（滿了停收，見 §5 ④）。
- 核心零改動；`.aosd/log.jsonl` 只續讀不裁；history.py 不動；三包今天不接。

## 3. 落盤格式（完整例子）

一行一筆，**以完整換行為紀錄邊界**（新契約，`read_jsonl` 不是這樣）；寫完 `flush`，不 fsync。`seq` 每通道從 1 起、只增不重用；封存段檔名用段內首筆 seq，輪替不改名意義。下例為排版折行，實檔一筆一行：

```json
{"v": 1, "stream": "team/obs", "seq": 42, "kind": "round.observed", "capture": "sample",
 "source": {"node": "team", "round": 17}, "at": "2026-10-09T13:02:11+08:00",
 "payload": {"last_round": {"round": 17, "summary": "…"}}}
{"v": 1, "stream": "team/must", "seq": 8, "kind": "demo.item.done", "capture": "published",
 "event_id": "team/demo/run-3/item-5", "source": {"node": "team", "task": "demo", "run": 3, "attempt": 1},
 "at": "2026-10-09T13:02:12+08:00", "payload": {"item": 5, "result": "ok"}}
```

- `capture`：`sample`（觀測最新檔，可能漏）、`source_log`（續讀 `.aosd/log.jsonl`）、`published`（合作來源主動交，必帶 `event_id`）。
- 取樣跳號另記一筆 `kind:"gap"`、`payload:{"from":r1,"to":r2,"why":"round_skip"}`；來源被換（log 變短或 inode 變）記 `why:"source_reset_unknown"`。
- 單筆上限 `max_record_bytes`（預設 64 KiB），超過回 `too_large` 不寫。

`state.json`（寫者在鎖內 `write_json` 原子換）：

```json
{"v": 1, "node": "team",
 "config": {"keep_segments": 4, "segment_bytes": 1048576, "max_record_bytes": 65536},
 "channels": {
  "obs":  {"next_seq": 43, "active_first": 40, "segments": [12, 24, 31], "dropped_upto": 11, "torn": 0},
  "must": {"next_seq": 9, "active_first": 1, "segments": [], "acked_upto": 5, "refused": 0, "torn": 1}},
 "sample": {"team": 17, "team/agents/amy": 9},
 "daemon_log": {"offset": 18234, "dev": 2049, "ino": 131077}}
```

**state 可由紀錄推回**：拿鎖後先恢復——活躍段尾不是換行就截到最後一個換行（`torn`+1；那筆沒回成功，來源會重送）；尾端有 `seq ≥ next_seq` 的完整紀錄就據以補 `next_seq`、`sample`、`daemon_log`；`active_first` 一律取活躍段首筆 seq（空則 `next_seq`）；封存檔與 `segments` 不符就以檔為準補列／移除並推 `dropped_upto`。輪替的目的檔已存在＝錯，回 `unknown`，絕不覆蓋。第一個寫者建 `state.json` 時寫入 config，之後以檔內為準。

## 4. 寫者、讀者、確認

- **寫者**＝取樣器（E1）與發布者（E2）。都經 `store.append`（§6）在鎖內寫；鎖逾時（`timeout=5`）或任何 OSError 都回 `unknown`，呼叫端照原 `event_id` 重送、不推進自己的進度。
- **發布去重**：同通道仍保留的紀錄裡已有同 `event_id` → 不再寫、回 `dup:true` 與原 seq；窗口＝仍保留範圍，超出即至少一次。
- **讀者**（E2）回 `records`、`next_cursor`、`earliest_cursor`、`coverage`、`gaps`、`errors`（§7.3）。游標＝下一個要讀的 seq（每通道各自）。游標早於最早仍保留者 → `gaps` 記 `retention`；取樣 gap、`source_reset_unknown` 一併列；壞 JSON 行與無法解釋的 seq 洞進 `errors`，游標不跨洞；無換行尾端不算。
- **兩種確認分開**：`append` 回成功＝保存確認（只抗程序 SIGKILL）；must 通道的**消費確認**＝`ack(events_dir, upto)` 推 `acked_upto`（第一版一個消費者）。讀到或 LLM 看過不算。

## 5. 五題代定（照 [pm](plan-2026-10-09-pm.md) §4；翻案位置＝改哪裡）

1. **保到哪**：合作來源逐件（`published`）＋明示取樣（`sample`／`source_log`），不承諾全系統每件都有。翻案：§3 `capture` 與 E1 取樣器範圍。
2. **用途**：obs＝回看，有界保留；must＝必讀，確認前保留；LLM 看過不算完成。翻案：§4 確認一節與 `ack`。
3. **落地單位**：先單 node（A 案），不做集中 B。翻案：另開 collector，本格式當來源暫存。
4. **滿了**：must 封存已 N 段且最舊未全確認、活躍段又滿 → 拒收回 `full`（`refused`+1），發布者不得當已保存、已發生的效果由它自留；obs 照刪最舊，讀者報缺口。翻案：store 的輪替函式一處。
5. **抗什麼中斷**：只承諾程序 SIGKILL 可接續（完整換行＋flush），不承諾斷電、不 fsync。翻案：寫入與輪替加 fsync，補斷電驗收。

## 6. 分線（領地互不重疊；細項見 json）

| 線 | 領地（皆在 `proto7-2/modules/events/`） | 件數 | done |
|---|---|---|---|
| **E1** 保存端＋取樣 | `aos7_events_store.py`、`aos7-events`、`spec.md`、`tests/test_events_store.py` | E1-1～E1-6 | append／半行／輪替／刪段各點 SIGKILL ×3 不丟不重；300 回合後檔數 ≤12、封存 ≤N |
| **E2** 發布＋讀者 | `aos7_events_pub.py`、`aos7_events_read.py`、`examples/`（`longrun/` 除外）、`tests/test_events_read.py` | E2-1～E2-5 | 重送同 `event_id` 不重複；壞尾／缺號／淘汰回 gaps／errors；游標接續；must 滿回 `full` |
| **E3** 整合長跑 | `README.md`（含契約卡）、`examples/longrun/`、`../README.md` 一列、`notes/problems.md` | E3-1～E3-3 | README 可照做；長跑檔數不長、垃圾會清 |

- **介面先凍結**（E2 依此寫，不等 E1）：`store.append(events_dir, channel, rec, *, node, config=None) -> {"ok", "seq", "dup", "why"}`（`why` ∈ `full`／`too_large`／`unknown`；`node` 與 config 規則見 E1-1）、`store.ack(events_dir, upto)`、`store.load_state(events_dir)`（唯讀、不恢復）。E2 讀者測試用手寫 fixture；發布測試等 E1 進 main 後 rebase 再跑全套（E1 15:15、E2 15:30）。
- 崩潰注入用 `aos7_fs.test_point("events:<點>")`＋`AOS7_TEST_CRASH`，子程序直接呼叫 store（aos7-run 會拿掉 `AOS7_TEST_*`）；不改 `tests/_proc.py`、`_hooks.py`。

## 7. 不做

集中收集（B）、fsync／斷電等級、三包接線、history.py 合併、核心出口（C2）、多消費者確認、跨 node 查詢。

## 8. 隊長代定（細節，好反悔）

① 「1 活躍＋N 封存」解讀為每通道各一套（兩通道留存規則不同，混放會誤刪必讀），總上限 12 檔，**請頂層核**；② must 已全確認的封存段照刪（責任完成即垃圾）；③ 預設段 1 MiB、單筆 64 KiB、鎖等 5 秒；④ 取樣進度放 `events/state.json`（與紀錄同鎖、可由紀錄推回），不放槽內 state；⑤ 半行截掉而非隔離成新檔（守檔數，那筆沒回成功）；⑥ 去重窗口＝仍保留範圍。
