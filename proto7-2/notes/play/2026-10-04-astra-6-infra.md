# proto7-2 第六輪回歸（astra-6）：loop6 驗收

**A6-01、A6-02 修補驗收通過，subd G3 正式壓力 10／10；budget 未見重複扣款、重複效果或守恆破壞。adapt 的流速、故障恢復、step 接法與長跑通過，但確認一項低嚴重 B：A7-01 的取整實作與 spec「四捨五入」不一致。藍圖 §3.3 的 800／799 門檻例子確實算錯，這部分實作依公式是對的，應改藍圖。** 三次全套各 363 項全綠，未觀察到 flaky。

受測 HEAD：`04c5d28866cdeacbb71e8bde43000f0e14a0c149`，包含 loop6 整合 `a1029d47`。依[組件契約](../component-contracts.md)、各包 README／spec 與[原則 9、10](../../../proto7/notes/principles.md)分類；M 不列 bug。本輪只新增本報告與指定 evidence，未修改既有程式、測試、文件，未 commit／push，未呼叫任何本機 LLM，也未刪除或清空 scratchpad。

**測試結果**

全套從 repo 根執行 `python3 proto7-2/tests/run_all.py -v`，三次循序；耗時為實際經過秒數。

| 測項 | 結果 | 耗時／範圍 |
|---|---|---|
| 全套第 1 次 | 363／363，rc 0 | 184.170 秒 |
| 全套第 2 次 | 363／363，rc 0 | 186.646 秒 |
| 全套第 3 次 | 363／363，rc 0 | 196.273 秒 |
| A6-01 stop 中斷 | 24／24；18 次 SIGKILL 精確命中 | 三窗口、兩種重開流程、正常對照各 3 次 |
| subd G3 正式壓力 | 10／10，全部重疊全套 | 合計 27.342 秒 |
| subd 新邊界 | 7／7 符合預期 | 含 X、M 與已知界線，不全算成功功能 |
| budget 原探針＋loop6 探針 | 50／50＋6／6 | 12.041＋2.901 秒 |
| budget 新邊界 | 6／6 | 6.589 秒 |
| budget 時鐘／step／daemon | 5 組額外觀察＋8／8 測試 | 9.886 秒 |
| step max_resends 新邊界 | 4／4 | 2.528 秒 |
| budget 獨立核帳 | 127／127 新快照、460 筆轉移；5／5 負對照抓紅 | 轉移數是跨快照核對量，不是獨立交易數 |
| adapt 獨立矩陣 | 29／29＋真 daemon 流速及控制 9／9 | 6.427＋35.340 秒；另測取整發現 A7-01 |
| A4-01～07、F47、§4.4 | 核心 17／17＋step 8／8＋step F47 2／2 | 未見退化 |
| step 長跑 | 450 已關回合，112 個完成快照全正確 | 25.253 秒 |
| adapt 長跑 | 初始 r1 後再跑 320 已關回合，止於 r321 | 3.304 秒，321 份取樣 |
| 核心行數 | `test_budget.py` 綠 | 總行 2757／2800、實碼 2123／2200 |

三次全套均無 failure、error 或 skip，adapt 28 案各跑三次全綠；未觀察到不穩定案，不等於證明永不 flaky。題述「曾放寬」的舊斷言未留在 Git 歷史，無法確認修改前後；現版 daemon 重開案使用回合 `>=`，三次均通過，獨立流速探針另核對實際取樣行為。[逐次原始結果](2026-10-04-astra-6-infra-evidence/regression/suites.json)、[回歸摘要](2026-10-04-astra-6-infra-evidence/regression/summary.md)。QA 計時器只解析到單行輸出的案例，曾把 145 個計時樣本寫成 `cases_count`；已改名並以 unittest 尾端的 363 作測試總數，沒有改測試或覆蓋失敗。[工具校正](2026-10-04-astra-6-infra-evidence/regression/harness-notes.json)。

**A6 驗收**

