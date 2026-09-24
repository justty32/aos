你可以開自己的 subagent 平行做事。這是**唯讀審查**任務：不改任何檔。用繁體中文。最後一則訊息就是報告，我會原樣存進 repo。

# 任務：agent 線三份規範第 3 輪審查（驗收第 2 輪必改 5 條＋定稿判定）

repo `/home/lorkhan/repo/simple_tools/aos`，全部以已提交版本（HEAD = 835bb4b）為準。先讀：
- 你上兩輪的報告：`proto5/notes/2026-09-23-rearch/review-agent1-report.md`、`review-agent2-report.md`（第 2 輪 E-1～E-5 必改、D-1～D-8 要寫死、B-6／B-7／B-8、C-1～C-3）。
- 這輪改了什麼：`proto5/notes/2026-09-23-rearch/agent-round3-changes.md`（與 round2-changes 的 C-1～C-10 表，其中 C-6／C-8 已改成沒通）。
- 三份第 3 輪草稿（審這三份）：`proto5/spec/agent.md`、`aos-agent.md`、`aos-llm-call.md`。
- 下層定稿：`cpu.md`、`kernel.md`、`daemon.md`（**注意**：這三份在 a221019 加了「實作補記（2026-09-24）」與新 CLI：`aos-kernel ack`、`init --cpu`、`ls --json`、`aos-daemon stop`，agent 規範若引用 CLI 要對得上）、`aos-exec.md`、`inst-posix.md`、`directives.md`。
- 使用者三件拍板不審方向（同上輪）。

## 要答的
**A. 驗收 E-1～E-5**：逐條「已解／部分／沒解」＋檔:行。特別核 E-1 的新機制：`<原名>.<消費 id>.done`、`intake`／`consuming` 記原路徑＋新路徑成對、`continue-<批 id>.json`——用第 2 輪 B-2 的時序（rename 後崩、生產者再投遞同名）與「rename 前崩」「rename 後 state 沒落盤」「兩份同名接連投遞」四個時序各走一次。
**B. 驗收 D-1～D-8、B-6／B-7／B-8、C-1～C-3**：一行一條，錯的給檔:行。
**C. 新洞**：這輪新加的東西（消費 id、`KernelIncompatible`／`KernelMismatch`、`aa-` 前綴、llm loader 只解六欄與「兩端 $env 要一樣」）有沒有引入新問題。最多 6 條，嚴重度標明。
**D. 定稿判定**：三份能不能定稿（能／不能）。不能就給「定稿前必改」編號清單（只列擋與要修，可先放的另列）。能的話列「實作時要注意」≤ 5 條。

格式：四節，條目編號、檔:行，總長 ≤ 5000 字。開頭「總評」≤ 5 行。不重述規範、不客套。
