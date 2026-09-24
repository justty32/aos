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
| lmstudio-run.md＋lmstudio/ | 2026-09-24 用本機 LM Studio（gemma-4-e4b）真跑新架構一條龍：daemon→kernel（k／0／llm）→once 問模型 6 秒回音、反覆行程 done、停機 0.3 秒、重跑通；`lmstudio/run.sh` 可重跑；撞到 8 條（daemon 沒停機 CLI、kernel 沒 ack 子命令、init 不能帶 cpu 表、kernel.log 空格也寫…） |
| impl-review-task.md／impl-review-report.md | 2026-09-24 astra（唯讀）審實作是否照三份規範：A 偏差 5 條（daemon 缺檔回 Usage、控制 pipe 沒驗信封、ack 名加 digest／boot 交接兩顆 kcpu 要回寫規範）、B 12 條 impl-findings 逐條裁（7 條規範補寫、1 條改程式、4 條照現況）、C 測試沒蓋到的崩潰窗口 8 條（cpu 家初始化半成品最急）、D 測試 flaky 7 條 |
| agent-round2-changes.md | 2026-09-24 agent 線三份第 2 輪（Opus）：12 條必改全落（`state.batch` 當批紀錄、`waits` 只當外部門、四種取消分清、`aw-` 前綴、內外兩層逾時…）＋使用者三件裁決（同步工具全拿掉、`aos-agent start`＝進現有池、llm.json 放 llm cpu 家由 `AOS_LLM_CONFIG` 指）；調度者裁決 21 條、要使用者拍 3 條；C-1～C-10 時序自走 10 通 |
| review-agent2-task.md／review-agent2-report.md | 2026-09-24 astra 審 agent 線第 2 輪：12 條 7 解 5 部分、還不能定稿；新洞 8 條（擋：同名輸入檔再投遞會被吞；要修：空 envs 的 clear 被省略、llm cpu 整份解 info 撞 $env、done_exit 與 tick 退出碼相撞）；下層引用核對通過；實作者還得猜 8 處；定稿前必改 5 條 |
| agent-round3-changes.md | 2026-09-24 agent 線第 3 輪（Opus）：必改 5 條全落（每次消費一個身分 `<原名>.<消費 id>.done`、`continue-<批 id>.json`、clear 一律寫、llm loader 只解六欄、`start` 驗 K 的 done_exit／KernelIncompatible、system／history 限單檔）＋實作者還得猜的 8 處寫死（ToolInvalid／ConfigInvalid／UnsupportedVersion、正規化順序、KernelMismatch、`aa-` 前綴…）；round2 表 C-6／C-8 改「沒通」 |
| review-agent3-task.md／review-agent3-report.md | 2026-09-24 astra 審 agent 線第 3 輪：E 5 條 4 解 1 部分、D／B／C 全解、四個消費時序都通；aos-llm-call.md 可定稿，agent.md／aos-agent.md 還差 3 條（被 state 引用的封存檔不可清、start 只解驗相容欄位、「讀驗錯什麼都不寫」限起始讀驗） |
| agent-round4-changes.md | 2026-09-24 agent 線第 4 輪（Opus）：最後 3 條落（被 state 引用的封存檔不可清、start 只就地解驗 done_exit／bad_after、「什麼都不寫」限起始讀驗）；三份標頭改「第 2 版，2026-09-24 定稿；程式未跟」 |
| review-agent4-task.md／review-agent4-report.md | 2026-09-24 astra 快驗第 4 輪：3 條全解、無新矛盾；結論「三份整組可當照它實作的定稿」（前提：單一驅動者、被 state 引用的封存檔不清） |
| impl-fix-round1.md | 2026-09-24 T5 修正第 1 輪：daemon 缺檔 SpawnFailed、控制 pipe 驗信封、cpu 家半成品恢復；新 CLI `aos-daemon stop`、`aos-kernel ack`／`init --cpu`／`ls` 摘要／`-h`、kernel.log 空格不寫；補 C-1／4／5／6 測試、修 D-1～7 flaky（917 條）；三份規範補句＋檔尾〈實作補記〉；跳過 C-2／3／7／8；要使用者拍 3 條 |
| agent-impl-findings.md | 2026-09-24 T9 照 agent 線三份定稿規範實作（aos-llm-call、aos-agent tick／start／stop、換掉舊 llm／tool cpu）時的歧義與實作選擇、要使用者拍的 |

舊規範已於 2026-09-24 換掉（副本在 proto5.1/spec/）。
