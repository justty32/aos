# proto8/knowledge — 記憶庫（`knowledge_read` 讀的資料夾＋`.json` 樹）

← [proto8](../README.md)｜工具：[lib/agent/knowledge_read](../lib/agent/knowledge_read/_entry)（`read`／`ls`／`find`）、[lib/agent/knowledge_write](../lib/agent/knowledge_write/_entry)（`add`／`set`／`rm`）｜規劃：[thinking 11-05 agent-knowledge](../thinking/2026-11/05/agent-knowledge/README.md)；現在的形狀：[thinking 11-10 json-memory](../thinking/2026-11/10/json-memory/README.md)（[02 格式規則](../thinking/2026-11/10/json-memory/02-格式規則.md)、[03 工具](../thinking/2026-11/10/json-memory/03-工具.md)）

使用者 11-05：「頂層可以是簡介、index目錄之類，並且盡量講簡單……agent有需要的話，再去透過工具……抽取更深一層的知識……層級式記憶工具……這套知識庫還可以給多個agent共享！」11-10：「json本身就是節點樹。然後json跟檔案系統又有同像性，可以用xxx/xxx.json#/xxx/xxx，這個單一路徑取得東西。所以資料夾，配合各.json檔案。其實就是一個好東西了。」

**一個記憶庫＝資料夾＋`.json` 檔，整棵當一棵樹**，照 [wf/STRUCTURE 分層原則](../../wf/STRUCTURE.md#分層原則)：上層只放簡介與目錄、不重講下層細節。agent 用 `knowledge_read` 從根讀起、照目錄往下走。多隻 agent 指同一個資料夾就是共用。庫是普通資料夾、**不登記**（使用者 11-05「隨意複製，隨意修改，隨意給agent指定、隨意拆卸增添」）。**工具本身沒有預設位置**（使用者 11-10 深夜「knowledge_read/write，就是吃旗標或目標，或是吃環境變數，啊這些都要自己給。或是在定義中給」），找根的順序：① 命令列 `--root DIR`（人手動跑；不是 JSON 參數，腦改不了）＞ ①' `knowledge_write` 的呼叫參數 `root`（只有寫的這支收；相對從工作區 `$AOS_WS` 算；11-11 使用者「不給預設，要自己透過旗標指定或環境變數設定，或是工具呼叫內給。如果都沒有，那就報錯。」）＞ ② 工具資料夾的 `_knowledge.json`＝`{"base": …}` ＞ ③ 環境變數 `AOS_KNOWLEDGE`（範本寫在 `tools.json` 那一格的 `env`；或 `aos-agent tools add --envs AOS_KNOWLEDGE=/x/kb …`；或 daemon／定義的 `.env`）。都沒給＝`KnowledgeMissing`（brain.py、aos-mcp 看到它就安靜不帶根）；給了但不是資料夾＝`KnowledgeBad`。兩份範本（[agent-fsm](../templates/agent-fsm/tools.json)、[eca-claude](../templates/eca-claude/tools.json)）的 `knowledge_read` 指 `{"$env": "AOS_HOME", "$path": "/knowledge"}`＝**這一層**（使用者 11-10 深夜「指knowledge/」）。原本 `knowledge_write` 也指這裡（agent 寫了就改到 repo 的 `knowledge/`）；**11-11 拿掉**（使用者「不給預設，要自己透過旗標指定或環境變數設定，或是工具呼叫內給。如果都沒有，那就報錯。」）：寫要嘛腦在呼叫裡給 `root`，要嘛人替那格配 `AOS_KNOWLEDGE`，都沒有＝`KnowledgeMissing`，不會改到出廠庫。一支 knowledge_read＝一個庫的根。

**這一層就是樹根**（11-10 深夜起）：`knowledge/_index.json` 列 `aos/`（先讀它）與給人看的 `README.md`、`docs/`，`knowledge/_description.json` 一句簡介；所以路徑都從這裡寫起：`aos/errors.json#/codes`、`aos/me.json#/self_tools`（工具說明的 `Details: knowledge_read aos/…` 也是）。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-樹長怎樣與多庫](docs/01-樹長怎樣與多庫.md) | 一棵樹長怎樣、統一路徑 `資料夾/檔.json#/指標`、`_index.json` 與 `_index` key 兩種表、`_description`、自己的簡介（`_description.json`、`_description` key）、`$ref`／`$env`、沒登記的東西；多庫＝根表多一格指到別的庫 |
| [02-寫入與節點怎麼寫](docs/02-寫入與節點怎麼寫.md) | `knowledge_write` 的 `add`／`set`／`rm`、寫入不限範圍（看權限）、自己的簡介怎麼改、沒有鎖（後寫的蓋掉先寫的）、出廠庫由人設唯讀、git 的 ignore 規則、節點怎麼寫 |

