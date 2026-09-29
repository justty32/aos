# 生命週期與恢復

← [基底](README.md)｜[共用契約](../contracts.md)

## B-601：按需執行〔使用者方向 2026-09-28，[來源](../../notes/2026-09-28-linux-resources-and-task-scheduling.md)〕

agent 的登記及 home 長存；無事件、無到期工作時不保留專屬程序與固定 CPU worker。tick 是短命的狀態推進工作，工具另行准入；等待 LLM 或工具完成不能讓 tick 原地阻塞占席位。身份與權限不以程序是否常駐決定。

**Given** 10000 個已登記 agent，只有 10 個有事件；**When** 觀察無維護到期的 60 秒窗；**Then** 其餘 9990 個沒有 tick 程序與週期喚醒，仍可透過登記找到身份及資料。

## B-602：claim 與單寫者〔建議預設，未拍板〕〔09-29 精簡，依冗餘審查 B2、A1 claim 部分〕

Owner：控制 writer 管 claim，launcher 管啟動，可信 supervisor 觀測受管程序，tick 管提案。本條是 tick 程序互斥與活性的唯一規範來源；執行器的觀測、收尾與逾時機制沿用 [B-201～B-203](execution.md)。Claim 邏輯紀錄必填 `agent_id`、`attempt_id`、`generation`、`checkpoint_revision:int>=0`、`claimed_at_ms`、`state:held|released`；checkpoint_revision 記錄取得 claim 時的 checkpoint revision，held 即 live claim。

控制層只在沒有 held claim、已確認前代 tick 受管範圍清空且 home 獨占鎖可取得時，才一次交易挑 ready／due agent、取得准入額度、分配 attempt、遞增 generation，保存 held claim。每 agent 同時至多一個 live tick claim；tick 執行期間持有 home 獨占鎖。輸入事件只新增 pending，不得因已有 tick 而丟棄。tick 完成交易在同一快照核對較新的 input／result，依 [S-201](../scheduling/admission.md) 重算當前可推進投影；只有後續 run 的輸入不喚醒仍在等待既有工作的當前 run。

首版不設 lease、定期 heartbeat、suspect 狀態或租期續寫。supervisor 由程序退出事件或 tick deadline 觸發收尾與對帳；deadline 沿用 [B-101](work.md) 的 timeout_ms 與 B-203 的經過時間判定，不能因沒有續租而取消逾時。逾時仍活著的 tick 按 B-203 停止；主程序退出但後代仍在則按 B-202 清理。只有確認舊 cgroup 清空、home 鎖可取得，並導入持久結果與核對提案提交收據，或按證據記錄 unknown 後，才將 claim 轉 released 並釋放名額；無法確認清空時保留 held claim，不得重派。正常退出、無提案退出及逾時皆走此回收條件，不能只憑退出通知或 deadline 當成已停止。

generation 是提交 fence，不是殺程序工具；checkpoint revision 仍用來拒絕過期快照。tick 提案提交、舊 generation 拒絕及已提交提案的重送均按 [C-05](../contracts.md)。工具可以平行執行但不能寫權威 checkpoint。控制端重啟依 B-603、停機依 B-604，維持重啟全殺、無可信已發布結果的在途工作變 unknown，不因取消續租而改成接續孤兒工作。若將來 supervisor 與控制端可獨立長期失聯，再加活性協議。

**Given** tick 結束前一刻新輸入到達；**When** 完成交易；**Then** 輸入仍保留，ready 依 S-201 重算。**Given** tick 到 deadline 仍活著，或主程序退出但受管後代仍在；**When** 收尾／對帳；**Then** 未確認清空前不釋放 claim、不開第二寫者；清空並核對結果後才可重派，遲來舊提案不能改 checkpoint 或發新工作。

## B-603：控制程序重啟〔建議預設，未拍板〕〔09-29 精簡，依 WSL 查證二・4、5 與裁定 7、附 WSL〕

〔使用者方向 2026-09-29，[裁定](../../notes/2026-09-29-verdicts.md) 7〕**重啟全殺是已知行為**：首版 control 與 work 可在同一個 systemd unit（預設 KillMode=control-group），控制端 stop、restart、崩潰後自動重啟，或 WSL VM 整台關機時，在途工作全部被殺；恢復時這些 attempt 一律照本條結算，沒有可信已發布結果者全部變 unknown，不承諾重新認領孤兒程序。work 分到獨立 slice 留給後續版本。

