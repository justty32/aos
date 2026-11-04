核心線結論：全套連跑三次都是 **272／272 通過、零 skip、零 failure/error**，已知 subd G3 本輪未觸發。六個額外探針中，四個 `until_round` 保證符合預期；另兩個重現同一個 **B：加掛路徑把讀不到當空值，消費合法請求或覆寫核心 birth**。這不是刪除誤用保護帶來的合理退讓。沒有修改任何產品碼、原有測試與文件；只新增此 evidence 子目錄，未 commit/push、未使用 LLM。

| 全套次序 | 測試數 | unittest 秒 | wall 秒 | 結果 |
|---|---:|---:|---:|---|
| 1 | 272 | 80.915 | 80.971 | OK |
| 2 | 272 | 80.623 | 80.679 | OK |
| 3 | 272 | 80.891 | 80.947 | OK |

三次合計 816 次測試執行、242.597 秒 wall；不是 816 個不同案例。與其他 QA 線並跑，未做獨占性能量測。入口為 repo 根的 `PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/core/run-suites.py`。數據：[suites.json](suites.json)；每次完整但精簡的 unittest 輸出：[1](suite-1.log)、[2](suite-2.log)、[3](suite-3.log)。[test-inventory.json](test-inventory.json) 收錄 272 個 test id：core 218、audit 1、control 15、diag 3、once_retry 4、subd 5、tools 3、modules/tests 3、step 20。

**待主報告編號：B，加掛讀取不知道仍做破壞性動作。** 對應卡 2.3 tick 與核心 spec §0 U、§4.5 加掛；`aos7_mount.py:107/120` 與 `139/157`。兩案都先以正常 tick 起合作式 keep 任務，等待正常 pid.json、tock 關 r1，再寫合法 `mount-req/data.json`。

1. 請求讀取點注入 EIO：命中 1 次，tick r2 仍刪請求、回 `raw:null / ok:false / not a JSON object`，沒有掛載。故障不是格式錯；應保留請求等下一圈。
2. 只在加掛函式重讀 birth 那一點注入 EIO，前段 judge 正常：命中 1 次，birth 從完整 run 1 被覆寫成僅有 mounts，掛載回條卻 `ok:true`。故障解除後任務仍活，judge 變 UNKNOWN、tock 記 birth 壞的 errors。wrapper 僅限定既有 fault hook 的時序，不偽造 read_json 回值；壞 birth 是產品自己寫出的，不是測試手改。

重現：`PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/core/core-probes.py`。原始及後態、命中 path、回條、tock 在 [core-probes.json](core-probes.json) 的 `mount_request_EIO_consumed` 與 `mount_birth_EIO_clobbered`。建議一行：加掛的請求／birth 讀取改保留 fact 三態，U 留請求、記錯、不得更新 birth；不須恢復 F31 複雜身分推論。

**待主報告合併：G，精簡後契約卡漂移。** 卡 2.2 仍寫 G2 待定，卡 1／2.3／2.4／2.6 仍寫 ctl-seen/ctl_id、核心 restart、kill run 可省；卡 2.5 仍有 pid uid。現行 spec／實作均已改。另 spec §0 稱非一般檔 U，但 §2.3 與 daemon `ctl_one` 對非一般控制請求採 B、搬 `.bad` 並回條；這是前置不合法輸入的現有例外，不另列 B。建議一行：同步契約卡到現行組件邊界，將 daemon 此例外明寫清楚，不回加已刪的保護。

A2／A3、G1／G2 的逐項現存測試映射、F31／F33／F28／F03／F36 刪保護界線與四錯誤路審查記在 [core-review.json](core-review.json)。既有矩陣的 fault helper 每案強制命中 ≥1；三次全套均未 skip，G2 真 chmod 唯讀案有跑。未知的主要回合／槽／程序路徑仍符合契約；不能因全套通過便推論所有讀取路徑都對，加掛就是漏网處。

**`until_round` 額外四案均通過。** after-launch 真 SIGKILL `rc=-9` 後超過期限：零外部執行、零 recovery start，once+launch 留表。after-birth 真 SIGKILL 後超過期限：零執行、零重派，報一次 lost+never_started，once 移除。busy 同槽 once 到期後即使原 run 被合法 kill，也不新起、pending 留表。keep r1 起且期限為 1：活到 r5 沒被期限殺，之後合法 kill，到 r8 仍總共只執行一次。證據同 [core-probes.json](core-probes.json)；沒有把持續執行误解成「過期須被殺」。

自己的暫存空間均在 `/tmp/astra3-core-*`，已清除；正常測試 cleanup 以具體 PID／PGID 與 AOS7_ROOT 辨識收程序，沒有 `pkill -f`。最後同時查 `ps -eo pid,ppid,stat,args` 與 `/proc/*/environ`，自有根的程序匹配為空、殘留目錄為空：[core-cleanup.json](core-cleanup.json)、[suite-cleanup.json](suite-cleanup.json)。未讀寫或清空 scratchpad 既有內容。
