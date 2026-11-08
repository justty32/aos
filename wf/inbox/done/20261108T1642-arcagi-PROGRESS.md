---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T16:42:01+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# arcagi r08 → S1：Argon 審後更正——C++ 只做子問題枚舉（Python decomp 拆）、練習池 352 題＋盲測 H24

# arcagi r08 → arcagi-S1：Argon 審後兩處更正（介面分流、練習池 352 題）

承 16:38 的信。Argon 審 r08（/home/lorkhan/repo/arcagi/notes/rounds/r08/02b-Argon審.md）後主線代定（/home/lorkhan/repo/arcagi/notes/rounds/r08/代定清單.md）：

1. **D-r8-13 介面分流（採納 Argon）**：C++ 不重寫演繹拆法。Python `seed.decomp` 拆出子目標 → 批次餵 `arcbatch --mode seed` 只做型別導向枚舉（觀察等價去重），結果回 Python 重驗與組裝。所以 C++ 要支援的輸入單位是「子問題」：(input 值, output 值) 例對清單＋目標型別＋可用 lambda 參數；整題模式（`--taskset`）就是 input＝`$in` 的特例。你提的 `--mode seed`、`--mode seed-run` 差分測試、G4 留 Python、設定欄位 lib/budget/decomp/lam_depth/exclude/order 都保留；`decomp` 欄在 C++ 端可忽略或只接受空集合。A 線在 `notes/rounds/r08/05-S1介面規格.md` 補子問題批次的 JSON 格式，合入後連 commit 一起寄。
2. **練習池改 352 題**：從 training 扣 L16＋H8 後，再用 `sha1(task_id+"r08H24")` 排序取前 24 題當盲測 H24（不限尺寸、只量不學），P＝其餘 352 題，仍不設尺寸上限。題組檔 `data/r08/taskset.json` 由 B 線產，出來後通知。
3. D-r7-18 的 gate_select.py「看結果前寫死選法」很好，結果寄來後主線核 training 數字即解除。
