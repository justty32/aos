# proto7-2 第五輪回歸（astra-5）：loop5 驗收

**A5-01 修補驗收通過；三次全套各 322 項全綠，450 已關回合長跑檔數沒有持續成長。但 loop5 尚不能整體判過：本輪確認兩個 B——A6-01 是 subd 的合法 stop 記錄中斷後錯收任務；A6-02 是 budget 後端讀取故障時，把未知誤報成退出碼 1。獨立核帳未發現重複扣款、重複效果或守恆破壞。** 沒有新增 G；誤用 M 不列 bug。

受測 HEAD：`392a1d645eceec98c41678ab2b685959e7ab0522`，在指定 `db387812` 之後。依[核心契約卡](../component-contracts.md)、各包 README 與[原則 9、10](../../../proto7/notes/principles.md)分類。只新增本報告及指定 evidence，未改既有程式、測試、文件；沒有 commit／push、沒有使用 LLM，也沒有刪除或清空 scratchpad。

**測試結果**

全套從 repo 根執行 `python3 proto7-2/tests/run_all.py -v`，耗時為實際經過秒數。

| 測項 | 結果 | 耗時／範圍 |
|---|---|---|
| 全套第 1 次 | 322／322，rc 0 | 137.309 秒 |
| 全套第 2 次 | 322／322，rc 0 | 132.839 秒 |
| 全套第 3 次 | 322／322，rc 0 | 139.680 秒 |
| 正式並行 G3 | 10／10 | 合計 26.236 秒；另加驗至 r7 |
| subd 邊界與中斷 | 13 組初探，2 組重現同一 B | stop 正常對照另 3／3；兩個失敗窗口各另 3／3 |
| budget 競爭／崩潰／故障 | 50 案完成；48 案符合契約或屬 M 觀察，2 案重現同一 B | 10.490＋1.652 秒；35 個真 SIGKILL 案例均命中 |
| budget 時鐘與 step | step／daemon 8／8；自製時鐘 4 組通過，另 2 組 M | 9.971 秒 |
| 獨立核帳 | 109／109 快照、311 筆轉移 | 5 個負對照全部抓紅 |
| A4-01～07、F47、§4.4 | 17 個核心＋8 個 step＋2 個 step F47 探針全過 | 未見退化 |
| step 長跑 | 450 已關回合 | 25.416 秒；111 個完成快照 |
| 核心行數 | `test_budget.py` 通過 | 總行 2757／2800；實碼 2123／2200 |

三次官方全套均無 failure、error 或 skip，**未觀察到全套不穩定案**。新增故障探針的兩個 B 是額外驗出的契約違約，不混成官方測試失敗。[全套與回歸摘要](2026-10-04-astra-5-infra-evidence/regression/summary.md)、[逐次結果](2026-10-04-astra-5-infra-evidence/regression/suites.json)、[budget 分類結果](2026-10-04-astra-5-infra-evidence/budget-crash/verdicts.json)。

**A5-01 驗收**

正式 G3 每案都先確認父 kill 後確有前代任務留下，再追蹤原 PID／starttime。10／10 在首次看到替代 daemon 時，三個原任務都已消失；換代約在 kill 後 2.240～2.280 秒。延長案追到新代 r7 已關，舊任務全部消失，舊 runner 全部退出；runner 當時短暫是探針 subreaper 下的 zombie，清場 waitpid 後消失，不能把它誤當活程序。[正式壓力結果](2026-10-04-astra-5-infra-evidence/subd/stress-parallel.json)、[r7 證據](2026-10-04-astra-5-infra-evidence/subd/g3-r7.json)。

這次正式樣本為 8 案重疊全套第二遍、2 案重疊第三遍，各案起訖都有全套在跑；**不是藍圖的 4＋3＋3 分布**。另外保留 10 次通過的預跑，但其多數沒有全套並行，不算進正式 10 案。

| subd 邊角 | 觀察與判定 |
|---|---|
| sibling、同名前綴 `a/sub2` | 都保留，沒有誤殺。 |
| 巢狀子空間的任務 | 被回收；README 明列包含巢狀，符合契約。 |
| 人手非 aos 程序，只有 cwd 在子根 | 沒有 AOS7 身分則保留。非 aos 執行檔本身不構成誤用。 |
| 非 aos 程序帶子 node 的 AOS7 身分 | 依身分被回收；合法繼承身分者原本就屬管理範圍，不列 bug。 |
| subd 起 argv 前 6 個 SIGKILL 窗口 | 全部命中，重開可接續清理，符合 X 恢復保證。 |
| argv 已起後 2 個 wrapper SIGKILL 窗口 | 子 daemon 還持 `daemon.lock`，重開 rc 1、不回收現役 daemon，符合契約。 |
| 子 daemon 自己崩潰，非父 kill | wrapper rc 137；下一代回收前代再起，通過。 |
| allow-stop、不帶 kill | 正常完成時接回原 PID／starttime；提交中斷反例見 A6-01。 |

