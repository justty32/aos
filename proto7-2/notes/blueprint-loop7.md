# proto7-2 第七輪藍圖（loop7）：kill／回收時序、budget↔step unknown 交接、數值與遷移漏接、假綠測試

依據：[next-steps](next-steps.md) 第一節第 3～6 組與 [next-steps-fixes.json](next-steps-fixes.json)、10-05 報告（[code-quality](reviews/2026-10-05/code-quality.md)、[deep-play](reviews/2026-10-05/deep-play.md)、[k-crosscheck](reviews/2026-10-05/k-crosscheck.md)、[play7](reviews/2026-10-05/play7.md)、[test-review](reviews/2026-10-05/test-review.md)、[packs-use](reviews/2026-10-05/packs-use.md)、[spec-readability](reviews/2026-10-05/spec-readability.md)）、核心 [spec](../spec.md) §2.3／§2.6／§4.4／§5.3／§6、[契約卡](component-contracts.md)、[loop6 藍圖](blueprint-loop6.md)。只讀 repo，Fable 2026-10-05。
現況：核心 **2766／2800 總行、2123／2200 程式**（餘 34／77 行）；364 測試全綠。

**範圍**：第 3 組（kill／回收時序）、第 4 組（budget unknown 與 step 交接）、第 5 組（數值、遷移漏接）、第 6 組的「先修假綠 T8-01～08」。**第 1 組（adapt 回歸）與第 2 組（subd 合法 stop 誤收）今天下午另有兩隊在修，本藍圖不設計**；只在撞檔處註明「交 adapt 隊／subd 隊」（N-66 subroot 的 subd 側測試、R8-18、R8-24、T8-03、C8-03 的 adapt 份）。

**每條的根因（檔:行號）、修法選項與推薦、要不要動核心、驗收測試、領地**已抽到 [blueprint-loop7-items.json](blueprint-loop7-items.json)（43 列；欄位 `id`、`group`、`also` 同件事的其他編號、`title`、`root_cause`、`options`、`recommend`、`core`、`test`、`lane` 分線代號、`files`）。本檔只寫跨條的設計、待決題、分線與驗收。

## 1. 第 3 組：kill／回收時序（R8-01、R8-02、R8-03、K-04、R8-29）

三對同族共一個根因：**回收義務只在 daemon 記憶體**，而 kill 契約（spec §6「最後確認 pid.json 記的程序不在才回成功」）在「還沒有 pid.json」的窗口整段被繞過。兩個設計：

**A. 啟動交接中的 kill（R8-01＝A8-06、K-04、R8-29，`lib/aos7_task.py:194`、`lib/aos7_proc.py:143／:183／:239`）**。推薦最小版：birth 有 `runner` 而 runner 還活著 → kill 回 `ok:false`、msg 以 `unknown` 開頭、請求留著下次再試（spec §6 本來的語意，5～8 行）；清場後再掃一輪後代群組＋身分複查才回 clean（K-04，6～10 行）；node 級回收打記著的 pgid 前做跟槽級一樣的身分重驗（R8-29，5 行）。要不要把 runner 納入 Q1 kill 範圍是語意題（D1）。

**B. 回收意圖落盤（R8-02＝C8-02、R8-03＝A8-05＝C8-01，`lib/aos7_daemon.py:186～207／:435～451`）**。(a) register／unregister 改成「候選 registry 寫檔成功才替換記憶體」（8 行，單獨就關掉半提交與重送短路）；(b) 回收未確認乾淨（`kill_node` 回 clean=False）就不開新時間線、保留 missing 與已知 pgid 下圈重試（8～12 行）；(c) 回收意圖持久化，三個做法：**(c1)** 新檔 `.aosd/reap-pending.json`＝`{node: {pgids, why, since}}`（20～30 行）；**(c2)** 不加新檔——unregister 的 node 在 nodes.json 留 `retiring: true` 直到確認收乾淨，node 替換則在開新線前先以身分掃描（AOS7_NODE＋TID 不屬於任何現存槽）收舊任務（約 12～15 行，少一個檔案協定）；**(c3)** 不落盤，C8-01／C8-02 寫進 spec §11 界線。推薦 (a)+(b)+(c2)；(c1)／(c3) 看行數預算（D7）。契約文字：spec §2.3 unregister 列與 §2.6 各加一句「kill 意圖先落盤／確認乾淨才開線」，契約卡 2.1 保證同步。