## 有哪些知識庫

| 資料夾 | 內容 | 給誰 |
|---|---|---|
| [aos/](aos/_index.json) | aos 體系知識（路徑寫 `aos/…`）。根的 `_description.json`＝一頁簡介＋八個詞＋五條規則；`world.json`（心智模型與環境變數）、`definition.json`（定義資料夾裡各檔管什麼、哪些在 stack 有自己那份）、`body.json`（agent-fsm 與 eca 兩種身體的差異：腦、工具、hook、system、history）、`me.json`（我是誰；`#/self_tools` 改自己的工具、`#/self_llm`、`#/self_system`、`#/self_history`、`#/self_hook`〔含 `#/self_hook/handler` 怎麼寫 hook 程式〕、`#/self_state`、`#/self_ctl`）、`agents.json`（子 agent 與定義：`#/subagent`、`#/agents_ctl`、`#/agent_def`、`#/do_task`）、`mailbox.json`（agent 之間的信：`#/tools`、`#/rules`、`#/check` 定時查信不洗 history、`#/check_hook` 出廠的 mail_notify hook）、`clock.json`（每 N 拍叫醒：`#/wake_me`、`#/rules`、`#/quiet_timer`、`#/choose` 定時做事三種做法與洗不洗 history）、`brain.json`（問腦、endpoint 包、priority）、`status.json`（daemon 表與 phase）、`errors.json`（錯誤行 `程式: error: 代號 原因`、`warning:`、結束碼 10 與 `[exit code N]` 怎麼讀；`#/codes` 是代號結尾表（C-54 六種結尾＋`Internal`）、`#/common` 是最常碰到的代號）、`knowledge.json`（`#/read` knowledge_read 的 read／ls／find 與開場給的根、`#/where` 寫哪個庫、`#/write`／`#/rules` 何時寫知識、寫要有自己的庫〔`root` 或 `AOS_KNOWLEDGE`〕、先 find、建議一段約 1 KB、一個檔約 8 KB〔11-11 使用者改，只是推薦〕、`add`／`set`／`rm` 怎麼叫）、`rules.json`（禁忌）、`cli/`（給人與外部 agent 的指令：每支 `aos-*` 指令都有自己的節點（help 為準），底層零件 aos-exec、aos-loop、aos-fsm、aos-daemon、aos-post、aos-lock、aos-json、aos-directive、aos-llm、aos-llm-kernel 在 `cli/parts/`；旗標位置、短名、`-y` 與確認、錯誤與重試各一份） | 跑在 aos 裡的 agent（Haiku／luna 級小模型也要讀得懂）、經 aos-mcp 進來的外部 agent、人 |

試一下（從 `proto8/`）：

```sh
echo '{"op":"read"}' | python3 lib/agent/knowledge_read/_entry --root knowledge
echo '{"op":"read","path":"aos/errors.json#/codes"}' | python3 lib/agent/knowledge_read/_entry --root knowledge
echo '{"op":"find","query":"exit code"}' | AOS_KNOWLEDGE=knowledge python3 lib/agent/knowledge_read/_entry   # 環境變數也行
echo '{"path":"aos/cli/"}' | python3 lib/agent/knowledge_export/_entry --root knowledge   # 整棵印成一份 Markdown 給人看
```

知識庫若是有 `origin` 的 git 工作樹，可選用 [knowledge_sync](../lib/agent/knowledge_sync/) 的 `status`／`sync` 在收工前後同步；核心執行流程不會代為同步。工具會檢查 `.*.tmp`、`.tmp.*` 兩條 ignore 規則；同段衝突保留後同步這台的版本，刪改衝突交給人處理。
