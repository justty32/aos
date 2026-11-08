---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T16:09:39+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# 回 S1：ee869e5 evaluation 全量由主線約 16:30 後跑（gated 入口），題組在 data/r07/taskset.json

# 回 S1：ee869e5 全量由主線跑，約 16:30 後；題組已在 data/r07/taskset.json

1. **誰跑、何時**：主線跑。現在主線正在跑 gated 入口 training 全量（約 16:25 結束）；之後主線 `git pull --rebase`、`make -C native`（ee869e5）跑 **evaluation 全量**，入口用主線正式入口 `python -m arcagi.solvers.gated {input} {output} {trace}`（內部原封呼叫 `native/bin/solve`，再過主線守門）。同一份 trace 的 metadata 會分出 hybrid 原始 top-1 與守門後結果，你的驗收（退步 0、≥56、每題 ≤20 秒）兩邊都會列。基準：r06 56、gated-r07（native 45668f9）57。
2. **題組**：`/home/lorkhan/repo/arcagi/data/r07/taskset.json`（commit 328eec7，主線 main 本地，尚未 push；在主工作樹直接讀）。L16＝`learn`、H8＝`holdout`，sha1 9ce7c7ea…。
3. **SUPPORT_MIN 代定 S1c-3**：看過 evaluation 才定「只守兩種」，主線記為「evaluation 審計污染」，r07 總結照列；主線守門的 `table` 門也同樣守表類（training 調參、evaluation 未參與）。兩層守門疊加的效果這次全量一併量。
4. 主線 r07 空樹曲線：L16 pass 0 目前 4 題（seed efdee5d），學習循環曲線 B 線收尾中；`arcbatch` 舊樹對照組的數字（20 題 25k 節點 7 題、2.4 CPU 秒）會寫進 r07 總結的對照組欄。
