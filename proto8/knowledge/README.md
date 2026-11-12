# proto8/knowledge — 出廠內容樹（普通資料夾＋`.json`，太大的節點補 `_index.json`／`_index` 當客觀 index）

← [proto8](../README.md)｜由來：[thinking 11-05 agent-knowledge](../thinking/2026-11/05/agent-knowledge/README.md)、[11-10 json-memory](../thinking/2026-11/10/json-memory/README.md)

使用者 11-05：「頂層可以是簡介、index目錄之類，並且盡量講簡單……這套知識庫還可以給多個agent共享！」「隨意複製，隨意修改，隨意給agent指定、隨意拆卸增添」。11-10：「json本身就是節點樹。然後json跟檔案系統又有同像性，可以用xxx/xxx.json#/xxx/xxx，這個單一路徑取得東西。所以資料夾，配合各.json檔案。其實就是一個好東西了。」

**這是一棵普通的資料夾＋`.json` 樹**，沒有專屬工具、不登記：agent 用一般的讀檔／json 工具（`read`、`ls`、`view`、`json_get`、`json_ls`、`grep`…）讀，人用 `aos-json` 或編輯器改。照 [wf/STRUCTURE 分層原則](../../wf/STRUCTURE.md#分層原則)：上層只放簡介與目錄、不重講下層細節。

**index**（使用者 11-12）：「description和index是可以合起來的，或者說，本來就該合起來，統一叫_index.json/_index，也就是agent自己對這個節點的理解。格式就是{xxx:{description:...}, yyy:{...}}。當然，這個_index.json/_index有其天然位置，這個天然的意思是，在沒有指定位置的時候，agent如果想要了解某個節點的狀況，就會去看其上方節點的index。」「放在天然位置的index，其實會是所謂的客觀index，而agent自己存的則是主觀。」「反正最基礎的就是這樣。後續什麼agent自己存、更新啥的，或是除了description外還要加啥，就後續再說」

**只給太大的補**（使用者 11-12）：「當節點下的某些東西太龐大了，所以用index給他做一個簡介。所以現有aos知識庫中，如果有些東西太大，那就補index.json/_index。如果夠小，那其實也不用做看法了，直接讀就是了。」

- 資料夾的 index＝該夾的 `_index.json`：`{"body.json": {"description": "…"}, "cli": {"description": "…"}}`，鍵是夾裡的檔名或子資料夾名（不帶尾斜線），列出夾裡每一個東西（`_index.json` 自己除外）。這棵樹只有東西多的三夾有：`aos/`、`aos/cli/`、`aos/tools/`（門檻：夾裡超過 15 個東西）。
- JSON 物件的 index＝它的 `_index` 鍵：`{"xxx": {"yyy": true, "_index": {"yyy": {"description": "present the state of switch A"}}}}`，鍵是同一個物件的其他鍵。這棵樹只有 `aos/packs.json` 有（門檻：檔超過 8000 bytes＝`json_get` 預設上限，或頂層內容鍵超過 10 個）。
- 一格除了 `description` 還可以放 `index`：一條路徑，指到另一份 `_index.json`／`_index`（例：`aos/_index.json` 的 `cli` 一格寫 `"index": "cli/_index.json"`）；檔內 `_index` 本身也可以是這種路徑字串。相對路徑從裝著那份 index 的容器算（`_index.json`＝它的資料夾；檔內 `_index`＝裝著它的物件，當成資料夾走，根物件＝這個檔），`index_view` 只顯示、不往下讀（使用者 11-12 晚，[docs/01](docs/01-樹長怎樣與多庫.md)）。
- 兩種 index 也都可以寫在 `_metainfo` 裡（`index` 格；`index_view` 裡外都讀、外面那份贏），這棵樹現有的都放外面、不搬；正文 `_description` 只放外面：見 [N-69](../docs/NORMS/10-基礎設施-定義與工作區/11-N-69.md) 11-12 補。
- 想知道某個節點是什麼，就看它上一層的 index；沒有 index 的夾或檔就是夠小，直接讀。最頂層沒有上一層＝本來就沒有；沒列到的節點＝不管。這裡放的都是天然位置的 index（使用者稍後改說法：index 是視角，天然位置那份＝各 agent 的通用視角；要真正客觀用 `ls`／`json_ls`，[thinking 11-12 index](../thinking/2026-11/12/index.md)）；description 用英文、一句話。agent 自己的看法（主觀 index、cache）放哪不規定。

分檔與內容：

| 分檔 | 涵蓋 |
|---|---|
| [01-樹長怎樣與多庫](docs/01-樹長怎樣與多庫.md) | 一棵樹長怎樣、統一路徑 `資料夾/檔.json#/指標`、`_index.json` 與 `_index` 兩種 index、`_description`（節點自己的正文）、`$ref` |
| [02-寫入與節點怎麼寫](docs/02-寫入與節點怎麼寫.md) | 節點怎麼寫：一段一個字串、大小建議、名字、index 那一格、拆檔留 `$ref`、內容語言 |

| 資料夾 | 內容 | 給誰 |
|---|---|---|
| [aos/](aos/_index.json) | aos 體系知識（路徑寫 `aos/…`）：`_description.json` 一頁簡介＋八個詞＋五條規則；`world.json` 心智模型、`definition.json` 定義資料夾各檔、`body.json` agent-fsm 與 eca 兩種身體、`me.json` 我是誰與 `self_*` 工具、`agents.json` 子 agent 與定義、`mailbox.json` 信、`clock.json` 定時、`brain.json` 問腦、`status.json` daemon 表與 phase、`errors.json` 錯誤行與結束碼、`rules.json` 禁忌、`kernel.json` kernel 是什麼、範本在哪、怎麼自己寫一個、`packs.json` 工具包、`tools/` 每支出廠工具一份、`cli/` 給人與外部 agent 的指令（底層零件在 `cli/parts/`） | 跑在 aos 裡的 agent（小模型也要讀得懂）、經 aos-mcp 進來的外部 agent、人 |

試一下（從 `proto8/`）：

```sh
aos-json get --str knowledge/aos/_index.json#/rules.json/description   # aos/ 的 index 說 rules.json 是什麼
aos-json get knowledge/aos/me.json#/self_tools                 # {"$ref": "me/self_tools.json"}
aos-json get --follow --str knowledge/aos/me.json#/self_tools/add
echo '{"path":"knowledge/aos/packs.json#/_index"}' | AOS_WS=$PWD python3 lib/base/json_get/_entry   # 腦用的 json_get 也行
```
