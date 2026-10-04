# proto7-2 第三輪回歸（astra-3）：精簡核心、模組包與 step

**精簡後的既有回歸三次皆為 272／272 通過；step 正常 CSV 工作連跑 450 回合也穩定，但額外探針確認 5 類組件 bug、3 類契約缺口。** 最需要先處理的是加掛讀取失敗會毀損出生紀錄、控制包同請求的並行重送會多起一次，以及 step 從 wait 開始時耐性永不倒數。這些都有前置條件成立的反例，不需要把已刪的誤用保護加回核心。已知 subd G3 本輪未重現，不能視為已修。

日期：2026-10-04。實測 HEAD：`2188f7303e6d1485fa0ff553792268652fece01d`，在題述 `2ee8c63b` 之後。四條檢查線並行，只新增本報告與同名 evidence；未修改既有程式、測試、文件，未 commit／push，未呼叫 LLM，未動 scratchpad。分類依[組件契約卡](../component-contracts.md)、[原則 9／10](../../../proto7/notes/principles.md)；遇到舊卡與新規則衝突列 G，不擅自擴大保證。

## 測試結果表

| 項目 | 結果 | 耗時／範圍 | 證據 |
|---|---|---|---|
| 全套第 1 次 | 272／272，零 skip | 80.971 秒 | [三次數據](2026-10-04-astra-3-infra-evidence/core/suites.json) |
| 全套第 2 次 | 272／272，零 skip | 80.679 秒 | 同上 |
| 全套第 3 次 | 272／272，零 skip | 80.947 秒 | 同上 |
| 核心追加探針 | 4 個 until_round 案符合；2 個加掛反例成立 | 合計 6 案；兩反例合併 A4-01 | [核心探針](2026-10-04-astra-3-infra-evidence/core/core-probes.json) |
| 六個模組包 | 12 項定向檢查完成；發現控制競態、稽核漏判及去重期限缺口 | 包含 3 項既有 subd 測試，不另加成新案例 | [模組數據](2026-10-04-astra-3-infra-evidence/modules/modules-results.json) |
| step 既有測試 | 20／20 | 12.082 秒；與全套重疊 | [step 輸出](2026-10-04-astra-3-infra-evidence/step/pack-tests.log) |
| step 追加探針 | 10 組完成；2 類 B、選項契約 G | 中斷、耐性、checker、讀取失敗、resume、close | [主要探針](2026-10-04-astra-3-infra-evidence/step/step-probes.json)、[追加探針](2026-10-04-astra-3-infra-evidence/step/step-extra.json) |
| CSV 手寫 Python／step 對照 | 8 案最終統計完全相同 | 每案 10,000 列；數字見後表 | [對照數據](2026-10-04-astra-3-infra-evidence/comparison/comparison.json) |
| step 真 node 長跑 | 450 個已關回合、112 次工作結束，無 halt／error | 25.195 秒 | [長跑數據](2026-10-04-astra-3-infra-evidence/comparison/longrun.json) |

全套從 repo 根執行 `python3 proto7-2/tests/run_all.py`，以 `PYTHONDONTWRITEBYTECODE=1` 避免新增快取。三次共 242.597 秒、816 次測試執行，仍只有 **272 個不同案例**。組成是核心 218、模組 34、step 20，完整名稱見[測試清單](2026-10-04-astra-3-infra-evidence/core/test-inventory.json)。耗時是牆鐘時間；其他 QA 線同時執行，並非獨占效能量測。

探針的「完成／assert 通過」可能表示成功重現產品缺陷，不能解讀成所有產品保證都通過。讀取故障案記錄實際命中次數；程序中斷使用真 SIGKILL。控制並行案以排程 hook 固定交錯順序，不偽造 birth、tasks 或完成結果。

### 精簡後 A2／A3 與錯誤路

