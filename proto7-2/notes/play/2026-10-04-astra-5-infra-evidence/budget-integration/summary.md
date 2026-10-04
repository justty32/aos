# budget 時鐘、step 與獨立核帳

本線未確認新的 B／G。step／daemon 8 個案例全過；另 4 組自製時鐘契約檢查通過、2 組時鐘重建誤用觀察標 M。獨立核帳共 **109 份快照、311 筆持久轉移**全過，5 種負對照全能變紅。最終本線測試耗時 **9.971 秒**；沒有呼叫 LLM，沒有修改受測程式、測試或文件。

## 證據與重跑

- [run_probes.py](run_probes.py)：從 repo 根 `python3 proto7-2/notes/play/2026-10-04-astra-5-infra-evidence/budget-integration/run_probes.py`。
- [results.json](results.json)：完整觀察、最新 21 份快照路徑及逐案清理；[step-unittest.log](step-unittest.log)：8 個案例結果。
- [audit.py](audit.py)：純 Python 標準函式庫，不 import budget、核心或既有測試；可用 `python3 …/audit.py <快照目錄> [--final]` 獨立重跑。
- [audit_crash_snapshots.py](audit_crash_snapshots.py)、[crash-audits.json](crash-audits.json)：核對另一線 `budget-crash/verified` 72 份、`budget-crash/extra` 16 份；共 88／88 通過、258 筆轉移。本線 21／21、53 筆。
- [negative-controls.json](negative-controls.json)：只變造自己的 `/tmp` 複本，受理計數加一、log 餘額加一、重複 reserve、錯誤結算證據雜湊、刪除 ops 各一案，全部拒收。

快照先持 `ledger.json.lock`，再持已知各 K 的 gateway 鎖、backend 鎖，才複製帳、入口與後端。核帳重放每筆 log 的餘額、非負性、守恆與序號；比對完整 K、kid 雜湊、內容 digest、ops 與 reserve／settle 一對一、入口終局回條雜湊、後端效果、accepted 計數及唯一連續效果序號。`final` 另要求在途為 0、帳的 used 等於後端效果總量。SIGKILL 當下的非終局快照允許保留預留。

## 覆蓋

| 項目 | 結果 |
|---|---|
| `from ≤ completed_tock < until` | c=4 為 not_yet；open round=6 代表 c=5，成功；closed c=9 成功；open round=11 代表 c=10，到期拒絕。 |
| 時鐘倒退至已成功 reserve 的高水位以下 | 已成功 c=9 後改成 c=8，新請求 unknown，無新支用。這是針對包明示偵測分支的合成時鐘測試。 |
| pause／真正 daemon 重開 | 原有 graceful restart 案全過；新增 pause 後 PID SIGKILL daemon，重開仍 pause，c 保持 6；resume 後走到 8，gen 1→2，新 call 成功，合計只用 2。 |
| 已准入 intent 過期恢復 | c=9 真 SIGKILL 於 gateway-after-intent；c=10 重跑同 K 成功、只計 1；同時新 K 到期拒絕。 |
| 耐性與 pause | 沒有帳寫者時，牆鐘等 0.3 秒、c 不動不退出；c 多 1 才達 patience=1，退出 3，請求保留。 |
| 同 request、新 attempt | 五個 call／gateway／backend SIGKILL 點逐一命中；step 終局 attempt 都是同 request 的 `-a2`，每 K 一次 reserve、一次 settle、一次效果。 |
| close 後重播 | step results 刪後同 K 回原 settle；log 保持 2、used=1、accepted=1。 |
| restart_on_end | 新 inst 產生新 request；額度 3 下三個 K 各一次效果，下一個工作被拒；used=3、available=0。 |
| 槽已刪、settle 與 step 解耦 | gateway 回條已寫而 step unknown；槽消失後直接 settle 用 1，resume --resend 不重扣。 |
| reserve 後首次准入才過期 | step halt 後走到 until 再 resend，gateway denied，結算 0、全額退回，後端無效果。 |
| 已受理但工作失敗 | step failed／ok:false，used=1，沒有把工作失败當退款理由。 |

