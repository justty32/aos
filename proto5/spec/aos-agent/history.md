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
