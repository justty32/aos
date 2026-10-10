# MN3 A／B 驅動準備回報

已新增三支標準庫腳本；未 commit、未呼叫真 AI、未改 packs。離線證據在 [offline/compare.md](offline/compare.md)，原始完整輸出保留於 `/home/lorkhan/repo/simple_tools/aos-wt/MN3.tmp/driver/`。

用法（下列 `E` 是本 evidence 的絕對路徑）：

```sh
E=/home/lorkhan/repo/simple_tools/aos-wt/MN3/proto7-2/notes/play/2026-10-10-menu-ab/evidence
# cwd 必須為學徒 node；真 AI 時由外部開 budget/llm ledger。
python3 -B "$E/driveab.py" A gap 1 /絕對路徑/out/A1-gap --tag S
python3 -B "$E/driveab.py" B mailcount 1 /絕對路徑/out/B1-mailcount --offline
python3 -B "$E/compareab.py" /絕對路徑/runs
# 清單每行 GROUP TASK REP；預設 node/runs/log 位於 MN3.ab。
python3 -B "$E/queue.py" /絕對路徑/jobs.txt --jobs 3 --token-cap 2700000
# 離線自測可指定 --root，避免與正式帳混用。
python3 -B "$E/queue.py" /絕對路徑/jobs.txt --offline --jobs 2 --root /絕對路徑/offline
```

Token 量法：A 加總 `llm.used` 與 `review.llm.used`；B 加總 `state.json.calls[].used`（包括 bad 重問），以及透明擷取入口保留的 author 回條 `review.llm.used`。兩組採相同帳本結算口徑，審查不算學徒 calls。`used = min(usage.total_tokens, reserve)`，所以超額時可能低於 provider 原始用量；原始回條留存可追查。缺 used 記 `token_missing`，compare 將③標無法判定；離線沒有模型帳，用量為零。A 離線 calls=0；B 練習每次回答仍算一次流程呼叫，便於驗證重問統計。B 每步回覆／真模型 llmcall 證據保留於 `steps/`，選單狀態、log、交件與葉子回條分別保留。

A format_blocks 固定 rule 清單：`text`、`json`、`schema`、`size`。依現行 `aos_three_gates.py`，段頭錯／沒有段頭／重複段名是 text；缺 row/report 段、欄位錯是 schema；不是獨立的 header/format rule。不把 territory/layout/readme 等全部第一關阻擋混入 A 格式計數。B 則是全部第一關阻擋＋log 的 bad 次數（照指定定義）。

離線結果：

| 測項 | 結果 |
| --- | --- |
| A mailcount 1 | exit 0，三關全過；rounds 1、calls 0、reasks 0、format_blocks 0、token 0 |
| B mailcount 1 | exit 0，三關全過；rounds 2、calls 15、reasks 1、fails {1:0,2:1,3:0}、format_blocks 1、token 0 |
| compare 兩份 summary | exit 0；印兩組 mailcount 表、三題空表與「次數不足」，正式判準無資料 |
| queue 兩行 A/B mailcount 2 | exit 0；started 2、completed 2、peak_active 2，兩題都過 |
| queue 用量 11／上限 10 | exit 3；started 0、remaining 2、stop token-cap |
| B 退 3 重跑 | 離線 stub 驗證兩次 argv 完全相同、最多兩次、stop exit-3-twice |
| 已有 summary 重跑 | exit 2；保護既有證據 |
| compare 合成 30 筆 | 驗證三種結論與 1/3、1.3 邊界、空資料／壞路徑 |
| queue 額外路徑 | fake driver 驗證第一題完成後停止新派工；本機 budget init/status/ledger 起停與沿用帳本通過，沒有模型呼叫 |

限制：AP4 三題 brief 目前仍可能退 2，驅動會留下 brief 原文／stderr 與 summary stop，不修改需求或摘要。未驗證真模型呼叫與 token 品質。用量上限只控制「新派工」，手上工作及預留額可使最終用量超限。比較請將同模型、審查、tag 批次與 offline 分開資料夾；混模型／審查／離線會提示，但仍照實際讀入資料印表。選單 run 名採 rid，因此同 node 重跑同 rid 必須換 rep/tag；已有未完成 out/req 也退 2，保留現場。未跑 C++ 全套，這次只有新增離線實驗腳本，沒有重構或改既有程式。