兩個設計領地不重疊（A 在 task／proc／run，B 在 daemon），可並行。

## 2. 第 4 組：budget unknown 與 step 交接（A8-10、packs-use 4.3、R8-13、A8-08、R8-14、R8-22、packs-use 4.5）

根因在交接面：step-result 把正常退出 3 發布成 `ok:false`（`packs/step/aos7_step_result.py:75～77`），step 走 fail／failed（`aos7_step.py:447～457`），永遠到不了 `on_unknown`；文件兩邊互相矛盾（budget README:14 推薦 `on_unknown: resend`，step spec:70 說非 0 即失敗）。

推薦（含一個語意題 D4）：**開關式交接**——step 步選項 `unknown_codes`（整數陣列，預設空＝現狀「非零即失敗」不動），列在裡面的退出碼讓 step 走 `on_unknown`（同 request 新 attempt、受 `max_resends` 限、`not_yet` 對照）；fakeapi 示範表開 `[3]`；文件同時照 F03／packs-use 4.4 寫清「step 拿不到結果」與「拿到 code 3」兩種 unknown、照 packs-use 4.3／F19 重寫退出碼表（3＝本次呼叫未完整交付終局結果，可能未預留、在途或已結算但輸出失敗；先 `status` 查 K 再同 K 重送）。step 側同檔三條一起序做：R8-13 過期 intent 轉 `on_unknown`（`aos7_step.py:494～499／:641～644`）、R8-14 重送額度搬到 request 層（`:461～469／:513～516`）、R8-22 先寫時序驗證案例再定（D5）。budget 側 A8-08 兩條路徑歸共同邊界（gate `:168～172` U→rc 3、`:185～188` 重播回條讀不到→rc 3 不以帳補欄）。核心零改動。

## 3. 第 5 組：數值、遷移漏接與其他（27 條）

三類：**(i) 核心小修、各檔獨立**（A8-11 巨大 interval＋R8-20、R8-05 倒數少扣、A8-07 動態加掛半提交＋R8-09、N-86 once 改排程再跑、N-66 subroot 隔代、R8-04／06／07／10／11／12／28），每條 1～12 行、都有舊版（proto7-1）或 spec 條文可對照，推薦全做；**(ii) 模組**（N-66 audit＋subd、R8-17／21／25／26；R8-18／R8-24 在 aos7-subd 交 subd 隊）；**(iii) 契約題**（N-06 剩餘回合數要不要落盤 D8、C8-03 槽外 tmp 由寫的人掃＋spec 一句、R8-30 無呼叫者 API 留不留 D10）。細節見 json 各列。

## 4. 第 6 組：先修假綠 T8-01～08

全部是測試檔改動，生產程式最多 1～2 行 `test_point`。原則：**先證明故障真的發生、再看恢復結果**——SIGKILL 後先拿「死亡快照」（pid.json 有、exit.json 無、`same_process` 為假）；crash 點驗 `exit.code == -9` 與中斷時的中間形狀；budget 崩潰在重起前讀 ledger／gateway 快照核表；`Fault.check_rules()` 逐條規則（op＋路徑＋errno）命中；ENDED once 的 tock 重播收尾補案例；once_retry 非 true 用真的 lost 候選。T8-07 改 `tests/_matrix.py`（全矩陣共用）**最先、獨立 commit**；T8-02／T8-04 分別與 S、B 線同測試檔，排在它們之後；T8-03 同 subd 隊測試檔，交 subd 隊。

## 5. 待使用者決定（都給預設建議，不替使用者定）

