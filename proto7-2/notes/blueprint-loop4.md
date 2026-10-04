# proto7-2 第四輪修補藍圖（loop4）

依據：principles 7／9／10、astra-3 報告 A4-01～10、component-contracts、core-slimming 頂層定案、r6 落地順序。只讀 repo，Fable 2026-10-04。
現況：核心 2791／2800 總行、2151／2200 實際程式（餘 9／49）；272 測試全綠；主要約束是**總行**。

## 1. 逐條歸屬與修法

| 條 | 歸哪 | 類 | 修法（一兩句） | 動核心？ |
|---|---|---|---|---|
| A4-01 加掛讀不到當空值 | 核心 tick（`aos7_mount.serve`／`_serve_one`） | B | 請求與 birth 改走 `fact`：U＝那一件留著、不寫回條、不改 birth，記一筆到 tick 的 `mounts` 結果；BAD 請求照舊回 `ok:false`。birth 非 OK 物件＝不審、留請求。 | **是**：核心自己把 U 當 N 違反 §0（spec 已寫「請求＝那一件」）。約 +8 總行；由 F47 付（見下）。 |
| A4-02 控制包並行同 req_id 多起一次 | control 包 | B | birth 重讀搬進 `edit_json` 的 `add` 裡：鎖內 `fact(birth)`，`x.req_id` 已等於或 `run` 已非原 run → 丟哨兵不改表，回 `once:"done"`。 | 否 |
| A4-03 step 初始 wait 沒耐性起點 | step 包 | B | 新框架建立時 `since = rnd`（rnd 已知）；每圈開頭 `since is None and rnd is not None` 補上。 | 否 |
| A4-04 step checker 壞型別拋例外、漏繼承限制 | step 包 | B | `check` 先過一輪欄位型別（`start`／`ok`／`fail`／`then`／`result.ok` 必須字串），不合就加 error、跳過圖檢查；`on_timeout: kill` 改查**套預設後的有效值**：非 run 步有效值是 kill → error「要在步內改回 unknown／fail」。 | 否 |
| A4-05 audit 不更新登記邊界 | audit 包 | B | `sitecustomize` 的 nodes 集合改每次判定時重讀（或比 nodes.json mtime 失效）。只記不擋不變。 | 否 |
| A4-06 control 去重期限沒寫清 | control 包 README | G→文件 | 寫明：同 req_id 的完成證據＝「表上 pending once 或**目前** birth 帶該 id」；槽正常換 run 後證據消失，再送同 id＝新意圖。要跨換 run 去重由呼叫者自己留證據（例如記 `restart_of` 的回條）。不加回 ctl-seen。 | 否 |
| A4-07 step 選項覆蓋／停點名稱 | step 包 spec＋checker | G→文件＋小改 | spec §2 列明可逐步覆蓋的只有 `wake`、`on_timeout`、`on_unknown`（`restart_on_end` 是工作級）；run 步 FIELDS 加 `wake`。§5.5 改寫「kill 後 `halt.kind=timeout`，處理同 unknown（等人 resume）」，程式不動。 | 否 |
| A4-08 契約卡過時 | 契約文件 | G→文件 | 見第 2 節。 | 否 |
| A4-09／A4-10 | — | X／M | 不修；A4-10 的「手改 frame 缺 pc 會 KeyError」寫進 step spec §7 一句即可。 | 否 |
| 線頭 1：birth 先於移項、槽第三個 tock 才刪 | 核心 spec §4.4／§5.1 | 保證補寫 | 核心只承諾它控制的兩個原語：(a) once 項從表上拿掉時該槽 birth.json 已寫好（4.2 第 3→7 步順序，現狀即如此）；(b) 已結束的槽最早在**報結束的下一個 tock** 才刪（5.1 現狀）。「第三個 tock」是 step 從 (a)(b) 推出的，寫在 step spec §5 第 4 點旁，引用核心這兩句。 | 文件 0 行；加一個核心測試（test_point 在 birth 與移項之間 SIGKILL，斷言下一 tick 看到 birth＋launch 就移項、不多起——test_matrix_once 已有近似案，補明確斷言即可）。 |
| 線頭 2：F47 vs 卡 2.4 | 核心 tock／tick ＋ 卡 2.4 | 兩難→**做成選項，預設做 F47** | 預設：刪 `retry_notify` 與 tock skipped 分支、tick 開回合前的補送（約 −45 總行／−40 程式）；只留「寫不進去記 `notify_errors`」與同回合重播補寫（那是 K 中斷分支，留）。理由：S-11 本來就說任務只看得到最新 tock、可能漏（卡 2.7 也這樣寫）；跨回合補送是給 history 這類取樣模組的便利，不是核心保證；行數是本輪唯一的硬資源。卡 2.4 改成「通知寫失敗記 `notify_errors`，不補送；要補由模組讀 round.json 自己做」。另一選項：保留補送、把 F47 從待辦刪掉，則 A4-01 要另找 8 行（刪 docstring 由來說明可付）。 | 預設**是**（淨減）。改 `test_matrix_a3.TestReplayNotify` 兩案為「記了、沒補、下一回合正常」。 |
| 線頭 3：G3 subd 父 kill 1 秒 | subd 包（低；核心 kill 寬限是通用行為） | B（低）／未重現 | 本輪**不改程式**：subd README 界線補兩句——父 kill 的 1 秒是核心 kill 的通用寬限，子 daemon 收不完的子任務由**下一個子 daemon**起來時的身分掃描收（5.4）；要永久拿掉子空間，先對子 daemon 下允許的 stop、等 `stopped.json`，再拿掉父表那項。回歸加壓力探針試重現。重現了再做成選項：核心 tasks.json 項目選項 `kill_grace_s`（預設 1，約 +4 行，過三問：S-17、包裝程式延不了父的 SIGKILL 期限、通用）vs 子 daemon 併行收槽（改 kill_node，也是核心）。預設前者。 | 本輪否 |