**A6-01 通過。** 原 astra-5 的 stopped 暫存檔 rename 前、life stopped 提交前兩窗口，連同新增 stop-seen 窗口，均重新真 SIGKILL。原流程與藍圖流程各含三窗口及正常對照、每組 3 次，共 24／24；18 次注入全部命中。重開補完停止記錄、不回收原任務；依規則刪 marker 後接回同 PID／starttime，槽仍 run=1。先刪 marker 的 life-tmp 情境會再補 marker、多擋一次，任務仍保留。[中斷證據](2026-10-04-astra-6-infra-evidence/subd/confirm-stop.json)、[逐項核對](2026-10-04-astra-6-infra-evidence/subd/audit.json)。

G3 正式十案均在全套執行期間起訖；每案先證明前代任務確實留下，首次看到替代 daemon 時已全部回收，延遲 2.242～2.279 秒。另有預跑 10／10，其中僅八案重疊全套，未混入正式統計。[正式壓力證據](2026-10-04-astra-6-infra-evidence/subd/stress-parallel.json)。

| subd 邊角 | 判定 |
|---|---|
| 直接 TERM 子 daemon，allow-stop false／true | 核心照 stop＋kill 收任務；沒有控制檔 stop 回條，不留 stopped marker，之後可重開。符合新規則。 |
| 上代 stop 回條＋本代 TERM | 舊回條早於本代 since，不會誤認為本代 allowed_stop。 |
| life 沒有 since | 合成刪欄模型會回收；**M**。Git 初版尚無 life，首次引入 life 的 `8c2145c4` 已含 since，沒有找到真實舊版缺欄紀錄，不冒稱遷移失敗。 |
| 牆鐘倒退一小時 | 成功 stop 的回條早於 since，重開會收原任務。**X／已知環境界線**：README 明定時間比較，loop6 已明說不另防倒鐘；依原則 9 不加新保護要求。README 宜揭露這個後果。 |
| status／stop 回條 EIO | 不收、不起；解除後補完 stopped，原任務保留，符合 X 的保守分支。 |

倒鐘測試只改測試程序看到的時間，未動主機時鐘。README 尚未單列正常牆鐘前置，因此這裡明列實際後果，不把它說成已受保護。[邊界證據與歷史查核](2026-10-04-astra-6-infra-evidence/subd/summary.md)。

**A6-02 通過。** 原 EIO 與真 EACCES 都回 rc 3、stdout 一行 unknown JSON、stderr 無 traceback；intent／預留保留，恢復後同 K 只新增一次效果。call→cancel→settle→call 在故障下也都回 3；grant／ledger／gateway 故障對照未退化。新增入口鎖與 inbox 寫入權限故障，同樣走共同 unknown 分支。[原 50 案](2026-10-04-astra-6-infra-evidence/budget/crash/verified/results.json)、[真 EACCES](2026-10-04-astra-6-infra-evidence/budget/crash/extra/results.json)、[budget 摘要](2026-10-04-astra-6-infra-evidence/budget/summary.md)。

| budget §9／§10 與新增行為 | 驗收 |
|---|---|
| `clock_hw` | 成功@5→拒絕@10→重播@12，水位皆推高；退回 6 新 K unknown，帳不多扣。沒有請求期間回撥但仍高於水位仍可放行，是 §9.2 明訂界線及時鐘前置的 M。 |
| 孤兒回條 | 首見 c6，c6／7／8 保留、c9 才掃；在途 K 不掃，重播回條除 at 外一致。pause／未知鐘不提早掃；帳重開從新首見重算寬限，只延後清理。 |
| 保存 | 30 K 完成後空跑 13 個合成時鐘值，ledger／backend／gateway 與鎖雜湊不變；30 ops、60 log、30 gateway JSON＋30 lock，符合成長率。 |
| 退役 | inflight=0 後標記退役，新 K denied、舊 K 可重播；marker 真 EACCES 時新 K unknown；重開帳仍拒新 K。 |
| `max_resends` | 0／預設 1／3 分別總共起 1／2／4 次，額度耗盡後 halted unknown，再推三回合不偷重送；同 request、attempt 遞增。人工 `resume --resend` 可接續。 |

§9 的可查回後端、合作式 holder、歷史成長與有限重送都有明訂範圍，本輪沒有新增 G，也不要求壓縮帳、驗證身分或無限重試。上述可控時鐘探針不冒稱真 daemon 回合；真 daemon pause／SIGKILL 重開另由八個整合測試涵蓋。

