# proto7-2 測試導引

← [proto7-2 README](../README.md)「測試」一節（從 README 拆出，內容原樣）；怎麼跑見那裡。

離線、純標準庫，459 項約 230 秒（10-09 loop7 整合時實跑，含 adapt C8-03 一案；`test_matrix*.py` 是 A2／A3 回歸矩陣，每個故障注入案例都斷言故障確實命中；要逐條規則都命中用 `_matrix.Fault.check_rules()`，T8-07）。核心測試在 `tests/core/`，模組包的在 `modules/<包>/tests/`，上層任務包的在 `packs/<包>/tests/`，counter／歷史 module 的在 `modules/tests/`；共用工具（`base.py`、`_matrix.py`、`_proc.py`、測試鉤子 `_hooks.py`）留在 `tests/`。各資料夾的測試檔名要唯一。每個測試類別的 docstring 開頭標類別：`〔core〕`、`〔<包名>〕`（control、subd、once_retry、diag、tools、observe）或 `〔misuse M-<契約卡號>〕`（誤用造成的，照[組件契約藍圖](../notes/component-contracts.md)，之後隨精簡刪掉）。測試起的子程序一律**先收程序、再刪空間**（`tests/_proc.py` 的 `track`／`reap`，`tests/base.py` 收尾時再掃一次環境變數 `AOS7_ROOT` 是暫存根的程序）；暫存根在 `/tmp/aos72-test-*`，跑完會刪。

