你可以開自己的 subagent 平行做事（multi_agent 已開）。全程唯讀，不要改任何檔案。用繁體中文回報。

# 任務：第三輪審查（cpu.md、kernel.md 再次整份重寫；daemon.md 新加入）

repo `/home/guanyu/projs/aos`。前兩輪報告在同一個資料夾：
`/tmp/claude-1000/-home-guanyu-projs-aos/81cce3ef-1a8d-4b57-ad46-a919d4a09c78/scratchpad/review-cpu-kernel-report.md`（第一輪）、
`.../review2-cpu-kernel-report.md`（第二輪，含 D 清單 18 題）。先讀第二輪。
三份規範：`proto5/spec/cpu.md`、`proto5/spec/kernel.md`、`proto5/spec/daemon.md`。每份 §9（daemon 是 §8）是使用者已拍板的前提，不要質疑；§10（daemon §9）是撰寫者自己選的。

第二輪之後撰寫者的三個根因解法（都是新機制，請重點盯）：
1. **名字帶 chain**：kernel 取的所有檔名都含 chain id（kernel §1.3）；tick 改用 aos-exec 普通檔模式（target＝cli/aos-kernel、args 帶 chain 與 seq），沒有 tick.json。
2. **帳本＋出貨箱**：K/state.json 是唯一帳本，procs/ 資料夾拿掉；acks／replies／stops 三張出貨箱「先記、再放、放完清」。
3. **先查原單、再查回音**：kernel 查 cpu 工作狀態的順序對上 cpu「先發回音、再刪原單」。

另外使用者又拍了兩件（前提）：kind=aos 併進一般失敗（沒有獨立 aos 計數）；兩個 kernel 共用 daemon、cpu 同名＝NameTaken。

## 要你做的

### A. 逐條驗收第二輪
C2-1～6、K2-1～13、X2-1～5、R2-1～6、D 清單 1～18：每條一行，已解／部分解（差什麼）／沒解／解法引入新問題。

### B. 三份之間與跟底層的一致性
- 三份互相引用的 § 對不對、名詞一不一致（例如 killing／stopping、偷看、出貨箱、殘格）。
- daemon.md 跟 cpu 範式的關係：daemon 自己也是一個家，它的 current／對帳／ack 是否真的能照範式 §6 做；spawn 副作用先於回音的說法對不對。
- kernel 偷看 D/state.json 判斷孩子活不活（不用 syscall）：daemon 寫 state 的時機（只在變動時寫）夠不夠讓 kernel 判斷；alive=true 但 daemon 死了的情況。
- 普通檔模式跑 tick：aos-exec.md 普通檔的規則（繼承串流、環境、沒有 exit 檔、126 沒執行權）套到 tick 上有沒有問題；cli/aos-kernel 的絕對路徑從哪來。

### C. 新機制的洞（每條給時序）
- 帳本一次寫的粒度：kernel §3 第 6 步「判定→一次寫帳本」與第 4 步出貨；崩在出貨中途（放了一筆、沒清）；同一格內出貨箱新增又出貨的順序。
- 名字帶 chain 之後還有沒有重用；boot 保留 cpus／procs／acks／replies 照舊但 chain 換了，舊 chain 名字的在途 req、acks、replies 在新鏈裡怎麼被處理，有沒有卡住。
- boot 交接：往舊 kernel cpu 放 stop → 等 daemon alive=false；daemon 沒在跑／kernel cpu 從來沒被 spawn 過／舊 kernel cpu 正在跑一格很長的 tick（tick 沒 timeout）；boot 逾時退 1 之後留下什麼。
- stopping：queued once 回 Stopping、在途收完、stops 出貨、kernel cpu 收到 stop 不跑已排的下一格；stopped 之後 K/requests/ 再來的 add 誰回；下次 boot 第 3 步先出貨 stops 的邏輯。
- rm 三種情況跟第 6 步「兩個都不在＝從沒放出去」的交互；rm 一個 once 且在途的。
- daemon：restart 只在非 0、killing／stopping 贏過 restart；孩子退 0 後被從表拿掉，kernel 下格看不到它就 spawn——這條跟 kernel stop 的交互（kernel stop 讓 cpu 退 0 → 但 kernel 也 stopped 不再 tick，OK；但 daemon 重啟後表空、kernel 還在 running → 下格全部 spawn，在途 req 的 cpu 開機對帳回 Interrupted，對嗎）。
- daemon 6.1 第 3 步用 kill(pid,0) 等上一任孩子死透：孩子沒有 timeout 的長工作；階梯從 TERM 開始對 cpu 來說是「第一次訊號＝溫和停」還是第二次？（cpu 的旗標是它自己行程內的，新 daemon 不知道它有沒有先收到 EOF）。
- pipe：daemon 讀 fd 1 丟掉、寫 fd 0 EPIPE；cpu 搬高位 fd；孩子 fork 出的孫子。

### D. 說明清不清楚（第三輪）
名詞表（三份 §0）有沒有跟正文脫節（改了正文、名詞表沒跟上）；「帳本」「出貨箱」「先記後放／先放後記」這幾個新詞在正文裡用得一不一致；三份各自的「一句話」。

## 回報格式
markdown：1. 總評（五行內：能不能當實作契約、還剩幾條擋）；2. A 驗收表；3. B；4. C，編號 C3-n／K3-n／D3-n／X3-n，每條「在哪／時序／後果／建議／嚴重度：擋／要修／可先放」；5. D 發現 R3-n。不客套、不重講規範。
