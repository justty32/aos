← [team](README.md)｜任務單：[tasks.md](tasks.md)｜郵差：[post.md](post.md)

# 驗收員：`aos-team verify`

照任務單的 `done_when` 跑**固定的檢查器**，每條回「過／不過／檢查失敗」。不叫模型；不執行專案裡的任何檔；沒有「跑任意指令」這種條目。
程式：[`lib/aos_team_verify.py`](../../lib/aos_team_verify.py)。第 2 隊，2026-09-24 第 1 版。

- 郵差收到 DONE 時**提交成一次性工作**（[post.md](post.md)），下一輪收結果檔；
- 人：`aos-team verify t-0001` 直接看（只讀，不改任何檔）；
- `judge` 條目歸審查員，這裡不跑、結果裡不列（人看的輸出最後列成「略過」）。

## 條目

路徑一律相對專案資料夾（`team.json` 的 `project`）；解開符號連結後在專案外＝檢查失敗。

| 條目 | 參數 | 過 |
|---|---|---|
| `{"kind": "file_exists", "path"}` | — | 路徑在（檔或資料夾） |
| `{"kind": "table_filled", "path", "column"?, "columns"?, "heading"?}` | `column`（一欄）或 `columns`（陣列），都沒給＝全部欄；`heading`：Markdown 挑哪個標題底下的第一張表 | 每一列那幾欄都非空；0 列＝不過。`.json` 要是 `wf-table/1`（`rows` 物件陣列）或物件陣列；`.csv` 第一列是欄名；其他當 Markdown |
| `{"kind": "check", "name", "args"?}` | 看檢查器 | 看檢查器 |

檢查器（`CHECKS` 登記表，`名字 → 模組:函式`）：

| 名字 | args | 過 |
|---|---|---|
| `contains` | `path`、`text` | 檔裡有這段字 |
| `not_contains` | `path`、`text` | 檔裡沒有 |
| `wf_residue` | — | 專案所有 `.md` 的 `{{`、〔導入判斷〕、〔模板說明〕都是 0；有讀不到的 `.md`＝檢查失敗（不當成 0） |
| `wf_lint_strict` | — | wf 工具包**自帶快照**的 `wf-lint.sh --strict` 退 0；檢查器本身壞了（退出碼不是 0／1、沒印 TOTAL、逾時）＝檢查失敗 |

後兩支叫第 3 隊的 `tools/wf/_wf.py`（`residue`、`lint`），跑的是工具包裡的快照，不是專案裡那份。
別隊加檢查器：`CHECKS` 加一行；函式 `fn(專案資料夾: Path, args: dict) → (過了沒, 一句白話)`，沒辦法判就丟 `CheckError`（＝檢查失敗）；函式自己的例外也只算那一條檢查失敗。

## 結果

```json
{"task": "t-0001", "rev": 1, "attempt": 2, "pass": false, "at": "2026-09-25T10:05:00+08:00",
 "results": [{"i": 0, "kind": "file_exists", "result": "pass", "pass": true, "why": "AGENTS.md 在"},
             {"i": 1, "kind": "check:wf_residue", "result": "fail", "pass": false, "why": "{{ 3、〔導入判斷〕 0、〔模板說明〕 1（AGENTS.md:3、…）"}]}
```

- `i`＝`done_when` 裡的原編號；`result` 三種 `pass`／`fail`／`error`（檢查失敗）；`pass`＝`result == "pass"`。
- 整份 `pass`＝每條機械條目都過（有檢查失敗也算沒過）。郵差把 `results` 原樣交給 `verified` 事件，修正信裡逐條列「過／不過 i. why」。
- **檢查失敗也會用掉工人一次機會**：例如 wf 工具包的快照壞了，三次後單子 failed，人會收到 FAILED 與逐條原因。

## 指令

```sh
aos-team verify t-0001 [--json] [--rev R --attempt A] [--out FILE] [--target 團隊資料夾]
```

印：

```text
t-0001 rev1 第 2 次 驗收：不過（1/2 條過）
  過   0. file_exists：AGENTS.md 在
  不過 1. check:wf_residue：{{ 3、…
  略過 2. （審查員判）原意沒變
```

全過退 0；沒過退 1（stderr `aos-team: NotPassed: t-0001 驗收沒過`）；單不在、名冊壞了＝退 1、代號照 `aos-team` 慣例。
`--rev`／`--attempt`：郵差用，寫進結果，讓郵差對得上是哪一次（對不上的結果任務單會忽略）；`--out`：結果另寫一份檔（暫存檔＋rename）。
