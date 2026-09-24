你可以開自己的 subagent 平行做事。這是**唯讀審查**任務：不改任何檔。用繁體中文。最後一則訊息就是報告，我會原樣存進 repo。

# 任務：agent 線三份規範第 2 輪審查（驗收第 1 輪必改 12 條＋找新洞）

repo `/home/lorkhan/repo/simple_tools/aos`。先讀：
- 你上一輪的報告：`proto5/notes/2026-09-23-rearch/review-agent1-report.md`（尾巴「定稿前必改」12 條）。
- 這一輪改了什麼：`proto5/notes/2026-09-23-rearch/agent-round2-changes.md`（含 C-1～C-10 時序自走表）。
- 三份第 2 輪草稿（審這三份）：`proto5/spec/agent.md`、`proto5/spec/aos-agent.md`、`proto5/spec/aos-llm-call.md`。
- 下層定稿（真理，不審）：`proto5/spec/cpu.md`、`kernel.md`、`daemon.md`、`aos-exec.md`、`inst-posix.md`、`directives.md`。注意 cpu／kernel／daemon 工作樹裡可能有另一條線未提交的「實作補記」改動，以 `git show HEAD:proto5/spec/kernel.md` 之類拿已提交版本為準。
- 使用者 2026-09-24 拍板的三件（已寫進三份的「已拍板的前提」）：同步工具全拿掉；`aos-agent start`＝`aos-kernel add <K> <agent>/tick.json`、進現有池、K 由 `AOS_K` 給；llm.json 放 llm cpu 的家、由該 cpu 的 envs `AOS_LLM_CONFIG` 指。**這三件不審方向，只審寫得對不對、接得上下層沒有。**
- 使用者的日常想像：`thinking/2026-09-23.md`、`thinking/aos-agent.md`（審「照這三份實作出來，他那個流程走不走得通」）。

## 要答的
**A. 驗收 12 條**：逐條「已解／部分／沒解」，部分與沒解要指出檔:行與缺什麼。
**B. 新機制的洞**：`state.batch`、`intake`、`consuming`、四步「送出了沒」判定、`aw-` 前綴、內外兩層逾時、`work/` 清理條件（帳本 procs 沒那個名才刪）、`start`／`stop`、`AOS_LLM_CONFIG`。每個機制照你第 1 輪的做法：時序→後果→建議，標嚴重度（擋／要修／可先放）。特別檢查：① `batch` 與 kernel 帳本的 once 行程生命週期（rm 之後 procs 何時消失、done 的 once 會不會永遠留在帳本讓 work/ 永遠清不掉）；② `aos-llm-call` 執行時才讀 agent 家——排隊期間 agent 又 tick 了會不會改到它要讀的檔；③ 同一 agent 的 tick 是反覆行程、它送的 once 又進同一池——只有一顆工作 cpu 時會不會自己等自己（死鎖）。
**C. 跟下層對不對**：引用的 cpu／kernel 節號、欄位名、錯誤碼、回音形狀逐一核；錯的列出。
**D. 實作者走一遍**：假設你明天要照這三份重寫 `aos_agent.py`，哪些地方還得猜。列最多 10 條。
**E. 定稿前必改**：彙整成編號清單（可為空）。

格式：五節 A～E，條目編號，每條有檔:行，總長 ≤ 7000 字。開頭「總評」≤ 6 行：能不能定稿、還差什麼。不重述規範、不客套。