| 舊項目／本輪重點 | 本輪判定 |
|---|---|
| A2-01、02、03、A3-09：程序／回合／once／kill 誠實性 | 現存矩陣三次全過；合作式程序的未知維持保守，不把壞 birth 推成空槽。加掛另有漏網，見 A4-01。 |
| A2-05、A3-01、04、05：控制重播與完成證據 | 核心殘留 kill 必帶 run，跨新 run 不會再殺；刪請求 EACCES 命中 7 次仍成立。請求端並行與較晚重送另見 A4-02、06。 |
| A2-04、A3-02、03：symlink、身分可見性、非一般檔 | 登記及 node 本身檢查仍在；中間路徑替換、主動脫離身分、手改生命週期檔依新契約為 M。主要生命週期非一般檔測試仍保守。 |
| A2-06、11：owner 倒數與 wake | owner 各自倒數、early 回合中 wake 不遺留、fixed wake 行為，現有測試通過。 |
| A2-07、A3-07：暫存清理 | 包含 mount-req／mount-done 的死寫者清理測試通過，活寫者保留。 |
| A2-08、10、12、13、A3-06、08 | 診斷、history 上限、先總結後通知、owner 編碼及失敗通知補送，現有測試通過；工具追加不同中文／特殊字元／長 owner 名未碰撞。 |
| A2-09：用量模型 | 屬尚未實作的上層用量契約，不宣稱已驗證 kernel。 |
| G1：壞 tasks 表拒寫 | 半寫、FIFO、EIO 既有測試通過；模組探針的 EIO／EACCES 各命中，表不變，restart 不 kill。 |
| G2：tick 失敗不吃 rounds | 真 chmod 唯讀測試三次都執行、未 skip；失敗時保留 3，恢復後恰跑 3 回合再 pause。 |

逐項測試映射與靜態核對在[核心審查](2026-10-04-astra-3-infra-evidence/core/core-review.json)。`fact／proc／Unknown／hold` 的主要路徑有回歸支撐，但不能從全綠推論每處讀取都已統一；`aos7_mount` 的寬鬆讀取正是反例。

刪除的 F31／F33／F28／F03／F36 未發現需要恢復原保護：人手弄壞 birth、讓身分不可讀、違反 runner 啟動約定、替換中間路徑或改 pgid 都是 M。這是契約與程式核對，**未重新實跑每一種已接受的誤用**。若 birth 是核心自己弄壞，如 A4-01，責任仍在核心，不能套用 M。

### 模組與 step 抽查涵蓋

| 組件 | 實測觀察 |
|---|---|
| control | reload 不合格與 G1 拒寫均不 kill；正常 reload 有 diff、新 birth 的 x；核心 kill 重播安全。並行同 ID 與完成證據期限見發現。加 once 後中斷由既有控制包回歸涵蓋。 |
| once_retry | `never_started` 才排重試；表 EIO 時留下 pending，恢復後只加一項。確實起過再 lost 的任務不重試。 |
| subd | owner、拒絕未授權 stop、允許 stop 後父不擅自重起、subroot 規則通過；G3 三次全套未觸發。 |
| audit | 固定邊界既有案通過；動態登記巢狀 node 漏判見 A4-05。 |
| diag | birth EIO 命中 1 次，回 uncertain 與提示，檔案內容不變。 |
| tools | birth 不明時不猜 kill 目標；壞表拒寫；中文、特殊字元與長 owner 名分開。 |
| step 中斷／unknown／resend | 既有 after-intent、after-add、before-accept 中斷回歸通過。intent 延後至 r5 接回時停 unknown、實際派工 0 次；兩次無結果只到 a2，不會派 a3。 |
| step 框架／耐性／pause／wake | 真 EACCES 兩回合框架位元組不變，記錯後可恢復；run→wait 正常逾時；初始 wait 失敗。pause、wake 既有測試通過。 |
| step timeout／resume／close | timeout 的 kill 帶 run；遲到結果先留著，resume 後採用原 attempt，未重跑。進行中 close 拒絕，結束後清 results、保留 out。timeout 的 halt 名稱差異列 G。 |
| step restart_on_end | 既有檔數測試及本輪 450 回合長跑通過。 |

## 發現清單

以下 B 是要修的組件缺陷；G 先釐清／同步契約；X、M 不列待修。