原生 Linux 與 WSL 的 daemon 都必須由 systemd unit 啟動，讓控制端與受管工作進入配置的資源域；WSL 不用 `wsl.exe -e aos` 直接起 daemon，Windows 排程若需參與，只負責叫醒 WSL（見 [WSL 查證](../../notes/2026-09-29-wsl-machine-check.md)）。

啟動先取得控制 writer 的排他鎖，打開帳本，暫停新派工但允許只讀診斷。按非終局 attempt 對帳受管 cgroup、boot ID、PID starttime、耐久結果與啟動閘門記錄。禁止以 PID 數字直接 kill，也不把 pidfd 序列化後重用。

有可信已發布結果且域清空者導入一次；域內仍有殘留程序者一律按取消流程清空，不接續工作，無可信已發布結果者結算 unknown；主程序已不在但後代還在亦先清理。記錄 starting 但無可信「從未放行」證據時不能判作安全未執行。已無程序、無結果、不能證明從未放行者 unknown，Error=result_unknown，保留外部副作用不明標記，不自動重做。

有確切閘門未放行證據且域已清空者 failed／spawn_error，可由上層 retry_class 決定新 attempt。實際機器 reboot 後舊 boot ID 不符，只表明舊程序已死，不表明外部副作用未發生；boot ID 相同也不表示舊程序仍活（例如 WSL 只終止 distro），存活以受管 cgroup 是否 populated 為準。完成基本對帳後解除無關 agent 的准入，未知工具／LLM 所屬 run 依排程規格轉人工處理。控制 tick 例外：已有 C-05 提交收據就保留已提交 checkpoint／final，程序收尾的 unknown 不撤銷提交，也不把已成功 run 改為 needs_attention；仍須清空舊程序才釋放 claim。沒有提案收據則維持舊 checkpoint，先清空舊範圍，再以新控制 tick job／generation 重新推進；因 tick 不直接執行外部工作，這不授權重做任何未知工具／LLM attempt。

**Given** 有在途 tool／LLM attempt 時分別發生 daemon crash、控制端 restart、整機 reboot、WSL VM 在 10 秒內消失、PID 重用；**When** 恢復；**Then** 在途 attempt 中沒有可信已發布結果者全部變 unknown，不錯殺非受管程序、不盲目重跑，已持久結果不被遺失。**Given** 睡醒後牆鐘大跳；**When** 恢復與派工；**Then** 逾時按經過時間判斷，不因牆鐘跳動一次全部判逾時。

## B-604：停機與退役〔建議預設，未拍板〕

正常 stop 由管理者發起，先停止新准入，保留 ready／queued，等現有工作 `stop_grace_ms`（可設定正整數；原生 Linux 建議 30000，WSL 關機大約只給 10 秒，建議不超過 8000），未結束者走 B-203；寬限內來不及收尾而被 systemd 或 VM 關機殺掉者，下一次啟動依 B-603 變 unknown；結果、計量與對帳資料寫入後退出。stop 超時或 kill 失敗需非零回報，列未清空 attempts；不可刪其 cgroup 或假釋放名額。強制停止亦先持久取消意圖；控制 writer 無法寫入時只能盡力停程序，下一次恢復視證據結算。

停用登記先 enabled→disabled，阻止新准入，再排空其所有 attempts；已排隊工作保留供取消或恢復。退役須管理者明示，完成無活程序、無 pending claim、quota／檔案所有權清單與未結清結果核對，才 status=retired。首版不自動回收 UID、GID、project ID，不自動刪 home；歷史資料與權限所有權需要另行明示處置。改 generation 不能消除舊檔案 ownership。

**Given** WSL 關機只給約 10 秒而工作未收尾；**When** 下次啟動恢復；**Then** 這些 attempt 全部 unknown，不因寬限未滿就當作已完成或可安全重跑。**Given** agent 有 setsid 後代及舊 UID 檔；**When** stop／retire；**Then** 先清空程序，留下資料清單與 retired 登記，該 UID 不分給新 agent。

## 待使用者拍板與現況

無常駐 worker 為方向；claim、stop 數值及退役流程是可實作預設；首版活性與回收依 B-602，不另設續租。〔09-29 精簡，依冗餘審查 B2〕萬級目標與恢復時限須實測，本文沒有宣稱已達成。
