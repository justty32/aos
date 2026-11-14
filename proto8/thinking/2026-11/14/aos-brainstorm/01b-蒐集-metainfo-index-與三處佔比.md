# 蒐集事實：`_metainfo` 與 `_index` 都是「約定、非強制、看不懂就忽略」，資料夾與 json 同像是條文、lua 只在 `cal/lua/py/aos` 公式 key 的預留，沒有任何現成 lua 執行支援

← [README](README.md)

只記事實與出處，不提建議。路徑縮寫：D＝proto8/docs，T＝proto8/thinking，L＝proto8/lib。

## 1. `_metainfo`

- **約定的來歷**：C-42b 說 inst 單子可多放九軸、traits、工具等，「這個抽屜叫 `_metainfo`」（D/CONCEPTS/03-基礎設施/01-inst至fsm.md）。abbr 條：「單子裡給 kernel 參考的抽屜…10-23 晚起 `_` 開頭不再表附註，`_metainfo` 是普通 key、不認得的程式照 C-48 忽略」（D/CONCEPTS/abbr.json:148）。
- **11-12 定的「只是約定」**：使用者原話「_metainfo這東西，他就是只活在概念與規範中，我們目前是不做單一程式去處理的，我們就是定下來，啊其他工具要不要支援，就看他們自己」（T/2026-11/12/metainfo/README.md「使用者原文」）。另一句：「我們就是開了metainfo這個口子，要用不用都可以」；`_entry` 不能搬進去。
- **裡外都讀、外面贏**：使用者「如果_metainfo內有tooldef，外面也有獨立出來的_tooldef，那就兩者合併，外面獨立出來的會覆蓋掉_metainfo內的」。合併規則「一層、同名整個換、外面贏」（T/2026-11/12/metainfo/README.md:63）；排成一線「`_metainfo` 裡的 < 獨立那份 < 讀者指定的」（T/2026-11/12/metainfo-views.md:130）。條文落在 N-69（D/NORMS/10-基礎設施-定義與工作區/11-N-69.md）。
- **壞了不擋**：「metadata is a point of view, not a rule: anything broken counts as not written」（L/metainfo.py 檔頭）；N-68「寫壞了＝當沒寫」；使用者裁定「`_metainfo.json` 壞掉時，index_view 對那個資料夾不該直接報錯」（cmd/aos-tools/bin/aos-tools:365）。
- **description 先不寫進**：「description 寫進 _metainfo <- 先不寫入。只有{}的_metainfo.json也算agent定義。」（T/2026-11/12/metainfo/README.md）。
- **能裝的格**（N-69／metainfo README）：`tooldef`、`index`、`cost`、`timeout_ms`、九軸、`comfort` 等；`_metainfo` 也可內嵌在 json 檔或 `檔.json#/指標` 物件裡的 `_metainfo` 鍵（C-72、D/CONCEPTS/01-設計理念/05-續-C-55-函數成長.md:21）。長成資料夾後讀資料夾的人只看 `_metainfo.json`（同檔:20）。`_metainfo` 不加狀態欄、實測不回寫（D/CONCEPTS/05-agent/05-C-89-不同質與族譜.md:11）。
- **L/metainfo.py（168 行）函式**：`read(def_dir, notes=None)`（讀資料夾的 `_metainfo.json`、json 內嵌 `_metainfo`、或 `檔.json#/指標`；沒檔＝None，壞＝None＋一句英文 note）、`timeout_ms(meta, notes)`、`eval_cost(value, vars, notes)`；內部 `_walk`（JSON Pointer）、`_calculate`（ast 白名單算 `cal`）。`eval_cost` 目前只認純數、`{"val":…}`、`{"cal":…}`；不認得的求值器＝None（metainfo.py:146-165）。
- **欄位長相**（實檔 proto8/templates/tool-python/_metainfo.json）：
  ```
  {"summary": "...", "resource": "cpu", "side_effect": false, "idempotent": true,
   "deterministic": true, "interrupt": "safe", "parallel": true, "arbitrary_exec": false,
   "cost": {"time_ms": 100}, "timeout_ms": 10000}
  ```
  九軸＝C-13（D/CONCEPTS/04-kernel.md:9）：副作用、冪等、碰外部檔案、持續性、有無 entry、確定性…；實檔上的鍵是 `side_effect`／`idempotent`／`deterministic`／`interrupt`（`safe`／`resumable`…）／`parallel`／`arbitrary_exec`。`resource` 可為字串或陣列（agent-fsm 範本：`"resource": ["llm"]`，`"cost": {"time_ms": 30000}`，只有 3 欄）。
