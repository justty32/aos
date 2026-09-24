# astra 唯讀審查任務書：proto5-2 納入 proto5＋拆檔 tidy（2026-09-24）

← [納入報告](README.md)

你是唯讀審查者。**不要改任何檔**，只讀、只寫回報（回報由 `-o` 收，直接輸出成 Markdown，用繁體中文）。

## 背景

proto5-2（池式 daemon／kernel）原本是 proto5 在 commit `c81a98b` 分岔出去複製的一份。分岔後兩邊各自改：
- proto5 這邊加了 agent 線的東西：`aos-agent check`（從 `aos-kernel check --agent` 搬來）、`aos-kernel ls` 的對齊表／`-v`／`--json`（advice-r1）、`listen --last／--show-calls`、`talk`、`tools add／rm／alias`、`access.json`＋`aos-jail`、基礎工具包、`templates/cli-agents`、教程 03～07、04b。
- proto5-2 那邊把 daemon／kernel 改成池式，並跟著改了 agent 線兩處（cpu.log 路徑、discard 查法）與 `aos-kernel check`、`ls`。

這次把 proto5-2 的程式三方合併（base＝`c81a98b:proto5/lib`）進 `proto5/lib`，規則：daemon／kernel／cpu／池／帳本以 proto5-2 為準；agent 線的 CLI、工具、權限以 proto5 為準。兩邊都改過的檔只有 `aos_kernel_check.py`、`aos_kernel_cli.py`、`aos_agent_init.py`（自動合）與 7 個測試檔。`aos-kernel ls` 兩邊都重寫過，合成一版（`lib/aos_kernel_ls.py`，`--json` 升 `aos_kernel_ls` 第 2 版，規範 `proto5/spec/kernel/cli-ls.md`）。之後拆檔：`aos_exec.py` → `aos_exec.py`＋`aos_exec_run.py`＋`aos_exec_spawn.py`；`aos_kernel_cpu.py` → `aos_kernel_cpu.py`＋`aos_kernel_rows.py`；tidy 刪了幾個沒人用的別名與函式、收掉重複的 `_peek`。

commit 範圍：`git log --oneline main..HEAD`（或看 `proto5/lib`、`proto5/cli`、`proto5/spec`、`proto5/tutorials`、`proto5/README.md` 的 diff）。proto5-2 的原始程式在 main 的歷史裡（`git show <main 的某個 commit>:proto5-2/lib/…`），分岔點 `c81a98b`。

## 請回答三件事

1. **proto5 分岔後新增的東西有沒有被蓋掉**：對照 `c81a98b..` 之間 proto5 的改動（agent 線、`aos_kernel_ls.py`、`aos_kernel_check.py` 的 `kernel_checks／finish` 拆法、`aos-kernel check --agent` 的用法錯訊息、`stderr_hint` 沒有字面 stderr 指 target 本身、`ls` 的 health broken 退 1 等），合併後是否仍在、行為一致。反過來，proto5-2 在 `aos_kernel_check.py`／`aos_kernel_cli.py`／`ls` 上的池式改動有沒有在合併時漏掉（例如 `check` 的 daemon 項逐池查、envs.json、agent 三個池的 count 0 警告、llm 只查 agent 的 llm 池、`ls --pool` 找不到池＝NotFound）。
2. **拆檔與 tidy 有沒有改行為**：`aos_exec*.py`、`aos_kernel_cpu.py`／`aos_kernel_rows.py`、刪掉的 `work_pools`、`serve`、`_log`、`DAEMON_ENV`、`_stderr_hint`、`aos_kernel.py` 匯出表縮減、`_peek` 收成 `aos_daemon_pools.peek`、`spawn_child` 改叫 `spawn_target`。找：被刪的名字仍有呼叫端（含 `proto5/cli/`、`proto5/tools/`、`proto5/templates/`）、mock／patch 目標因搬家而失效（測試仍綠但沒測到真的程式）、例外型別或錯誤訊息變了、import 循環。
3. **合併版 `aos-kernel ls` 與 `aos-agent check`**：跟 `proto5/spec/kernel/cli-ls.md`、`cli-ops.md`、`aos-agent/cli-check.md` 對得上嗎？`--json` 第 2 版欄位與規範表一致嗎？預設只列 bad／有標記的行程、`--procs` 全列、`-v`、`--pool` 的組合有沒有怪行為？

## 回報格式

- 開頭一段總評。
- 然後一條一條編號（P1、P2…），每條標 **必修**（會造成錯誤結果、功能被蓋掉、與規範明文衝突）或 **建議**，寫：位置（檔:行）、問題、怎麼重現或推理、建議改法。必修放前面。沒把握標「待確認」，不要灌水。
