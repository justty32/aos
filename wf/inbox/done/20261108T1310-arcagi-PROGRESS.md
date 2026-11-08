---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T13:10:59+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# arcagi 第四輪收輪：evaluation 37/400，同大小 8→13；附支線清單

# arcagi 第四輪收輪：evaluation 37/400（r03 32），同大小 8→13，退步 0

## 成績
- evaluation **37/400**、training **92/400**（r03 32／86）；兩個 split 退步 0、errors 0；同大小 evaluation 8→13/270。commit a825c65（求解器 9dcf110）。
- fable 驗收：同大小 ≥13 達到；evaluation ≥38 差 1；training ≥95 差 3；過 train 答錯 13（≤18 達到）。
- 論壇：開輪 p-20261108-124910-ac52、規劃 p-20261108-125124-091a（精華）、總結 p-20261108-131037-fa9e（精華）。

## 學到什麼
- 「每個物件各自規則」有效：evaluation 新解 5 題全靠它（換成碰到的物件色、朝最近物件移動／延伸）。
- 否定結果：只加大搜尋預算（節點 5 倍、秒數 4 倍）0 增量，out_of_budget 0/400；深度 4 在 training 100 題也 0 增量。瓶頸是參數候選太窄，不是算力 → 要吃 CPU 得放寬候選（C++ 支線適合）。
- 公式 2 層＋抽取特徵：live 24→35，本輪無新解。

## 用了哪些程式方法
- `src/arcagi/objrule/`：原語 recolor_from／move_from／extend_from，參數來源＝物件視角抽取積木（對每個物件各跑一次取值）；擬合＝train 物件對齊→每物件目標→找一致來源；防背答案物件 ≥3、參數值 ≥2 種。
- `blocks/pool/` 拆成套件；`budget.allocate()` 讓帳本的 generator_budget 真的決定三台產生器的候選數。
- `blocks/gen_meta.py`＋`aos/blocks/_gen/_meta/`：產生器的產生器（變異 gen_formula 設定、training 便宜評分、層數封頂 2）。
- `arcagi eval --workers N` 並行評測。

## aos 接了哪些
- 物件視角抽取積木落地在 `aos/blocks/extract_<hash>/`（body `scope:"object"`），被當動作參數來源時也分紅：`_gen/extract` 分紅 0→311.5。
- 帳本預算閉環：epoch 3 決定本輪 extract 5000／formula 11993／pred 8007 候選；epoch 4 重算為 42／33／26%。
- 真退休第一次觸發：40 個 covered 且連 3 epoch 0 收入的 pred_* 改 retired。
- `_gen/_meta`（`aos-exec --ws aos aos/blocks/_gen/_meta --dry-run`）。

## 「優化產生積木」進展
從「產生器產生積木、帳本記功」推到「帳本決定產生器預算＋一層產生器的產生器調設定」——元優化第一次閉環。

## 使用者三則新想法怎麼處理
- 12:52 支線：清單見下方，也存 `notes/rounds/支線.md`（連進交棒總表）。
- 12:56「整棵樹當搜尋對象、遞迴嵌套」：本輪小做一層 `_gen/_meta`（D-r4-7）；完整版列第五輪主軸。
- 13:09「呼叫鏈當原始碼、$ref、janet／lua／python、拉普拉斯變換」：本輪不做（施工已近尾聲），與 12:56 合併為第五輪主軸候選（D-r4-11）：積木 JSON ⇄ janet 雙向轉換、在原始碼空間改寫搜尋、_meta 擴三台改用帳本分紅評分、層數封頂 2。

## 代定（全文 notes/rounds/r04/代定清單.md）
D-r4-2 每物件規則做成原語、參數來源用抽取積木名；D-r4-4 評測並行；D-r4-6 預算單位＝候選數；D-r4-7 遞迴想法本輪只做一層；D-r4-8 `_gen/_*` 不分預算；D-r4-9 支線清單；D-r4-10 搜尋預算維持 10 萬節點／20 秒、深度 3；D-r4-11 13:09 想法併入第五輪。

## 下一輪打算
主軸＝上述合併（樹／呼叫鏈當可改寫的程式＋遞迴元優化）；另：每物件規則 2 步（換色後移動、斜向、形狀→色）、放寬參數候選。驗收建議 evaluation ≥42、同大小 ≥18。

## 可並行的支線清單
## 主線保留（支線不得寫）

`src/arcagi/{dsl,solvers,blocks,objrule,eval,experiments,tasks}/`、`src/arcagi/cli*.py`、`aos/blocks/`、`aos/pool/`、`aos/solver/`、`tests/` 既有子夾、`notes/rounds/r*/`、`reports/dsl-search-*`、`wf/`（hub 檔與 inbox）、`wf/workflows/experiments/ledger.json`（支線把 ledger 列寫在自己的報告，主線核後寫入）。

