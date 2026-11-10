# proto8/knowledge — 記憶庫（`memory` 讀的資料夾＋`.json` 樹）

← [proto8](../README.md)｜工具：[lib/agent/memory](../lib/agent/memory/_entry)（`read`／`ls`／`find`）、[lib/agent/memory_write](../lib/agent/memory_write/_entry)（`add`／`set`／`rm`）｜規劃：[thinking 11-05 agent-knowledge](../thinking/2026-11/05/agent-knowledge/README.md)；現在的形狀：[thinking 11-10 json-memory](../thinking/2026-11/10/json-memory/README.md)（[02 格式規則](../thinking/2026-11/10/json-memory/02-格式規則.md)、[03 工具](../thinking/2026-11/10/json-memory/03-工具.md)）

使用者 11-05：「頂層可以是簡介、index目錄之類，並且盡量講簡單……agent有需要的話，再去透過工具……抽取更深一層的知識……層級式記憶工具……這套知識庫還可以給多個agent共享！」11-10：「json本身就是節點樹。然後json跟檔案系統又有同像性，可以用xxx/xxx.json#/xxx/xxx，這個單一路徑取得東西。所以資料夾，配合各.json檔案。其實就是一個好東西了。」

**一個記憶庫＝資料夾＋`.json` 檔，整棵當一棵樹**，照 [wf/STRUCTURE 分層原則](../../wf/STRUCTURE.md#分層原則)：上層只放簡介與目錄、不重講下層細節。agent 用 `memory` 從根讀起、照目錄往下走。多隻 agent 指同一個資料夾就是共用。庫是普通資料夾、**不登記**（使用者 11-05「隨意複製，隨意修改，隨意給agent指定、隨意拆卸增添」）；指法兩種，具體的蓋一般的：① 定義裡給這隻 agent 指定——範本（11-10 templates-cp 起）把 `memory` 直接登記成 `lib/agent/memory`，庫寫在那一格的 `env`：`"AOS_MEMORY": {"$env": "AOS_HOME", "$path": "/knowledge/aos"}`（例 [templates/agent-fsm/tools.json](../templates/agent-fsm/tools.json)）；也可以在工具資料夾放 `_memory.json`＝`{"base": …}`（相對從那個資料夾算）；③ 覆蓋層：`aos-tools … add --envs AOS_MEMORY=/x/kb …` 把變數寫進登記格（11-05 晚 R1）；② 環境變數 `AOS_MEMORY`（絕對路徑，或相對管我的 daemon 的 stack；寫進 daemon 或 agent 定義的 `.env`，跟 `AOS_LLM_KERNEL` 同一套）。一支 memory 工具＝一個庫的根。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-樹長怎樣與多庫](docs/01-樹長怎樣與多庫.md) | 一棵樹長怎樣、統一路徑 `資料夾/檔.json#/指標`、`_index.json` 與 `_index` key 兩種表、`_description`、`"."` 格、`$ref`／`$env`、沒登記的東西；多庫＝根表多一格指到別的庫 |
| [02-寫入與節點怎麼寫](docs/02-寫入與節點怎麼寫.md) | `memory_write` 的 `add`／`set`／`rm`、寫入只准在庫根底下、沒有鎖（後寫的蓋掉先寫的）、出廠庫由人設唯讀、git 的 ignore 規則、節點怎麼寫 |

## 有哪些知識庫

| 資料夾 | 內容 | 給誰 |
|---|---|---|
| [aos/](aos/_index.json) | aos 體系知識。根表 `"."`＝一頁簡介＋八個詞＋五條規則；`world.json`（心智模型與環境變數）、`me.json`（我是誰；`#/self_tools` 改自己的工具、`#/self_llm`）、`agents.json`（生子 agent；`#/thought`）、`brain.json`（問腦、endpoint 包、priority）、`status.json`（daemon 表與 phase）、`errors.json`（錯誤行 `程式: error: 代號 原因`、`warning:`、結束碼 10 與 `[exit code N]` 怎麼讀；`#/codes` 是代號結尾表（C-54 六種結尾＋`Internal`）、`#/common` 是最常碰到的代號）、`memory.json`（何時寫知識、先 find、一段 ≤ 2 KB、`add`／`set`／`rm` 怎麼叫）、`rules.json`（禁忌）、`cli/`（給人與外部 agent 的指令：aos-agent、aos-daemon-ctl、aos-tools、aos-grow、aos-eca-screen；旗標位置、短名、`-y` 與確認、錯誤與重試各一份） | 跑在 aos 裡的 agent（Haiku／luna 級小模型也要讀得懂）、經 aos-mcp 進來的外部 agent、人 |

試一下（從 `proto8/`）：

```sh
echo '{"op":"read"}' | AOS_MEMORY=knowledge/aos python3 lib/agent/memory/_entry
echo '{"op":"read","path":"errors.json#/codes"}' | AOS_MEMORY=knowledge/aos python3 lib/agent/memory/_entry
echo '{"op":"find","query":"exit code"}' | AOS_MEMORY=knowledge/aos python3 lib/agent/memory/_entry
echo '{"path":"cli/"}' | AOS_MEMORY=knowledge/aos python3 lib/agent/memory_export/_entry   # 整棵印成一份 Markdown 給人看
```

知識庫若是有 `origin` 的 git 工作樹，可選用 [memory_sync](../lib/agent/memory_sync/) 的 `status`／`sync` 在收工前後同步；核心執行流程不會代為同步。工具會檢查 `.*.tmp`、`.tmp.*` 兩條 ignore 規則；同段衝突保留後同步這台的版本，刪改衝突交給人處理。
