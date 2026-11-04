step 的既有 20 項測試全過（12.082 秒），新增 10 組探針確認 2 類組件 bug：工作直接從 wait 開始時耐性永不倒數；檢查器部分結構型別錯誤跳過診斷、直接拋出 TypeError。一般 run→wait、中斷接續、unknown／一次 resend 上限、pause／wake、close 與 restart_on_end 的既有保證在本線抽查中成立。這不否定另一線 CSV 長跑：CSV 由 run 起步，不會踩到初始 wait 缺陷。

| 覆蓋 | 結果 | 證據 |
|---|---|---|
| 既有 step 全套 | 20/20；12.082 秒 | [pack-tests.log](pack-tests.log) |
| 3 個中斷點 after-intent／after-add／before-accept | 既有 test_crash_points_advance_once 通過，各步各執行一次 | [pack-tests.log](pack-tests.log)、原測試程式 |
| intent 寫後中斷，延後到第 5 回合接回 | unknown；子工作執行 0 次、沒有補派，符合保守窗口 | [step-probes.json](step-probes.json) delayed_intent_unknown |
| 冪等子工作連續兩次無結果結束 | 同 request、a1→a2；共執行 2 次後 unknown，沒有第 3 次 | 同上 resend_at_most_once |
| 初始 wait／run→wait 對照 | 前者 8 回合後仍 running、since=null；後者差值 3 > patience 2 時 timeout | 同上 initial_wait_patience、entered_wait_patience |
| timeout kill | 請求帶 run=2；框架 halt timeout，沒有結果檔 | 同上 timeout_kill；其 exit 後續已被正常清槽，因此最終記錄 null 不代表未殺 |
| 暫時讀不到框架 | chmod 000 造成真實 EACCES，error 記 PermissionError；2 回合框架位元組不變，恢復後成功結束 | [step-extra.json](step-extra.json) frame_EACCES_freeze_recover |
| 逾時後結果遲到／resume | 結果到後仍 halted；resume 才採用原 attempt，a 共執行 1 次 | 同上 late_result_resume_close |
| close | 進行中拒絕，rc=3；結束後 rc=0、清 results、保留 out、closed=true | 兩份 JSON |
| pause／wake／restart_on_end | 既有 test_pause_freezes_patience、test_wake_option、test_file_count_bounded 均過；長跑由另一線提供 | [pack-tests.log](pack-tests.log) |
| 壞框架、改表 | 既有壞 JSON freeze／version halt 測試過；手改刪 pc 是 M，記 KeyError 但不列修 | [step-probes.json](step-probes.json) malformed_frame_misuse |
| 清理 | 自建 10 個 /tmp 根全移除，ps 根路徑匹配 0；使用原測試精準 root 身分／PID 群組清理，不用 pkill | 兩份 JSON cleanup；[cleanup.json](cleanup.json) |

發現 1（B）：初始 wait 的 patience 不生效。

- 契約：step README「直譯器」保證耐性用本地回合；spec §3 since 是走到現在這步的回合；§5.5 差值 > patience 到期。使用合格步驟表與單一 keep，前置條件成立。
- 重現：`python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/step/probe_step.py`，看 `initial_wait_patience`。表 start=w，w 為永不成立的 exists、patience=2；走真實 8 次 tick/tock。
- 結果：checker 無 error；seen 從 1 到 8、since 始終 null、phase 一直 running。對照 run→wait，since=3，round=6 就 timeout。
- 證據：[probe_step.py](probe_step.py)、[step-probes.json](step-probes.json)。
- 建議：建立／重開工作時，以目前確知的本地回合初始化 since；若當下回合未知，首次確知時再補。

發現 2（B）：檢查器未把部分結構錯誤轉成診斷清單。

- 契約：step README「檢查器」負責結構錯誤；spec §6 回 JSON issue 陣列、有錯 rc=1。作者把未通過檢查的步驟表交給 check，正是合法輸入，不能歸為內部檔誤用。
- 重現：同腳本 `checker_edges`，分別給 start=[]、run.ok=[]、wait.result.ok=[]。
- 結果：3 例皆 rc=1 但 stdout 空白，stderr TypeError「unhashable type: list」；沒有約定的診斷 JSON。scalar step=3 正確回 error，是對照。另 options.on_timeout=kill 被 wait 繼承時 check rc=0，未阻擋 §6「kill 只給 run」的限制；可與結構檢查一併處理。
- 證據：[step-probes.json](step-probes.json) checker_edges 各例含輸入與 stderr。
- 建議：先做欄位型別檢查再查圖／dict key，並用套用預設後的選項檢查 wait 的 timeout 限制。

契約缺口（G，可併主報告文件漂移）：spec §2 說 options 可由步內同名欄覆蓋；實際 run 步 `wake:true` 被 check 拒絕（不認得欄位），步欄位清單也未列 wake。README 說 run_all 預設不收 packs，但 runner `test_dirs()` 已收 `packs/*/tests`。前者先定清楚哪個選項可以逐步覆蓋，再讓 checker／欄位表一致；後者更新 README 文字即可。

外部故障（X）：SIGKILL 造成 intent 跨回合不明／子工作沒結果，均停 unknown 或依宣告只重送一次；框架 EACCES 暫停更新、記錯、恢復後續跑。這些按契約處理，沒有要修項。

誤用（M）：手改 frame 移除 pc 後會 KeyError；這违反 README／spec §7 的所有權前置條件，僅記「誤用、不處理」。既有壞框架測試通過不代表本輪要新增一般內部檔型別防護。

重現命令：

```sh
python3 proto7-2/tests/run_all.py packs/step/tests
python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/step/probe_step.py
python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/step/probe_step_extra.py
```

本線沒有改程式、既有測試或既有文件，沒有 commit／push，未使用 LLM，沒有碰 scratchpad。
