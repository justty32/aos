# 給 codex 的任務書（第 6a 輪：第四批裁決 5 條回寫 spec，2026-09-05 晚上）

你在 /home/lorkhan/repo/simple_tools/aos 工作。規定在 wf/workflows/spec/（先讀 README.md、01-terms.md、notes/rulings-2026-09-05.md 看前三批怎麼回寫）。撞到這五題的原始紀錄在 proto/FINDINGS.md「codex 第 1 輪」「codex 第 2 輪」與 wf/workflows/spec/notes/janet-binding-findings.md（只讀，不改）。

硬規則：
- 不 commit、不 push、不 git add。
- 只准碰：wf/workflows/spec/01～13 各章（含 b 檔）、wf/workflows/spec/schemas/、wf/workflows/spec/notes/rulings-2026-09-05.md、wf/workflows/spec/data/conformance.json（若要加驗收列，用 wf/tools/tabledb.py，先看 notes/README.md 怎麼用）。**不准碰** proto/（另一輪 codex 正在改）、ideas/、notes/README.md。
- 每個 md ≤ 12 KB；條款不可改號不可刪號（作廢就在原號註明）；標籤〔裁決 2026-09-05〕／〔主編補〕。
- 改完 `bash wf/tools/wf-lint.sh` broken=0。全部大白話中文。

## 使用者今晚裁的（第四批，5 條）

| 編號 | 題目 | **定案** |
|---|---|---|
| Q-01 | 帳簿要不要加「思考 token」欄 | 加正式欄位 `tokens_reasoning`（整數或 null）；`tokens_out` 不含思考 |
| Q-02 | 「做事的格數」記在哪 | 接力棒 `series.json` 與停止原因檔 `stopped.json` 都加正式欄位 `busy_ticks`（整數）；定義：這一格至少執行了一步（inst／call／await 有進展）才算做事 |
| Q-03 | LLM 世界 `requests/` 放原件還是狀態物件 | 拆兩個資料夾：投遞物原件 rename 進 `llm-inflight/`（一字不動）；狀態物件另寫 `requests/<id>.json`（state／unit／request 摘要或路徑）；做完原件移 `llm-done/`（若 spec 已有 done 目錄就照既有名） |
| Q-04 | 子地停下沒寫結果、停止原因不是三種時，父看到哪種狀態 | daemon 對帳逐種映射：`idle`／`budget`／`steps_done` → `no_result`；`failed`／`parse_error`／`stalled` → `child_failed`；`signal`／`control_stop` → `killed`；狀態檔 `ext.stopped_reason` 保留原始原因 |
| Q-05 | 登記表 schema 跟原型打架 | schema 收編：`result`（結果落點絕對路徑，可 null）、`args`（物件，可 null）、`daemon_pid_start`（整數，可 null）升成登記表正式欄位；`ext.result`／`ext.args` 作廢 |

## 要做

1. 每條找到 spec 對應章節（Q-01→09／09b 帳簿條款與 `ledger.schema.json`；Q-02→05 接力棒、06 run 停止、`series.schema.json`、`stopped.schema.json`；Q-03→09／09b 與相關 schema；Q-04→08b daemon 對帳（S-08-7x 附近）與 07b 狀態檔 reason 列舉、`status.schema.json`；Q-05→08 登記表與 `registry.schema.json`），改寫或新增條款，標〔裁決 2026-09-05〕；純為了閉合而補的標〔主編補〕。schema 同步改，`additionalProperties:false` 的要把新欄加進 properties。
2. 章末摘要表同步。
3. notes/rulings-2026-09-05.md 末尾加「第四批：原型與 Janet 綁定撞到的 5 條（2026-09-05 晚上）」一節：編號、定案、動到哪幾條。
4. `bash wf/tools/wf-lint.sh` broken=0；`python3 -c "import json,glob;[json.load(open(f)) for f in glob.glob('wf/workflows/spec/schemas/*.json')]"` 不報錯。

回報：每條一行「編號：改了 S-xx-yy／補了 S-xx-zz／schema 檔名」，撞到的事，lint 結果。
