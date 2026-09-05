# 給 codex 的任務書（aos 新實作原型，2026-09-05）

你在 /home/lorkhan/repo/simple_tools/aos 工作。這是一個「另起爐灶」的專案：舊系統在 core/（不准當憑據、不准改），新規定在 wf/workflows/spec/（先讀 README.md 與 01-terms.md，需要哪份再讀哪份），能跑的 Python 純標準庫原型在 proto/（先讀 proto/README.md 與 proto/FINDINGS.md 前兩節）。

硬規則：
- 只碰任務書點名的路徑；不 commit、不 push、不 git add。
- Python 只用標準庫；跑法 `python3 proto/aos.py <子命令>`；改完一定跑 `bash proto/run-all.sh` 全綠（測試 `python3 -m unittest discover proto/tests`）。
- 撞到 spec 沒講或不合理的，記進 proto/FINDINGS.md 末尾新開一節「codex 第 N 輪」，格式照該檔「每條怎麼讀」。
- 回報用大白話中文：做了什麼（檔案路徑）、測試結果、沒做完的、撞到的。

# 第 1 輪：原型隊留下的交接清單（LLM 世界的可見度與帳簿）

只准碰：proto/aosp/llm.py、proto/aosp/status.py、proto/aosp/cli.py、proto/aosp/run.py（只為 status 的格數計算）、proto/examples/agent/brain.py 與 proto/examples/agent-real/brain.py（兩份是同一份副本，改要一起改）、proto/tests/（加測試）、proto/FINDINGS.md（末尾加「codex 第 1 輪」一節）、proto/README.md（子命令說明若變）。**不准碰** proto/doorman.py、proto/doorman-tests/、proto/examples/team/、proto/play-team.sh、proto/bench/、proto/play-logs/（別隊正在寫或已定案）。

背景先讀：proto/FINDINGS.md 的「真模型第一輪」那節（8 條發現）、wf/workflows/spec/09-llm-world.md 與 09b-llm-queue.md（LLM 世界的規定）、schemas/ledger.schema.json、schemas/llm-request.schema.json。

要做（照順序，每做完一項跑一次 `python3 -m unittest discover proto/tests`）：
1. `aos llm serve` 的 stdout 沒 flush，長請求期間 log 是 0 位元組：改成行緩衝（`sys.stdout.reconfigure(line_buffering=True)` 或每次 print 帶 flush），每筆請求送出時印一行「<request_id> 送出 <unit>，等待中」、回來時印一行「<request_id> 回來 <ms> ms <tokens>」。
2. LLM 世界缺「在飛的請求」狀態：收件匣裡分不出「排隊中」與「已送出等回話」。做法：送出前把該投遞物搬到 `.aos/llm-inflight/<id>.json`（原子 rename），回來後搬到 `.aos/requests/<id>.json`（spec 09 用的名字；若原型現在叫 llm-done/ 就改成 requests/ 並更新所有引用與 README）。`aos llm ls` 印三欄：排隊中／在飛／已完成，各幾筆與最舊一筆等了多久。重啟後 llm-inflight/ 裡的請求＝結果不明，照 spec「送出後斷線不重送」：寫 `<result>.status.json` reason `unknown_after_restart` 並搬到 requests/。
3. `max_wait_ms` 預設 30000 會誤殺本機慢模型的排隊請求：預設改為 600000，並且「排隊等待」與「後端回話」分開計時——等待上限只算排隊時間，送出後不再因 max_wait_ms 被殺（後端逾時另有 unit 的 timeout，沒有就不限）。play-agent.sh 若有硬調 600000 的地方可以拿掉（那個檔可以改這一行）。
4. 帳簿 `tokens_out` 把模型思考與輸出算在一起：若後端回應有 `usage.completion_tokens_details.reasoning_tokens`（OpenAI 相容）就拆成 `tokens_out`（純輸出）與 `tokens_reasoning`；沒有就 `tokens_reasoning: null` 並在 README 明寫「本機模型分不出」。schemas/ledger.schema.json **不准改**（spec 隊的）；在 FINDINGS 記「schema 要加 tokens_reasoning 欄」。
5. `aos status` 印的 `tick`（實測 612）跟真做事的格數（21）差 20 倍：接力棒或 stopped.json 多記 `busy_ticks`（該格至少有一筆指令跑或有串前進才算），`aos status` 兩個都印：「格 612（做事 21）」。
6. `brain.py`：每圈做成沒做成沒往機器面報。每圈結束寫 `rounds/<NNN>/round.json`：`{"round":N,"tool":"…","ok":true/false,"reason":"…"}`，並在 agent 地根寫 `.aos/agent-progress.json`（最近一圈的摘要＋連續失敗次數）。連續失敗 3 次（spec 的 fail_streak）就停並寫停止原因 `fail_streak`。
7. 每項加最少一條測試（假後端 `echo:`／`fail:`／`slow:` 都在 llm.py 裡，看怎麼用）。最後 `bash proto/run-all.sh` 全綠。

回報格式：每項一行「做了／沒做＋檔案＋測試名」，然後撞到的事，最後一句 run-all 結果。
