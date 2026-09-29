# 生命週期與恢復

← [基底](README.md)｜[共用契約](../contracts.md)

## B-601：按需執行〔使用者方向 2026-09-28，[來源](../../notes/2026-09-28-linux-resources-and-task-scheduling.md)〕

agent 的登記及 home 長存；無事件、無到期工作時不保留專屬程序與固定 CPU worker。tick 是短命的狀態推進工作，工具另行准入；等待 LLM 或工具完成不能讓 tick 原地阻塞占席位。身份與權限不以程序是否常駐決定。

**Given** 10000 個已登記 agent，只有 10 個有事件；**When** 觀察無維護到期的 60 秒窗；**Then** 其餘 9990 個沒有 tick 程序與週期喚醒，仍可透過登記找到身份及資料。

## B-602：claim 與單寫者〔建議預設，未拍板〕

Owner：控制 writer 管 claim，launcher 管活程序，tick 管提案。控制層一次交易挑 ready／due agent、取得准入額度、分配 attempt、遞增 generation，保存 live claim。每 agent 同時至多一個 live tick claim；home 另有獨占鎖作程序互斥。輸入事件只新增 pending，不得因已有 tick 而丟棄。tick 完成交易在同一快照核對較新的 input／result，依 S-201 重算當前可推進投影；只有後續 run 的輸入不喚醒仍在 wait 的當前 run。

generation 是單寫者 fencing，不是殺程序工具。lease 預設 30000 ms、heartbeat 唯一責任者是可信 supervisor，每 10000 ms 透過控制寫入者更新活性，tick／工具不得自報續租；逾期只觸發對帳，不得立即另開 tick。重派前須確認舊 cgroup 清空及 home 鎖可取得。tick 提案提交按 C-05；舊 generation 一律 stale_generation，不能修改 pointer 或發新工作。工具可以平行執行但不能寫權威 checkpoint。

**Given** tick 結束前一刻新輸入到達，或 lease 過期但程序仍活；**When** 完成／對帳；**Then** 新輸入維持 ready，活舊 tick 未清除前不開第二寫者。

## B-603：控制程序重啟〔建議預設，未拍板〕

〔使用者方向 2026-09-29，[裁定](../../notes/2026-09-29-verdicts.md) 7〕**重啟全殺是已知行為**：首版 control 與 work 可在同一個 systemd unit（預設 KillMode=control-group），控制端 stop、restart、崩潰後自動重啟，或 WSL VM 整台關機時，在途工作全部被殺；恢復時這些 attempt 一律照本條結算，沒有可信已發布結果者全部變 unknown，不承諾重新認領孤兒程序。work 分到獨立 slice 留給後續版本。

啟動先取得控制 writer 的排他鎖，打開帳本，暫停新派工但允許只讀診斷。按非終局 attempt 對帳受管 cgroup、boot ID、PID starttime、耐久結果與啟動閘門記錄。禁止以 PID 數字直接 kill，也不把 pidfd 序列化後重用。

有可信已發布結果且域清空者導入一次；域內仍活者先接管監看，若無法安全接管則按取消流程清空，再結算 unknown；主程序已不在但後代還在亦先清理。記錄 starting 但無可信「從未放行」證據時不能判作安全未執行。已無程序、無結果、不能證明從未放行者 unknown，Error=result_unknown，保留外部副作用不明標記，不自動重做。

有確切閘門未放行證據且域已清空者 failed／spawn_error，可由上層 retry_class 決定新 attempt。實際機器 reboot 後舊 boot ID 不符，只表明舊程序已死，不表明外部副作用未發生；boot ID 相同也不表示舊程序仍活（例如 WSL 只終止 distro），存活以受管 cgroup 是否 populated 為準。完成基本對帳後解除無關 agent 的准入，未知工具／LLM 所屬 run 依排程規格轉人工處理。控制 tick 例外：已有 C-05 提交收據就保留已提交 checkpoint／final，程序收尾的 unknown 不撤銷提交，也不把已成功 run 改為 needs_attention；仍須清空舊程序才釋放 claim。沒有提案收據則維持舊 checkpoint，先清空舊範圍，再以新控制 tick job／generation 重新推進；因 tick 不直接執行外部工作，這不授權重做任何未知工具／LLM attempt。

**Given** 有在途 tool／LLM attempt 時分別發生 daemon crash、控制端 restart、整機 reboot、WSL VM 在 10 秒內消失、PID 重用；**When** 恢復；**Then** 在途 attempt 中沒有可信已發布結果者全部變 unknown，不錯殺非受管程序、不盲目重跑，已持久結果不被遺失。**Given** 睡醒後牆鐘大跳；**When** 恢復與派工；**Then** 逾時按經過時間判斷，不因牆鐘跳動一次全部判逾時。

## B-604：停機與退役〔建議預設，未拍板〕

正常 stop 由管理者發起，先停止新准入，保留 ready／queued，等現有工作 `stop_grace_ms`（可設定正整數；原生 Linux 建議 30000，WSL 關機大約只給 10 秒，建議不超過 8000），未結束者走 B-203；寬限內來不及收尾而被 systemd 或 VM 關機殺掉者，下一次啟動依 B-603 變 unknown；結果、計量與對帳資料寫入後退出。stop 超時或 kill 失敗需非零回報，列未清空 attempts；不可刪其 cgroup 或假釋放名額。強制停止亦先持久取消意圖；控制 writer 無法寫入時只能盡力停程序，下一次恢復視證據結算。

停用登記先 enabled→disabled，阻止新准入，再排空其所有 attempts；已排隊工作保留供取消或恢復。退役須管理者明示，完成無活程序、無 pending claim、quota／檔案所有權清單與未結清結果核對，才 status=retired。首版不自動回收 UID、GID、project ID，不自動刪 home；歷史資料與權限所有權需要另行明示處置。改 generation 不能消除舊檔案 ownership。

**Given** WSL 關機只給約 10 秒而工作未收尾；**When** 下次啟動恢復；**Then** 這些 attempt 全部 unknown，不因寬限未滿就當作已完成或可安全重跑。**Given** agent 有 setsid 後代及舊 UID 檔；**When** stop／retire；**Then** 先清空程序，留下資料清單與 retired 登記，該 UID 不分給新 agent。

## 待使用者拍板與現況

無常駐 worker 為方向；claim、lease、stop 數值及退役流程是可實作預設。萬級目標與恢復時限須實測，本文沒有宣稱已達成。