astra-5 獨立核帳器原樣沿用、SHA256 相同，只用標準函式庫。對本輪 127 份新快照重算守恆、非負、每 K reserve／settle 唯一性、log／ops、結算雜湊、效果與 accepted 計數，460 筆跨快照轉移全過；五個負對照全部抓紅。[核帳結果](2026-10-04-astra-6-infra-evidence/budget/audit-summary.json)、[負對照](2026-10-04-astra-6-infra-evidence/budget/negative-controls.json)。

**adapt 驗收表**

獨立腳本透過檔案協定、真 daemon 或實際核心 tick／tock 啟動任務；沒有只拿作者測試代替獨立驗收。流速是設定 interval，非保證實際頻率。

| 情境 | 實測結果／分類 |
|---|---|
| src／dst＝20／200 ms | 來源每次跨多版；skipped 增 36，age≤1，保持 ok。 |
| 200／20 ms | 45 份樣本有 34 對相鄰重複依據，age=0，不因來源慢翻 unknown。 |
| 50／50 ms | 20 份樣本依序前進，age=0，skipped 不增。 |
| **10／2000 ms** | 六份樣本 seq 116→408，skipped 增 287，age=0，保持 ok。 |
| **2000／10 ms** | 100 份樣本有 98 對相鄰重複，age=0，保持 ok。 |
| 來源 pause／resume | pause 時來源鐘及年齡不長，預設 stall=null 維持值；resume 後恢復 advancing。stall=3 第四次未前進才 unknown。 |
| 來源 daemon 被殺重開 | 同一 daemon 根重開，來源回合接續，未誤判 reset。 |
| 來源 node 重建 | 停止無任務的來源，重建其 `.aos`，由真 tick／tock 產生新 r1；舊 basis 作廢、reset／unknown，新值後恢復 ok。未手改 round.json。 |
| 來源真 EACCES | patience=2 時前兩回合撐舊值，第三回合 unknown 且 last 保留；恢復後 ok。**X 正常處理。** |
| 半寫／換成資料夾 | 同耐性分支，不崩潰；依 spec §7 標 **M**，不列 bug。缺欄、缺 round、非數字也有實測。 |
| 工作中改鏈 | `chain_changed` unknown，不採新鏈；改回恢復。**M**，符合明列界線。 |
| adapt 任務 SIGKILL | keep 重起接回 since／last_seq／skipped，同版不重算漏取樣。 |
| dst pause | 暫存器不動、耐性不走，resume 後接續。 |
| 門檻／誤差帶 | ge／gt／le／lt 各五個邊界，包含區間剛好碰門檻；結果符合公式。另見 A7-01 取整文字落差。 |
| max_age=2 | age=1／2 可用，age=3／4 為 expired；不拿 dst 快慢換算來源效期。 |
| step `num` | 790／799 不滿足 ≥80；800 因誤差帶 unknown、value=null，不前進；801 時走 then。 |
| 320 回合長跑 | 檔名集合不變；細節見下節。 |

[獨立矩陣](2026-10-04-astra-6-infra-evidence/adapt/matrix-results.json)、[五組流速與控制](2026-10-04-astra-6-infra-evidence/adapt/flows-results.json)、[完整驗收摘要](2026-10-04-astra-6-infra-evidence/adapt/summary.md)。另以獨立程式核對 617 份 basis SHA 與 605 次 Decimal 誤差帶判斷，無額外失敗。[獨立核算](2026-10-04-astra-6-infra-evidence/adapt/audit-results.json)。受測 repo 找不到題述 `loop6-adapt-evidence/summary.md`；本輪直接驗 README／spec／實作，未引用不存在的自報證據。

**發現清單**

**A7-01〔B／adapt scale，低嚴重〕取整平手時採偶數捨入，未兌現 spec「四捨五入」。**

