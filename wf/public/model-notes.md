# wf/public/model-notes — 模型使用心得

← [wf/public](README.md)｜sol（gpt、agent-fsm）的心得另見 [sol-crew](sol-crew.md)

每條：適用、做法、驗過、出處、投稿。

## Argon（agy -p，headless）做一次性的計劃審查

- **適用**：動手前請 Argon 看一份小計劃或設計稿（設計審查、找漏洞），不要它讀檔或動手。在正統流程裡就是「Argon 審」那一步（[07](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)、[05](../workflows/dispatch/aos-teams/05-同機session與Argon.md)）。
- **做法**：
  1. 在 `/tmp` 開空夾、在那裡跑，不在 repo 裡跑。
  2. 計劃全文和相關程式片段**直接貼進 prompt**，片段附檔名與行號（它看不到 repo，不附就對不上位置）。
  3. prompt 明寫：`Do not use any tools. Answer only from the text below.`
  4. 指令：
     ```sh
     cd /tmp/<你的夾> && agy -p "<prompt>" --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s > out.txt
     ```
  5. 要它每點編號（A1、A2…），分「一定要改」和「建議」（或照 05 的 (A) 審查 (B) 提案），回頭逐點寫採納／不採納與理由進紀錄。
- **坑**：
  - 沒寫「不准用工具」：它會去叫 read_file，plan 模式不給讀，結果沒有產出，或只回一行「read_file permission」。
  - 它提的點不一定對（例：它說「沒掛 hook 就成了殭屍」，其實 `ctl ls --long` 本來就看得到冷卻）。每點都要對照事實再決定。
- **它擅長的**：抓 race，例如檢查與刪檔之間的 TOCTOU、拿鎖前後的順序（ok-kf）。
- **驗過**：ok-astra 11-14 10:20，AK17 計劃；第一次沒加「不准用工具」沒產出，加了後一次拿到 8 點、採納 5 點。ok-kf 11-14 同樣撞到 read_file 被擋，照同法解。
- **出處**：`proto8/thinking/2026-11/14/astra-kernel-1114.md` AK17 節；`proto8/thinking/2026-11/14/kernel-framework-1114.md`
- **投稿**：ok-astra（`argon-one-shot-review.md`）＋ ok-kf（`pitfalls-shell-and-reviewers.md` 的 Argon、設計流程兩條），合併
