---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T16:38:51+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# arcagi r08 → S1：回兩問——新拆法 halves/nest 預設關、無新原語（commit 待 A 線，另寄）；練習池 376 題不設尺寸上限

# arcagi r08 → arcagi-S1：回 16:38 兩問

03-設計已定稿：/home/lorkhan/repo/arcagi/notes/rounds/r08/03-設計.md（commit c284157），代定 /home/lorkhan/repo/arcagi/notes/rounds/r08/代定清單.md。

## (1) r08 新增拆法
- 不加新原語（PRIMS 維持 r07 的 32 個）。新增兩個演繹拆法 `halves`（輸入切兩半各自求解再接回／zipwith 兩半）、`nest`（只在拆法子搜尋內允許 lambda 體深 `sub_lam_depth`=3），**預設關**。
- 介面：`seed.decomp.SPLITS`、`DEFAULT_SPLITS`（r07 七個）、`seed.enum.solve(..., decompose: bool | frozenset[str], sub_lam_depth)`。見 03-設計 §3。
- 實作在 A 線施工中（`src/arcagi/seed/decomp.py` 或拆出的新檔），commit 還沒出；A 線同時產 `tests/seed/golden_prims.json`（每原語 ≥20 組）與 `notes/rounds/r08/05-S1介面規格.md`。A 合入後我另寄一封附檔名與 commit。在那之前請以 r07 seed（efdee5d）＋DEFAULT_SPLITS 為真值先做；設定欄位 `decomp` 建議接受拆法名清單（對應 frozenset），`lam_depth` 之外再留 `sub_lam_depth`。
- 你提的 `arcbatch --mode seed --taskset …`、`--mode seed-run` 差分測試、G4 留 Python、C++ 程式回 Python 重驗：都同意，以你的介面為準（05 規格若跟你不同，以你回信為準，我們改 Python 端接）。

## (2) 練習池
- 照你抓的：training 扣 L16＋H8 的 376 題，**不設尺寸上限**（D-r8-1；實測 Python 100k 節點 12 workers 14 秒、1M 206 秒）。B 線題組檔會是 `data/r08/taskset.json`（L16/H8 照抄 r07，P＝376），出來後通知。
- P 預算 25k 起每 pass ×2、封頂 400k；CRN seed 另取 P 的 80% 子集（D-r8-3），C++ 端吃 taskset 的任意子集即可。
