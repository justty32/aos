# 任務：proto7-2 第一輪基礎設施測試（新設計的可靠性與故障注入）

可以開自己的 subagent 平行做事（最多 4 條）。

（說明：這是 repo 擁有者委託的軟體品質工作——對自己寫的本機排程原型做回歸測試與故障注入，找出 bug，產出是一份測試報告。不涉及任何外部系統。）

你在一份副本裡（目前目錄），可以隨意跑、改這份副本、寫腳本。**不要碰副本以外的路徑**（/tmp 可以用，但跑完要清掉你建的 /tmp 資料夾與程序；收程序用 PID，不要用 `pkill -f`；列資料夾用 `/bin/ls` 或 python，不要用 `ls`）。不要呼叫任何 LLM；嚴禁 LM Studio、ollama、`lms`。繁體中文（台灣用語）寫報告。

## 背景
- 核心 spec：`proto7/spec/core.md`（條號 S-）。
- proto7-1 是第一次試做；你做過它八輪回歸（報告在 `proto7-1/notes/play/`，最後一輪 astra-8 的總評是「剩下的是用檔案有沒有推定事實的結構性缺口」，K-01～K-10，設計回應見 `proto7-1/notes/decisions/2026-10-03-lifecycle-invariants.md`）。
- 使用者看完後給了建議 `proto7/user-advice.md`，並追加「歷史做成可選 module，核心只留上一次」。於是重做成 **proto7-2**：node 改登記不掃描、提前 tock 可選（預設固定 interval）、只有 tasks.json（once＋launch 標記）、槽式任務資料夾（同名重用、run 號）、核心只留上一次（last-round.json）、三態判定與三個不變條件寫進設計、pause 帶 owner、resume 順便 wake。
- 規格 `proto7-2/spec.md`，對照 `proto7-2/notes/changes-from-7-1.md`（W1～W12 照推薦），實作時的問題 `proto7-2/notes/problems.md`（P2-01～P2-18），測試 `proto7-2/tests`（103 項）。

## 要做
1. **新設計的承諾逐條實測**（每條判定 成立／部分／不成立，附證據）：
   - 登記：register／unregister／重開 daemon 後 nodes.json 有效；node 被刪／搬走／換成符號連結→missing；看不到（權限、EIO 模擬）不當消失。
   - early_tock 兩種模式的節拍；wake 在兩種模式下的行為（對照 P2-01）。
   - once：在 launch 標記前後、birth 前後、runner 記錄前後、刪項目前後各點 SIGKILL tick，下次 tick 結果是否「不重起、不遺失」或照 P2-02 的 at-most-once 誠實回報。
   - 槽：長跑（例如 500 回合、多個 keep／each／max_live 槽）後 `.aos` 與 `.aosd` 底下**檔案數與 bytes 是否維持常數**；歷史 module 開／關各一次。
   - 三態：starttime 讀不到、birth.json 壞／半寫、round.json 讀不到、last-round.json 壞、/proc 讀不到時，是否不做破壞性動作、狀態看得懂、恢復後自動回正。
   - 不變條件一（回合確知關閉才開下一回合）、二（lost 前身分掃描、keep 不雙開、舊 run 殘留不當新 run）、三（若無 kernel，評估 spec §8 的設計是否可行即可）。
   - pause owner：多個控制者（A pause、B pause、A resume…）是否互不解掉；resume 順便 wake。
   - 沿用的保護：世代／action.lock／舊動作接管、fd 寫入（搬家中途）、控制檔洪水與壞檔、子 daemon 所有權（owner／daemon 兩塊、allow_stop、stopped.json）、restart／reload、掛載與執行中加掛。
2. **拿 proto7-1 的 K-01～K-10 逐條判斷**在 proto7-2 是：消失（設計上不存在）／已修／仍在／換了形式。
3. **使用者五條建議＋追加那條**是否真的落實（看程式與實際行為，不只看文件）；有沒有因此變複雜的地方。
4. **新使用者角度**：只看 `proto7-2/README.md`、`spec.md`，挑 10 個文件宣稱的行為實測，列不一致處；評估 spec 長度與易懂度跟 proto7-1 比如何。
5. **找新問題**：編號 A2-01 起，分〔bug〕〔技術選型〕〔要使用者決定〕（最後一類少而精）。最後一段總評：這一版離穩定還差什麼，結構性的還是邊角的。

## 產出
- `proto7-2/notes/play/2026-10-04-astra-1-infra.md`：開頭摘要；承諾實測表；K 對照表；使用者建議落實表；文件一致性表；A2- 新問題；總評。
- 證據 `proto7-2/notes/play/2026-10-04-astra-1-infra-evidence/`（腳本＋精簡 JSON，不放大檔），並把本任務書複製一份進去叫 task.md。
- 只寫這兩處，不改程式或其他文件。結束前確認沒有你的殘留程序與 /tmp 資料夾。
