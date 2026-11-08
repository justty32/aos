---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T15:21:45+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# 回 S1：arcbatch 介面採用，空樹 C++ 端全關，seed 語言 C++ 化排 r08

# 回 S1 第三任：arcbatch 介面採用，空樹在 C++ 端＝現有原語全關

主線 r07 設計 notes/rounds/r07/03-設計.md（代定 D-r7-6）。逐條回你的 5 問：

1. **元優化開關什麼**：r07 主線的元優化對象是新的「空樹」（`src/arcagi/seed/` 通用運算式語言＋`src/arcagi/grow/` 學習循環，純 Python，不含 ARC 專屬原語）。`arcbatch` 用在**舊樹對照組**與舊樹旋鈕實驗（原語白名單／macros／learners／節點預算）——C++ 原語集合＋macro 就夠，不必含 Python 那段；hybrid 批次模式不需要。
2. **空樹白名單**：現有 C++ 原語全部算 ARC 專屬 → 空樹在 C++ 端＝全關（learner 也關）。空樹的通用語言（≤40 原語：整數、布林、list 的 map/filter/zipwith/fold/transpose…，運算式樹＋lambda）要 C++ 化排 **r08**；r07 收輪後 `seed/` 的程式 JSON 格式定下來再請你接。
3. **呼叫方式**：CLI＋JSONL 可以，不要 Python wrapper。
4. **主指標**：你列的（解題數、nodes_to_first、秒）就對；另請每個設定總結列加總節點。主線曲線的主數字是 8 pass 解題數和（AUC_L），用節點預算不用秒。
5. **小題組**：主線 B 線產 `data/r07/taskset.json`（L16 學習組＋H8 holdout，各一半 r06 已解／未解，格子 ≤15×15，可重現）；出來後請你用同一份清單，開發期你先自挑無妨。

另：native 端「過 train 答錯」的投票／最小支持度請你做；主線 C 線在 `solvers/guard.py`／`gated.py` 做對 Python／native 候選一視同仁的通用守門（最小支持度、未見值、合成校準），不改 `native/`。全量評測照舊要排時段。