小結：動核心的只有 A4-01（+8）與 F47（−45），淨減約 37 總行；spec 改三處（§0 例外、§4.4 保證、§7 F47）。其餘全在包與文件。

## 2. 契約卡同步（A4-08）

**拆法：核心卡留在 `notes/component-contracts.md`，包的卡住進各包 README**（step 已是這個格式）。再過時的根因是卡複述了機制細節；改成**卡只寫四欄（職責／前置／保證／明確不管），每條保證引 spec 節號，機制不重抄**，spec 改時 grep 節號就找得到卡。

要改的卡與方向：

- **§1 清單與所有權表**：拿掉 `ctl-seen.json`；`owner.json`／`stop-guard.json` 標「包寫、核心只讀守門檔」；`tasks.json` 加 `launch` 欄是 tick 的；控制檔處理那列改「daemon ctl＋槽 kill」。
- **2.1 daemon**：前置「node 路徑沒有符號連結」→「node 本身不是符號連結；中間段換連結＝誤用」；保證改「登記時檢查＋O_NOFOLLOW 開 node」（頂層定案 2）；補守門檔一句。
- **2.2 時間線**：刪「G2 待定」，改「tick 退出碼非 0／3＝失敗、不算回合、不扣 rounds（§2.1）」。
- **2.3 tick**：刪 ctl-seen／ctl_id；加掛保證改成 A4-01 修後的文字；加線頭 1 的保證 (a)。
- **2.4 tock**：照 F47 選項結果改最後一句；加保證 (b)。
- **2.5 run**：pid.json 欄位去掉 `uid`（現狀沒有）。
- **2.6 控制檔處理**：只剩 daemon ctl（2.3）與槽 kill（§6，`run` 必填）；restart／reload／req_id 整段移到 control README 的「契約卡」節；刪「不帶 run 的 kill 打到新 run」（已不存在）；補「請求檔不是一般檔＝B 拒收（搬 `.bad`），是 §0 U 規則的例外，因為請求檔只可能是別人放的」——同一句也進 spec §0。
- **2.7 模組**：縮成一段「包的卡在各包 README」＋連結表（control、subd、once_retry、audit、diag、tools、step）；每個包 README 補「契約卡」節（四欄，約 6～10 行）。
- **2.8 任務**：四類例子裡把「帳本、准入」從核心任務移到通用包（r6 §1.4 對齊 core-slimming §10）。
- **§4 A2／A3 試分類、§5 建議、§6 拍板題**：刪（歷史與已定案的東西），§6 改一行「三題已在 core-slimming 頂層定案」。§3 錯誤分類與流程圖留，它是方法。

