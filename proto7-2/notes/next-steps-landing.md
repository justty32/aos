# proto7-2 原定落地順序：選項與待決題

← [接下來的方向](next-steps.md)｜[proto7-2](../README.md)｜[10-05 報告索引](reviews/2026-10-05/README.md)

[next-steps](next-steps.md) 第二節的展開。SESSION-LOG 10-04 傍晚記的順序是事件保存 → agent／LLM 作者與 adapt-llm；kernel 任務包是 [core-slimming](core-slimming.md) 裡還沒做的一塊。三份報告都是唯讀提案，**待決題與預設建議都只是供選擇**。

## 事件保存（event-store）

[報告](reviews/2026-10-05/event-store.md)。結論：核心零改動可存快照、daemon 追加事件與任務主動發布的事件；要所有底層事件不漏須補來源端交接契約。

**選項**（[§6](reviews/2026-10-05/event-store.md#6-三個候選做法)，可組合、不是三選一）：A 每 node 存 JSONL、模組自行分段；B 集中 collector；C 來源只提供事件出口、保存交模組。不論選哪案，§7 列了要先寫清楚的四項契約（紀錄／事件／確認分清、來源識別、讀者能表達缺口、留存不破壞恢復證據）。

**待決 5 題**（[§11](reviews/2026-10-05/event-store.md#11-需要使用者決定的題)）與預設：① 保到什麼程度——預設合作來源的逐件業務事件＋明示為取樣的核心觀測；② 給人／LLM 回看還是有任務必須逐件處理——預設兩種用途分開宣告；③ 先單 node 還是直接集中——預設先單 node（A）驗契約；④ 空間滿了工作要不要等——預設必讀通道停收新責任、一般觀測繼續但明報缺口；⑤ 抵抗哪種中斷——預設第一版只承諾程序 SIGKILL 可接續。

prior-art 相關借用：觀測歷史、恢復證據與去重帳不能共用同一保存假設（[§11.4](reviews/2026-10-05/prior-art.md#114-觀測歷史恢復證據與去重帳不能共用同一保存假設)），`log.on` 不是完整必達來源（[§11.5](reviews/2026-10-05/prior-art.md#115-logon-也不是完整必達的事件來源)）。

## agent／LLM 作者與 adapt-llm（llm-author）

[報告](reviews/2026-10-05/llm-author.md)。結論：現有核心夠承載第一個原型；要在包層補候選驗證、發布與恢復、單次呼叫回條、token 部分結算。

**選項**（[§九](reviews/2026-10-05/llm-author.md#九最小可試切法與驗收計畫)）是三刀：第一刀固定工具的作者（先驗完整交付路徑）、第二刀單次 LLM gateway＋token 結算、第三刀一條非控制用途的 adapt-llm。

**待決 12 題**（[§十](reviews/2026-10-05/llm-author.md#十待決題與預設建議)），最先卡住開工的四題與預設：先證明作者價值還是跨 node 轉換價值——預設先做 CSV 固定工具作者；作者能寫任意程式嗎——預設只組合可信工具；候選自動發布嗎——預設先產生可審查候選；遠端結果不明時——預設保留預留額、不自動重送。其餘八題（舊工作替換、adapt 新鮮度政策、逐件或最新值、token meter、usage 未知能否交付、語意驗收標準、保存故障等級、何時升級完整 agent）在報告表裡。「逐件或最新值」那題的逐件分支會接回事件保存（[§三的最小交接](reviews/2026-10-05/llm-author.md#與事件保存的最小交接)）。

prior-art 相關借用：穩定 request、attempt 與效果帳分離（Temporal，[§9](reviews/2026-10-05/prior-art.md#9-temporaldurable-workflow借流程嘗試與效果的分離)）。

## kernel 任務包（kernel-pack）

[報告](reviews/2026-10-05/kernel-pack.md)。結論：不改核心即可成立；第一版建議可接續的決策骨架加綁定原始 run 的 kill，step／budget／adapt 保持獨立。

**選項**見 [§8 最小第一版切法](reviews/2026-10-05/kernel-pack.md#8-最小第一版切法與-aos7-pack-的界線)（aos7-pack 可分開做）。

**待決 7 題**（[§10](reviews/2026-10-05/kernel-pack.md#10-待決題與預設建議)）與預設：第一版先證明什麼——預設 kernel 骨架＋進度監督範例、只觀測與 run-bound kill；規則用純函式還是外部程式——預設純函式；已提交的 kill 能否撤回——預設不自動撤回、釘原 run；接續保證跨多大——預設同部署、同 node、同槽；誰能控制同一槽——預設單一控制者；三個現有包要不要改成插件——預設保持獨立；aos7-pack 綁不綁第一版——預設分開。

prior-art 相關借用：有界重試與停手原因、父結束後孩子的處置、意圖版本與已生效版本分開（[§12 借用順序](reviews/2026-10-05/prior-art.md#12-符合最小核心原則的借用順序)，Erlang／k8s 那幾節）。
