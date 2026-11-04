# proto7-2 第五輪改進循環藍圖（loop5，astra）

> **改名（使用者 10-04）**：原名 account 會跟 Linux account 的定義重疊，包名改為 **budget**（`packs/budget/`、`<node>/budget/`、`budget_id`；「帳戶」改稱「一份預算」）。組件名 grant／ledger／gateway 不變。下文已替換；astra 原意見檔仍是舊名。

**本輪先修 A5-01，再整合 budget 第一版；兩者可平行實作，核心零新增。** 依原則 10，先定契約與歸屬，再修、再回歸。
本次只有唯讀設計，未改檔、未 commit、未執行會寫入的測試，未刪除或清空 scratchpad。
基準：唯讀重算核心 **2757／2800 總行、2123／2200 程式行**；astra-4 全套三次各 280 項通過，G3 壓力探針 0／10 通過。

依據：[原則](../../proto7/notes/principles.md)、[loop4](blueprint-loop4.md)、[astra-4](play/2026-10-04-astra-4-infra.md)、[核心契約](component-contracts.md)、[r1](../../proto7/notes/thinking/2026-10-04-r1-synthesis.md)、[r6 落地順序](../../proto7/notes/thinking/2026-10-04-r6-synthesis.md)。

**1．A5-01：由 subd 補完前代收尾**

| 問題 | 判定與依據 |
|---|---|
| 已確認現象 | 父 kill 後，三個保留正常身分、忽略 SIGTERM 的原任務全部存活；重開子 daemon 到 gen 2、r7 已關仍是原 PID／starttime。非 zombie、PID 重用或誤用。見[壓力證據](play/2026-10-04-astra-4-infra-evidence/stress/summary.md)。 |
| 直接缺口 | [subd 包裝](../modules/subd/aos7-subd)只有訊號轉送與等待，沒有持久的「前代尚未收乾淨」記錄及恢復動作。 |
| 寬限的角色 | 父 kill 最多等 1 秒；子 daemon 逐槽收尾，每槽可能各等 1 秒，整批收尾沒有完成保證。現有證據不能斷言每案被截斷的確切指令。 |
| 為何重開不會補收 | [核心 §5.4](../spec.md)先判任務／runner 是否存活；仍活就是 LIVE，只有疑似 lost 才進身分掃描。一般 daemon 重開接回活任務符合核心契約。 |
| 歸屬 | **B／subd**。[README](../modules/subd/README.md)把 §5.4 誤當成重開必收前代的保證。父 kill 回 `ok:true` 只表示核心 §6 的父任務收尾條件成立，不代表子空間已空。 |
| 核心是否修改 | **否，新增 0 行。** 不延長通用 kill 寬限、不改一般 daemon 重開語意；固定延長寬限仍無法保證任意數量的子任務都收完。 |

| 主方案：重開前回收關卡 | 實作約束 |
|---|---|
| 先留恢復依據 | subd 在起 argv **之前**，原子寫包自有生命週期記錄，標明擁有者、父 run、子根與尚未確認乾淨；不能等 SIGTERM handler 才寫。 |
| 恢復時取得獨占 | 持 `subd.lock`，並在回收期間取得 `daemon.lock`；其他 daemon 仍在就不起。讀前代記錄與子根登記範圍，固定待收的 node／run 身分。 |
| 包自己收前代 | 在 subd 內復用既有程序身分與 kill 工具，收前代 launcher、runner、任務並再次掃描確認；包含 paused node，無須 resume。避免尚未 fork 的舊 runner 在回收後又起任務。 |
| 不越界 | 只收認領子根內確認屬於前代的程序；排除自己、祖先與 sibling。不寫核心的 birth／exit／round，不改 pause；一般 daemon 重開照舊。 |
| 中斷與未知 | 查不清楚、收不掉或恢復中再被殺，保留包自有記錄，不起新 argv；下次繼續。沒有標記但已有舊 owner／槽，不直接當全新空間。 |
| 放行 | 確認前代已空，先寫本代未完成記錄，再釋放 `daemon.lock`、起 argv；`subd.lock` 全程持有。只有確認乾淨才解除未完成狀態。 |
| 文件同步 | subd 契約改成「由包在重開前補收」，移除「核心 §5.4 自動收前代」說法；原有外部 stop、守門檔與 `stopped.json` 行為保留。 |

