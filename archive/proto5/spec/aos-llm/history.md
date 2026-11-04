← [aos-llm](README.md)｜[spec 總導航](../README.md)

# 沿革

原標題：`aos-llm-call：問模型一次（程式規範，第 2 版，2026-09-24 定稿（astra 三輪審查＋第 4 輪補 3 條）；已實作）`

> 2026-09-23 草稿；2026-09-24 照 審查報告「定稿前必改」與使用者三件裁決改成第 2 輪；同日照 第 2 輪審查 改成第 3 輪；第 3 輪審查 判可定稿，第 4 輪只補一條實作提醒。（審查與實作紀錄在 [rearch 筆記](../../notes/2026-09-23-rearch/README.md)）
> **已實作**（2026-09-24，T9）：`lib/aos_llm_call.py`＋`cli/aos-llm-call`，實作發現見 agent-impl-findings。
> 這份把兩件事合成一支普通程式。調度者裁決在檔尾（09-24 試玩 r3 搬），已拍板的前提在 §9。
> 2026-09-24 fix-r4：入口 `aos-llm-call` 改成 `aos-llm call`（新入口 `cli/aos-llm`，stderr 前綴 `aos-llm: `），規範檔名 aos-llm-call.md 改成 aos-llm.md。
> 2026-09-24 proto5-2 池式納入：§1 的環境改由池的 `envs.json` 給、info 例子改成 `pools` 的一格、改環境改成「改池的 envs＋`aos-daemon kill --all`」。草稿在 proto5-2/spec。
