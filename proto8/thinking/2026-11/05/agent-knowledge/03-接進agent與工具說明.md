← [入口](README.md)｜知識怎麼送進三種 agent 的 context、工具說明怎麼建立在知識上、等新功能隊收工後的實作步驟｜上一份 [02-aos知識庫](02-aos知識庫.md)｜下一份 [04-實測](04-實測.md)

# 接進 agent、工具說明建立在知識上（fable 代定，可翻案）

## 原則：根進 system prompt、其餘按需用 `memory` 拿

- **根（2 KB）每次都給**：放進 agent 的 system prompt（或外部 agent 的開場白）。給的是 `memory read` 根的輸出原文（文＋子節點目錄），不是 README 檔本身——目錄那段是工具印的，這樣腦看到的跟它之後呼叫 `memory` 看到的一模一樣。
- **其餘九節按需**：腦自己叫 `memory`（`read`／`ls`／`find`）往下走。Haiku 實測一題平均 1～2 次查詢就答對（[04](04-實測.md)）。
- **定義預先配**（使用者「規劃該agent用途時就在定義給他配上」）：某隻 agent 一定會用到的節，寫進它定義的 system prompt 檔（`system.txt`），不等它查；例：生子 agent 的隊長把 `agents` 節整段貼進去。
- **知識庫指法**：`AOS_MEMORY` 寫進 daemon 定義的 `.env`（整台共用）或某隻的 `.env`（只它）。相對路徑相對 `$AOS_DAEMON`。

## 三種 agent 各怎麼拿到

| agent | 根怎麼進去 | 深層怎麼拿 | 現在要改什麼 |
|---|---|---|---|
| **agent-fsm**（aos 自己的 loop／fsm agent） | `brain.py` 的 `--system system.txt` 之外加一個 `--memory`（或認 `AOS_MEMORY` 有設就做）：think 格每次組請求時叫一次 `memory read` 根、接在 system 後面當同一則 system 訊息（不存進 history，P-41 的 system 做法照舊）。目錄每次重讀＝知識庫改了下一題就看到 | `tools.json` 登記 `memory`（捷徑到 `lib/agent/memory`）；腦叫 `memory` 跟叫 clock 一樣走 act 格 | `demo/agent-fsm/brain.py` 加旗標、`tools.json` 加 `memory`、`fsm.json` think 格的 argv 加 `--memory`、demo/docs/02 一段；範本 `.env` 寫 `AOS_MEMORY`（絕對路徑或相對 daemon） |
| **eca-claude／codex**（外部 coding agent 經 `aos-eca-turn`） | 開場白檔（`aos-eca-turn --prompt FILE`）＝根的輸出＋一句「use tool memory for more」；開場白只在 history 空時投一次，之後靠 MCP 工具 | `cli.json` 的 `tools` 登記檔加 `memory`，經 aos-mcp 變成 MCP 工具 `memory` | `demo/eca-claude/tools.json` 加 `memory`、`loop.json` 的 argv 加 `--prompt knowledge_root.txt`（檔由人 `memory read > knowledge_root.txt` 產，或 aos-eca-turn 之後認 `AOS_MEMORY` 自己叫）；demo/docs/01 一段 |
| **外部 agent 直接經 aos-mcp**（Claude Code、pi 等，人自己接） | MCP `initialize` 回應的 `instructions` 欄位＝根的輸出（aos-mcp 有 `AOS_MEMORY` 就叫 `memory read` 塞進去；沒有＝照舊不給）。MCP 用戶端會把 `instructions` 放進它的 system prompt——不用改任何用戶端 | 登記檔裡有 `memory`＝tools/list 看得到、照叫 | `extras/ai_tools/bin/aos-mcp` 加 `instructions`（≈15 行）、README 一句 |

人在殼裡：`memory` 直接跑（`echo '{"op":"read","path":"cli"}' | AOS_MEMORY=… aos-exec proto8/lib/agent/memory`），或讀 `knowledge/aos/cli.md`。

## 工具說明（`_tooldef.json` 的 description）建立在知識上

規則（給之後改寫 self_tools、agents、clock 等 description 的人）：