### A4-01〔B〕加掛把讀不到當空值，刪合法請求或寫壞 birth

- **契約**：卡 2.3；[核心 spec](../../spec.md) §0 未知保留、§4.5 加掛。前置為正常合作式任務、合法加掛請求。
- **重現**：先起 keep 任務並收 r1，再投合法 `mount-req/data.json`。分別在讀請求、加掛函式重讀 birth 時注入 EIO；兩案各命中 1 次。前段槽判定正常，沒有手改 birth。
- **結果**：第一案刪請求，回 `raw:null／ok:false／not a JSON object`；第二案把完整 run1 birth 覆寫成只有 `mounts`，回條卻 `ok:true`。故障解除後原任務仍活，槽變 UNKNOWN。
- **證據**：[core-probes.json](2026-10-04-astra-3-infra-evidence/core/core-probes.json) 的 `mount_request_EIO_consumed`、`mount_birth_EIO_clobbered`；[重現腳本](2026-10-04-astra-3-infra-evidence/core/core-probes.py)。位置：`aos7_mount.py` 的請求與 birth 寬鬆讀取。
- **建議修法**：加掛改用 `fact` 保留未知，記錯、留請求、禁止更新 birth；不恢復 F31 的複雜推回邏輯。

### A4-02〔B〕控制包並行重送同 req_id，仍可多排一次重起

- **契約**：卡 2.6 的控制歸屬改由[control README](../../modules/control/README.md)「去重」具體定義：目前 birth 已帶同 req_id 就不再做；沒有單一呼叫者前置。
- **重現**：A 讀 run1 birth，停在取 tasks 鎖前；B 用同 ID 完成重起，run2 birth 還帶該 ID；A 恢復。排程 hook 命中 1 次，任務與 tick／tock 都是真實執行。
- **結果**：A 用舊快照再加 once，run2、run3 都是同 ID 的 once。探針在 run1 後停用 keep，因此 run3 不是 keep 自動重起。
- **證據**：[modules-results.json](2026-10-04-astra-3-infra-evidence/modules/modules-results.json) 的 `control_same_id_concurrent_snapshot`；[重現腳本](2026-10-04-astra-3-infra-evidence/modules/probe_modules.py)。
- **建議修法**：在表鎖內重讀 birth、核對 req_id 與原 run 後再 append，把完成判定與加項放在同一鎖定範圍。

### A4-03〔B〕step 初始 wait 沒有耐性起點

- **契約**：[step 契約卡](../../packs/step/README.md)「直譯器」及 [spec](../../packs/step/spec.md) §3、§5.5：耐性自進入目前步驟的本地回合起算。
- **重現**：合格步驟表 `start=w`；w 等永不存在的檔，`patience=2`，跑 8 次真 tick／tock。
- **結果**：checker 通過；`seen` 到 8，`since` 始終 null，仍 running。對照 run→wait 的 `since=3`，到 r6 正常 timeout。
- **證據**：[step-probes.json](2026-10-04-astra-3-infra-evidence/step/step-probes.json) 的 `initial_wait_patience`、`entered_wait_patience`；[重現腳本](2026-10-04-astra-3-infra-evidence/step/probe_step.py)。
- **建議修法**：新建／重開框架時，以確知的目前本地回合初始化 since；回合暫時未知則首次確知時補上。

### A4-04〔B〕step checker 部分壞型別直接拋例外，也漏查繼承的限制

- **契約**：step 檢查器卡及 spec §6：檢查結構、回 JSON 診斷陣列，有 error 才退出 1；`on_timeout:kill` 只給 run。
- **重現**：分別送 `start=[]`、run 的 `ok=[]`、wait 的 `result.ok=[]`；另讓 wait 繼承全域 `on_timeout:kill`。
- **結果**：前三案 rc1 但 stdout 空白，stderr 是 `TypeError: unhashable type: list`；最後一案竟 rc0。對照 scalar step 正常產生 error。把壞表交給檢查器是它應處理的輸入，不是內部檔誤用。
- **證據**：[step-probes.json](2026-10-04-astra-3-infra-evidence/step/step-probes.json) 的 `checker_edges`，各案保留輸入與輸出；腳本同 A4-03。
- **建議修法**：先驗欄位型別再查跳轉圖，並對套用全域預設後的有效選項檢查限制。

