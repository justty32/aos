---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T14:16:01+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# arcagi 第五輪收輪：evaluation 38/400、training 96，退步 0；S3 可開、S1 擴充點已開

# arcagi 第五輪收輪：evaluation 38/400（+1）、training 96（+4），退步 0

總結簡報：/home/lorkhan/repo/arcagi/notes/rounds/r05/04-總結簡報.md（代定清單同資料夾、跑分 reports/dsl-search-r05/README.md）。論壇 p-20261108-141541-b14e（精華）。

## 成績（白話）
- evaluation 37→38、同大小 13→14、training 92→96（槽積木收緊後 95）；過 train 答錯 eval 14／train 26（r04 13／24）。目標 40／42 沒達到。
- 支線 S1 native（主線先跑、C++ 補）evaluation 42/400，我核過輸出檔：對 r05 多 4 題、退步 0，ledger 已寫；它跑在本輪施工中的工作樹，r06 用最新 HEAD 重跑。S5 合成集 ledger 列也已寫。

## 學到什麼
- 在原始碼空間對「差一點就對」的程式做鄰域改寫（殘差補一步、換參數／原語／步驟），evaluation **0** 解、training 1～2 解。差的那一點多半是原語表達不了的結構——瓶頸是表達力，不是搜尋方式（r04「加深 0 增量」再往前推一步）。S1 的寬樹 +4 是同一結論的正面證據。
- 帶參數槽的子樹積木挖得到，但都是 BFS 本來搜得到的兩步組合；放進主搜尋還增加背答案（training 新增誤判 8 中 6 個）→ 只給改寫用。

## 程式方法
- `src/arcagi/srcspace/`：積木 JSON ⇄ janet 原始碼（844/844 往返、janet parse 全過）、`$ref` 折疊（照 N-45，catalog 會解）、子樹反合一 → `aos/blocks/m_sub_*`（kind slot_macro）。
- `solvers/rewrite*.py`：BFS 無解時的改寫搜尋（種子前景 IoU、殘差子題、≤8 秒）。
- `objrule/`：8 向、兩步、公式距離、同盤面圖例取色。

## aos 接了哪些
`$ref` 指示詞、子樹即積木（進 node-pool 帳）、呼叫鏈當原始碼（`python -m arcagi.srcspace`）、帳 epoch 5（真退休 59 個產生積木）。沒接：`_gen/_meta` 擴三台（延 r06）。

## 使用者想法進展
- 12:56「整棵樹當搜尋對象、遞迴嵌套」：本輪只做到子樹當積木；遞迴元優化（meta 調三台、帳分紅當分數）延 r06（Argon 也建議別砍，r06 首項）。
- 13:09「呼叫鏈當原始碼、$ref、janet、拉普拉斯變換」：變換與逆變換做出來且無損；在變換域做改寫搜尋本輪 0 增量（否定結果）。
- 13:13「子樹也是積木」：做成帶參數槽的 `m_sub_*`，進帳。

## Argon 意見
採納：種子改前景 IoU＋殘差子題、子樹反合一抽參數槽、不做跨對形狀死表＋兩步走殘差串接（部分）、門檻改法（eval ≥40 保底、同大小 ≥16、管新增誤判）。不採納本輪：E3 用 training 帳調 gen_extract（子 agent 已滿，列 r06 首項）。全文 notes/rounds/r05/02b-Argon審.md、代定 D-r5-6～10。

## 代定（摘要）
E3 延後；改寫引擎 Python、janet 只當表示；`$ref` 正本放 JSON；槽積木只給改寫用；改寫預設開（總耗時 ×3）；支線擴充點。全文 notes/rounds/r05/代定清單.md。

## 下一輪打算
E3 元優化正式做（`_gen/_meta` 先調 gen_extract，分數＝training 帳分紅＋合成集軟接，meta 另記帳）、吸收 S1 寬樹（物件原語不限第一步）、改寫只對高 IoU 題開；量法照 arknights 帶去清單（空基準重跑、兩條基準量雜訊）。

## 支線清單更新（notes/rounds/支線.md）
- **S3 可開**：寫 `src/arcagi/objrule/families/`（`FAMILY_PRIMS`，主線已一行接好）、`tests/objrule/families/`；清單 `notes/rounds/r05/S3-training-same-size-unsolved.txt`（training 同大小未解 216 題）。
- **S1 擴充點已開**：新原語 Python 版寫 `src/arcagi/dsl/ext/`（`EXT_PRIMS`，registry 已一行合併、內建名優先）、`tests/dsl/ext/`。
