# 腳手架第一版藍圖（scaffold1）：選單包＋學徒做工具的 A／B

← [意圖卡](intents/scaffold.md)｜起因 [apprentice-4](play/2026-10-09-real-ai/apprentice-4.md)｜錯誤 [blueprint-errors](blueprint-errors.md)｜分線 [teams.json](blueprint-scaffold1-teams.json)。Fable 10-09 晚。

**白話三行**：做一個「選單」小包：人寫一棵選擇樹，AI 每次只看一層、只回一個編號（頂多再填一格），走到葉子才由專用工具真做事。先用在「學徒寫 aos 工具」：同一個笨模型 luna，一次交整包 vs 一層一層交，看通過率差多少。數字事先寫死，達標才往別處推。

## 1. 一句話

新包 `packs/menu/`：**純函式走樹**（`step(menu, state, reply)`）＋**llmcall 驅動**＋**工具目錄**（葉子只叫登記過的專用工具，不給 shell）＋一棵「aos-tool 學徒」選單。核心零改動；author／up／skills／kernel 程式不碰。

## 2. 第一個套用：學徒做工具

- 為什麼先這裡：目標 3 唯一可量的地方；AP4 有同模型同三題的基線；AP5 的文字格式正好當「沒腳手架」的 A 組。
- 走法（B 組）：層「下一個交哪個檔」（README／入口／主程式／測試／交齊了／寫不出來）→ 層「寫出全文」（格子；本機檢查：≤8192 bytes、README 章節、入口 ≤12 行）→ 回上層… → 層「索引一列」→ 層「REPORT」→ 葉子工具：組成 AP5 文字、跑 `aos7-gates check` → 過＝做完；沒過＝層「改哪個檔」（只附那關 issues ≤600 字＋檔名選項＋放棄）→ 回「寫出全文」。三關最多 5 輪。
- AI 每步只看到：需求摘要（≤1500 字）、已交的檔名、這層的問題與選項；**已交的檔內容不重附**（改檔時才附那檔）。

## 3. 資料格式、放哪、指令

選單 `menu.json`（每層 2～5 個選項、必有出口；超過或缺出口＝選單錯、退 2）：

```json
{"v":1,"name":"aos-tool","start":"which",
 "layers":{
  "which":{"ask":"下一個交哪個檔？","options":[
    {"text":"README.md","next":"write","set":{"file":"README.md"}},
    {"text":"bin/aos7-{name}","next":"write","set":{"file":"bin/aos7-{name}"}},
    {"text":"aos7_{name}.py","next":"write","set":{"file":"aos7_{name}.py"}},
    {"text":"tests/test_{name}.py","next":"write","set":{"file":"tests/test_{name}.py"}},
    {"text":"都交齊了","next":"row","when":"required_done"}],
   "exit":{"text":"寫不出來，要你決定"}},
  "write":{"ask":"寫出 {file} 的全文","slot":{"max_bytes":8192,"sections":["## 第一次跑"]},
   "do":{"write":"out/{file}"},"next":"which"},
  "row":{"ask":"索引一列","slot":{"prefix":"| `packs/{name}/` |","max_lines":1},"do":{"write":"out/row"},"next":"report"},
  "report":{"…同 row，next":"gates"},
  "gates":{"do":{"tool":"aos-tool-gates","args":{"run":"{run}"}},"ok":"end","fail":"fix"},
  "fix":{"ask":"沒過：{issues}。改哪個檔？","options":"files_done","next":"write"}}}
```

- AI 回法（凍結）：第一行 `選：N`；有格子時第二行起 `格：` 之後到結尾是內容（原樣、不加圍欄）。不合＝一行提醒重問同層；第 3 次不合＝停下（退 1）。出口固定是最後一個編號。
- 狀態 `<node>/menu/<run>/state.json`：`{"v","menu_sha","layer","vars","done":[檔],"tries","calls":[{"layer","call_id","rc"}],"gate_rounds"}`，一次 rename；**先存 state 再呼叫 AI**，call_id＝`menu/<run>/<層>/<第幾次>`，被殺重跑同 id 不重問。`log.jsonl` 每步一行；`out/` 是葉子寫出的東西。
- 格子檢查五種：`max_bytes`、`max_lines`、`prefix`、`sections`（行首必要章節）、`tool`（暫存檔給工具，退 0 過、stderr 一行當錯）。`do` 只有 `write`（寫 out/ 內）與 `tool`。**沒有 shell**：`tool` 只能是目錄 `packs/menu/tools.json` 登記的名字：`{"aos-tool-gates":{"argv":["python3","examples/aos-tool/build.py","{run}"],"args":["run"],"out":"json-line"}}`；argv 不經 shell、只填模板、輸出一行 JSON 或退出碼。既有指令（aos7-gates、aos7-skills、aos7-ctl…）直接登記不改碼。AI 看不到目錄，只看到該層選項。
- 放哪：`packs/menu/`（aos7_menu.py 純函式＋檢查、aos7_menu_run.py 驅動、bin/、tools.json、spec.md、tests/）；學徒選單 `examples/aos-tool/`（menu.json、build.py）；玩具選單 `examples/hello/`（三層、練習用的 AI 可走、不花錢）。
- 對外指令 2 個：`aos7-menu run <node> <menu.json> [--llm MODEL | --reply FILE]`（不給 `--llm`＝練習用的 AI；`--reply` 只走一步，給測試與人手走）、`aos7-menu status <node>` 一行白話。

