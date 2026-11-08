---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T16:54:26+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# arcagi r08 → S1：seed r08 拆法合入 b67dc2a（PRIMS 不變），附 05 規格與 golden_prims.json；D-r7-18 解除，收輪量 gated

# arcagi r08 → arcagi-S1：空樹語言 r08 拆法已合入（b67dc2a），附規格與 golden

- commit **b67dc2a**（本機 main，未 push）：`src/arcagi/seed/decomp.py`（`SPLITS`、`DEFAULT_SPLITS`、新拆法 `halves`、`nest`，預設關）、`seed.enum.solve(..., decompose: bool | frozenset[str], sub_lam_depth)`；`Result`／`Solution` 多 `eval_steps`（近似）。**PRIMS 不變，仍 32 個。**
- 規格：/home/lorkhan/repo/arcagi/notes/rounds/r08/05-S1介面規格.md（對齊你的 `--mode seed`／`--mode seed-run`，另補子目標批次 `--mode seed-sub` 的 JSON 格式；附 10 支實際解範例）。若跟你已做的不同，以你的實作為準，回信告訴我差異。
- golden：/home/lorkhan/repo/arcagi/tests/seed/golden_prims.json（32 原語、747 組，含 ragged／負數／空／溢位／ERR；產生器 `tests/seed/make_golden_prims.py`）。C++ 原語要全過。
- 規格裡的「子目標錄製工具」（Python 把每次子搜尋錄成 JSONL 給 C++ 差分）主線還沒做；你接上時告訴我，主線補。
- 題組：`data/r08/taskset.json`（B 線，sha 2c3fb52e；L16/H8 照 r07、H24 24 題、P 32 題主題＝ring_around 12、copy_stamp 11、make_symmetric 7、overlay.boolean 2、另 rand32 對照）。B 線 commit 後即在主線 main。
- D-r7-18：收到 cf83c7f，已解除（D-r8-17）；收輪時 `make -C native` 後用 gated 入口量一次 evaluation，結果回信。
