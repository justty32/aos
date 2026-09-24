← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 沿革

原標題：`aos-agent：走一格、登記、取消登記（第 2 版，2026-09-24 定稿（astra 三輪審查＋第 4 輪補 3 條）；已實作）`

> 2026-09-23 草稿；2026-09-24 照 審查報告「定稿前必改」與使用者三件裁決改成第 2 輪；同日照 第 2 輪審查 E／D／B／C 改成第 3 輪；照 第 3 輪審查 D 節補 3 條（第 4 輪）後定稿。（審查與實作紀錄在 [rearch 筆記](../../notes/2026-09-23-rearch/README.md)）
> **已實作**（2026-09-24，T9）：`lib/aos_agent.py`＋`cli/aos-agent`，實作發現見 agent-impl-findings。
> 調度者裁決移到檔尾（09-24 試玩 r2 搬），已拍板的前提在 §14。
> 2026-09-24 fix-r4：命令列改 `--target DIR`、`AOS_K` 改名 `AOS_KERNEL_HOME`、`last` 換成 `listen`（§1.5）、`say --wait [秒]`、加 `pause`（§1.6）與兩種暫停都解的 `continue`、tick 上 flock 並寫下併發分析（§2.1）、think 改叫 `aos-llm call`。
> 2026-09-24 fix-r5（試玩 r4 兩份報告的共同痛點）：`status` 第一行多 `恢復中`／`重試中（連敗 N/3）`／`已解除暫停，等下一次成功`（§1.3）；`continue` 放 `resumed`、成功結清才刪（§1.4、§7），加 `continue --all`；舊錯縮短、「（已恢復）」移到最前、stuck 行不再叫人 touch（§9）；`listen --last` 講「還在處理中」並附時間（§1.5）；沒登記的 `say` 在 stdout 說別再說一次，`say --wait`／`listen --wait` 開始前看 kernel 健康與 `bad`（§1.2）；已登記的 `start` 退 0（§11）；`init` 在非空的非 agent 資料夾要 `--force`、`NotAnAgent` 講是哪種家（§1、§1.1）。
> 2026-09-24 advice-r1（使用者建議）：加 `check [--target DIR] [--probe]`（§1.7），整段接手原本的 `aos-kernel check --agent`；K 由 `AOS_KERNEL_HOME` 或 `tick.json` 找，不用再給。
> 2026-09-24 listen 微調（使用者要）：`listen` 不給看法改成用法錯（`--last` 不再是預設）、`--last [N]` 印最後 N 則並帶輪次標頭、加 `--show-calls`／`--show-calls-full`（三種看法都有效）；§1.5 從 cli-talk.md 搬到 cli-listen.md。
> 2026-09-24 talk（使用者要的極簡 REPL）：加 `talk [--target DIR] [--wait 秒] [--show-calls]`（§1.9，[cli-talk-repl.md](cli-talk-repl.md)）：送出前記 H0、「印到哪」邊到邊印不重印，晚到的回話下次 Enter 補印；slash 指令 `/status`、`/context`、`/history`、`/tools`、`/wait`、`/pause`、`/continue`、`/help`、`/quit`；Ctrl-C／EOF 退 0。
> 2026-09-24 access-impl（A1）：`tools add` 能原地引用資料夾或單一 `.json` 檔、加 `--as`／`--only`（寫成 `tools` 元素的 `$opt`）；加 `tools ls [--json]`／`rm`／`alias`／`unalias`（[tools-manage.md](tools-manage.md)），都持 `info.json` flock、寫前整份試算；改完最後一行改成「下一批工具生效，不用重 start」。
> 2026-09-24 access-impl（A2）：權限牆（[access.md](access.md)）：act 批建批時解 `access.json` 存 `batch.access` 快照、有表就把工具包成 `aos-jail …`（壞表、沒 bwrap＝那件跑不起來、不送）；加 `access ls／set／rm／cwd／net`；`check` 多查 access／bwrap／aos-jail 與牢裡找不找得到程式，`status` 多一行 `access bad`。
> 2026-09-24 access-impl astra 修（A1）：tools／access 寫入改鎖不會被 rename 的 `<家>/.admin.lock`（tick 不拿）；CLI 與 `init` 寫的 `info.json` 改縮排 2；`tools ls` 遇到明寫卻不在的 access 檔印「錯」與 `access_error`；`tools add` 有 access 檔時改講牢裡的工作根目錄。
> 2026-09-24 proto5-2 池式納入：只換三句——§6.1 `kind=aos` 的 cpu.log 路徑改 `K/pools/<池>/cpus/*/cpu.log`；§1.7 check 的池項改看 K 的 `pools`（tick.pool／llm.pool／tool_pool 三格、count 0＝warn）、`llm/<池>`。§1.3 status 的 health 判定換了（看池摘要，[kernel health](../kernel/health.md)），字不改。草稿在 proto5-2/spec。