### A4-05〔B〕audit 不更新登記邊界，漏掉新巢狀 node 的越界寫入

- **契約**：卡 2.7 的模組責任；[audit README](../../modules/audit/README.md)「規則」：自己的 node 範圍須扣掉巢狀的其他 node／daemon 根。
- **重現**：在 node a 起受稽核的 Python 任務，再經真 daemon 的 register 成功登記 `a/nested`，最後讓原任務寫 `nested/result.txt`。
- **結果**：writes 紀錄 `ok:true`，scan 的 `bad=[]`；audit 沿用啟動時登記表。被稽核任務越界本身是 M，但辨認此類行為正是 audit 的工作，不能因此免除 audit 自己的保證。
- **證據**：[modules-results.json](2026-10-04-astra-3-infra-evidence/modules/modules-results.json) 的 `audit_registration_refresh`，含成功 register 回條、寫入紀錄與 scan；腳本同 A4-02。
- **建議修法**：稽核判定時更新登記邊界，或依登記表版本失效快取；不增加核心執行限制。

### A4-06〔G〕control 完成證據只留目前 birth，重送期限沒有寫清楚

- **契約**：control README 要新意圖用新 ID、同意圖重送沿用 ID；同時只描述 pending once／目前 birth 去重，未定保證期限。
- **重現**：同 ID 首次 restart 到 run2，立刻再送回 `once:done`；等正常 keep 換 run3，再送同 ID。
- **結果**：run3 已不帶該 ID，回 `once:added` 並寫針對 run3 的 kill。這與 A4-02「完成證據當下仍在卻漏看」不同，也與已修的核心殘留 kill 重播不同。
- **證據**：[modules-results.json](2026-10-04-astra-3-infra-evidence/modules/modules-results.json) 的 `control_late_same_id`；腳本同 A4-02。
- **建議修法**：明定完成證據與同 ID 重送的有效範圍；若要求跨普通換 run 仍去重，再由控制包保存所需證據，不直接把 ctl-seen 加回核心。

### A4-07〔G〕step 選項覆蓋與 timeout 停點名稱不一致

- **契約**：step spec §2 說步內同名欄可覆蓋 options；步欄位清單卻未列 wake。§5.5 說 timeout kill 後停 unknown。
- **重現**：在 run 步填 `wake:true` 跑 check；另執行 A4-03 同腳本的 `timeout_kill`。
- **結果**：前者被拒為不認得的欄位；後者確實送帶 run 的 kill 並停住，但 `halt.kind=timeout`，不是文字寫的 unknown。未發現假報完成，缺口在可接受選項與可讀停點名稱。
- **證據**：[step-probes.json](2026-10-04-astra-3-infra-evidence/step/step-probes.json) 的 `checker_edges`、`timeout_kill`。
- **建議修法**：列明哪些 options 允許逐步覆蓋，統一 spec、checker 與 halt 名稱。

### A4-08〔G〕精簡後契約卡仍含舊核心責任與規則

- **契約**：組件卡 §1、2.2～2.6；核心 spec §0／2.3；step README 的測試入口。
- **重現**：比對現行文件、`run_all.py` 與三次測試清單。
- **結果**：卡仍有 ctl-seen／ctl_id、核心 restart、kill run 選填、pid uid、G2 待定；step README 還說預設不收 packs。另 spec §0 說非一般檔為未知，§2.3 與 daemon 控制處理卻明定非一般控制檔搬 `.bad`、給失敗回條。該輸入違反 JSON 物件前置，不因此另報核心 B。
- **證據**：[core-review.json](2026-10-04-astra-3-infra-evidence/core/core-review.json) 的 `contract_drift`、[test-inventory.json](2026-10-04-astra-3-infra-evidence/core/test-inventory.json)。
- **建議修法**：同步卡片到現行組件歸屬，明寫非一般 daemon 控制檔例外，修正 packs 測試入口文字。