## 4. 驗證：A／B，門檻先寫死

- 模型：學徒 `chatgpt-gpt-6-luna`（同 AP4）；審查 `gpt-6-astra-high`；全走 llmcall。三題＝AP4 的 gap／runs／audit，每組每題 5 次。
- A 組：`aos7-author propose --format text`（AP5 一次交整包，最多 6 輪）。B 組：`aos7-menu run … examples/aos-tool/menu.json`（三關最多 5 輪）。「過」＝三關含審查都過，不發布。
- 基線（AP4 luna A）：題 1 1/5、題 2＋3 7/10；格式型被擋 81/151 輪；每次三題 166k token。
- **成功＝三條都達**：①通過率 B 三題合計 ≥ A＋4（15 次），且題 1 B ≥ 3/5；②格式型被擋（段頭／schema／json／size）B ≤ A 的 1/3；③B 每次三題總 token ≤ A ×1.3。達 ①② 不達 ③＝「有訊號，再各跑 5 次」；其餘＝機制收下、不往 brain 推。另記：每題時間（B 預期 ≤ A ×2）、呼叫次數、每步 token。
- 上限：真 AI ≤300 次、≤250 萬 token（AP4：297 次／279 萬）。

## 5. 跟 AP5 怎麼銜接、不撞領地

- AP5 在改 `packs/author/`（文字格式、mail 四題、第二次自我改進實驗）。本藍圖**不碰 `packs/author/` 任何檔**：B 組的葉子工具把 out/ 組成 AP5 凍結的 `=== 路徑 ===` 文字再叫 `aos7-gates check`；A 組直接用 AP5 的 `propose --format text`。
- MN1 現在就能開，與 AP5 零交集。MN2、MN3 **等 AP5 進 main 再開**；段頭格式有變只改 build.py。I2 已進 main，索引列由 MN4 補。

## 6. 錯誤與人類面

退出碼照 blueprint-errors：0 做完／1 停下（3 次不像、三關到上限、AI 選出口）／2 你給的不對（選單檔：>5 選項、缺出口、next 指不到、工具沒登記；參數）／3 不確定（llmcall 未確定、state 故障；再跑接續）。stderr 一行「aos7-menu: 發生什麼。怎麼辦」。README 三行頭＋第一次跑（hello、練習用的 AI、≤5 分鐘、不花錢、2 指令、4 概念）；其餘在 ADVANCED。QUICKSTART 不動。

## 7. 分線（細節在 json）

| 線 | 波 | 領地（皆 `packs/menu/`） | done |
|---|---|---|---|
| MN1 核心 | 1（現在） | aos7_menu*.py、bin/、tools.json、spec.md、tests/、examples/hello/ | 純函式單測；選單錯退 2；3 次不像退 1；SIGKILL ×3 不重問；hello 10/10 |
| MN4 文件＋新手 | 2（MN1 後） | README、ADVANCED、索引各一列、code map | Haiku／luna ≥7、2 指令 ≤4 概念 |
| MN2 學徒選單 | 2（MN1＋AP5 後） | examples/aos-tool/、tests/test_menu_aos.py | 整圈過；luna 3 次 ≥1 次全過、≤40 次呼叫 |
| MN3 A／B | 3（MN2 後） | notes/play/…/scaffold-1.md＋evidence/ | §4 三條燈號；每組每題 5 次；花費表 |

## 8. 不做（本輪）與下一步候選

不做：AI 寫選單、自由文字層、`cmd`／shell 動詞、自動升級模型、brain 改走選單、多 node、改 author。
達標後（順序照意圖卡盤點表）：①需求單 `tools` 欄改工具名；②brain「停在哪」選項化、四選一改選單格式；③skills 三本書各附選單＋葉子工具；④「aos 改東西」導航樹（1 新工具 2 新模組 3 改文件 4 回信 5 都不是）當目標 3 入口；⑤強模型替弱模型搭樹。待續：工具目錄要不要併進 modules/tools。

## 9. 代定預設（使用者可翻）

選單人寫｜3 次不像就停、不升級｜brain 碼不動｜門檻照 §4｜題目沿用 AP4 三題。
