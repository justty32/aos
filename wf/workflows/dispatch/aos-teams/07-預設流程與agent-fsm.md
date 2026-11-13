# 預設流程（11-13 晚）：opus 帶隊、sonnet 搜集、fable 規劃、實作的 gpt 走 aos 的 agent-fsm

← [入口](../aos-teams.md)｜涵蓋：預設流程、實作誰做、gpt 系改走 agent-fsm、家機的 gpt 端點、待補｜上一份 [06-公司WSL活樹與任務書硬規則](06-公司WSL活樹與任務書硬規則.md)

## 預設流程

**opus 帶隊 → 指揮 sonnet 搜集訊息 → opus 整理匯總 → fable 規劃與設計架構 → opus 深化細化架構 → 實作。**

- **opus 從頭帶到尾**：寫任務書、派 sonnet 搜集、把搜集來的整理成給 fable 的匯總；fable 交稿後深化細化架構；實作時管輪內架構、權衡、審實作與整個流程。
- **sonnet 搜集**：查找、盤點、跑指令收結果，屬「簡單工作」（界線見[入口「簡單工作」](../aos-teams.md)）。現在給 sonnet；agent-fsm 有雛形之後也可給 gpt 系（簡單 terra、普通 sol）（使用者 11-13 晚「搜集也可以給gpt，只是這可能要等loop fsm有了雛形之後」）。
- **fable 規劃與設計架構**：只做頂層規劃／設計，**只讀 opus 備好的匯總**、不廣讀 repo；fable 可再派 fable 子 agent。這一輪可在輪間、輪中跑，次數不限；實作時 fable 不即時參與。
- **實作照既有分工**（使用者 11-13 晚選 A）：gpt 系優先、照圖紙寫碼，claude（opus 普通、sonnet 簡單）補位；gpt 系不參與設計決策（入口「gpt 系」那條照舊）。**gpt 系改走 aos 體系**：見下節。
- 派出去的 agent 先通讀 wf/ 規矩，並先讀知識庫 `~/aos-home/knowledge/aos/_description.json` 大致掌握 aos 體系；兩者同一套例外，簡單工作與雜活免讀（入口「讀規矩」；使用者 11-13 晚「照預設走」）。

原話見 [03「使用者 11-13 晚原話」](03-使用者原話.md#使用者-11-13-晚原話工作流程)。第 4 句把 11-07 午那條鏈寫定：搜集由 sonnet 做（11-07 午「可以是opus計劃，讓gpt收集」是舉例）；11-07 午「fable 只做頂層規劃、只吃備料、實作時不參與」與午後「輪中也可、次數不限」照舊。

## gpt 系改走 aos 的 agent-fsm（11-13 晚）

使用者：「codex這塊幫我改一下，改成走aos體系，也不用eca，就直接loop fsm」。

- 派 gpt 系做事時，**在 aos 體系裡開 agent-fsm 身的 agent**（`loop.json` 的 fsm 身、腦接 gpt 系模型），不直接叫 codex CLI、也不用 eca 身（eca＝外部 CLI 當身，codex 也是一種 eca）。
- 舊的 codex 條文（入口的 codex 隊員、02 分檔的 codex CLI 指令、沙箱、`/goal`）先留，等 agent-fsm 那套跑通再清（使用者 11-13 晚「照預設走」）。
- **家機的 gpt 端點**：本地 LiteLLM proxy `http://127.0.0.1:4000`（OpenAI 相容；使用者「我本地litellm proxy開起來了」）。模型普通工作 `chatgpt-gpt-6.1-sol`、簡單工作 `chatgpt-gpt-5.6-terra`；另有 `-low`／`-medium`／`-high`／`-xhigh`／`-max`／`-nothink` 後綴與本地模型。

### 知識庫查得到的線索

- 兩種身：agent-fsm＝aos 自己的四格迴圈（idle、think、wait、act），腦是寄信給 llm kernel；eca＝Claude Code 或 Codex CLI 當身（`aos/body.json`）。
- agent-fsm 範本獨有 `body.json`（`aos-loop loop.json`）、`fsm.json` 與各格程式；兩個範本都有 `llm.json`（如 `{"model": "sonnet"}`），用 `agent_def` 複製範本（`aos/definition.json`）。
- agent-fsm 的 `llm.json` 裡 `model` 是 **endpoint pack 名**，身會把它放進信的 `endpoint`；pack 由 llm kernel 擁有、固定模型與取樣設定，`aos-llm ls` 列出現有的 pack（`aos/brain.json`）；kernel 依它的 `kernel.json` 裡的 endpoint pack（slots、priority、budget）挑信（`aos/cli/parts/llm_kernel.json`）。

### 待補

- 怎麼在 llm kernel 加一個指向 LiteLLM proxy、模型 `chatgpt-gpt-6.1-sol`／`chatgpt-gpt-5.6-terra` 的 endpoint pack（知識庫沒寫 pack 的端點網址、模型怎麼填）。
- 開 agent-fsm agent 做實作的具體步驟（從哪個範本複製、給哪些工具、工作區、怎麼收結果）、它能不能寫碼（工具只有已註冊的 aos 工具）。
- 公司 WSL 有沒有同樣的 proxy。
