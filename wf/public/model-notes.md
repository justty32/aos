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
  - 同一個坑的另一種樣子：它想跑指令查東西，整輪只印一行 `jetski: no output produced — a tool required the "command" permission that headless mode cannot prompt for, so it was auto-denied.`。這不是 `Authentication required`，原樣重試沒用；在提示**第一行**加「重要：不要呼叫任何工具（不要跑指令、不要讀檔）；所有材料已完整貼在下面，請直接用文字回答。」就好（ok-llmk2，51 KB 提示）。不要改用 `--dangerously-skip-permissions`（越過權限邊界）。
  - 重試迴圈兩種失敗都抓，成功才收：
    ```bash
    for i in 1 2 3; do
      agy -p "$(cat prompt.txt)" --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s > r$i.txt 2>&1
      grep -qi "authentication required\|no output produced" r$i.txt && continue
      cp r$i.txt out.txt; break
    done
    ```
  - 它提的點不一定對（例：它說「沒掛 hook 就成了殭屍」，其實 `ctl ls --long` 本來就看得到冷卻）。每點都要對照事實再決定。
- **它擅長的**：抓 race，例如檢查與刪檔之間的 TOCTOU、拿鎖前後的順序（ok-kf）；砍東西：反對「notify_box 預設寄給掛它的人」、建議不做 `who --chain`、parent 統一成字串，三處都讓設計變小（ok-devt）；多層算式的漏洞（ok-llmk2）。ok-kmsg 九條裡三條是真的會出事的（提示貼設計稿加相關原始碼約 58 KB，回覆 12 KB）。
- **它不可靠的**：沒看過的圖紙它會照摘要瞎推，採納表要逐條對原文（ok-devt 的 B7）；系統呼叫回哪個錯誤碼這類事實會說錯，以本機小實驗為準（ok-sec E12，見 [設計與查證](設計與查證.md)）。
- **驗過**：ok-astra 11-14 10:20，AK17 計劃；第一次沒加「不准用工具」沒產出，加了後一次拿到 8 點、採納 5 點。ok-kf 11-14 同樣撞到 read_file 被擋，照同法解。ok-llmk2 11-14 撞到 "command" 那種：同一份 51 KB 提示第一次只得一行錯，開頭加那句後兩次（早評、審計劃）都產出 16～18 KB。
- **出處**：`proto8/thinking/2026-11/14/astra-kernel-1114.md` AK17 節；`proto8/thinking/2026-11/14/kernel-framework-1114.md`；`proto8/thinking/2026-11/14/llmk2-1114/02b-Argon早評.md` 檔頭
- **投稿**：ok-astra（`argon-one-shot-review.md`）＋ ok-kf（`pitfalls-shell-and-reviewers.md` 的 Argon、設計流程兩條）＋ ok-llmk2（`argon-headless-no-tools.md`），合併；11-14 收尾補 `wf/temp/{ok-devt,ok-kmsg,ok-sec,ok-llmk2}/wrapup-1114/經驗.md`

## claude -p 做到一半再交新話：stdin 用 stream-json、先不關

- **適用**：自己起 `claude -p`（eca、工具、腳本），想在它做事做到一半時再交新的話給它。
- **做法**：
  1. 加 `--input-format stream-json --output-format stream-json --verbose`。每則訊息寫成一行 `{"type":"user","message":{"role":"user","content":"..."}}`，寫完 flush，**先不要關 stdin**。
  2. 中途再寫一行，模型會在**手上那個工具做完後**讀到（實測工具做完 1.6 秒就處理）。兩則合成同一個 result。
  3. 看到 `type: result`、又沒有要再寫的，才關 stdin，0.6 秒後行程 exit 0。**不關 stdin 它就一直等**，記得加逾時。
  4. 可以跟 `--resume <id>` 一起用（session_id 不變）。
- **坑**：
  - PostToolUse hook 回的 `additionalContext` 送得到，但模型會當成「工具輸出裡的可疑指示」而不照做。真要用，system 先講明這段是誰送的、為什麼從這裡來。
  - `claude -p` 的環境裡也有 `CLAUDE_CODE_MESSAGING_SOCKET`（跨 session 收件口），往裡寫信封也收得到，但那是沒寫進文件的介面。能用 stdin 就用 stdin。
  - 前景 `sleep N` 會被 Claude Code 擋下，模型改丟背景；這時 `-p` 行程會活著等背景任務跑完，中間也收得到訊息。量測時別用包一層的方式繞過這個擋，模型會拒絕；要量長指令改用忙迴圈。`-p` 模式沒有 Monitor，給它的提示別叫它用 Monitor。
  - 模型叫了背景任務會先回一個 result（「在跑了」）：看到 result 就關 stdin 的話，之後的信寫不進去。模型取走中途信後先答的那句不在最後的 result 裡，只看 result 會掉（修在 `lib/agent/cli_stream.py:117`、`:38`；怎麼測見 [審查與實測](審查與實測.md)）。
  - 用預設的 snapshot `--resume` 時，新加的 `--append-system-prompt` 模型看不到，要 `--system-prompt-snapshot off`（claude 2.1.325；`lib/agent/cli_cfg.py:155` 的 docstring 早有寫，`cli_print.py:141` 只補一次旗標）。
- **驗過**：ok-wake 11-14，claude 2.1.325、haiku；探針 `run-stdin-1`、`run-stdin-2`（第二則 4.5 秒後、工具做完時進對話），`--resume` 那次接回同一段對話。審稿時對過 02-實測的結論與探針節。
- **出處**：`proto8/thinking/2026-11/14/wake-1114/02-實測.md`（stdin 探針、additionalContext 探針兩節）、03、05；探針腳本在 `~/code/wake-1114/scripts/`
- **投稿**：ok-wake（`wf/temp/ok-wake/public-submit/claude-p中途餵信.md`；後三個坑補自 `wf/temp/ok-wake/wrapup-1114/經驗.md`，探針 `real/bg-1`、`real/edit-1`、`real/hint-1`、`run-sysflags-2`）

## 用 Claude Code 本機紀錄算 token：同一則回覆會寫好幾列，要跨檔去重

- **適用**：用 `~/.claude*/projects/**/*.jsonl` 算 Claude 用量。
- **做法**：全域以 `message.id` 為鍵，取 `output_tokens` 最大的那列。不能逐列加總（會重算約一倍），也不能只在單檔內去重。
- **驗過**：ok-llmk2 11-14：主帳號 160,259 列只對到 85,529 個 id；output 不同的 9,578 個 id 都是最後一列最大；82 個 id 跨檔重複（commit db0cfbb29）。
- **出處**：`proto8/thinking/2026-11/14/llmk2-1114/06-Claude電表原型.md:11-25`；`wf/temp/ok-llmk2/wrapup-1114/經驗.md`