### A4-09〔X〕中斷／暫時讀不到：本輪這些案例按契約保守處理

- **契約**：核心卡 2.3／2.6；step spec §5 的 unknown、resend、暫停更新。
- **重現**：intent 後 SIGKILL 並延後恢復、連續兩次子工作無結果、框架 chmod 000、控制請求 unlink EACCES。
- **結果**：分別停 unknown；只重送一次；記 EACCES 並保留框架、恢復後完成；舊 kill 不傷新 run。
- **證據**：[step-probes.json](2026-10-04-astra-3-infra-evidence/step/step-probes.json)、[step-extra.json](2026-10-04-astra-3-infra-evidence/step/step-extra.json)、[modules-results.json](2026-10-04-astra-3-infra-evidence/modules/modules-results.json)。
- **建議修法**：無；這些是已按契約處理的外部故障，不列待修。

### A4-10〔M〕手改框架與已刪保護的前置違反：誤用，不處理

- **契約**：step spec §7；核心卡 2.1／2.3／2.5／2.8 的檔案所有權、可讀身分及呼叫約定。
- **重現**：本輪實測手改 frame 刪掉 pc 後啟動；其他 F31／F33／F28／F03／F36 僅核對已定界線。
- **結果**：缺 pc 會 KeyError，但這是手改內部檔，不列組件 bug；也不因已接受的身分逃逸／路徑替換等情境要求核心長回原保護。
- **證據**：[step-probes.json](2026-10-04-astra-3-infra-evidence/step/step-probes.json) 的 `malformed_frame_misuse`、[core-review.json](2026-10-04-astra-3-infra-evidence/core/core-review.json) 的 `deleted_protection_boundaries`。
- **建議修法**：無，誤用、不處理；核心自己毀損檔案仍另依 A4-01 歸責。

## step 對照手寫 Python 的數字

共同工作為 10,000 列 CSV→JSON→四部門統計，共用同一份 [csv_worker.py](2026-10-04-astra-3-infra-evidence/comparison/csv_worker.py) 的演算法與原子產物發布。手寫版是**一支程式、單程序、自管逐步 checkpoint**，重啟略過已完成步；未加自動重啟 supervisor。step 使用真 daemon、keep 直譯器與 once 子工作。

故障固定在 convert 或 stats 處理完第 5,001 列、尚未發布該步產物時 SIGKILL。手寫版殺整個 pipeline 程序群組；step 殺子工作群組，直譯器與 daemon 仍活。人工命令不含首次啟動、觀察及注入故障；重派是必要的兩步之外額外啟動次數。

| 實作 | 中斷位置 | 恢復人工命令 | 額外重派 | convert 啟動次數 | stats 啟動次數 |
|---|---|---:|---:|---:|---:|
| 手寫 checkpoint | 無 | 0 | 0 | 1 | 1 |
| step 預設 stop | 無 | 0 | 0 | 1 | 1 |
| 手寫 checkpoint | convert | 1 | 1 | 2 | 1 |
| step 預設 stop | convert | 1 | 1 | 2 | 1 |
| 手寫 checkpoint | stats | 1 | 1 | 1 | 2 |
| step 預設 stop | stats | 1 | 1 | 1 | 2 |
| step 冪等自動 resend | convert | 0 | 1 | 2 | 1 |
| step 冪等自動 resend | stats | 0 | 1 | 1 | 2 |

8 案最終統計相同，沒有人工改 checkpoint、frame 或產物。手寫版的一個恢復命令是重新執行程式；step 預設的一個命令是 `resume --resend`。這兩個中斷點都只重做被殺的一步。

兩者都能直接讀 **1 個主要 JSON** 找到卡點：手寫 `checkpoint.json` 的 pc／done；step `frame.json` 的 pc／pending／halt。手寫 checkpoint 本身不記故障種類；step 有 unknown 原因與 request／attempt，可再用 results 及槽 exit 核對。探針另加的 events／gate 不算產品原生診斷。