- **契約條目**：[adapt spec §2](../../packs/adapt/spec.md)：「有 round 就四捨五入到小數 round 位」。
- **重現**：來源原子發布 `value.x=2.5`；合法鏈 select x → scale `{mul:1,q:0.5,round:0,as:"c"}`、need c。check 回 0、`[]`，真 adapt 任務輸出 `state:ok,value.c:2.0`，一般四捨五入應為 3。0.5→0、4.5→4 亦重現，1.5→2、3.5→4 為對照，另保存負數樣本。
- **影響**：宣告取整結果與文件不一致；不是誤差界失效，err=0.5 仍涵蓋真值，也不是核心或 budget 問題。
- **證據**：[完整宣告、來源與暫存器](2026-10-04-astra-6-infra-evidence/adapt/rounding-results.json)、[可重跑真任務探針](2026-10-04-astra-6-infra-evidence/adapt/rounding_probe.py)。
- **建議修法一行**：實作改成約定的四捨五入；若原意就是平手取偶數，則明確修訂 spec 的取整規則並補平手案例。

沒有第二項新 B／G。以下是文件勘誤及界線揭露，不另湊 bug 編號。

**藍圖 §3.3 應改，公式與實作正確。** mul=0.1、q=0.05、ge80 時：

| t_dc | x±err 的區間 | 正確結果 |
|---:|---|---|
| 790 | [78.95, 79.05] | false／ok |
| 799 | [79.85, 79.95] | false／ok，沒有跨 80 |
| 800 | [79.95, 80.05] | null／unknown，跨 80 |
| 801 | [80.05, 80.15] | true／ok |

因此應將藍圖「800→true、799→unknown」改成上表，不應反過來把實作改成違反誤差公式。unknown 暫存器的整個 value 為 null，門檻 null 可在 trace 看見，符合 spec §5。[獨立 Decimal 計算](2026-10-04-astra-6-infra-evidence/threshold-independent.json)與真任務結果一致。subd 倒鐘後果也宜補入 README 界線，但不要求新增防護。

**長跑與既有回歸**

step 真 daemon 跑 CSV convert→stats→end，`restart_on_end:true`；最終確認 round=450、open=false。112 個完成快照全正確，每步 attempt=1、halt／error=0，完成階段固定 10 檔。本次未見持續成長，不外推無限長度。[step 長跑](2026-10-04-astra-6-infra-evidence/regression/step/longrun.json)。

adapt 由真核心 tick／tock 從已關 r1 再跑 320 回合至已關 r321，每回合檢查暫存器與檔名集合；dst/in 1 檔、dst/adapt 1 檔、adapt 槽 5 檔、src/out 1 檔，前後集合含隱藏檔皆相同。這是可控核心回合長跑，另有上表五組真 daemon 流速測試。[逐回合資料](2026-10-04-astra-6-infra-evidence/adapt/long320-registers.json)。budget 的帳與 gateway 按 §10 隨 K 保存，不能拿其成長誤判成 step／adapt 檔案洩漏。

A4-01～07、F47、§4.4 抽查共 27 案未退化：掛載故障、控制競爭／去重、動態登記、step 耐性／型別／選項、同回合補通知／跨回合不補，以及 once 崩潰與槽刪除時機均符合契約。核心 `test_budget.py` 綠，lib 的 18 個 tracked 檔案與 `daf8d5cf` 逐檔 SHA256 相同；該版以後 lib 沒有 commit 變更。[回歸摘要](2026-10-04-astra-6-infra-evidence/regression/summary.md)、[核心行數](2026-10-04-astra-6-infra-evidence/regression/core-lines.json)。

四條線均已結束，自建 `/tmp` 測試根已清除，程序按 PID 回收並以 ps 核對，沒有本輪殘留程序；大量快照已封裝 tar.gz。460 個既有 tracked proto7-2 檔案的 SHA256 前後相同，HEAD 未變，git status 只新增本報告與 evidence，另保留原有未追蹤的 `proto7/user-advice.md`。[收場稽核](2026-10-04-astra-6-infra-evidence/final-audit.json)、[最終 ps](2026-10-04-astra-6-infra-evidence/ps-final.txt)；各線清理明細在其摘要。

**最該修的三條**

1. **A7-01：統一 scale 平手取整的實作與 spec。** 低嚴重，但合法輸入已有可重現落差。
2. **修正藍圖 §3.3 的 800／799 驗收數字。** 公式及現有門檻實作保留。

沒有第三條已確認必修問題，不湊數。