**2．budget 第一版：契約卡**

以[草稿](../packs/budget/README.md)與 [astra 五項意見](play/2026-10-04-astra-4-infra-evidence/contracts/summary.md#account-草稿意見不算發現)收斂；三個邏輯組件都放 `packs/budget/`，屬通用任務包。

| 組件 | 職責 | 前置條件 | 保證 | 明確不管 |
|---|---|---|---|---|
| grant：使用權 | 判斷誰可在指定範圍與期間使用多少資源 | 發行者提供唯讀、固定內容的 grant；包含帳戶、持有人、資源／入口、額度、時鐘與效期 | 資格判定區分准許／拒絕／未知；讀不到不視為無限制；v1 明定 `delegate:false`，拒絕子 grant | 不量測資源、不算即時餘額、不保證供應或完成期限、不防惡意繞過 |
| ledger：帳 | 處理 reserve／settle，保存可用、在途、已用及去重證據 | 單一 `keep,max_live:1` 寫者；持有人送 reserve；settle 必須引用入口證據；同操作鍵內容一致 | 預留與餘額、去重結果同次原子提交；重播不重扣；未知保留預留；有支用照量結算，證明未支用才退 | 不把 step 失敗、`never_started`、逾時或 `usage.json` 當未支用證明；不管跨 node 一致性 |
| gateway：入口 | 核對資格與預留、准入資源、保存支用證據 | 合作式部署；請求人對應 grant 持有人；預留的帳戶、資源、入口、業務鍵與金額吻合；同業務鍵互斥 | 首次准入前查資格與效期；未知不放行但可續查；終局回條固定；本示範同業務鍵最多產生一次效果 | 不靠 caller 欄位提供 OS 隔離；不替任意外部 API 保證效果只發生一次；支用成功不等於工作產物成功 |

| 第一版範圍 | 決定 |
|---|---|
| 最小切片 | 單 node、一個帳戶、一種整數消耗資源、一個入口；一份不可再分的 grant。沒有 split、跨 node、動態配額算法、adapt 或 LLM。 |
| 非 LLM 示範 | **假 API 受理次數**：純本機假後端，每個業務請求預留 1 次。明確拒絕計 0；已受理後工作失敗仍計 1。效果可精確記錄，避免把 CPU／磁碟取樣誤當精確帳。 |
| grant 再分 | 本輪不實作、不宣稱支援。未來 split 必須同時驗「子不超父」並從父可用額度轉出，不能只複製 grant 檔。 |
| 時鐘 | 明定本 node 的 **completed_tock**：合法 `round.json` 為 closed 時取 round，open 時取 round−1；沒有合法值即未知。效期為 `from ≤ c < until`。 |
| 時鐘邊界 | pause 不前進；daemon 重開接續原回合，不綁 daemon gen。重建 budget／時鐘須換識別，不移植舊 grant。半開 until 不直接抄成核心含上界的 `until_round`。 |
| 到期 | reserve 與首次入口准入各查一次效期；到期擋新准入，已准入的恢復與結算繼續。讀不到時鐘不阻擋已有證據的結算。 |
| unknown | 非終局，可隨證據補齊更新；逾時只觸發查證／提示，**不自動退款**。 |
| 保存 | 帳、入口意圖／回條、效果與取消紀錄、去重證據放 `<node>/budget/`，活過槽刪除與 step close；v1 不自動清除，保存至帳戶明確退役。 |

**3．reserve → run → settle 如何接 step**

沿用 [step README](../packs/step/README.md) 與 [spec](../packs/step/spec.md) 的普通 run、request／attempt、槽外結果及 close；**不新增 step 種類，不改核心**。

| 項目 | 契約 |
|---|---|
| 接法 | 一個普通 `run` 呼叫 budget 包裝程式；內部依序 reserve → gateway run → settle。取得終局結算回條後才完成包裝命令，再由既有 step 結果包裝發布結果。 |
| 業務鍵 | `K = (budget_id, holder, step.request)`；同一 request 的新 attempt 沿用 K。attempt、slot#run 只作追查，不作新扣款鍵。 |
| 操作去重 | 分別使用 `(K,reserve)`、`(K,run)`、`(K,settle)`，避免 reserve 擋掉 settle。同鍵不同業務內容拒絕；attempt 等傳輸資訊不算內容變更。 |
| 帳提交與回條 | 餘額、操作結果、去重紀錄同次原子提交，再發布回條。帳已提交但回條未寫時，重開由帳重建，不再扣款。 |
| 入口恢復 | 呼叫後端前先持久記錄准入意圖；未准入者恢復須重查 grant，已准入者查詢／重播同 K。unknown 不保存成永久拒絕。 |
| 效果先於回條 | 假後端把「K 的效果記錄＋受理計數」同次原子提交；效果完成、入口回條未寫就被殺，仍能查回同一結果，不再受理一次。 |
| 全退所需證據 | 「查不到 K」不夠。取消須與支用互斥，持久留下 K 已取消的終局記錄，讓晚到 run(K) 也不能執行，才可 settle 0。 |
| 工作失敗 | `ok:false`、缺產物、命令退出非零或 `never_started` 都不能直接退款：已受理結算 1、確定取消結算 0、未知繼續預留。 |
| close 後重播 | step close 只清自己的結果；帳與入口仍認得 K。同 K 重播不重扣、不重做；新工作 inst 產生新 request 才是新交易。 |
| 帳的可觀察性 | 每筆能查 K、目前階段、預留、支用證據與結算結果；每次持久轉移皆滿足「可用＋在途＋已用＝初始額度」，各項非負。 |

**4．本輪順序與驗收**

| 順序 | 工作與完成門檻 |
|---|---|
| ① 先定契約 | 將本藍圖落成 subd 修正契約與 budget v1 spec；明列檔案所有權、去重期限與未知分支。 |
| ② 可平行實作 | A 線只動 `modules/subd/` 與其測試；B 線只動 `packs/budget/`、範例與其測試。共享導航由整合者同步。 |
| ③ A5-01 先過關 | 先通過原壓力探針，確認基礎設施修補成立，再做 budget＋step 整合驗收。 |
| ④ astra 回歸 | 沿用「藍圖→修→回歸」，新問題先按契約分類；誤用不列 bug，不因 budget 把資源語意塞回 daemon／tick。 |

| 驗收項目 | 通過条件 |
|---|---|
| A5-01 同探針 | 沿用 [run_stress.py](play/2026-10-04-astra-4-infra-evidence/stress/run_stress.py) 的負載與判準：三次全套並行，4＋3＋3 共 10 案，每案三個忽略 TERM 任務、父帶 run kill、追原 PID／starttime。**10／10 通過**，替代 daemon 出現後兩回合內原任務全消失；補查 r7 與殘留 runner。 |
| subd 恢復窗口 | 起 argv 前、回收中、回收完但尚未起新代時中斷皆可接續；paused node 也收；未知不起新代；不殺 sibling／新代；既有 stop、guard、認領、stopped 測試全綠。 |
| budget 正常與競爭 | 正常消耗 1；兩請求搶最後 1 額度只能一個成功；同鍵同內容並行不重做，異內容拒絕；持有人／資源／入口不符拒絕；子 grant 拒絕。 |
| budget 崩潰 | reserve／准入／效果／settle 各持久提交前後中斷；效果完成但回條未寫可恢復；unknown 補證據可結算；取消與晚到 run 競爭不雙花。 |
| budget 時間與失敗 | 到期前 reserve、到期後首次 run 被擋；已准入可結算；pause、daemon 重開、壞鐘／壞帳符合契約；工作失敗但已受理仍計 1。 |
| step 整合 | 同 request 新 attempt、槽已消失、結果未發布、close 後重播均不重扣／重做；結算恢復不依賴 step 結果仍存在。 |
| 獨立核帳 | 每次持久轉移重算守恆與非負；每 K 後端效果最多一次；全部終局後，實際受理次數與已用帳一致。 |
| 全套與既有回歸 | 從 repo 根跑 `python3 proto7-2/tests/run_all.py`，三次皆綠；重驗 A4-01～07、F47、§4.4、step 450 回合固定階段檔數。budget 帳依保存契約成長，另驗每 K 不因重播重複累積。 |
| 行數 | [test_budget](../tests/core/test_budget.py) 通過；本輪核心維持 **2757／2800、2123／2200**，保留 43／77 行餘量，不調高上限。 |
| 文件與證據 | 更新包契約、入口導航與 code map；新回歸另存 evidence，不覆寫 astra-4。全程不刪除或清空 scratchpad。 |