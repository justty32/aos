# 任務：研究「受限制的 LLM CPU 數量」下的排程管理（純規劃）

> 交接書是唯一契約。**純研究與規劃，不寫程式。**

## 背景與唯一目標

使用者 2026-08-30：「一切都是在 llm cpu 只有一個的狀況下，也就是要做排程管理，可能要先派一個團隊去研究。」
現況：每隻 agent 的 `step` 自己直接打 LM Studio（`aos llm`）或起 `pi`；多隻 agent、多個世界、heartbeat 的 `ask`、
未來的子 agent 團隊，全部搶同一顆 CPU（本機 LM Studio 一次只能服務有限並行；DeepSeek 也有速率上限）。
**唯一目標**：交一份使用者能拍板的排程方案——誰排隊、隊伍住哪、誰消化、優先序與公平、餓死與逾時怎麼辦、
跟回合制怎麼相容——每個分歧列選項＋建議＋代價。

## 先讀

- [PROTOCOL](PROTOCOL.md)、`core/loop/README.md`、`core/agent/README.md`、`core/llm/README.md`、`core/agent/docs/pi-cpu.md`、`core/tick/README.md`
- [top-down-cli §三](../../ideas/top-down-cli.md)：「LLM 不是被呼叫的函式，是另一台跑同一套協定的機器」——把「想一次」投遞到 llm pu 資料夾、本地回合輪詢結果。
- [ideas/llm-cpu.md](../../ideas/llm-cpu.md)（若存在）、workshop [finite-resource-queue](../../workshop/records/finite-resource-queue.md)（五位一致要「使用者層級的 endpoint 佇列」）、使用者 2026-08-25 的話：「外部處理器自己監控一個資料夾、甚至不必引用 aos lib」（排隊是外部處理器的家務）。
- [ideas/tools/call-loop.md](../../ideas/tools/call-loop.md)（三回合往返）、[nested-worlds](../../ideas/nested-worlds.md)、[usability-target](../../ideas/usability-target.md)（第二級：agent 團隊）。
- 采風 [ai-core-field/synthesis.md](../../ideas/ai-core-field/synthesis.md)：ai_core 對 resources／lifecycle 軸的主張。

## 工作（Fable 隊長＋codex ×3）

1. **盤點爭用點**：現在哪些路徑會打 LLM（agent step 兩種 engine、heartbeat ask、未來 tool 型 LLM 呼叫、子 agent），各自的呼叫頻率與阻塞方式；LM Studio 實際能並行幾個請求（查文件與 `curl` 實測一次即可，**不 load／unload 模型**）。
2. **方案空間**（至少三個，各附代價）：
   - A「LLM PU 是另一個世界」：`llm/` 資料夾＋`aos run`，agent 把 prompt 投到它的 inbox，回合輪詢結果——排程＝那個世界的匯聚順序；
   - B「外部處理器監控資料夾」：獨立小程式（不引用 aos lib）看一個佇列目錄、逐個打 LLM、寫回；
   - C「loop 內的資源閘」：`state.json`／登記表標 `resources: llm`，loop 每回合只放行 N 條需要 LLM 的 inst；
   - 其他你想到的。
3. 每個方案回答：優先序（使用者對話 > agent 自語？heartbeat ask 最低？）、公平（多世界輪詢）、餓死／逾時／CPU 掛了怎麼辦、**跟「一回合一批、回合邊界不變」怎麼相容**、對現有 `step`／`aos llm`／pi 引擎各要改多少、子 agent 團隊（第二級）撐不撐得住。
4. 寫 `wf/workflows/ideas/scheduling/README.md`（≤ 3 頁：爭用點盤點、方案對照表、建議、**要使用者拍板的清單**每條問題／選項／建議／代價）＋ `experiments.md`（實測數字與指令）。

## 硬性限制

- 不寫程式、不改 `core/`；只寫 `wf/workflows/ideas/scheduling/`。commit 到 worktree 分支（只加這路徑）；不 push、不 merge。
- 不 load／unload LM Studio 模型、不取鎖、不開 GUI、不用 wf-lint。
- 方向性的留給使用者，只列選項與建議。

## 驗收（就這 3 條）

1. `README.md` 有爭用點盤點表、≥ 3 個方案的對照表、拍板清單（每條四欄齊）。
2. 每個方案都回答了「跟回合邊界怎麼相容」與「對現有程式改多少」。
3. `experiments.md` 有 LM Studio 並行度的實測數字與指令。

## 回報

最後一則訊息＝拍板清單原文（≤ 25 行）＋STATUS＋worktree 路徑與分支名。

## 隊長裁決

（隊長追加）

> **使用者修正（2026-08-30）**：題目是「受限制的 LLM CPU 數量下」——N 顆有限、各有並行上限與成本；N=1 只是特例。多補一題：請求怎麼選 CPU。
