你可以開自己的 subagent 平行做事（multi_agent 已開）。全程唯讀，不要改任何檔案。用繁體中文回報。

# 任務：第二輪審查（cpu.md、kernel.md 已照第一輪意見重寫）

repo `/home/guanyu/projs/aos`。第一輪報告在 `/tmp/claude-1000/-home-guanyu-projs-aos/81cce3ef-1a8d-4b57-ad46-a919d4a09c78/scratchpad/review-cpu-kernel-report.md`（C-1～8、K-1～13、X-1～8、R-1～10），先讀它。
兩份規範已整份重寫：`proto5/spec/cpu.md`、`proto5/spec/kernel.md`。每份的 §9 是使用者已拍板的前提（不要質疑），§10 是撰寫者自己選的。

第一輪之後使用者又拍了四件（都是前提）：
1. params 不包 inst 內容，改成 aos-exec 的命令列一對一：`target`（aos-exec 的 xxx，三種目標都行）＋ `dir_target`／`timeout_ms`／`stderr`／`args`。cpu 不讀 inst，全交 `aos_exec.run_target()`。
2. daemon 的 `spawn` 帶 `name`＋`restart:true`，孩子死了 daemon 自己再拉；kernel cpu 死了靠這個。
3. rm 正在跑的行程後，同名 add 拒絕到它跑完。
4. kernel 的 stop 分 stopping／stopped 兩段，在途工作與 once 回音收完才叫 cpu 停。

撰寫者為了回應第一輪另外引入的機制：回音要收件者放 `ack` notification 主人才刪（不再是收件者自己刪）；cpu 的寫入順序改為「寫 current → 跑 → 發回音 → 刪原單 → 清 current」，開機對帳是 cpu.md §6.2 的五列表；kernel 鏈改用 boot 給的 `chain` id 守門、接鏈「先放後記」、派工「先記 state 再 link」、收件「讀→寫 state→ack」、state 多了 `proc`／`discard`／`acks`；boot 不跑整格；`stop-`／`ack-` 檔名前綴是規定；控制 pipe 搬到高位 fd。

## 要你做的

### A. 逐條驗收第一輪
把第一輪每條（C／K／X／R）標成：已解／部分解（差什麼）／沒解／解法本身引入新問題（說清楚）。不用重講第一輪的內容，一條一行。

### B. 新引入機制的洞
重點盯這些，每個都要具體給時序（「A 做到第幾步崩了／B 在此時做了什麼 → 結果」）：
- ack 機制：收件者崩在讀與 ack 之間、ack 放了主人還沒處理就死、ack 指到不存在的回音、回音被 ack 後同名 request 又來。
- cpu §6.2 五列表是否真的窮盡；§6.3 順序與 §5.1～5.3 三種停的交互；回音發不出去退 1 之後 daemon restart 會怎樣（會不會無限重啟）。
- kernel §3 十步：每一步「崩在這裡」的說法對不對；第 6 步「兩個都不在＝從沒放出去」這個推論在 cpu 的順序下是否成立（含 cpu 開機對帳的路徑）；第 2 步 EEXIST 的判斷有沒有誤判（例如殘單是舊鏈的）；第 9 步 stopped 之後那份殘單與下次 boot 的交互；boot 第 1 步偷看 `current` 的競態。
- once 的生命週期：add 收到→pending→派→回音→轉交→ack，每個縫。rm 與 once、rm 與 discard、discard 那顆 cpu 被 daemon 重拉。
- params 改成 target 路徑後：相對路徑以 C 為起點是否跟 aos-exec 的 base 規則相容；`stderr` 路徑相對 C；`args` 只給普通檔；kind=aos 的 code 用 1 不換 125 會不會跟 aos-exec.md 打架；`.json` 不存在＝kind aos 的行為對 kernel 判定（aos 連續 2 次退件）的影響——agent 還沒把檔寫出來就被退件？
- 池：kernel 池恰好一顆的檢查時機；行程指定的池在 info 改掉後消失了怎麼辦。

### C. 說明清不清楚（第二輪）
第一輪 R-n 有沒有真的改好；新寫的 §6.2 表、§3 十步標「讀／寫 state／放檔」的寫法讀起來順不順；還有哪裡要先看別段才懂但沒指引。

### D. 為 daemon 規範先探路
撰寫者接下來要寫 daemon（很薄：spawn／ls／kill／stop、孩子表、restart、pipe 停機階梯、跟 cpu 範式一樣的家）。從 cpu.md／kernel.md 已經對 daemon 提出的要求裡，列出 daemon 規範**必須**回答的問題清單（例如：restart 的節流、同名 spawn 的判斷依據、控制 pipe 寫端不可漏給別的孩子怎麼做到、daemon 自己被 KILL 後孩子怎麼辦、daemon 家的主人是誰、daemon 的 stop 跟 kernel 的 stop 先後）。只列問題與你看到的約束，不要替他設計。

## 回報格式
markdown：1. 總評（五行內，這版能不能當實作契約、還差什麼）；2. A 驗收表；3. B 發現，編號 C2-n／K2-n／X2-n，每條「在哪／時序／後果／建議／嚴重度：擋／要修／可先放」；4. C 發現 R2-n；5. D 問題清單。不客套。
