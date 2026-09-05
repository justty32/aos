# 給 codex 的任務書（aos 新實作原型，2026-09-05）

你在 /home/lorkhan/repo/simple_tools/aos 工作。這是一個「另起爐灶」的專案：舊系統在 core/（不准當憑據、不准改），新規定在 wf/workflows/spec/（先讀 README.md 與 01-terms.md，需要哪份再讀哪份），能跑的 Python 純標準庫原型在 proto/（先讀 proto/README.md 與 proto/FINDINGS.md 前兩節）。

硬規則：
- 只碰任務書點名的路徑；不 commit、不 push、不 git add。
- Python 只用標準庫；跑法 `python3 proto/aos.py <子命令>`；改完一定跑 `bash proto/run-all.sh` 全綠（測試 `python3 -m unittest discover proto/tests`）。
- 撞到 spec 沒講或不合理的，記進 proto/FINDINGS.md 末尾新開一節「codex 第 N 輪」，格式照該檔「每條怎麼讀」。
- 回報用大白話中文：做了什麼（檔案路徑）、測試結果、沒做完的、撞到的。

# 第 2 輪：兩條擋路的機制 bug＋門房接成子命令＋合併發現

先讀：proto/examples/team/FINDINGS-team.md（T-01、T-02、T-03）、proto/DOORMAN.md（十條發現與交接清單）、wf/workflows/spec/07b-result-path.md（S-07-60～63）、13-doorman-l1.md、08b-daemon-reconcile.md。上一輪 codex 的改動已在工作樹裡（看 `git status`／`git diff`），不要撤銷它。

只准碰 proto/。不准碰 wf/、core/。

要做（照順序，每項做完跑 `python3 -m unittest discover proto/tests` 與 `python3 -m unittest discover proto/doorman-tests`）：
1. **T-01 SIGCHLD 讓結束碼全為 0（最重要）**：proto/aosp/daemon.py 的 `_loop` 設了 `SIGCHLD=SIG_IGN`，跨 exec 繼承給 `aos run`，導致 `subprocess` 的 waitpid 拿 ECHILD、returncode 變 0。修法：daemon 起子行程前（`preexec_fn` 或 spawn 後在子端）把 SIGCHLD 恢復 SIG_DFL；daemon 自己改用非阻塞 `waitpid(-1, WNOHANG)` 定期收屍，不用 SIG_IGN。加測試：daemon 起的 run 裡一步 `sys.exit(3)` 要得到 `exit_code: 3`、串 failed（FINDINGS-team T-01 有最小重現）。
2. **T-03 落點碰撞沒人擋**：實作 S-07-60～63：開呼叫前結果檔、`.status.json`、`.usage.json` 三個都不得已存在（存在＝退出碼 3、嚴格解析拒絕，訊息指出哪個檔）；同一格多筆 `call`／`await` 的 `result` 必須兩兩相異；違反整格拒跑。加測試（兩子指同一落點、落點沒清就重跑）。
3. **T-02 父分不出子「做完／壞了／被停」**：daemon 對帳時若子地的 run 結束了（pid 消失或 stopped）而登記表那筆有 `result` 欄，且落點旁既沒結果檔也沒 `.status.json`，daemon 代寫 `<result>.status.json`：reason 依子地 `.aos/stopped.json` 的原因映射（`idle` 但無結果→`no_result`、failed→`child_failed`、signal→`killed`）。這是 spec 08b 的補刀規則；加測試。
4. **門房接成子命令**：把 proto/doorman.py 的核心搬進 proto/aosp/doorman.py，`aos doorman <根目錄> [--home …]` 子命令（proto/aosp/cli.py），原 proto/doorman.py 留一行薄殼呼叫它以免 doorman-tests 壞掉（或把測試路徑改掉，兩者擇一，測試要全綠）。門房補完刀時不寫任何地的檔（13 章），改成在事件本子 `doorman.jsonl` 記 `needs_status`，由第 3 項的 daemon 對帳代寫。
5. **回歸與導航**：proto/examples/team/run.sh（能在 30 秒內跑完、自己起停暫存家的 daemon）讓 proto/run-all.sh 撿到；proto/README.md 範例清單補 agent、agent-real、team，子命令表補 daemon add、doorman；把 proto/examples/team/FINDINGS-team.md 與 proto/DOORMAN.md 的發現各合併成 proto/FINDINGS.md 的兩個小節（保留原檔，小節末尾註「原文見 …」）。
6. `bash proto/run-all.sh` 全綠。

回報格式：每項一行「做了／沒做＋檔案＋測試名」，撞到的事，最後 run-all 結果。