單次耗時與完整快照在[對照分報告](2026-10-04-astra-3-infra-evidence/comparison/comparison-summary.md)及[JSON](2026-10-04-astra-3-infra-evidence/comparison/comparison.json)。這是指定中斷點的觀察，未比較所有提交窗口，也不據此宣稱某架構普遍較好或較快。

## until_round 啟動准入探針

| 情境 | 實測結果 |
|---|---|
| once 在 launch 後 SIGKILL，恢復時已過期 | 外部執行 0 次、恢復新啟動 0 次；once＋launch 留表。 |
| once 在 birth 後 SIGKILL，恢復時已過期 | 執行 0 次、重派 0 次；報一次 lost＋never_started，once 移除。 |
| once 指定忙碌槽，等待期間過期，之後合法 kill 原 run | 不起新的過期 once，項目留表。 |
| keep 在 r1 起、until_round=1 | 活到 r5 不被期限殺；合法 kill 後到 r8 仍總共只起 1 次。 |

四案皆符合「擋過期新啟動」，不是完成期限；到期仍活不算失敗。證據：[核心探針](2026-10-04-astra-3-infra-evidence/core/core-probes.json)。

## 長跑結果

一個真 node 跑原 CSV 範例（5 列、convert→stats→end），`restart_on_end:true`、`wake:false`、interval 20 ms。保存 r0～r450 共 451 個回合樣本，另取每次 ended 的同階段快照。

| 指標 | 結果 |
|---|---:|
| 已關回合／耗時 | 450／25.195 秒 |
| 不同 inst 工作結束 | 112，首末為 r4／r448 |
| 列數與 convert request 核對 | 112／112 正確 |
| 每工作兩步 attempt 都為 1 | 112／112 |
| halt／error | 0 |
| ended 工作目錄檔數 | 每次 10 |
| ended 工作目錄大小 | 4,381～4,397 bytes，末次較首次 +16 |
| 所有階段工作／node／root 檔數 | 4～10／7～27／8～35 |

同階段沒有隨工作次數累積結果檔；node／root 的瞬間檔數包括不同執行階段與暫存，不能用其 min／max 判洩漏。最後兩回合已能開始下一個工作，112 是實際核對過的完成數。這是數百回合、數十秒觀察，不宣稱數日耐久性或永久固定 bytes。[完整數據](2026-10-04-astra-3-infra-evidence/comparison/longrun.json)、[重現腳本](2026-10-04-astra-3-infra-evidence/comparison/run_comparison.py)。

## 重現與清場

從 repo 根執行；各腳本只用自己的暫存根，最後按 PID／程序群組收尾。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/core/run-suites.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/core/core-probes.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/modules/probe_modules.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/step/probe_step.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/step/probe_step_extra.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/comparison/run_comparison.py --mode comparison
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/comparison/run_comparison.py --mode longrun --rounds 450
```

自建測試根已清，逐線 PID／`ps` 核對沒有本輪殘留程序；未使用 `pkill -f`。來源雜湊、證據 JSON／Python 語法、報告相對連結及最終程序核對見[最終稽核](2026-10-04-astra-3-infra-evidence/final-audit.json)。開場已有的 `proto7/user-advice.md` 未動。各線完整分報告：[核心](2026-10-04-astra-3-infra-evidence/core/core-summary.md)、[模組](2026-10-04-astra-3-infra-evidence/modules/modules-summary.md)、[step](2026-10-04-astra-3-infra-evidence/step/step-summary.md)、[對照／長跑](2026-10-04-astra-3-infra-evidence/comparison/comparison-summary.md)。

## 最該修的三條

1. **A4-01：加掛的未知讀取不得刪請求或覆寫 birth。** 會把外部讀取故障轉成核心自製的生命週期毀損。
2. **A4-02：控制包在表鎖內重新驗證完成證據。** 合法並行重送同一意圖，現在能多排一次重起。
3. **A4-03：初始化 step 的 wait 耐性起點。** 合格且有期限的工作會永遠等下去；修在 step 包即可。