## M：時鐘重建沿用舊預算

兩個額外探針觀察到 `clock_hw` 實際只持久保存**成功 reserve 時的 c**：

1. c=5 成功，c=10 新 reserve 被到期拒絕，clock_hw 仍是 5；把時鐘改回 c=6 後，新 K 可成功。
2. c=5 reserve 後被殺，c=9 首次 gateway 准入成功，clock_hw 仍是 5；把時鐘改回 c=6 後，新 K 可成功。

這沒有列 B／G。README 明定「重建時鐘須換預算識別、不移植舊 grant」，核心卡也把人手倒退 round 排除；兩案是 M，沒有找到合法 daemon 操作自然退鐘的路徑。spec §2「帳記住看過最大值」可在日後文字整理精確成成功預留的高水位，但不能據此要求更多核心防護。正常 pause／重開的時鐘接續已實測。

## 「五個自列缺口」來源核對與可追溯替代表

目前 `packs/budget/spec.md` 只有 §1～§8（84 行）；HEAD `392a1d64` 與建包 commit `025d2bfe` 都沒有題目所稱 spec 末五個自認缺口。因此**無法把不存在的五條當成已完成逐條驗收**。以下只對照確實存在的 [astra-4 五項草稿意見](../../2026-10-04-astra-4-infra-evidence/contracts/summary.md#account-草稿意見不算發現)，不是冒充原清單。

| 可追溯 astra-4 意見 | 現版對應 | v1 評估 |
|---|---|---|
| gateway 缺前置條件 | README 已寫合作式 holder、同 K 同內容 reserve、gateway lock、後端只經入口；spec §3～5 補鍵與比對。 | **v1 已具備**。不需添加 OS 隔離。 |
| 工作失敗與退款混在一起 | ledger 只讀 gateway 終局證據；accepted／failed 都用 1，rejected／cancelled 才退。 | **v1 已具備並通過**。工作失敗、槽刪與 step close 均不誤退。 |
| unknown 不應永久定案或到期自退 | grant／clock／gateway unknown 非終局、在途保留；到期僅擋新預留與首次准入，intent 可恢復。 | **契約已具備；同輪 backend 讀取故障的退出碼違約應在 v1 修**，見另一線的 backend EIO／EACCES 證據。帳與去重守恆已通過獨立核帳。 |
| request／attempt／操作去重與持久保存 | K=(budget,holder,request)，reserve／settle 分開，attempt 不入 K；帳與 gateway 在 node 的 budget/，不隨 step close 清。 | **v1 已具備並通過**。五個 SIGKILL 點重送、close 後重播、restart_on_end 全符合。 |
| grant 再分與時鐘 | delegate 必須 false、parent 子 grant 拒絕；c 明訂 completed_tock、半開效期，pause 不推進。 | **時鐘語意 v1 已具備並通過；split／跨 node 合理延後**。現版不宣稱支援再分，不能列 bug。 |

## 測試工具自身修正

第二次執行曾沿用第一次的快照目錄，留下舊 request 的 gateway 檔；核帳因混代資料報紅，導致 10 筆測試／subtest 失敗。這是**QA 快照工具污染，不是產品不穩定**。保留 [harness-stale-results.json](harness-stale-results.json) 與 [harness-stale-step-unittest.log](harness-stale-step-unittest.log) 供查核。現版改為每次唯一快照根，並補寫者鎖；最終 8／8 全綠。報告與核帳統計只採 [results.json](results.json) 列出的最新 21 份，以及另一線 verified／extra 的 88 份，不把早期混代快照算進去。

## 清理

直接 CLI 探針的 PID 都已 reap，[own-cleanup.json](own-cleanup.json) 的 PID 定向 `ps` 無殘留。8 個 step／daemon 案例各自的 `/tmp/aos72-test-*` 都移除，按完整 `AOS7_ROOT` 掃 `/proc` 無存活程序，結果在 results 的 cleanups；未動 scratchpad。沒有 commit、push 或外部訊息。
