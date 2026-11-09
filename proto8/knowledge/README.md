# proto8/knowledge — 知識庫（層級式記憶工具 `memory` 讀的資料夾）

← [proto8](../README.md)｜工具：[lib/agent/memory](../lib/agent/memory/_entry)（`read`／`ls`／`find`）、[lib/agent/memory_write](../lib/agent/memory_write/_entry)（`add`／`edit`／`rm`）｜規劃：[thinking 11-05 agent-knowledge](../thinking/2026-11/05/agent-knowledge/README.md)（[01 工具](../thinking/2026-11/05/agent-knowledge/01-層級式記憶工具.md)、[02 aos 知識庫](../thinking/2026-11/05/agent-knowledge/02-aos知識庫.md)）

使用者 11-05：「頂層可以是簡介、index目錄之類，並且盡量講簡單……agent有需要的話，再去透過工具……抽取更深一層的知識……層級式記憶工具……這套知識庫還可以給多個agent共享！」

**一個知識庫＝一個資料夾樹**，照 [wf/STRUCTURE 分層原則](../../wf/STRUCTURE.md#分層原則)：每個節點是一段短文＋它的子節點，上層只放簡介與目錄、不重講下層細節。agent 用工具 `memory` 從根讀起、照目錄往下走。多隻 agent 指同一個資料夾就是共用。知識庫是普通資料夾、**不登記**（使用者 11-05「隨意複製，隨意修改，隨意給agent指定、隨意拆卸增添」）；指法兩種，具體的蓋一般的：① 定義裡給這隻 agent 指定——`tools/memory/` 做成小資料夾（`_tooldef.json`／`_metainfo.json` 兩個捷徑指回 `lib/agent/memory/`，`_entry` 是一行單子 `["../../../../lib/agent/memory/_entry"]`——不能是捷徑，aos-exec 解開捷徑後 `AOS_CD` 會是 lib 那格）加一個 `_memory.json`＝`{"base": "../../../../knowledge/aos"}`（相對從那個資料夾算；例 [templates/agent-fsm/tools/memory](../templates/agent-fsm/tools/memory/_memory.json)）；③ 覆蓋層：`aos-tools … add --envs AOS_MEMORY=/x/kb …` 把變數寫進登記格（11-05 晚 R1）；② 環境變數 `AOS_MEMORY`（絕對路徑，或相對管我的 daemon 的 stack；寫進 daemon 或 agent 定義的 `.env`，跟 `AOS_LLM_KERNEL` 同一套；現在最方便）。一支 memory 工具＝一個知識庫；多庫可照下節放捷徑，仍當一個根。

## 多庫與寫入

多庫＝一個資料夾放幾條捷徑，各指一個庫；`_memory.json` 的 `base` 或 `AOS_MEMORY` 仍只指這個資料夾，不加設定格式。例如人先準備：

```text
~/kb/
├─ README.md                   # 根簡介由人寫
├─ aos -> /path/to/proto8/knowledge/aos
└─ notes/
   └─ x.md
```

`memory read /` 會列出兩部分；`find` 跨捷徑查，命中保留 `aos/rules` 這種掛載路徑；`memory_export` 也跟捷徑，遇到繞回上層就停止。

要讓 agent 寫自己的庫，另配 [memory_write](../lib/agent/memory_write/)；它沿用同一套找根，`add` 建葉、`edit` 整段換文、`rm` 刪節點（子樹要 `recursive: true`）。根本身唯讀，`rm` 根層捷徑回 `PathBad`，更深的捷徑只拆捷徑；出廠 `knowledge/aos` 仍由人寫，範本接線屬 W5。**掛出廠庫要由人設成唯讀**（11-07 晚審裁定 7 選推薦，[晚審 04](../../wf/workflows/refactor/reports/2026-11-07-晚審/04b-要使用者裁定-續.md)）：跑 agent 的通常就是 repo 主人，「沒權限＝唯讀」不成立，經捷徑 `edit aos/rules` 會真的改到 repo、污染每隻 agent 的 system prompt；所以把 `knowledge/aos` 掛進別的記憶根時，由人先設唯讀（`chmod -R a-w` 那份，或掛一份唯讀副本）。寫前自動拿資料夾鎖、寫後釋放，租約固定為牆鐘 10 秒，不沿用呼叫者的時鐘或時鐘間隔；Linux 權限決定能不能寫，PATH 需有 `aos-lock`。既有檔用暫存後原子替換並保留權限。

庫在 git 下時，`.gitignore` 加 `.lock/`、`.tmp.*`、`.rm.*`；葉升級的暫存資料夾另加 `.new.*`。不要把鎖與暫存檔當知識提交。

## 節點怎麼寫（給人改內容時看）

- 資料夾節點 `<路徑>/`：文在 `README.md`，子節點＝裡面的子資料夾、`*.md` 與 `*.json`；葉節點是 `<路徑>.md` 或 `<路徑>.json`。名字只用 `[a-z0-9_-]`；`.`、`_` 開頭的檔不算節點。
- `.json` 葉可用 `memory` 的 `read` 讀 `節點#/json/pointer`（RFC6901，`~0` 表示 `~`、`~1` 表示 `/`），例如 `{"op":"read","path":"data#/items/0"}`；回傳該位置的 JSON 值。節點路徑不帶 `.json`；`ls`／`find` 不接受 `#`。
- `.md` 的文是 Markdown：第 1 行 `# 標題`，標題後第一個非空行是**一句話摘要**（`ls`／`read` 的目錄印這句），再往下才是本文。
- 寫給小模型：短句、具體的呼叫例子、一致用詞、一個節點 ≤ 2 KB；撐大就拆成子節點、上層只留摘要。內容語言英文（AI 讀）；本 README 與各知識庫的人用說明繁中。**11-07 改讀**：「內容語言英文」管的是出廠的 `knowledge/aos`；從外部語料收進來的庫，節點名英文、內文照語料原文存（見 [CONCEPTS C-42 續「知識庫存什麼、給人看什麼」](../docs/CONCEPTS/05-agent/01-續-C-42.md)）。（11-07 使用者裁定，傍晚選項框 ltn-7 選推薦，[lift-to-norms](../thinking/2026-11/07/lift-to-norms/README.md)）

## 有哪些知識庫

| 資料夾 | 內容 | 給誰 |
|---|---|---|
| [aos/](aos/README.md) | aos 體系知識：一頁簡介＋八個詞＋五條規則（根）；`world`（心智模型與環境變數）、`me`（我是誰、`self_tools` 改自己的工具）、`agents`（生子 agent）、`brain`（問腦、endpoint 包、priority）、`status`（daemon 表與 phase）、`errors`（錯誤行 `程式: error: 代號 原因`、`warning:`、結束碼 10 與 `[exit code N]` 怎麼讀；子節點 `codes` 是代號結尾表（C-54 六種結尾＋`Internal`）、`common` 是最常碰到的代號）、`rules`（禁忌）、`cli`（給人與外部 agent 的指令：aos-agent、aos-daemon-ctl、aos-tools、aos-grow、aos-eca-screen；11-06 拆成資料夾，旗標位置、短名、`-y` 與確認、錯誤與重試各一節） | 跑在 aos 裡的 agent（Haiku／luna 級小模型也要讀得懂）、經 aos-mcp 進來的外部 agent、人 |

試一下：`cd proto8 && echo '{"op":"read"}' | AOS_MEMORY=knowledge/aos python3 lib/agent/memory/_entry`。
