# astra-3 模組包分報告

六包抽查完成，12 個探針／既有單案、2.251 秒；探針的預期觀察全部成立，但其中 **2 案刻意斷言重現 bug**，不能把 runner 的 `OK` 解讀成產品無缺陷。找到 control 同請求並行的重複 restart（B）、audit 動態登記 node 後的漏報（B），另有完成後換代的 req_id 去重期限缺口（G）。原 A3-01 的**核心殘留 kill 重播**安全：帶舊 run 的控制跨 3 次換代沒有再次殺新 run。

證據：[探針腳本](probe_modules.py)、[JSON 結果](modules-results.json)、[精簡 log](probe.log)、[清理核對](cleanup.json)。執行 `python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/modules/probe_modules.py` 即可重現。

| 包 | 抽查與觀察 | 結果鍵 |
|---|---|---|
| control | 殘留 ctl.json 刪除 EACCES 注入命中 7 次；run 1→2→3→4；舊 kill 不殺新 run。回條保留請求 run=1，但後續 result 更新為「已换人」 | `control_stale_kill_replay` |
| control | reload 不合法不 kill；tasks.json EIO 命中後拒寫、不 kill；有效 reload 改 argv、x 並回 diff | `control_reload_and_g1` |
| control | 同 req_id 並行呼叫：第二個完成 birth#2 後第一個仍追加 once，得到同 req_id 的 birth#3 | `control_same_id_concurrent_snapshot` |
| control | 完成後立即重送回 done；普通 keep 換 run 後同 id 重送卻 added | `control_late_same_id` |
| once_retry | after-birth 真 SIGKILL：lost＋never_started；表讀 EIO 後 pending 保留；復原重試只排 1 項、副作用 1 次 | `once_retry_pending` |
| once_retry | 任務及 runner 已起後由 PID 殺掉：lost 無 never_started，不重派 | `once_retry_started_lost` |
| audit | 任務啟動後 CLI 動態 register 巢狀 node，越界寫誤記 ok:true，scan.bad 空 | `audit_registration_refresh` |
| diag | birth.json EIO 命中 1 次、uncertain 有原因；診斷前後檔案名字／大小／mtime／內容全同 | `diag_unknown_readonly` |
| tools | birth EIO 不寫 kill；tasks EACCES 不覆蓋表；8 組中文、分隔符、長 owner 檔名相異 | `tools_unknown_and_encoding` |
| subd | stop-guard 拒 stop、拒父 register 子空間內 node；allow-stop 留 stopped 並阻止重起；移除自己測試根的 stopped 後恢復；位置不合／重複認領拒起 | `_cases` 最後 3 案（借用既有測試，未改原測試） |

## 發現（主報告統一編 A4）

### M-B1：control 同 req_id 並行在 birth 快照過期後重複追加 once

- **分類 B，控制包自己的 bug。** 契約卡 §2.6「同一個意圖重播只生效一次」＋ §2.9 工具 bug 歸工具；新版 control README `restart` 第 2 點「槽現在 birth 已帶同 req_id → 不做、done」。README／API 未要求同 req_id 只可由單一呼叫者執行。
- **重現**：run 1 正常結束，把普通 keep 用合法 tasks API 設 enabled:false；A 呼叫 restart(req_id=concurrent)，讀 birth#1 後、拿表鎖前暫停；B 同 id 呼叫並正常 tick/tock 完成 birth#2；恢復 A。A 用舊快照追加相同 once，下一輪 birth#3 仍是 once:true、req_id=concurrent、restart_of=w#1。
- 只在 `edit_json` 入口插入排程 hook（1 次），重播真 API 與 tick/tock；沒有改生命週期檔。run 紀錄 `[1,2,3]`，後兩次都來自同意圖 once，disabled keep 不會自行起它們。
- **證據**：JSON `control_same_id_concurrent_snapshot` 的 `trace.birth_before_A_lock`、`queued`、`third_birth`。
- **一行建議**：拿到 tasks 表鎖後重驗 birth 的 run／req_id，再决定追加 once，避免用鎖前的完成證據快照。

### M-B2：audit 快取 node 登記表，動態 register 後把越界寫記成允許

- **分類 B，audit 自己的 bug；被稽核任務的越界動作是 M，這不免除稽核器的標示保證。** 契約卡 §2.7「模組自己的 bug 歸模組」，audit README 規則「ok＝自己的 node，扣掉巢狀別的 node／daemon 根，或掛載目標」。
- **重現**：daemon 只 register a；audit 包裝任務在 a 起來後寫 ready 並等 release；用公開 CLI register a/nested，等成功回條；放行任務，讓它直接寫 a/nested/result.txt。該任務沒有掛載巢狀 node。
- **實測**：register 回條 ok:true；該寫入紀錄 ok:true；scan 共 1 個任務、3 筆寫入，bad=[]。`sitecustomize.py` 第 61 行的 `others` 只在程式啟動算一次，巢狀檢查未刷新；沒有手改 nodes.json。
- **證據**：JSON `audit_registration_refresh` 的 `registration`、`write`、`scan`。
- **一行建議**：audit 判寫入邊界時刷新已登記 node 集合（或以可觀測的登記版本失效快取），不改核心。

### M-G1：control 完成證據的去重期限未明列

- **分類 G。** 契約卡 §2.6 概括承諾同意圖只生效一次；新版 control README 精確描述只檢查「目前」birth 的 req_id，但「重送同一件才沿用 id」未說保證到哪一代。
- **重現**：restart r 完成 birth#2，重送 r 回 done；普通 keep 結束並換成 birth#3 後重送 r，回 added，表再多一項 restart_of=w#3。這與殘留核心 kill/run 重播是兩回事。
- **證據**：JSON `control_late_same_id`。
- **一行建議**：先寫清 caller 的重試有效期間／如何判完成，再決定是否要比目前 birth 更長的去重記錄；不直接要求核心增加日誌。

## 清理與限制

最後一版全部 12 個測試根均已清除；以 `/proc/*/environ` 找測試根身分、再 `ps -eo pid,ppid,stat,args` 核對，存活程序與命中根路徑的程序皆為 0。只清自己 `/tmp/aos72-test-*` 根，未碰 scratchpad。未改產品程式碼／測試／文件，未 commit／push、未用 LLM。subd 父 kill 的 G3 由全套三跑線涵蓋；本線未另做重負載統計。
