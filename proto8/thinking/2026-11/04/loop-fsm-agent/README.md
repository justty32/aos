# 2026-11-04 aos 體系自己的 loop／fsm agent：用 aos-loop＋aos-fsm 組、腦接 LLM、走 queue 協議、對外接法跟 eca 對齊（fable 規劃）

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜前情：[11-03 aos-agent](../../03/aos-agent.md)（say／listen 以後併進通用介面、對接 eca 與這隻）、[10-30 eca](../../../2026-10/30/eca/README.md)（外部 coding agent 包成同形資料夾；02 兩塊比較）、[10-30 agent-lifecycle](../../../2026-10/30/agent-lifecycle/README.md)（queue 協議、決定 33～36）、[11-03 eca-tools](../../03/eca-tools/README.md)（`tools.json` 登記檔）、[eca 21](../../../2026-10/30/eca/21-11-04-開場白檔可指定.md)（開場白改旗標 `--prompt`）、[11-03 procs](../../03/procs/README.md)、[11-03 ctl-commands](../../03/ctl-commands/README.md)、[11-03 aos-post](../../03/aos-post/README.md)｜被刪的上一套：[10-28 agent-round](../../../2026-10/28/agent-round/README.md)、[archive/agent-round-concepts](../../../../archive/agent-round-concepts/README.md)（只留概念）｜條文：[C-19、C-46、C-50、C-62](../../../../docs/CONCEPTS/05-agent.md)、[C-51、C-52、C-56、C-69](../../../../docs/CONCEPTS/01-設計理念.md)、[N-36、N-39](../../../../docs/NORMS/07-基礎設施-組合子.md)、[N-16](../../../../docs/NORMS/05-基礎設施-窗.md)、[N-53](../../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[P-08、P-11、P-12、P-19、P-20、P-35、P-41、P-42、P-43](../../../../docs/CONVENTION/02-題目stack停錯腦.md)｜程式（只翻、沒改）：[impls](../../../../impls/README.md) aos-exec／aos-loop／aos-fsm／aos-daemon／aos-post、[bin](../../../../bin/README.md) aos-tools／aos-eca-turn、[lib](../../../../lib/README.md)、extras/human、extras/eca、`tests/fixtures/agent-eve`（P-41 範本，舊協議）

本檔只記使用者原文（逐字）、決定、fable 照原則定的規劃（可翻案）、原則推不出答案的衝突與方向題（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。**規劃 11-04 裁完、照規劃實作**；統一的 aos-agent 介面本身這輪不規劃，只把兩邊不一樣的地方標出來留給它。

## 使用者原文

- 11-04（逐字）：「接下來是弄aos loop/fsm agent了，讓fable去規劃吧」
- 11-04 補（逐字）：「這個好了之後，就可以綜合eca和這個的特性，弄出統一的aos-agent介面」
- 本題照用的既有原文：10-16「agent的定義就是一個狀態機……我們的規範會說，為了讓agent方便審視自己，所以agent就是一個被人驅動的狀態機，需要外面有人用loop驅動他」（C-62）；10-23「範本」（aos-agent 做成範本、不是程式）；10-29「這一層更接近訊息的queue概念」（決定 33）、「aos-loop是aos agent這個程式中的內部組件」（決定 34）；10-29「第一個就是射後不理……第二個則是射後有理……如果是aos agent，還可以暫停其狀態機，去修改更多東西」「這應該是寫死在定義裏的」；10-30「fsm的next可以按照結束碼分岔」（N-36）；10-31「可以都先做成單檔案，有需要再將其中功能拆出來成 aos 函數」、「只有一個檔案固定，剩下的，則都由這個檔案指定。要再靈活一些，可以用上環境變數或argv指定」（C-51 加註）；11-01「環境變數……有點類似janet中的dyn，最好要謹慎，只在必要的時候使用」、「明明現有的機制組合一下就能搞定，偏偏在那邊亂搞一通」、「腦這東西未來會被統一管理……那塊就到時候再說」；11-03「封存這條線，1.該刪的都刪光刪乾淨」（round）、「對於eca來說，他收到信後，丟給claude之類的，然後這封信就算是完成了」、「每次aos-eca-turn就是把所有信一起丟進去(當然，是有順序的)」；11-04「不該在json中指定檔案名稱，應該改成用旗標指定」。

## 決定

- 11-04：要做；規劃交 fable（「讓fable去規劃吧」）。
- 11-04：做完之後才綜合兩邊弄統一的 aos-agent 介面；這輪不規劃它。
- 11-04：[04 衝突與方向題](04-衝突與方向題.md#決定11-04使用者) 四題都選建議（逐字選項）：衝突 1「接進對話紀錄就收」、衝突 2「think 也退 10，條文加註」、方向題 1「放範本裡，每隻複製」、方向題 2「等答完回 idle 再收」；並說「記完就實作」。條文 P-11、P-19、P-35 照這兩個衝突加 11-04 註（原字不改）。

## 一句話

**一隻 aos agent＝一個範本資料夾 `demo/agent-fsm/`**：`_entry`＝`["aos-loop", "loop.json"]`、`loop.json` 開 `ctl.json`／`state.json` 窗、每次跑一格 `fsm.json`；表上三格 idle／think／act 各是範本裡一支純標準庫 Python（`idle.py` 從 `$AOS_STACK/queue/` 收信接進 `history.jsonl`、`brain.py` 帶 history 與 `tools.json` 的工具問 OpenAI 相容端點、`act.py` 照最後一則 assistant 的 `tool_calls` 用 `aos-tools call` 跑工具）；`next` 照結束碼分岔（N-36）：think 退 10＝答完回 idle、idle 退 10＝queue 空（表上接住＝停著等、不接＝收工）。對外只碰 stack 三樣（P-42）：aos-say／aos-listen 一字不改、`aos-daemon-ctl add` 直接掛、暫停粒度到一格。**跟 eca 同形**：同一種 `_entry`／`loop.json`、同一個 queue／history／ctl／state、同一份 `tools.json`、同一個 `--prompt FILE` 開場白、信接進去就收；不同的只有一輪的身體（fsm 三格 vs aos-eca-turn）、queue 空的寫法（表 vs 旗標）、工具怎麼接（aos-tools 直接叫 vs aos-mcp）、沒有畫面與名片——對照表在 [02](02-跟-eca-對照.md)，留給統一 aos-agent 用。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../../../wf/STRUCTURE.md) 按 `##` 標題拆開；本檔留前言與表，各段在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-設計](01-設計.md) | 1 範本資料夾；2 `loop.json` 與 `fsm.json`；3 三格各做什麼（idle／brain／act、旗標、結束碼）；4 腦怎麼叫；5 工具怎麼接；6 queue、history 與對話紀錄；7 stack 佈局；8 跟 daemon、aos-say／listen 怎麼接；9 失敗與邊緣狀況；10 不做的、以後的 |
| [02-跟-eca-對照](02-跟-eca-對照.md) | 兩邊一樣的、兩邊不一樣的（給統一 aos-agent 用）、條文要加的註 |
| [03-實作步驟](03-實作步驟.md) | 步驟表（每步含驗證）、測試清單 |
| [04-衝突與方向題](04-衝突與方向題.md) | 要使用者看的：衝突 2 條、方向題 2 題（各附建議） |