| # | 題 | 預設建議 |
|---|---|---|
| D1 | 啟動交接中的 kill：回 unknown 等下次，還是把 runner 納入 Q1 範圍一起收（spec §6／§2.6 要改） | 回 unknown（最小、不改範圍） |
| D2 | K-04 漏收窗口與 R8-29 裸 pgid：修（各 5～10 行）還是寫進 §11 界線 | 修；node 級不該弱於槽級 |
| D3 | 核心加不加測試注入點：`write_json` 的 `inject("write")`、tock `_finish` 的 `test_point("tock-seen-round")`（各 1 行） | 加；否則 R8-03／T8-06 只能用 chmod 製造 |
| D4 | budget rc 3 接不接 step 的有限重送 | 接，但開關式 `unknown_codes` 預設空 |
| D5 | R8-22 若驗證成立：縮補加窗口（`cur > intent_round`）還是 intent 改記 completed_tock | 先驗；成立取縮窗 |
| D6 | budget 單位：「次數」（amount 限 1）還是「加權成本」（改 README 單位定義） | 加權成本；帳本已是加權，token 結算之後要用 |
| D7 | **核心行數預算**：第 3＋5 組核心估 105～145 程式行，餘額 77 程式／34 總行，一定爆 | 先做 B(a)(b)(c2)＋小修、N-06 與 R8-29 取文件版壓到約 70 程式行，**總行上限這輪放寬到 2900、程式行維持 2200**；或由使用者指定砍哪些 |
| D8 | N-06 剩餘回合數：paused.json 加 `steps`（8～12 行）還是 spec §2.4 寫成已知限制 | 行數夠就落盤，不夠寫限制 |
| D9 | audit＋subd：audit 讀 `AOS7_SUBROOT`（快）還是通用 `AOS7_AUDIT_ALLOW` 由 subd 設（兩模組不互認） | 通用 env |
| D10 | R8-30 無呼叫者的 `run_target_full`／`run_inst`／`spawn_target`／`load_obj` 刪不刪 | 留，kernel 包可能用 |

> **使用者 2026-10-09 早上已裁**：D1～D10 **全照預設建議**，唯 D7 改為「**行數上限全部放寬、這輪不設上限**」——開發階段不設上限，等成果整理階段再重構拆檔濃縮（`test_budget` 照此調整）。D8 因此直接落盤。T8 系列在家裡 Manjaro 可重試（加限時、限程序數保護；公司 WSL 仍不跑這批）。

## 6. 分線（領地不重疊；代號對應 json 的 `lane`）

| 線 | 領地 | 內容 | 量 |
|---|---|---|---|
| K1 | `lib/aos7_task.py`、`aos7_proc.py`、`aos7_run.py`、spec §6／§5.4；`tests/core/test_ctl.py` | 設計 A（R8-01、K-04、R8-29）＋同檔小修 N-66 subroot、R8-10／11／12 | 中 |
| K2 | `lib/aos7_daemon.py`、spec §2.3／§2.6、契約卡 2.1；`tests/core/test_daemon.py` | 設計 B（R8-02／C8-02、R8-03／C8-01）＋N-06、R8-04 | 大 |
| K3 | `lib/aos7_daemon_timeline.py`；`tests/core/test_errors.py`＋新 `test_timeline_rounds.py` | A8-11＋R8-20、R8-05、R8-06 | 小 |
| K4 | `lib/aos7_mount.py`、`aos7_tick.py`、`aos7_fs.py`、`aos_directives.py`、spec §4.3／§5.5；新 `test_mount_dyn.py`、`test_once_threestate.py` | A8-07＋R8-09、N-86、R8-07、R8-28、D3 注入點、C8-03 spec 句 | 中 |
| S | `packs/step/`（程式、spec、tests） | A8-10(b)、R8-13、R8-14、R8-22 驗證、C8-03 step 份；收尾接 T8-02 | 中 |
| B | `packs/budget/`（程式、README、spec、tests） | A8-08、4.3／F19 文件、4.5（D6）、A8-10 文件面與 fakeapi 表、C8-03 gateway 份；收尾接 T8-04 | 中 |
| M | `modules/audit/`、`history.py`、`once_retry/` | N-66 audit＋subd、R8-25、R8-17／21、R8-26、T8-08 | 小 |
| T1→T2 | `tests/_matrix.py`、`modules/diag/tests/`；`tests/core/test_matrix_once.py`、`test_matrix_faults.py`、`test_matrix_docs.py` | T8-07 先獨立 commit；再 T8-01、T8-05、T8-06 | 小 |

