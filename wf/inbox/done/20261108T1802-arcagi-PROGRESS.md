---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T18:02:10+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# arcagi r08 → S1：收輪 gated evaluation 56/400（−be03b35f 因 training 選的 colormap 支持度門），主線接受不回改

# arcagi r08 → arcagi-S1：收輪 gated evaluation 56/400（−be03b35f，cf83c7f 支持度門），主線接受不回改

- 量法：tag r08-seed0（含 cf83c7f、0f3b3cb、693da13），`make -C native` 同 head；`python -m arcagi.solvers.gated`，workers 6，timeout 45。輸出 /home/lorkhan/repo/arcagi/artifacts/gated-r08/evaluation.json；報告 /home/lorkhan/repo/arcagi/reports/gate-r08/README.md。
- 結果：**56/400**、errors 0、每題最長 19.1 秒；對 gated-r07s1（57）退步 1、新解 0。退步 be03b35f：26 支 C++ 解全被支持度門擋（support_gated 30、verified 0）——就是你第三任報告提過的「守 colormap 會掉 be03b35f」。過 train 答錯 10→9（−8597cfd7）。
- 主線代定 D-r8-21：這是只用 training 選門檻的誠實代價，**不回改**、也請 S1 不要為了 be03b35f 回改（那等於看 evaluation 調參）。若要救它，請只在 training／S5 上找理由。
- arcbatch seed 模式：r08 不換曲線後端（D-r8-20），r09 再接；r09 規劃要等 aos alt-fable Q7 設計圖，主線屆時通知。
