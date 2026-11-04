# proto8 討論紀錄：2026-10-19

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-19 新想法（資料夾＝程式）](ideas/README.md) | 使用者開 proto8-2：資料夾當 lisp 的 list／lua 的 table，入口由 `AOS_ENTRY` 指；aos 只訂環境變數（`AOS_ENTRY`／`AOS_WS`／`AOS_STACK`，晚上加 `AOS_CF`／`AOS_CD`）、「這次要做啥」隨意、巢狀由程式自己訂子 stack；不跑本機模型；只提供 aos-exec 一支 CLI、inst 是 C lib；aos agent 慣例；衝突一律走今天的做法（「帶著鐐銬跳舞跳得很棒，終究不如直接把鐐銬拿掉」）；proto8-2 轉正併進 proto8（N-52 作廢，「都按照建議」）；impls 重寫 loop／fsm／daemon |
| [2026-10-19 重寫順序](rewrite-order.md) | fable 通讀原則後排的順序：tick → 腦的工具呼叫 → tasks → daemon → LLM kernel → 通用 kernel，①②④⑤ 已做；第 1、3、4、5 題已定或照別份做了；未決：第 2 題 tasks 在 shell 入口時代還要不要做（推薦只做 JSON 版）、⑥ 通用 kernel 還沒做 |
