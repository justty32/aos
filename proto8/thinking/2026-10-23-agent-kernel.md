# 2026-10-23 在 fsm 上做 aos-agent 與 aos-kernel

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前一份：[daemon 的 ctl 只寫變動、`$ref` 切檔](2026-10-23-daemon-ctl-ref.md)

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。相關條文：[C-50、C-62](../docs/CONCEPTS/05-agent.md)、[C-47](../docs/CONCEPTS/04-kernel.md)；前情：[10-21 計畫 § 5](2026-10-21-plan.md#5-agent)。

## 使用者原文（整理版）

> 我原本想說是在fsm的基礎上去做aos-agent，乃至於aos-kernel。你覺得呢

頂層問「aos-agent 比較接近範本還是程式」，使用者答：

> 範本

## 決定（使用者定）

- **aos-agent＝範本，不是一支包了邏輯的程式**：它只產生標準的 agent 資料夾，跑的時候仍靠 aos-loop＋aos-fsm（接 C-50、C-62）。

## 未決（頂層提議，使用者沒反對、還沒拍板）

- 方向跟 C-50（agent＝狀態機＋各狀態跑的 inst）、C-62（agent 的定義就是一台狀態機）一致。
- `tool_calls`（腦的工具呼叫）是做 agent 第一個會撞到的題目。
- kernel 的樣子：一個 loop，每次跑一台 fsm 做決定，再把結果寫進 daemon 的 ctl（`loops_added`／`loops_removed`），由 daemon 去執行——kernel 決定、daemon 動手，符合 C-47。
- 順序：`tool_calls` 的形狀與真 agent 先做（見 [腦的工具呼叫](2026-10-23-tool-calls.md)），kernel 最後。
