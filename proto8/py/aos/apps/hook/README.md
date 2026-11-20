# proto8/py/aos/apps/hook — aos-loop 那一層的 hook 點宣告（之後的 aos-hook 指令也放這裡）

← [apps](../)｜讀它的小庫：[aos.hook_point](../../hook_point.py)｜設計：[aos-hook-plan-1120](../../../../thinking/2026-11/20/aos-hook-plan-1120/README.md)

目前只有 [`loop_points.json`](loop_points.json)：用 aos-loop 跑、而且 loop.json 有接線的任何子程式提供的四個點（`after_start`、`after_stop`；`before_run`、`after_run` 先宣告、標 `not_fired_yet`，aos-loop 還沒接）。

這是施工第 1 刀（線 aos-hook-k1-1120）：只加檔，執行時還沒有人讀；現在程式實際用的仍是 `py/aos/agentlib/hooks.py` 的 `EVENTS`。`aos-hook` 指令（第 4 刀）做好後，本體也放這個夾。