1. **只寫增量**：這個工具做什麼、參數、回什麼、最常見的一兩個錯。不解釋 daemon、stack、overlay 是什麼——那是知識庫的事。
2. **用知識庫的詞**（[02 用詞表](02-aos知識庫.md#用詞表知識庫與工具說明都用這些字)），不用同義詞；提到概念時指節點：「see memory node `agents`」。
3. **英文**（給 LLM 的內容本來就不在「程式輸出英文化」規矩內，但知識庫是英文、description 混中文會讓小模型對不上詞；self_tools 現在的 description 是中文、agents 是英文，要統一）。
4. **≤ 80 字**：長說明搬進知識庫對應節點；description 留「怎麼叫＋哪裡看細節」。
5. **代號不重講**：description 只列工具自己的代號名（`PathBad`、`ToolExists`…），結尾怎麼讀交給節點 `errors`。

範例（self_tools，照規則改寫）：

> Add, remove or list your own tools. Changes only your overlay (your definition and other agents are untouched) and takes effect from your next turn. `path`: relative to your workspace, or absolute under `lib/`. Errors: PathBad, PathMissing, ToolExists, ToolUnknown, DaemonMissing. Details: memory node `me/self_tools`.

## 等新功能隊收工後的實作步驤（給隊長排；這輪沒動他們的檔）

| 步 | 內容 | 動哪些檔 | 派 |
|---|---|---|---|
| K1 | self_tools、agents、clock、lib/base 其餘工具的 `_tooldef.json` description 照上面五條改寫成英文增量 | `lib/agent/self_tools/_tooldef.json`、`lib/agent/agents/_tooldef.json`、`lib/base/*/_tooldef.json` | sonnet（純文字；改完 opus 對一遍用詞） |
| K2 | agent-fsm 接根：`brain.py --memory`（或認 `AOS_MEMORY`）、`tools.json` 加 `memory`、`fsm.json` think 格 argv、範本 `.env` 範例、demo/docs/02 | `demo/agent-fsm/{brain.py,tools.json,fsm.json}`、`demo/docs/02-agent-fsm.md` | opus |
| K3 | eca 接根：`demo/eca-claude/tools.json` 加 `memory`、開場白檔與 `loop.json --prompt`、demo/docs/01 | `demo/eca-claude/*`、`demo/docs/01-eca-claude.md` | sonnet |
| K4 | aos-mcp `initialize.instructions`＝`memory read` 根（有 `AOS_MEMORY` 才做） | `extras/ai_tools/bin/aos-mcp`、README | opus |
| K5 | 假腦劇本跑一遍：fsm1 掛上→say「給自己加 math」→腦先 `memory read me/self_tools` 再 `self_tools add`；接進 demo/docs/05 的件 1 段 | `demo/llm-kernel/kernel.json` 劇本、`demo/docs/05-feat-proto.md` | opus |
| K6 | 轉換工具原型（使用者：人要看就轉 markdown／html）：`lib/agent/memory_export/`（或 memory 的 `op: export`？代定另立工具，memory 保持唯讀純查詢）：把一個知識庫整棵印成一份 markdown（json 節點照印成 code block）；不強求 | 新資料夾、lib docs/03 一列、code map | sonnet |
| K7 | 增刪改（`add`／`edit`／`rm`，照 [01 鎖協議草稿](01-層級式記憶工具.md)）、**多庫假裝一庫**（`_memory.json` 的 `base` 收陣列，根目錄把各庫列成子節點、路徑第一段選庫；使用者裁題 3「後續可以修改這個memory工具，讓他可以接多個庫，只是假裝頂層還是一個庫」）、JSON 後端（`base` 指 `.json` 時走 aos-json `#/` 指標；使用者裁題 4「等大了再做」）——**另派 fable 規劃**後才做 | — | fable |
| K8 | 條文：C-42 加「11-05 落實：memory（層級式記憶）」；N-63 hub 型環境變數表加 `AOS_MEMORY` 一列；CONVENTION 加一條「agent 的 system prompt 以 memory 根開頭」（草稿，使用者定） | `docs/CONCEPTS/05-agent/*`、`docs/NORMS/10-…/07-hub-型環境變數與父子交代.md`、`docs/CONVENTION/*` | opus（條文不派 sonnet） |

依賴：K1～K4 互不相干可並行；K5 等 K1、K2；K8 最後。

## 給新功能隊的請求（本輪沒動他們的檔）

- **R1 aos-tools 登記格加選填 `env`**（`{"memory": {"path": "…/lib/agent/memory", "env": {"AOS_MEMORY": "../knowledge/aos"}}}`，`aos-tools call` 時合進那次呼叫的環境；相對路徑相對登記檔）：這樣 `aos-agent tools add` 寫進**覆蓋層**也能替這一隻換知識庫，不必在定義裡做包裝資料夾。優先序建議：工具資料夾的 `_memory.json` ＞ 登記格的 `env` ＞ 外面的 `AOS_MEMORY`（具體的蓋一般的）。動 `bin/aos-tools`、docs；aos-mcp 經 aos-tools 自然拿到。
- **R2 agent-fsm／eca 範本**：K2、K3 接根時，`tools.json` 登記 `memory` 用 R1 的 `env` 或包裝資料夾（二選一，照 R1 做不做定）。