- **N-68 的 cost**：三維 `token`（`in`/`out`/`cached`）、`counter_calls`、`time_ms`；「cost 裡還想放什麼就放…不認得的 key 照 C-48 忽略」；`cost.time_ms`＝估時不強制，頂層 `timeout_ms`＝逾時才殺（D/NORMS/10-基礎設施-定義與工作區/10-N-68.md）。另有 `comfort`（AI 工學舒適度）。
- **數量**（find，排除 .git）：repo 裡 **86** 份 `_metainfo.json`（lib/base 31、lib/agent 24、lib/aos 21、templates 5、archive 5）；~/aos-home 裡 87 份（含 repo 連結／同步，未細查）。
- 短例二（proto8/lib/aos/jsonx_ls/_metainfo.json）：`{"summary":"Like json_ls, with $ref/$env options…","resource":"disk","side_effect":false,"idempotent":true,"deterministic":true,"interrupt":"safe","parallel":true,"cost":{"time_ms":30},"timeout_ms":3000}`。

## 2. `_index`

- **格式**：資料夾放 `_index.json`、json 物件裡放 `_index` 鍵；形狀 `{名: {"description": …, "index"?: 路徑}}`；一項裡可多塞別的鍵、`index_view` 只讀 `description` 與 `index`（D/CONCEPTS/05-agent/04-C-88-記憶與index.md:8）。例（T/2026-11/12/_index.json）：`"codebase-cleanup": {"description": "11-12 晚程式碼庫整理（fable 領隊）：…"}`。
- **index_view**（L/base/index_view/_tooldef.json）：輸出首行 `[index] WHERE, N entries`，之後一行一項 `KEY<TAB>description`，有 `index` 時多第三欄 `index: PATH`；`index` 欄不跟著往下走，要讀就再叫一次 `{"index": PATH}`；指定的 index 疊在天然那份上、同名以指定為準；天然位置＝被描述節點的上一層（C-88 同檔）。
- **三層疊法**：`_metainfo` 裡的 `index` < 獨立 `_index` < 指定的（T/2026-11/12/metainfo/04-題與代定.md:27）。
- **index 是「視角」不是事實**：「index的用途…就是一個透鏡」；客觀用 `ls`／`json_ls`（C-88）。
- **知識庫片段**（~/aos-home/knowledge/aos/_index.json）：`"me.json": {"description": "Finding your own name, what is in your stack, and what you are allowed to change."}`、`"me": {"description": "Long sections of aos/me.json kept as their own files …"}`。
- **數量**：repo 36 份 `_index.json`；~/aos-home 9 份。
- **門檻**：「資料夾超過 15 個東西（`_index.json` 自己不算）才放；json 檔超過 8000 bytes 或頂層內容鍵超過 10 個才放」＝代定可翻案（T/2026-11/12/knowledge-removal.md:31；C-88:11；wf/tools/index_gen.py 檔頭「超過設定檔 more_than」，使用者 11-13「index範圍按照11-12的門檻」）。使用者原話：「如果有些東西太大，那就補index.json/_index。如果夠小，那其實也不用做看法了，直接讀就是了。」
- **index_gen.py**（/home/lorkhan/repo/aos/wf/tools/index_gen.py）：只讀檔頭不跑程式；`--apply` 才寫；一句話取法：md 第一個標題（分檔取「涵蓋：…」）、夾取 README.md／INDEX.md（工具夾取 `_tooldef.json`／`_metainfo.json` 的 summary）、json 取 `description`／`summary`／`$comment`／`title`；取不到＝`DescMissing` 退 1；手寫例外放 index_gen_desc.json；同時生 wf/knowledge/code-map/proto8/<夾>.json。
- 使用者 11-12：index「也可以寫進 `_metainfo`…`_metainfo` 本身不算 index」；改 index「直接用 json 工具」。

## 3. 值的雙形與 N-68 語言 key

