# 給 codex 的任務書（第 6b 輪：原型照第四批裁決改，2026-09-05 晚上）

你在 /home/lorkhan/repo/simple_tools/aos 工作。能跑的 Python 純標準庫原型在 proto/（先讀 proto/README.md、proto/FINDINGS.md 的「codex 第 1 輪」「codex 第 2 輪」兩節）。規定在 wf/workflows/spec/（只讀；另一輪 codex 正在改它，不要依賴它的最新內容，照下面的定案做）。

硬規則：
- 只准碰 proto/aosp/、proto/tests/、proto/doorman-tests/、proto/FINDINGS.md、proto/README.md。**不准碰** proto/play/、proto/play-chat.sh（使用者正在玩）、proto/examples/（除非測試非改不可，改了要說）、wf/、core/。不 commit、不 push、不 git add。
- Python 只用標準庫。改完 `bash proto/run-all.sh` 全綠、`python3 -m unittest discover proto/doorman-tests` 全綠。
- 撞到的記 proto/FINDINGS.md 末尾新節「codex 第 6 輪」。回報大白話中文。

## 使用者今晚裁的（第四批，5 條）——原型要照這個

| 編號 | 定案 | 原型要做 |
|---|---|---|
| Q-01 | 帳簿正式欄位 `tokens_reasoning`（整數或 null），`tokens_out` 不含思考 | 現在已這樣寫；確認每行都有這欄（不會思考的模型填 null），補測試 |
| Q-02 | `series.json` 與 `stopped.json` 都有正式欄位 `busy_ticks`；定義：這格至少執行了一步才算 | 現在已寫；確認定義一致（純空等的 await 格不算），`aos status` 印「格 N（做事 M）」，補測試 |
| Q-03 | 投遞物原件 rename 進 `llm-inflight/`（一字不動）；狀態物件另寫 `requests/<id>.json`（`state`／`unit`／`request` 欄，request 放原件路徑或摘要）；做完原件移 `llm-done/` | 第 1 輪把原件搬進 `requests/`，現在要改成兩個資料夾；`aos llm ls` 讀狀態物件；重啟後 `unknown_after_restart` 改名 `result_unknown`（跟 spec 帳簿字彙一致）；`proto/play-agent.sh` 第 193 行附近收檔段改收 `llm-done/` 與 `requests/`（這支這輪准改） |
| Q-04 | daemon 對帳逐種映射：`idle`／`budget`／`steps_done` → `no_result`；`failed`／`parse_error`／`stalled` → `child_failed`；`signal`／`control_stop` → `killed`；狀態檔 `ext.stopped_reason` 留原始原因 | 改 proto/aosp/registry.py 的映射；每種各一個測試 |
| Q-05 | 登記表正式欄位 `result`（絕對路徑或 null）、`args`（物件或 null）、`daemon_pid_start`（整數或 null）；`ext.result`／`ext.args` 作廢 | 原型改成只寫頂層三欄（每筆都有，沒有就 null），不再寫 ext.result／ext.args；讀的地方相容舊 ext 一次（讀到就搬上來） |

## 順序

Q-05 → Q-04 → Q-03 → Q-01 → Q-02，每項做完跑 `python3 -m unittest discover -s proto/tests -t .`。最後 `bash proto/run-all.sh`。

回報：每條一行「做了／沒做＋檔案＋測試名」，撞到的事，run-all 結果。
