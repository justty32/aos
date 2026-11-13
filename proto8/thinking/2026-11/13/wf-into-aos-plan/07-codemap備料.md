# 07 code map 備料：Q14「code map 要搬」給 fable 的唯一輸入（現況、兩支生成器、index 與知識庫 json 慣例）

← [回入口](../wf-into-aos-plan.md)｜上一份：[06-試驗紀錄](06-試驗紀錄.md)｜下一份：[08-fable-codemap規劃](08-fable-codemap規劃.md)

隊長唯讀查的（11-13 晚 21:55，家機，main `bfd40f05c`）。

## 使用者原話（逐字）

- 11-13 晚，對 Q14（code map 逐檔表要不要搬到 `wf/knowledge/`，推薦不搬）：「14.要搬，這個要特別用fable規劃，看aos json如何處理。」
- 同一則：「8.要改，要納入aos json體系。.csv應該可以不用了。」（鐵律 6 的同質表改走 aos json）
- 11-05：「逐檔表改生成」（code map 的逐檔表從檔頭一句話生成）。
- 11-12 晚：「.json比markdown好，有需要的話再做一些輔助工具和程式幫助人看json就好。」
- 11-13：「8kb上限可帶入(但只限.md)」——8 KB 是推薦值、只限 md、只在拆檔工作流時照做。
- 11-13：「index範圍按照11-12的門檻。」（一夾直接的東西超過 15 個才放 `_index.json`）

## code map 現況

- **手寫地圖** `wf/workflows/common/code-map.md`（4.9K）：一分鐘看懂（proto8 各頂層夾是什麼、impls 依賴鏈一句）、逐檔表在生成冊、檔頭一句話寫在哪、常查表、真相層優先序。被 `AGENTS.md`「碰原始碼前」直接指；`common/conventions.md` 被 34 個檔連入、`code-map.md` 也有不少連入。
- **生成冊** `wf/workflows/common/code-map/proto8/*.md`（252K、31 冊＋README＋一份 `_index.json`）：一個 proto8 頂層夾一冊（`lib.md`、`impls.md`…），超過約 7.6K 就按第二層夾切成 `lib-2.md`…`impls-9.md`。每冊開頭 generated 標記、導航行，然後每個夾一張 md 表 `| 檔（相對連結） | 負責什麼 |`；impls 冊開頭有依賴表（從各 CMakeLists 的 `target_link_libraries`）。
- **維護鏈**（`common/conventions/02`）：修改前先讀地圖→生成冊；檔頭一句話是來源；commit 前跑 `python3 wf/tools/codemap_gen.py --apply`（**鐵律 3**，AGENTS.md 寫死這條指令）；生成冊不手改；原始碼不加「對應 code map」註釋。
- 通用版 `proto8/knowledge/wf/knowledge/code-map-rules.json`：真相層優先序、維護鏈；專案自己的「領域表與優先序」放工作區 `wf/knowledge/code-map.json`（骨架 `wf/skeletons/code-map.json`）。通用版講的是**手寫領域表**，沒有逐檔生成表這件事。

## 兩支生成器

- **`wf/tools/codemap_gen.py`**（379 行）：掃 `git ls-files proto8`，去掉 thinking／archive／notes／user-advice／docs、`.md`（knowledge 除外）、`_index.json`；讀檔頭一句（C/C++ 第一行註解、腳本跳 shebang 後第一行註解或 docstring、CMake 第一行註解、JSON 取 `description`／`summary`／`$comment`／`title`、`_entry` 印「入口：argv」、knowledge 的 md 取標題）；工具夾三個契約檔併成一列；寫冊到 `wf/workflows/common/code-map/proto8/`；不帶 `--apply`＝檢查（不一致退 1，印 `CodemapStale`）；一句話空只 warning（現在 43 條 warning，多是 knowledge json 沒有 description 鍵）。
- **`wf/tools/index_gen.py`**（296 行＋`index_gen.json` 範圍＋`index_gen_desc.json` 168K 手寫一句話）：替範圍內「直接的東西超過 15 個」的夾生成 `_index.json`（`{名: {"description": 一句, "index": "子夾/_index.json"}}`）；**範圍已含程式區**：stage 2 有 `proto8/lib`、`cmd`、`py`、`impls`、`extras`、`cases`、`feedback`（deep）、`templates`（頂層）；**程式檔的一句話「照 codemap_gen 的認法」**（同一個檔頭來源）；不帶 `--apply`＝檢查。手寫不生成的 index 登記在 `hand_indexes`（knowledge 那棵樹手寫）。`index_check.py` 查 `_index.json` 跟實際樹對不對得上。
- 現有程式區 index 例：`proto8/lib/_index.json`＝`{"README.md": {...}, "agent": {"description": "高層工具：…", "index": "agent/_index.json"}, …}`；33 份 index、791 格。
- 所以**同一份「檔頭一句話」現在被兩支各讀一次、各寫一種東西**：codemap_gen 寫 md 冊（每夾都列、跨夾一冊），index_gen 寫 `_index.json`（只到超過 15 個的夾、就放在那個夾裡）。

## index 與知識庫 json 的慣例（出處 `proto8/knowledge/docs/01`、`02`）

- `_index.json`：一夾一份，`{名: {"description": 一句, "index": 子 index 路徑（選填）}}`；一格可塞別的鍵（`index_view` 只讀 description 與 index）；description 可是字串或字串陣列。`index` 只能指另一份 index。門檻 15。
- `$ref`／`index` 路徑規則 11-13 晚剛改（線址 `d980a950b`、`cbadd29a2`：`#` 左邊一律檔案系統、右邊一律 json；兩者規則相同）。
- 知識庫節點：一檔建議約 8 KB、一段約 1 KB（推薦、不訂死）；同質記錄「只整批讀、不單筆引用」的可以用陣列，會被單獨引用的用鍵；拆檔留 `{"$ref": "新檔.json"}`。
- 人讀 json：`index_view`（鍵 TAB 一句）、`json_get`／`json_ls --depth`、`aos-json get/ls/search`；repo 有 `wf/tools/json_text*`（git textconv，讓 diff 看得懂 json）。
- 使用者這次也裁了：SESSION-LOG 單條化成 json；鐵律 6 的同質表改走 aos json、不再用 `.csv`；工作流規矩轉 json 節點放 `wf/workflows/`、`wf/knowledge/`。

## 限制

- `codemap_gen.py`、`index_gen.py` 在 `wf/tools/`，本線可改；`proto8/lib`、`py`、`cmd`、`impls` 另有線在改，本線不碰。
- 生成物要跟程式同一個 commit（鐵律 3），任何線改程式都得跑一次。