- **C-48「值的雙形」**：「一個值除了字面純值，也可以寫成物件（展開形），像 Lisp 的 `3` 與 `(+ 1 2)`（例：`priority` 寫 `"low"` 或 `{"val","deadline"}`；展開形的原值推薦用 `val`…實作麻煩就權衡，太麻煩的地方可以不支援物件形）」（D/CONCEPTS/01-設計理念/01-C-01～C-48.md:11）。C-55 講成長：純值不夠用就長成物件、原值放進固定一格 `val`、「只剩原值那一格」可縮回（D/CONCEPTS/01-設計理念/05-布局成長與檔案權限.md:5）。
- **N-68 語言 key**：「公式用語言名當 key」；使用者 11-07 原話：「直接寫"lua":"...."或"py":"..."，然後呼叫相應lua.exe/python.exe(這臺是linux，沒有)。或是直接跑aos函數。初期可以用簡單的四則+min/max。其實沒啥規定，就是隨着複雜度增加，可以替換到所需技術棧。搞不好到後面，就是呼叫aos　agent」。例：`{"cal":"4000 + in_bytes * 1.2"}`、`{"lua":"..."}`、`{"py":"..."}`、`{"aos":"<aos 函數路徑>"}`（stdin 給變數、stdout 印數字）；同一格只寫一種；「現在只實作 `cal`；`lua`／`py`／`aos` 等用到再接」；aos-exec 與指示詞不碰這些 key；讀者沒有求值器＝當沒估值、不報錯（10-N-68.md）。

## 4. 檔案系統與 json 同像

- **C-51／C-55**：「資料夾／檔案與 JSON 物件有同像性（C-51），所以長大的規則同一套」（C-55，05-布局成長與檔案權限.md:5）；C-76 把「與檔案系統的同像性」列為選 JSON 的五個好處之一（D/CONCEPTS/01-設計理念/08-C-76～C-78.md:5）。
- **C-68／C-71／C-72**：使用者 10-19「純粹把資料夾作為lisp的list或lua的table，然後有一個entry」；C-71 後來定「比喻用 lua 的 table、不用 lisp 的 list」；`agent-bob/_entry` ⇄ `js["_entry"]` 同名兩處都用（N-57，D/NORMS/10-基礎設施-定義與工作區/01-N-57.md）。能力三樣（`_entry`、`_metainfo`、`_tooldef`）可是資料夾檔，也可是同一份 JSON 或 `檔.json#/指標` 的三個鍵（C-55 續:21）。
- **路徑規則**（T/2026-11/13/ref-path-rules.md，使用者 11-13 晚）：`#` 左邊一律檔案系統、右邊一律 json 內部；`#/a`＝根的 a、`#./b`＝所在物件的 b、`#../c`＝上一層的 c；`./zzz.json`、`../xxx.json` 是檔案；`yyy.json#/kkk` 是該檔的 key；`yyy.json#./`、`#../`、`#aaa`、`yyy.json#aaa` 都報錯；`$at` 刪掉；`$ref` 與 index 路徑同一套規則、同一支解析函式（Python `aos_refpath.spot`、C++ `aos::ref_spot`，同跑 lib/tests/ref_path_cases.json）。
- **`$ref` 也能讓一格換成別的檔**：`{"$ref": ["a.json","b.json#/c/d"]}` 多份合成（C-48 文、N-45）。
- **json 工具跨資料夾**：`json_ls`／`json_get` 等（L/base/json_*）的 `path` 說明寫的是 `FILE#/POINTER`（檔，加 json 內指標）；`jsonx_*`（L/aos/jsonx_*）是同樣加 `follow`（走過 `$ref`）、`resolve`（列出解開 `$ref`／`$env` 後的值）。工具說明沒寫能把資料夾當節點往下走；這點未實測，不下斷言。資料夾端用 `ls`，index_view 則可吃資料夾與 json 兩種（C-88）。

## 5. lisp／lua／plan9／fennel 出現處（grep -ril 全部命中，挑 15）

