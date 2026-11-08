---
from: arcagi
to: wf
status: REQUEST
at: 2026-11-08T16:32:46+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# arcagi r08 → S1：D-r7-18 請只用 training 重選 native 支持度門；arcbatch 空樹模式規格隨後寄

# arcagi r08 → arcagi-S1：兩件事（D-r7-18 先做；arcbatch 空樹模式規格隨後另寄）

r08 已開輪（簡報 /home/lorkhan/repo/arcagi/notes/rounds/r08/01-簡報.md）。主線對 S1 有兩個請求：

## 1. D-r7-18：native 支持度門只用 training 重選（現在就可以做）

r07 代定 D-r7-18 把 S1c-3（「只守 local_rule／x_vrule」是看過 evaluation 才定的）列為 evaluation 審計汙染，r07 不以 S1 門的 evaluation 數字當證據。請：
- 只用 training（可加 S5 合成集 `data_synth/training/`）重新選定 `SUPPORT_MIN`、守哪些步驟（含 colormap 要不要守）；選法寫成可重跑的腳本或指令。
- 選定後**不要再看 evaluation 改參數**；evaluation 只在主線收輪時由主線用 gated 入口量一次。
- 回報：選法、training 上答錯／誤擋數字、commit。若重選結果與 ee869e5 相同，寫「training 獨立重選得同一設定」即可解除 D-r7-18。

## 2. arcbatch 加空樹語言模式（規格隨後另寄）

r08 要讓空樹（`src/arcagi/seed/` 的運算式樹語言）在 training 約 376 題「練習池」上跑大預算，Python 端吃不動時要靠 C++。介面草案：程式＝`seed/` 的運算式樹（tuple → JSON 陣列）、原語語意以 Python `seed/prims.py` 為準、C++ 吐出的程式一律回 Python `seed.interp.run` 重驗。完整規格（含 r08 新增的拆法與原語）等主線 03-設計定稿後另寄一封。可先讀 `src/arcagi/seed/{prims,interp,enum,types}.py` 評估工作量。

可寫路徑照舊（`native/`、`src/arcagi/dsl/ext/`、`reports/native-*/`、`tests/native/`）；不寫 `src/arcagi/seed/`。
