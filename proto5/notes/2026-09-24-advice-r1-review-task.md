# advice-r1 唯讀審查任務書（給 astra）

你是唯讀審查者，**不要改任何檔案**，只把審查結果寫成 Markdown 輸出。用繁體中文。

## 背景

使用者 09-24 的兩條建議（原話）：

1. 「`aos-kernel check --agent xxx` 這個指令不應該放在 aos-kernel 下面。應該改成 `aos-agent check`，然後遵循 `--target xxx`、默認 xxx 為 `.` 的原則。」
2. 「`aos-kernel ls` 的時候列印出來的東西，希望能好看一些。然後可以的話加上 `aos-kernel ls --json`，用 json 方式印出來。」

這一輪（advice-r1）照這兩條改了 proto5。看 `git log --oneline main..HEAD` 與 `git diff main..HEAD -- proto5/` 就是全部改動（報告與本任務書除外）。

## 要審的檔

- 規範：`proto5/spec/aos-agent/cli-check.md`（新）、`proto5/spec/aos-agent/cli.md`、`essentials.md`、`README.md`、`history.md`；`proto5/spec/kernel/cli-ls.md`（新）、`cli-ops.md`、`cli.md`、`README.md`、`history.md`。
- 實作：`proto5/lib/aos_agent_check.py`（新）、`aos_agent_cli.py`、`aos_kernel_check.py`（拆出 `kernel_checks()`／`finish()`）、`aos_kernel_ls.py`（新）、`aos_kernel_cli.py`。
- 測試：`proto5/lib/test/test_advice_r1.py`（新），以及改過的 `test_kernel_check.py`、`test_kernel_cli.py`、`test_kernel_fix_r5.py`、`test_kernel_health.py`、`test_kernel_integration.py`。
- 參考：`proto5/lib/aos_agent.py`（`start` 的 `_tick_inst`／`_register` 怎麼比對 tick.json 的 K）、`aos_agent_status.py`（`tick_binding`）、`aos_kernel_health.py`、`aos_kernel_boot.py` 的 `status()`。

## 請回答

1. **規範與實作對得上嗎**：逐條對 `cli-check.md` 與 `cli-ls.md` 的每句話，找實作不照做的地方（輸出字串、順序、退出碼、何時略過哪些項目、daemon 家的找法、K 的找法與 KernelMismatch 判定是否真的跟 `start` 一致）。
2. **`--json` schema 有沒有洞**：欄位型別在所有情況（沒帳本、帳本缺鍵、daemon 沒活、info 沒 `daemon`、kcpu 不在 info、帳本裡的 cpu 不在 info、proc 缺 `pool`／`target`、`status` 是 null）是否仍符合 `cli-ls.md` 的表；「只加鍵不改名」的承諾有沒有被現在的實作細節（例如 `settings` 從 info 取、`counts.procs.status` 的鍵集合）弄破；stdout 是否可能混進非 JSON（例如 health 或 agent 標記過程印東西）；退出碼與文字版是否一致。
3. **舊指令的錯誤訊息**：`aos-kernel check --agent` 各種寫法（帶值、不帶值、`--agent=X`、重複、跟 `--probe` 混用、放在 `--target` 前）是否都退 2 並指到新指令；`-h` 是否乾淨；有沒有哪個寫法會被 argparse 先吃掉而變成別的錯。
4. **文字版 ls**：第一行 health 有沒有被改到（順序、字句）；對齊在中日韓字、空表、只有 kernel cpu、daemon 沒活、名字剛好 24 格等邊界是否正確；`_cut` 有沒有會出錯的輸入（空字串、全形字、limit 很小）。
5. **測試漏什麼**：列出值得補的測試（具體到情境）。
6. **其他 bug**。

## 輸出格式

分「必修」（會讓使用者看到錯的行為、規範與實作不一致、schema 承諾破掉）與「建議」（可不修）。每條寫：檔:行、問題、怎麼重現或為什麼、建議改法。沒有問題的節寫「無」。