1. D/CONCEPTS/01-設計理念/06-C-68～C-72.md:7：C-68「資料夾＝程式」，「純粹把資料夾作為lisp的list或lua的table，然後有一個entry，在lisp就是第一個元素，在lua就是metatable裡面定義的…」。
2. 01-C-01～C-48.md C-43：最終效果「一套 library，寫完編譯成基於 aos 的類 LISP 程式，把 aos 當作業系統跑」。
3. 同檔 C-48：值的雙形「像 Lisp 的 `3` 與 `(+ 1 2)`」。
4. D/CONCEPTS/03-基礎設施/01-inst至fsm.md:30：使用者 10-19「算元素？由entry指定，你看，lisp的quote就是那個功能」。
5. D/CONCEPTS/附錄3-條號表/01-條號-檔.md:50：C-71 資料夾比喻用 lua table、不用 lisp list。
6. D/CONCEPTS/05-agent/01-腦-工具-可預測性與agent函數binding.md:20：「我們現在就是把 JSON＋資料夾當 Lisp 的 list，這就是一個函數啊，何必再造一個體系？」
7. D/CONCEPTS/02-設計理念-時空.md:10；T/2026-11/05/fs-image/README.md:15：資料夾停住像 lisp 的 image。
8. T/2026-11/05/portable-flow/README.md:17：使用者「lisp可以做image…daemon就像是硬體，各stack就是各程序所佔據的記憶體」。
9. D/CONCEPTS/附錄1-名詞.md:17：空間「資料庫、硬碟、快取、記憶體、雲端這類外部設備也可以納入空間（像 Plan 9）」。
10. D/NORMS/05-基礎設施-窗/03-N-13～N-14.md:5：state／ctl 外顯的檔「像 Plan 9／FUSE」。
11. D/NORMS/10-基礎設施-定義與工作區/10-N-68.md：公式 key `lua`／`py`／`aos`（見 §3）。
12. D/NORMS/10-基礎設施-定義與工作區/01-N-57.md：使用者 10-19 lisp list／lua table 原話。
13. T/2026-11/04/four-elements/05-原則打架與方向題.md:24：舊的「aos-lua 用 `os.execute` 拼字串跑 mkdir／chmod」（早期 Lua 實作的遺跡）。
14. T/2026-11/07/lift-to-norms/04-打架.md、T/2026-11/07/kb-ideas/README.md、T/2026-11/07/evolve-design/README.md：N-68 公式 key 的討論。
15. T/2026-11/10/self-family/hook/01-圖紙.md:14：引 lisp list／lua table 原話。
- 未見命中 fennel（實際命中檔裡未見獨立討論）。

## 6. 現有 lua 執行支援

- 在 proto8/impls、lib、cmd 中 grep `lua` 沒有任何程式碼命中，只有文件。aos-exec 入口四種：可執行檔（含 shebang 檔）、inst 單子、argv 陣列、`js[$AOS_ENTRY]` 的值（單子、陣列、字串路徑）（C-73／N-61，N-57）。aos-exec 本身**不選直譯器**：入口是可執行檔就 exec，是 argv 就起那條命令；要跑 lua 只能寫成 shebang 檔或 argv `["lua","x.lua"]`（aos-exec README 範例是 `{"argv":["cat"]}`）。
- metainfo 公式求值只實作 `cal`（`lib/metainfo.py:163`）。
- 本機環境有 /usr/bin/lua、/usr/bin/luajit、/usr/bin/fennel（`which` 查到）。

## 7. 規模事實（T/2026-11/13/any-resource-os/01d-蒐集-規模.md，只從程式推、沒跑）

- llm kernel 是 C++（aos-llm-kernel），一輪＝一次行程，daemon 每 300 ms 起一次（`interval_ms: 300`）；狀態全在檔案、每輪重讀；不是事件驅動，信最多晚 300 ms 被看到。
- 端點同時處理數＝kernel 的 slots（總格＋每包格＋保留 high 格），放行側夠用；撐不住的是「等待的信很多」與「agent 端每隻都在輪詢」。
- 每輪對 new/ 全 readdir＋每封整份 letter.json 解析，成本 ≈ 等待信數×每封大小；等待沒有上限、無每人上限；排序近似全域 FIFO＋aging。
- 每個放行請求＝起一個 aos-loop proc＋aos-exec＋一支 Python；同時只有 slots 個。
- agent 端每拍（300 ms）起新 Python 行程，idle 也輪詢；粗估 1000 隻＝30～80 核輪詢負載、100 隻＝3～8 核（無量測）。
- 現有量測只有 daemon 層（edge-round2：3000 封信、200 loop、4300 列表）；llm kernel 的大量等待壓測沒找到；使用者 11-08 自己說「LLM endpoint 同時間只能處理十幾個請求」，上千的是無 LLM 的函數節點。

## 8. 「三處邏輯佔比」相關的現成字句（供腦力激盪）

- C-55：能力階段長 ①資料夾＋`_entry.json`＋小腳本 ②補 `_metainfo.json` ③補 `_tooldef.json`；三樣也可同一份 JSON 內的三個鍵（05-續-C-55-函數成長.md:21）。
- N-68 公式 key 換求值器、格式不變（「隨着複雜度增加，可以替換到所需技術棧」）：這是目前文件裡「邏輯從 json 數值→cal→lua/py→aos 函數」逐級搬位的唯一條文。
