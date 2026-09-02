# 任務：tool 的規劃——先合成三份采風，再定 tool 登記表與表述、呼叫迴路、agent 通訊錄

> 交接書是唯一契約。**純規劃，不寫程式。** 采風原文在 [ideas/ai-core-field](../../../ideas/ai-core-field/README.md)（F1／F2／F3 三份）；現況 [PROTOCOL](../PROTOCOL.md)、`core/agent/src/tools.cpp`、`core/agent/docs/pi-cpu.md`；使用者裁決 [nested-worlds](../../../ideas/nested-worlds.md)。

## 背景與唯一目標

使用者 2026-08-30：「在這個環境下 tool 就很簡單，任何支持 POSIX 呼叫的程式都可以是 tool，所以要有一個檔案作為 tool 的登記列表，還有表述。」並補：子世界不管；**子 agent 不登記、就是一份通訊錄（像 wf inbox 的 contact list）**；tool 調查一個團隊就好。
**唯一目標**：交出一份使用者能拍板的 tool 規劃——登記表長什麼樣、表述給誰看、怎麼呼叫、agent 通訊錄長什麼樣——**每個分歧點列選項＋建議＋代價**，不替使用者決定方向。

## 團隊（你是 Fable 隊長）

codex ×3–4（`codex exec -m gpt-5.6-sol -C <worktree> --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`，只讀 aos 與 `~/repo/ai_core`，寫在指定檔）。你負責合成與判斷。

## 工作

1. **合成**：讀 F1／F2／F3 五段格式的 ③④⑤，寫 `wf/workflows/ideas/ai-core-field/synthesis.md`（≤ 2 頁）：起源對照表（ai_core 主張 → aos 現況 → 差距）、三隊在登記表形狀上的分歧與相容點（F1 三層來源／F2 一資料夾一 tool＋metainfo 三級降級／F3 exec+model+meta 兩層），以及「值得抄」的交集。
2. **登記表**（`wf/workflows/ideas/tools/registry.md`）：住哪（世界層 `.aos/tools/`？）、一項的欄位（最少必填幾欄）、來源優先序（手填／`--metainfo` 自述／預設）、`aos tool add <name> -- <argv>` 的行為、跟 agent 白名單的關係、LLM 類工具要不要強制標記。附一份範例（登記 8–10 個真實程式：`ls`、`grep`、`jq`、`git`、`aos deliver`、`aos say`、`aos llm`、`aos run <sub>`、handy 的 `llme`）。
3. **表述**（同檔或 `description.md`）：給模型看的一行長什麼樣（名稱＋一句＋args 型別＋stdin 模式）、給機器看的完整 JSON；呼叫格式改 argv list 的利弊（F2 指出 `{args}` 單字串折斷 argv-as-list）。
4. **呼叫迴路**（`call-loop.md`）：現行三回合往返要不要壓、錯誤怎麼結構化退回、危險工具要不要問人、**pi 引擎繞過 inst 的洞**（F3：工具事件須回填 `batch/`；可行的接法是什麼）、多步工具鏈。對照 `tools.cpp` 列差異清單。
5. **agent 通訊錄**（`contacts.md`）：像 wf inbox ROSTER——名字→資料夾（＝投遞地址），欄位最少化、誰維護（`aos agent init` 自動加一行？）、住哪（`.aos/contacts.json`？）、跨世界怎麼用。**不是登記表、不是白名單。**
6. 最後寫 `wf/workflows/ideas/tools/README.md`：導航＋**「要使用者拍板的清單」**（每條：問題／選項／建議／代價，≤ 12 條）。

## 硬性限制

- 不寫程式、不改 `core/`、不改 ai_core；只寫 `wf/workflows/ideas/tools/` 與 `ai-core-field/synthesis.md`。
- 不 push；commit 到你的 worktree 分支（只加上述路徑）。不取鎖、不開 GUI。
- 不要替使用者做方向性決定；實作層的小判斷可以建議。

## 交付與驗收（就這 3 條）

1. 六個檔都存在且 ≤ 各自頁數上限；README 的拍板清單每條四欄齊。
2. `registry.md` 的範例 JSON 能被 `python3 -m json.tool` 解析。
3. `synthesis.md` 的對照表每列都指得出 F1／F2／F3 哪一段。

## 回報

最後一則訊息＝README 拍板清單原文（≤ 30 行）＋STATUS＋worktree 路徑與分支名。

## 隊長裁決

（隊長追加）
