# 2026-09-23 重架構：daemon→kernel→cpu 這條線的規範重寫

← [proto5 README](../../README.md)｜新規範：[spec/cpu.md](../../spec/cpu.md)、[spec/kernel.md](../../spec/kernel.md)、[spec/daemon.md](../../spec/daemon.md)

使用者當天拍板的方向（都寫在各規範的「已拍板的前提」一節）：cpu 範式（一個家一個主人、info／state／requests／responses）、
規則一軟性、cpu 聽命執行不自己迴圈、pipe 只管生死、JSON-RPC 2.0、所有 request 都是 aos-exec（llm／tool cpu 變成程式）、
kernel 也是一格一格的 exec、params＝aos-exec 的 argv、daemon spawn 有 restart:true。

| 檔 | 內容 |
|---|---|
| review1-task.md／review1-report.md | astra（gpt-6-astra，唯讀）第一輪：cpu.md＋kernel.md，C／K／X／R 編號＋痛點對照表 |
| review2-task.md／review2-report.md | 第二輪：驗收第一輪、新機制的洞（C2／K2／X2／R2）、daemon 必答 18 題 |
| review3-task.md／review3-report.md | 第三輪：三份一起，驗收第二輪＋新機制的洞（C3／K3／D3／X3／R3） |
| review4-task.md／review4-report.md | 第四輪：措辭、易用性（人／agent／實作者各走一遍）、未來（W／X／U／F）；尾巴有「定稿前必改」13 條 |
| impl-task.md | 派 astra（bypass）照三份規範實作 lib／cli／測試的任務書（四段） |
| review-agent1-task.md／review-agent1-report.md | agent 線三份草稿（aos-llm-call／agent／aos-agent）第一輪審查：結論「還不能定稿」，必改 12 條（waits 兼工作索引、批次紀錄、記憶／ack／state 恢復…） |

舊規範已於 2026-09-24 換掉（副本在 proto5.1/spec/）。