K1～K4 四條核心線**檔案互不重疊**但共用行數預算（D7）——隊長先分配額度再開線；`test_daemon.py` 被 K2 用，K3 另開檔。S／B／M／T 與核心線無共用檔。交給別隊的：subd 隊（R8-18、R8-24、T8-03、N-66 subroot 三層測試、D9 的 1 行）、adapt 隊（C8-03 adapt 份）。建議順序：T1 → K1～K4／S／B／M 並行 → T2、T8-02／04 → 整合（README 測試表、problems.md 各一列、code map、contracts 2.1、SESSION-LOG）→ astra 回歸。

## 7. 驗收

- 全套 `python3 proto7-2/tests/run_all.py` ×3 皆綠，預期 364 → 約 400；`tests/core/test_budget.py` 以 D7 定的上限為準。
- 第 3 組：runner 停在 Popen 前的 kill 回 unknown 且請求留著、放行後下一次成功；nodes.json 寫失敗重送後記憶體＝磁碟；unregister 後殺 daemon 重起舊 PID 已收；node 替換＋回收中斷重起新舊不同活；K-04 FIFO 案例、R8-29 偽 pgid 不打。deep-play C8-01／C8-02 重現步驟各跑 3／3。
- 第 4 組：EIO 讓 call 回 3 → 開 `unknown_codes` 時 a2 同 request、`accepted==1`、超額才 halted unknown；不開時 halted failed 可 `resume --resend`；payload EIO rc 3 而壞 JSON 仍 rc 2；重播回條 EIO 時 `--out` bytes 不變；過期 intent 走 receipt／resend／stop 三型；R8-14 表寫失敗後 `ran==2`（指讀表拒寫那條路；attempt 號照加，派出的可能是 a1、a3，驗收看「不得有第三次實跑」，不是看號碼。實體寫入錯誤那條路停在 unknown、ran==1，人手 `resume --resend` 後 ran==2，見 step spec §5、A9-04）；astra-5 50 案與 `audit.py` 不退化。
- 第 5 組：每條一案（json `test` 欄）；proto7-1 的 `test_interval_huge_int` 搬回；三層 subd 由 subd 隊驗。
- 測試：T8-01～08 每條「拿掉故障注入就轉紅」各手動驗一次並記在 play README。
- 文件：spec §2.3／§2.6／§4.3／§5.5／§6 各一句；budget README／spec 退出碼表與單位定義；step spec `unknown_codes`、過期 intent、重送額度歸 request；契約卡 2.1；problems.md 加 A8-05～A8-11、C8-01～03 列。

## 8. 風險

- **行數預算**（D7）是本輪最大的不確定：不先拍，K2 做到一半會卡 `test_budget`。
- 設計 B 改 daemon 主迴圈，是本輪唯一碰「不變條件」的改動；K2 要用 deep-play 的重現步驟當回歸，且每步 SIGKILL ×3。
- S 線四條同區序做，R8-22 若驗出核心時序問題會回頭牽 K4（tick）——先驗再排。
- 與 adapt／subd 兩隊同 repo：K1 的 N-66 subroot 會改 subd 的 launcher 判定行為，開線前先通知 subd 隊；一律 `git commit <明確路徑>`。
- T8 假綠修完可能把現有綠燈翻紅（本來就該紅）；翻紅的先歸 bug 線、不改回斷言。
