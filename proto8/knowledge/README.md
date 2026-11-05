# proto8/knowledge — 知識庫（層級式記憶工具 `memory` 讀的資料夾）

← [proto8](../README.md)｜工具：[lib/agent/memory](../lib/agent/memory/_entry)（`read`／`ls`／`find`）｜規劃：[thinking 11-05 agent-knowledge](../thinking/2026-11/05/agent-knowledge/README.md)（[01 工具](../thinking/2026-11/05/agent-knowledge/01-層級式記憶工具.md)、[02 aos 知識庫](../thinking/2026-11/05/agent-knowledge/02-aos知識庫.md)）

使用者 11-05：「頂層可以是簡介、index目錄之類，並且盡量講簡單……agent有需要的話，再去透過工具……抽取更深一層的知識……層級式記憶工具……這套知識庫還可以給多個agent共享！」

**一個知識庫＝一個資料夾樹**，照 [wf/STRUCTURE 分層原則](../../wf/STRUCTURE.md#分層原則)：每個節點是一段短文＋它的子節點，上層只放簡介與目錄、不重講下層細節。agent 用工具 `memory` 從根讀起、照目錄往下走。多隻 agent 指同一個資料夾就是共用。知識庫是普通資料夾、**不登記**（使用者 11-05「隨意複製，隨意修改，隨意給agent指定、隨意拆卸增添」）；指法兩種，具體的蓋一般的：① 定義裡給這隻 agent 指定——`tools/memory/` 做成小資料夾（`_entry`／`_tooldef.json`／`_metainfo.json` 三個捷徑指回 `lib/agent/memory/`）加一個 `_memory.json`＝`{"base": "../../knowledge/aos"}`（相對從那個資料夾算）；② 環境變數 `AOS_MEMORY`（絕對路徑，或相對管我的 daemon 的 stack；寫進 daemon 或 agent 定義的 `.env`，跟 `AOS_LLM_KERNEL` 同一套；現在最方便）。一支 memory 工具＝一個知識庫；要接幾個就登記幾支（多庫假裝一庫是後續步驟）。

## 節點怎麼寫（給人改內容時看）

- 資料夾節點 `<路徑>/`：文在 `README.md`，子節點＝裡面的子資料夾與 `*.md`；葉節點 `<路徑>.md`。名字只用 `[a-z0-9_-]`；`.`、`_` 開頭的檔不算節點。
- 文是 Markdown：第 1 行 `# 標題`，標題後第一個非空行是**一句話摘要**（`ls`／`read` 的目錄印這句），再往下才是本文。
- 寫給小模型：短句、具體的呼叫例子、一致用詞、一個節點 ≤ 2 KB；撐大就拆成子節點、上層只留摘要。內容語言英文（AI 讀）；本 README 與各知識庫的人用說明繁中。

## 有哪些知識庫

| 資料夾 | 內容 | 給誰 |
|---|---|---|
| [aos/](aos/README.md) | aos 體系知識：一頁簡介＋八個詞＋五條規則（根）；`world`（心智模型與環境變數）、`me`（我是誰、`self_tools` 改自己的工具）、`agents`（生子 agent）、`brain`（問腦、endpoint 包、priority）、`status`（daemon 表與 phase）、`errors`（錯誤代號怎麼讀）、`rules`（禁忌）、`cli`（給人與外部 agent 的 aos-agent 指令） | 跑在 aos 裡的 agent（Haiku／luna 級小模型也要讀得懂）、經 aos-mcp 進來的外部 agent、人 |

試一下：`cd proto8 && echo '{"op":"read"}' | AOS_MEMORY=knowledge/aos python3 lib/agent/memory/_entry`。
