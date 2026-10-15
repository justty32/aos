# 2026-10-15 布局成長：檔案→資料夾、純值→物件，同一套規則

← [討論紀錄](README.md)｜落成：[C-55](../CONCEPTS/01-設計理念.md#布局成長10-15-使用者說原文)｜相關：[C-48 值的雙形](../CONCEPTS/01-設計理念.md)、[C-51 資料夾⇄JSON](../CONCEPTS/01-設計理念.md)、[C-54 命名](../CONCEPTS/01-設計理念.md#命名10-15-使用者說原文)、[同像性](2026-10-15-homoiconic.md)、[意見 5～7](2026-10-15-opinions-5-7.md)、檔案那邊的既有規矩 [wf/STRUCTURE.md](../../wf/STRUCTURE.md)（膨脹即拆、四級成長）

## 原文（10-15，照貼）

「然後佈局，佈局這塊包括資料夾和檔案，還有json物件等。就像先前說的，他們有同像性，然後先前也說過，json那邊，一個key的value可以是純值也可以是物件/陣列，這就跟檔案系統這邊，一個檔案他可以是純資料或資料夾一樣，所以...」

「啊，就是wf/STRUCTURE.md那個啦，一個檔案的內容如果太大太多，或是單個檔案無法承擔這麼多的職責，那就將其變成資料夾，然後原本檔案變成index+readme，然後資料夾內部按照既有的路徑去變化，比如index獨立出來，readme獨立出來...這樣。json那邊也是，純值，比如priority: 3，不夠用，那就將其變成obj: priority: {"val":1, "type":"normal task", "_notes":"haha", "timeout":0}」

## 決定

- 寫成設計理念 **C-55**（布局成長）：檔案那邊的規矩不重寫（wf/STRUCTURE.md 是唯一出處），C-55 只說「JSON 那邊照同一套」與兩邊怎麼對。
- 現況查證（AI，只是事實）：檔案那邊已照做——wf 的 `x.md` 長成 `x/`、`x.md` 留原位當入口（STRUCTURE 四級、整檔拆資料夾原路徑保留）；proto8 的 `CONCEPTS.md`＋`CONCEPTS/`、`NORMS.md`＋`NORMS/`、thinking 的 `2026-10-15-naming.md`＋`2026-10-15-naming/`；inst 那邊 TARGET 是資料夾時找裡面的 `inst.json`（N-35）。JSON 那邊已有三處雙形：ctl 的 `paused`／`stop`＝布林或 `{"val", "now"}`（N-07）、`priority`＝純量或 `{"level", "deadline"}`（lib gate）、fsm 的格＝TARGET 字串或 `{"target", "next"}`（N-36）。

## 結論（AI 整理）：兩邊怎麼對

| | 檔案系統 | JSON |
|---|---|---|
| 純形 | 一個檔 | 純值（字串、數字、布林） |
| 展開形 | 資料夾 | 物件 |
| 什麼時候長 | 內容太大、或一個檔扛不了那麼多職責 | 一個值不夠用、要帶別的屬性 |
| 原名 | 資料夾用原名（`x.md` → `x/`） | key 不變（`priority` 還是 `priority`） |
| 原內容去哪 | 入口檔：`x.md` 留原位（wf、proto8 的做法），或搬進去當 `README.md`／`inst.json` | 固定一個 key 裝原本那個純值（見下「`val`」） |
| README（導引、給人看） | `README.md` | `_notes`（`_` 開頭＝附註、宿主忽略，C-48 已定） |
| INDEX（結構） | `INDEX.md` | 物件的 key 本身就是目錄，不用另開；要說形狀用 `_schema`（同像性決定 6） |
| 往下長 | 資料夾內各檔再照同一套長 | 物件裡每個 key 的值再照同一套長（`timeout: 0` → `timeout: {"val": 0, …}`） |
| 讀的人 | 連結不斷（入口保留） | 兩形都收（純值＝只給了原值那一格） |
| 降級 | 子項消失就併回單檔 | 只剩原值那一格就縮回純值 |

## 拍板（10-15 晚）

使用者原文：「都按照推薦」（對本稿的 A～C 與命名盤點 P1～P7、M1～M9 一起回）。

- **選 A：原值一律 `val`**。已做：`priority` 的 `{"level"}` → `{"val"}`（lib gate、LLM kernel 的 `level()`、規則判官、kernel.md、demo kernel、測試）；fsm 格 `{"target", "next"}` → `{"val", "next"}`（`aos_methods.cell`、`aos_tree.slots`、N-36、fsm.md、agent-frame 說明、六張 demo fsm.json、測試）；think 連錯計數 `{"n", "error"}` → `{"val", "error"}`。ctl 本來就是 `val`。
- **共用 helper**：`aos_cli.expand(v, key="val")` 已加（物件照抄一份、純值包成 `{key: v}`、None 照回），ctl 的 `paused`／`stop`、gate 的 `priority`、think 的計數改用它；測試 `test_cli.test_expand`。
- **例外（AI 實作時發現，最小做法先過）**：fsm 的格不能直接 `expand`——格的「純值」本身可能就是物件（內嵌 inst），所以仍是「物件裡有 `val`＝展開形，沒有＝內嵌 inst」。內嵌 inst 不會有 `val` 這個 key，目前不衝突。
- **`_notes`**：照推薦固定叫 `_notes`，寫進 C-48 的例子。
- 落點：[C-48、C-55](../CONCEPTS/01-設計理念.md)、[N-36](../NORMS/07-基礎設施-組合子.md)。

## 未決（已拍板，見上）：JSON 那邊「原值放哪個 key」（AI 查現況，附推薦）

使用者例子用 **`val`**；C-48 現行沒定 key 名，現況三處三個名字：

| 地方 | 純形 | 展開形的原值 key | 誰定的 |
|---|---|---|---|
| ctl `paused`／`stop`（N-07） | 布林 | **`val`** | 使用者 10-12 |
| `priority`（lib gate `normalize_priority`、kernel `level()`） | `"low"`／數字 | **`level`** | AI 整理（[LLM kernel](2026-10-15-llm-kernel.md)），使用者「隨意」 |
| fsm 的格（N-36、`aos_methods.cell`） | TARGET 字串 | **`target`** | AI 推薦，使用者「照推薦」 |

選項：

- **A. 統一 `val`**：`priority` 的 `level` → `val`、格的 `target` → `val`（`{"val": "think.json", "next": "done"}`）。一次記住：看到物件就知道原值在 `val`；縮寫表已收 `val`。代價：改 lib gate／gate_kernel／kernel／judge_rules／methods／fsm、N-36、lib kernel 兩頁與 fsm.md、demo 幾張表、測試（約 20 檔，測試會抓）。
- **B. `val` 當預設，純值本來就有現成名字時可用那個名字**（`level`、`target`），各 lib 頁寫明。不動程式；但每處 key 名要各記一次，違反 C-54「記一次全體系通用」。
- **C. 統一 `val`，`priority` 另認 `level` 當同義**：多一條路，不推。

**推薦 A**：使用者自己兩個例子（10-12 的 ctl、今天的 priority）都用 `val`；C-54 的「一次記住」；現在是原型、改名成本一次付清。拍 A 就把三處改名併進 [命名盤點](2026-10-15-naming/盤點.md)的機械清單。

**讀值的程式**（兩種拍法都適用）：建議一個共用 helper 放 `aos_cli.py`（命令列程式共用部分）：`expand(v, key="val")`＝物件照抄、純值包成 `{key: v}`、`None` 照回；各程式一律先 `expand` 再只看自己認得的 key（C-48）。現況三處各自 `isinstance(…, dict)` 判一次，收成一個 helper 就是「兩邊同一套規則」在程式裡的樣子；型別檢查（ctl 要布林）仍各程式自己做。

**`_notes`**：C-48 已定 `_` 開頭＝附註、宿主程式忽略、給別人看（`_tool`、`_metainfo`、`_schema` 都是），所以 `_notes` 現在就合規、不用新規矩。要不要把「給人寫備註」固定叫 `_notes`（跟 `_metainfo`＝被叫者自報的特性分開）由使用者定；推薦固定 `_notes`，寫進 C-48 的例子。

**對命名盤點的影響**（已寫進盤點各條）：成長原則支持「同類多個→複數資料夾」那幾條（`brains/`、`gates/`、`judges/`、兩種 kernel 的 demo 併成 `kernels/llm/`、`kernels/general/`）與 frame 裡的窗分資料夾（`loop/state.json`、`fsm/state.json`）；`work/think-fails.json` 的 `{"n", "error"}` 正是「計數長成物件」，拍 A 就是 `{"val": 計數, "error"}`。