## 3. 本輪範圍：先只修，不推進 account

建議：**只修＋契約同步＋F47＋線頭 1**，不開 account／adapt。理由：(1) 5 條 B 橫跨 4 個組件，加上卡的拆分，已是一輪的量；(2) 原則 10——account 要先有自己的契約卡（grant／預留／結算的前置與保證），那是下一輪藍圖的開場，不該夾在修補裡；(3) r6 第二步「step 接 kill 子任務」其實已成立（A4-07 驗證 `on_timeout: kill` 送帶 run 的 kill），剩的是 account；(4) step 自己的 B（A4-03／04）先綠，account 才有乾淨的地基。
若修補提前收完，唯一順手可做的是 **account 契約卡草稿（只文件、不程式）**，放 `packs/account/README.md` 草稿或 notes，供下一輪藍圖用。

## 4. 驗收條件

**測試**（全套 ×2 皆綠，從 repo 根 `python3 proto7-2/tests/run_all.py`）：
- 核心新增 3：加掛請求 EIO → 請求留著、無回條、birth 不變；加掛時 birth EIO → birth 不變、請求留著、故障解除後下一 tick 正常掛上；birth 與移項之間 SIGKILL → 下一 tick 移項、只起一次（線頭 1）。
- F47：`TestReplayNotify` 兩案改斷言「記 `notify_errors`、不補送、下一回合 tock.json 正常」；同回合重播補寫案不變。
- control 新增 1：A 停在表鎖前、B 同 id 完成重起、A 恢復 → 表上恰一個 once、A 回 `done`。
- step 新增 4：`start=w` 的 wait 到期照 patience timeout；`start=[]`／`ok=[]`／`result.ok=[]` 各回 JSON error、rc 1、stderr 無 traceback；全域 `on_timeout:kill`＋wait 步 → error；run 步 `wake:true` 通過 check。
- audit 新增 1：執行中 register 巢狀 node 後寫入 → `ok:false`、scan 的 bad 有它。
- 預期總數 272 → 約 281。

**行數**：`test_budget` 綠，且**總行餘量 ≥ 30**（目標約 2755／2800、程式約 2120／2200）；若選保留補送的選項，餘量 ≥ 9 即可但要說明 A4-01 的 8 行從哪付。

**文件**：spec §0 例外句、§4.4 兩條保證、§7 F47 結果；contracts 照第 2 節改完後 `grep -n 'ctl-seen\|ctl_id\|uid\|G2' notes/component-contracts.md` 為 0；七個包 README 各有「契約卡」節；control README 去重期限；step spec §2／§5.5／§7、README 測試入口句（run_all 已預設收 packs）；subd README 界線兩句；problems.md 加 A4-01～08＋F47 各一列；play README astra-3 那列「後續」填 commit；05-gaps G3 加一行「loop4 未重現，界線已寫，重現再做選項」。

**回歸（astra-4）**：A4-01～07 探針改跑已修版（期望反例不再成立）；三次全套；step 450 回合長跑檔數不長；G3 壓力探針（全套並行時，父 kill 帶 3 個不理 SIGTERM 子任務的 subd ×10）——通過準則是「無孤兒，或孤兒在下一個子 daemon 起來後兩回合內被收」；契約 grep 為 0；新問題一律先標組件／類別再報，M 不進 bug 節。