[完整邊界、中斷與清理摘要](2026-10-04-astra-5-infra-evidence/subd/summary.md)。

**發現清單**

**A6-01〔B／subd〕允許 stop 的記錄提交中斷，重開錯收應接回的任務。**

- 契約：[subd README](../../modules/subd/README.md)「被允許的 stop 之後不回收」及 stopped 擋重起保證；不帶 `--kill` 的 stop 留下任務，依文件刪掉 `stopped.json` 再起應接回。
- 重現：合法 `--allow-stop` 子 daemon 接受無 kill 的 stop，成功回條及 `status.stopped=true` 已存在。分別在 `stopped.json` 暫存檔 rename 前、以及 stopped 已提交但 `subd-life.json` 的 stopped 尚未提交時，對 wrapper 真 SIGKILL。
- 結果：前一窗口直接重開；後一窗口先確認 marker 擋重開，再依 README 刪 marker 重開。兩者 life 正本仍為 running，原任務被回收並起 run 2。兩窗口各另確認 3／3；正常 stop 對照 3／3 保留同一 PID／starttime。未手改 life／owner，原任務在回收前為存活 S，非 zombie 或 PID 重用。
- 歸屬：SIGKILL 是 X 觸發，但合法 stop 的恢復路徑做了契約禁止的破壞性回收，故是 subd 的 B。
- 證據：[重複確認與身分資料](2026-10-04-astra-5-infra-evidence/subd/confirm-stop.json)、[可重跑探針](2026-10-04-astra-5-infra-evidence/subd/confirm_stop.py)。
- 建議修法：由 subd 統一合法 stop 的持久判定與恢復，能從既有停止事實接續未完成提交；僅交換兩次寫入順序不足以涵蓋更早窗口。

**A6-02〔B／budget call〕後端讀不到仍在途，卻以退出碼 1 回報。**

- 契約：[budget README 的 call 契約](../../packs/budget/README.md)與 [spec §6 第 2 點](../../packs/budget/spec.md)：非終局未知回 3，1 表示已結算但不成功或被拒。
- 重現：開帳、單一 ledger、同 K 已有 intent；讓 `backend.json` 讀取遭遇 EIO，再重跑 call。另以有效既存 backend 暫設權限 000，實際 EACCES 獨立確認，不依賴注入器。
- 結果：兩案都是 rc 1、stdout 沒有 JSON、stderr traceback；K 保持 intent／inflight，尚未結算。恢復權限後 backend 原始內容未變，同 K 可成功結算且不重扣。grant／ledger／gateway 的同類 EIO 對照均正確回 3。
- 歸屬：合法內容遭遇外部讀取故障，call 漏掉既有 unknown 分支，故是 B。**沒有觀察到帳損或重複效果**；影響是上層按 1／3 分流時得到錯誤訊號，不擴大宣稱所有 step 接法都會停止重試。
- 證據：[EIO 案 `eio-backend.json`](2026-10-04-astra-5-infra-evidence/budget-crash/verified/results.json)、[真 EACCES 案 `eacces-backend`](2026-10-04-astra-5-infra-evidence/budget-crash/extra/results.json)、[重現與程式位置](2026-10-04-astra-5-infra-evidence/budget-crash/summary.md)。
- 建議修法：在 budget 入口／call 的共同故障邊界，把 Unknown／讀取 OSError 轉為非終局 unknown 與退出碼 3，保留 intent／預留並沿同 K 重送。

**budget 驗收與獨立核帳**

40 個同 K call 只受理一次；60 個不同 K 搶額度 17，恰 17 受理、43 拒絕；同 K 兩種內容各 20 個 call，只有一種內容成功；40 組 run／cancel 競爭，每 K 最後只有受理或取消，晚到 run 不新增效果。

35 個真 SIGKILL 案例包含 spec 的 9 個鉤子，以及 26 個實際 rename 前後窗口，涵蓋 init、reserve／settle 帳、intent、backend 效果、gateway 終局、取消、inbox／回條與輸出。每案都有命中與退出 -9 證據，並保留中斷及恢復快照。unknown 留預留，取消無效果才退，效果已提交後取消回原終局。[50 案摘要與重跑方式](2026-10-04-astra-5-infra-evidence/budget-crash/summary.md)。

效期半開邊界、open／closed 的 completed_tock 換算、pause 耐性、真 daemon SIGKILL 重開均通過；已准入 intent 在到期後可恢復，新 K 則拒絕。step 五個中斷點都以同 request 的新 attempt 接續；close 後重播不增帳，restart_on_end 產生新 request 才是新交易；槽刪後仍可獨立 settle，已受理但工作失敗仍計 1。[整合證據](2026-10-04-astra-5-infra-evidence/budget-integration/summary.md)。

