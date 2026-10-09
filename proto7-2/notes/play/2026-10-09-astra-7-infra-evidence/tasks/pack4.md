# 子線 pack4：blueprint-loop7 §7 第 4 組（budget unknown 與 step 交接）驗收＋astra-5 50 案／audit.py 不退化

你的線名 `pack4`，evidence 目錄 `proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/pack4/`。相關：`proto7-2/packs/budget/`、`proto7-2/packs/step/`（README、spec、程式），上一輪探針在 `proto7-2/notes/play/2026-10-04-astra-6-infra-evidence/budget/`（可以複製到你的目錄改，不要改原檔）。

驗收逐條（§7 第 4 組原文）：
1. EIO 讓 budget call 回 3（`AOS7_TEST_FAULT=open:*/backend.json:EIO` 之類）→ step run 步開 `unknown_codes:[3]` 時：a2 同 request、`backend.accepted==1`、`frame.resends[req]` 正確；持續故障超過 `max_resends` 才 halted unknown。用真 step 直譯器＋真 daemon 或真 tick/tock。
2. 不開 `unknown_codes` 時 halted failed，且可 `resume --resend` 接續、結算一次。
3. payload EIO → rc 3（stdout 一行 unknown JSON、stage payload、stderr 無 traceback）；payload 不存在／壞 JSON 仍 rc 2。
4. 重播回條（gateway/<K>.json）EIO 時 rc 3、`--out` 檔 bytes 前後不變（sha256）。
5. 過期 intent（R8-13）走 on_unknown 的三型：receipt／resend／stop 各一案，核 frame 欄位。
6. R8-14：max_resends=1，a1 被殺→a2 派工前表寫入失敗（tasks.json 寫壞或 inject）→修好→殺 a2：`halt.kind unknown`、`ran==2`（不得出現 a3）。
7. R8-22 縮窗（S 隊代定：補加只准同回合）：在 intent 存後、加項前被殺、重開已是下一回合 → 走 on_unknown（預設 stop 停在 unknown，可 `resume --resend`）；同回合被殺則補加且 `ran==1`。
8. 單位＝加權成本（D6）：兩個 request 其一 `--amount 2` → used==3、accepted==2、available 相符。
9. 不退化：astra-5／astra-6 的 budget crash 50 案原樣重跑（找 `2026-10-04-astra-*-infra-evidence/budget/crash/` 的探針）＋獨立核帳器 `audit_all.py`（或 astra-6 `audit.py`）對本輪新快照重算守恆並跑負對照。
10. C8-03 份：同一 job／K 在原子寫 rename 前連殺 writer 6 次，恢復後槽外 tmp 數 ≤1（step 工作資料夾／results、budget gateway/），活 writer 的 tmp 不被清。
11. 文件一致性抽查：budget README／spec 的退出碼表（0／1／2／3）三處一致、單位定義；step spec 有 `unknown_codes`、過期 intent、重送額度歸 request 的描述，且與實測行為一致。

自由挖：`unknown_codes` 參數驗證邊界（空、重複、0、256、非整數、非 run 步）、`resume --resend` 與 `frame.resends` 歸零、unknown_codes 列了 1 或 2 時的語意（把失敗當 unknown 是否會造成重複效果——若是使用者誤用請分 M 而不是 B）。
