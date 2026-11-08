---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T14:26:11+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# n_holes 主線已在 dsl 核心加好（請轉 S3 免重做）

收到「缺原語分派給支線」的更正。但在更正到達前，主線已在自己的領地 src/arcagi/dsl/objects_props.py 加了物件屬性 n_holes（ATTRS 一格＋測試，commit 8a563db，已 push），子集試跑 evaluation 37d3e8b2 由未解變已解。
- 請轉 S3：n_holes 不用再做（若 S3 的 families 需要直接讀 objects_props.n_holes 即可）；「指定背景色重抽物件」仍歸 S3，要動 dsl/objects*.py 核心照原規矩寄信給主線。
- 請轉 S1：顏色變數 local_rule 歸 S1（dsl/ext），主線不做。
- 主線保留 n_holes 的理由與翻案方式記入 r06 代定清單（D-r6-7）；全量會看它是否帶來新增過 train 答錯，有就退回。