| 檔 | 測什麼 |
|---|---|
| `tests/core/test_tick_tock.py` | 槽與 run 號、換 run 清基礎設施檔留任務的檔、each 跳過與 max_live 槽、keep 不雙開、from_round／enabled、once、刪槽（報完再一回合）、**200 回合檔案數不變**、tock 之後才結束的 run 照樣報、inst |
| `tests/core/test_ctl.py` | kill（run 必填）、kill 範圍（setsid 孫程序、偽造 pgid、inst 的另一個 session）、**lost 前的身分掃描（NODE＋TID＋RUN）**、掛載與執行中加掛；loop7 K1：runner 還在啟動時 kill 回 unknown 留請求（R8-01）、清場後補收最多 3 輪（K-04）、node 級記著的 pgid 重驗（R8-29）、runner 先用 `AOS7_RUN`（R8-10）、`is_runner` 只看 argv 前兩項（R8-11）、stat 怪名稱（R8-12）、任務環境不帶繼承來的 `AOS7_*` |
| `tests/core/test_mount_dyn.py` | loop7 K4：動態加掛在連結建好、birth 未記時被殺可冪等恢復（A8-07）、失敗紀錄不算已掛（R8-09）、`fact` fstat 失敗關 fd（R8-07）、指示詞非 ASCII 數字索引與 `$at: null`（R8-28） |
| `tests/core/test_once_threestate.py` | **once 在 launch 標記後、birth 後、Popen 後、刪項目前各點 kill -9 tick**、成組 once 中途被殺；帶 launch 的 once 改排程後不重跑（N-86）；**三態**：round.json／birth.json 讀不到、starttime 讀不到、槽列不出來 |
| `tests/core/test_daemon.py` | **登記／取消登記**、node 刪掉／搬走／換掉 → missing、看不到≠不存在、**early_tock 兩種**、**pause owner**、resume 順便 wake、resume rounds、stop／SIGTERM、第二個 daemon、root 搬走、回條同名蓋掉、控制檔洪水與壞檔、處理丟例外的請求刪掉不重做、log.on、卡住的 tick／tock、**kill -9 daemon 後新 daemon 收回合不雙開**、舊動作接管；loop7 K2 `TestDaemonDurableRecovery`：回收意圖落 nodes.json `reaping`、被殺重開續收、確認乾淨才開新時間線、register／unregister 寫檔失敗可重送、paused.json `steps` 接續 rounds 倒數（R8-02／03／04、C8-01／02、N-06） |
| `modules/subd/tests/test_subd_ownership.py` | **子 daemon 包**（包裝程式 aos7-subd）：守門檔與 owner、allow-stop、stopped.json、人手重開、子根位置檢查與重複認領（含別名路徑，R8-24）；三層 subroot 環境與收尾（N-66） |
| `modules/subd/tests/test_subd_recover.py` | 子 daemon 包 **重開前回收前代**（A5-01）：父 kill 後原任務收乾淨、paused node、起 argv 前／回收中／回收完被殺可接續、掃不完不起新代、壞紀錄、不碰 sibling 與本代；回收後斷言「全部收完」且以 starttime 認身分（T8-03） |
| `modules/subd/tests/test_subd_keep.py` | 子 daemon 包 **被允許的 stop 留下的任務不誤收**：stop 回條寫不進去（A8-09）、刪 stopped.json 重接時 argv 前被殺（MC-01）；回收記錄不巢狀（R8-18） |
| `packs/step/tests/test_step.py` | **step 任務包**：步驟表直譯器、槽外結果檔、檢查器；直譯器各中斷點接回不多派、unknown 不誤報、耐性、pause、wake、restart_on_end、close；loop7 S：run 步 `unknown_codes`（A8-10(b)）、過期 intent 走 on_unknown（R8-13）、重送額度記 request 層 `resends`（R8-14）、補加只准同回合（R8-22）、啟動清死暫存檔（C8-03）、三個 crash 點先驗 exit -9（T8-02） |
| `packs/adapt/tests/test_adapt_unit.py`、`test_adapt_flow.py` | **adapt 任務包**：轉換鏈與誤差界、三組流速、來源 pause／重開／重建、壞來源檔、dst pause、任務被殺接回、門檻邊界、step `num` 條件吃暫存器、300 回合檔數不長；數值精確度（A8：精確十進位鏈、發布不失真、門檻精確比、超出 float 範圍 out_of_range） |
| `packs/budget/tests/test_budget_ledger.py`、`test_budget_step.py` | **budget 任務包**：grant／帳／入口，競爭、各持久點真 SIGKILL、效期與時鐘、獨立核帳（可用＋在途＋已用＝初始）、接 step 的同 request 不重扣；loop7 B：payload／重播回條讀不到退 3（A8-08）、加權成本（D6）、`gateway/` 死暫存檔（C8-03）、fakeapi 開 `unknown_codes [3]` 重送同 request（A8-10）、崩潰核帳在重起前快照（T8-04） |
| `modules/audit/tests/test_audit_wrapper.py`、`test_audit_allow_threads.py` | 稽核包：包裝過的任務寫檔有紀錄；`AOS7_AUDIT_ALLOW` 只放寬自己 node 內的巢狀邊界、每次重讀（N-66／D9）；多 thread 同時寫不漏記（R8-25） |
| `modules/control/tests/test_control.py` | 控制包：restart（同槽新 run、state 接得上、加掛帶過去）、reload 與拒絕、壞表不 kill、req_id 去重、請求端／tick／tock 在交接點被殺只重起一次 |
| `modules/once_retry/tests/test_once_retry.py` | once 保證包：x.retry_lost 的 once 從沒起來過就加回跑一次、預設最多一次、舊欄位被拒、模組當 keep 任務跑；真 lost 候選（T8-08）、槽被 keep 重用／birth 讀不到／缺／撤回時的 pending 處理（R8-26） |
| `tests/core/test_errors.py`、`test_exits.py` | 錯誤四分支（G1 寫表三態、G2 tick 失敗不算回合、不是一般檔＝不知道）；timeline 壞設定（巨大整數 interval 等）用預設並記錯、node 照開回合（A8-11＋R8-20）；核心給模組的出口（`x` 照抄、`never_started`、stop-guard.json） |
| `modules/diag/tests/test_diag.py` | 診斷包：aos7-diag 照抄 last_error 並給恢復步驟、按需列出判不出的槽、唯讀（跑前後檔案不變）；proc-stat 兩條用 `Fault.check_rules()` 逐條規則驗命中（T8-07） |
| `tests/core/test_timeline_rounds.py` | loop7 K3：tock 後確認讀取不知道、下圈讀到已關只補扣一次 rounds（R8-05 `owe_round`）；退避指數上限、wait 後清 wake（R8-06） |
| `tests/core/test_budget.py` | **防再胖**：核心 `lib/aos7_*.py` 總行 ≤ 2800、實際程式 ≤ 2200；10-09 起只印不擋（D7，`ENFORCE = False`），超過時逐檔表印到 stderr |
| `modules/tests/test_modules_history.py` | counter 示範、歷史 module、history 事件也截行；來源檔名可逆編碼、不占 daemon 事件檔名（R8-17） |
| `tests/core/test_matrix_faults.py` | **A2 回歸矩陣：讀不到＝不知道**——/proc（list／stat／environ／cmdline）× EIO／ESTALE／EACCES × 情境（健康、孤兒、兩者都死、birth 壞）；birth／exit／pid／round／last-round 開檔與列槽讀不到；daemon 看 node 讀不到；last-round 寫後讀回不符＝回合不關（T8-05） |
| `tests/core/test_matrix_docs.py` | **A2 矩陣：檔案半寫、缺欄、型別錯**——round.json（不知道、不 tick、人寫回後接著數）、birth.json × 其他證據（活程序／exit／pid／都沒有）、last-round.json（重新產生、不跳號）；ENDED once 在 tock 三個點被殺的重播收尾（T8-06） |
| `tests/core/test_matrix_once.py` | **A2 矩陣：once／keep 在 tick 七個點與 aos7-run 兩個點 SIGKILL**——執行次數、lost 只報一次、同槽不雙開；runner-before-exit 恢復前驗死亡快照（T8-01） |
| `tests/core/test_matrix_a3.py` | **A3 回歸**：kill 帶 run 的重播（請求刪不掉、處理到一半被殺）只對同一個 run、生命週期檔換 FIFO、mount 子目錄暫存、重播通知失敗記錄（F47：不跨回合補送）、P2-01 wake 提前結束固定 interval 回合 |
| `tests/core/test_options_a3.py` | `until_round` |
| `tests/core/test_matrix_misc.py`、`test_matrix_daemon.py` | **A2 矩陣其餘**：node 本身換成符號連結（同 inode／指到 root 外）＝missing 且不寫出 root、rounds 按 owner、暫存檔清理、wake 不保留、tock.json 晚於總結 |
