# 執行器

← [基底](README.md)｜[共用契約](../contracts.md)

## B-201：啟動與狀態交接〔建議預設，未拍板〕

Owner：控制層負責 attempt 狀態與准入名額，supervisor 負責實際程序。輸入為已准入 job、唯一 attempt ID、可信登記版本；輸出為 [B-103 結果](work.md)。控制交易先寫 `reserved` 與派出意圖，啟動器以 attempt ID 去重，建立受控 cgroup 後記 `starting`。啟動閘門尚未放行前，child 只能執行固定可信啟動碼，不能讀 agent 描述或 fork 工作。

完成資源、群組、UID、fd 設定，持久保存程序識別與「準備放行」記錄後才可放行；控制層記 running。實際放行與 DB 並非原子交易，重啟遇不確定窗口按生命週期對帳，不再放第二個相同 attempt。exec 失敗由 close-on-exec 錯誤通道回報 spawn_error；啟動失敗須清空 cgroup 才歸還名額。禁止 worker 常駐等待下一份工作。

**Given** 在 reserved／starting／放行後分別殺控制程序；**When** 重啟；**Then** 每個 attempt 至多一個受管執行範圍，不能因 DB 尚未 running 再次啟動。

## B-202：程序樹與完成〔建議預設，未拍板〕

每 attempt 使用唯一 leaf cgroup；supervisor 保持在控制域，持有 pidfd 與 exec 錯誤通道。程序識別保存 boot ID、PID、starttime、cgroup 相對路徑；PID 不單獨作授權或殺程序依據。主程序退出後若後代仍存活，進收尾；先向可識別後代送 SIGTERM，預設等 5000 ms，再 `cgroup.kill`。無法送訊號、無法確認 populated=0，不得宣告 succeeded 或釋放程序名額。捕獲主程序退出結果並不等於所有子孫結束。

正常退出須等待 pipes 排空、結果持久發布、cgroup 無程序；才提交終態並回收程序名額。若後代被強制清理，結果 reason=signal、state=failed，另附受限診斷；不能將主程序 exit 0 包裝為完整成功。歷史資源計量先存控制帳本再刪空 cgroup。

**Given** 工具 fork＋setsid 後主程序退出；**When** 收尾；**Then** 後代也被停止，名額僅在確認清空後釋放。

## B-203：取消與逾時競態〔建議預設，未拍板〕

取消輸入為已認證 attempt ID 與 reason；授權者限 owner 或管理者。尚未放行可直接阻止放行並清理；running 先記 canceling、SIGTERM、5000 ms 後 kill，再保存結果。取消僅在已確認無活程序後成 canceled；無法確認為 unknown 並保留受占資源，交管理者處理。timeout 使用執行期間 monotonic clock，排隊時間不算；重啟無法恢復單調基準時立即對帳並保守取消，不給全新 timeout。

終態提交是競態裁決點：成功結果已提交則取消回已終止；取消意圖先提交則之後取得 exit 0 也按 canceled。timeout 先提交則結果 failed／timeout。取消的 RPC 成功只代表已接收意圖，客戶端需查終態；不能保證撤銷外部副作用。

**Given** exit 0 與取消同時到達；**When** 交錯兩種交易順序；**Then** 終態依提交先後唯一決定，重送取消不重複釋放名額。

## B-204：OOM 與啟動資源耗盡〔建議預設，未拍板〕

啟動前記 leaf `memory.events` 基線；收尾讀差值。有 oom_kill 增量且工作失敗記 failed／oom；不能只把 SIGKILL 當 OOM。agent 父域 OOM 導致多工作死亡時記受影響 attempts 並附父域證據，無法歸因則 reason=signal 而診斷註明壓力。pids／fork／exec 的 EAGAIN 或 ENOMEM 記 spawn_error，保留原 errno。控制域不可受 agent memory.max 約束。

**Given** OOM、pids.max、exec 不存在各一例；**When** 啟動或執行失敗；**Then** 控制端仍可持久回報區別原因並收回已清空名額，沒有自動重試。

機制依據：[pidfd_open](https://man7.org/linux/man-pages/man2/pidfd_open.2.html)、[cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)。pidfd 追蹤程序實體；cgroup.kill／populated 管受控子樹，兩者不能互相替代。

## 待使用者拍板與現況

閘門實作可用受控 child 或 clone3，但驗收一致。5000 ms 等數值未拍板；無實作或故障注入結果。