## 共用規矩

- 先讀 `AGENTS.md` → `wf/WORKFLOWS.md` → `wf/workflows/common/{user,conventions,code-map}.md`。純 stdlib、不新增 Python 依賴（C++／CUDA 另開資料夾、不進 Python 依賴）。
- 機器限制：`nice -n 19`、worker ≤12、單批 ≤16GB（`systemd-run --user --scope -p MemoryMax=16G`）、顯存 ≤12GB、swap 只有 512MB；**全量評測同一時間只准一條**——要跑全量先寄信給主線排時段。
- 成績以 evaluation 為準；產生／評分積木只用 training。commit 英文、只 add 自己路徑；被拒就 `pull --rebase`。

## 支線

| # | 目標 | 可寫路徑 | 驗收（數字） | 跟主線的介面 |
|---|---|---|---|---|
| S1 C++／CUDA 搜尋引擎 | 用同一套 JSON 程式格式重做枚舉器，深度 3→4～5、每題同樣 20 秒內走更多節點 | `native/`（原始碼、Makefile、`native/bin/` 被 gitignore）、`reports/native-*/`、`tests/native/` | evaluation：主線最新已解題**退步 0**、解題數 ≥ 主線＋3；每題 ≤20 秒；吐出的程式能被 Python `arcagi.dsl.program` 執行並在 train 全對（抽 50 題核） | 程式＝`[[原語名, 參數…], …]`（`src/arcagi/dsl/program.py`）；原語語意以 `src/arcagi/dsl/` 為準；接法 `arcagi eval --external 'native/bin/solve {input} {output} {trace}'`（`docs/solvers.md`、`docs/traces.md` 的 `arcagi-trace/1`）；積木清單讀 `aos/blocks/*/_metainfo.json`（只讀） |
| S2 aos-llm 接上（蒸餾第一步） | LLM 讀未解題寫四型 JSON（謂詞／抽取／公式／變換程式），程式驗 train，過的落成候選積木 | `src/arcagi/llm/`（新套件）、`aos/llm/`（提示、快取、候選）、`reports/llm-*/`、`tests/llm/` | 20 題 evaluation 未解題（主線指定清單）：記 train 通過率、test exact 題數、每題 token／秒；候選積木在 training 重評分 ≥1 個進 live（由主線產生器帳收） | 四型外殼 `{"kind":pred\|extract\|formula\|transform,"in","out","body"}`（S 式 JSON）；執行器 `arcagi.dsl.predicates`、`arcagi.dsl.extract.run`、`arcagi.dsl.formula.evaluate`、`arcagi.dsl.program`；候選以 `aos/llm/candidates/<hash>/_rule.json` 交主線，**不直接寫 `aos/blocks/`** |
| S3 每物件規則積木族 | 第四輪 A 線開的 `objrule` 之上加新的參數來源與動作族（鄰接、排序、相對位置、路徑） | `src/arcagi/objrule/families/`（新檔，第四輪收輪後劃出）、`tests/objrule/families/` | training 同大小未解題子集解題數（主線給清單）；evaluation 同大小 ≥ 主線＋2，退步 0（全量由主線排時段跑） | `objrule.OBJRULE_PRIMS` 的 Primitive 介面（`apply`、`candidates(states, targets)`）；註冊由主線在 `objrule/__init__.py` 加一行 import |
| S4 題型細分與失敗分析 | 800 題標題型與失敗原因，讓主線知道下一個池子在哪 | `docs/taxonomy/`、`scripts/taxonomy_*.py`、`reports/taxonomy-*/` | 800 題全標（`task_id,category,subcategory` CSV，`wf-table/1`）；對主線最新報告出每類解題率；未解題抽 50 題寫失敗原因 | `arcagi compare … --labels <csv>`（`src/arcagi/experiments/labels.py`）；讀 `artifacts/` 的 eval 報告與 traces |
| S5 合成題評分集 | 用 re-arc 生成 training 題的變體，給產生器評分防背答案 | `scripts/synth_*.py`、`data_synth/`（gitignore，靠指令重生）、`reports/synth-*/` | 每題 ≥20 個合成 pair、固定 seed 可重生；主線產生器換用合成集評分後 evaluation 不退步 | `src/arcagi/generation/`（只讀呼叫）；輸出官方 JSON 格式 |

- 優先序建議：S1、S2 先開（最能用到 aos 寬額度與 CPU／GPU），S4 隨時可開，S3 等第四輪收輪、S5 視 S2 進度。
- 支線回報：寄 arcagi inbox（`wf/inbox/`）`PROGRESS`，附指令、commit、輸出檔路徑；主線核數字後寫 ledger。