獨立核帳器只用 Python 標準函式庫，**不 import budget、核心或既有測試程式**。重放每筆 log，重算守恆、非負、序號、每 K reserve／settle 唯一性，再比對 ops、內容雜湊、終局證據雜湊、效果及 accepted 計數；終局快照另要求在途為 0、used 等於效果總量。109 份快照含中斷狀態，合計 311 筆轉移全部通過；這是跨快照核對筆數，不宣稱 311 筆獨立交易。五個負對照為受理計數錯、log 餘額錯、重複 reserve、結算雜湊錯、缺 ops，全部被拒。[核帳器](2026-10-04-astra-5-infra-evidence/budget-integration/audit.py)、[跨線核帳](2026-10-04-astra-5-infra-evidence/budget-integration/crash-audits.json)、[負對照](2026-10-04-astra-5-infra-evidence/budget-integration/negative-controls.json)。

手改壞帳、刪帳、重建時鐘沿用舊 grant 都依卡片標 M。壞／缺帳實測不自動開空帳、不受理且保留請求。時鐘另觀察到 `clock_hw` 只保存成功 reserve 的值；人手退鐘但仍高於此值可放行。因重建時鐘沿用舊預算已被前置條件排除，沒有找到合法 daemon 操作自然退鐘的反例，不列 B／G，也不要求為此增添核心防護。

**budget「五個自列缺口」評估**

來源有落差：受測 HEAD 與建包 commit `025d2bfe` 的 spec 都只有 §1～§8、84 行，**沒有題目所稱末尾五項自認缺口**。已提出來源詢問，收尾前未取得另一份清單，因此不能宣稱完成那份清單的逐條評估。下面改以確實存在的 [astra-4 五項草稿意見](2026-10-04-astra-4-infra.md)逐條對照，明確不是冒充所指清單。[來源查核](2026-10-04-astra-5-infra-evidence/budget-integration/contract-source.json)。

| 可追溯的五項舊意見 | 現版評估 | v1／後續 |
|---|---|---|
| gateway 前置條件不足 | 已明列合作式 holder、同 K 同內容預留、鎖與後端入口界線。 | v1 已具備；不用擴充 OS 隔離。 |
| 工作失敗不等於未支用 | 只依入口證據結算；已受理後失敗仍計 1。 | v1 已具備並通過。 |
| unknown 不能永久定案或自動退款 | 契約與持久狀態符合；backend 讀故障的退出碼違約。 | **A6-02 應在 v1 修。** |
| request／attempt 去重與 close 後保存 | K 不含 attempt；帳與入口活過槽刪、step close。 | v1 已具備並通過。 |
| grant 再分與效期時鐘未定 | v1 明拒子 grant，completed_tock 與半開效期已定並驗過。 | 時鐘 v1 已具備；split／跨 node 合理留待後續。 |

**450 回合長跑與既有回歸**

真 daemon 執行 CSV convert→stats→end，`restart_on_end:true`、interval 20ms。正式結果另驗 `round.json` 為 `open:false` 且 round=450：25.416 秒，451 個取樣、111 個完成快照全部報表正確，每步 attempt=1，halt／error=0。同 ended 階段全部固定 **10 檔、4,381～4,397 bytes**；全階段 job／node／root 檔數為 4～11／7～30／8～37。本次 450 回合未見同階段檔數持續成長，不外推任意長度；budget 帳依保存契約成長，與 step 自身檔數分開判。[長跑資料](2026-10-04-astra-5-infra-evidence/regression/step/longrun.json)。

A4-01 掛載故障、A4-02／06 控制競爭與去重期限、A4-05 動態登記邊界、A4-03／04／07 step 耐性／型別／選項均未退化。F47 同回合重播補通知、跨回合不補；history gap、once_retry 漏取樣、step 槽外結果與原耐性都符合各自契約。§4.4 真 SIGKILL 後 once 不重起，正常與重播都於報結束的下一個 tock 才刪槽。[逐項回歸](2026-10-04-astra-5-infra-evidence/regression/summary.md)。

QA 工具本身有三項校正：長跑補強「已關回合」斷言；EIO 注入器改為真正命中核心使用的 os.open；核帳快照改用每次唯一目錄與寫者鎖，避免前次檔案混入。先行資料保留，正式統計只採校正後結果，沒有把工具假失敗列成產品 bug。

四條線均已結束，自建 /tmp 測試根已清、程序按 PID 回收並以 ps 核對；286 個既有 tracked proto7-2 檔案 SHA256 前後相同，HEAD 未變。相對連結與最終程序檢查見[收場稽核](2026-10-04-astra-5-infra-evidence/final-audit.json)。

**最該修的三條**

1. **A6-01：subd 合法 stop 的中斷恢復。** 會殺掉明訂應保留的任務，優先修。
2. **A6-02：budget 後端故障的 unknown 回報。** 保留目前正確的帳與預留行為，修正退出碼及結果。

沒有第三條已確認 B／G，不湊數。
