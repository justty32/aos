← [在 `aos exec` 上做一條會動的 agent loop](../agent-loop.md)（分檔 12/24）｜所在：第 1 輪評分與意見｜[上一份](11-第-1-輪評分與意見.md)｜[下一份](13-二aos-agent-該收掉什麼.md)

### p3（Joe Armstrong persona）

分數見[上一份](11-第-1-輪評分與意見.md)的表。

**評語**：誠實度的範本（已知 bug 留著當證據、race 兩種結果都報、不確定處加但書、沒試就寫「沒試」）。唯一走完「不重複付錢的復原」：`codex exec resume` 拿回被砍那輪的答案。模型 cwd 指空資料夾是該記一功的決定。扣分：「`~/.codex/sessions/` 是空的、存在 sqlite」沒有輸出且是錯的；claude、pi 沒有一手資料。

**下一輪要做的。**
1. **租約原型（全場第一優先）**：呼叫前原子建立 `turns/<N>/lease.<pid>`，跑完刪；重跑 `mv .runi inst.json` 雙重計費實驗，驗收是「偵測到孤兒還活著、拒絕動作、只付一次」（`thread#1 == thread#2`）。做出來後寫成 `aos exec` 在 fork 前後該做什麼的規格草稿。
2. 用 `write_file` 當工具、在工具回合崩潰後重播，貼出同一個檔被寫兩次的現場，證明冪等不能靠自律。
3. `~/.codex/sessions/` 那句用 `find` 輸出確認後重寫。

### p4（Julia Evans persona）

**評語**：「投遞前擋＝自我修復、投遞後擋＝靜默死亡」直接回答了 `aos agent` 該收什麼，兩邊都有實測。退出 3 先搬空 inbox 經評委讀 `run_exec.cpp` 驗證屬實。唯一三支 CLI 都接進 loop。扣分：「pi 只能塞 argv」沒有失敗現場，又疊上 ARG_MAX 論證當選 codex 的第一條理由。

**下一輪要做的。**
1. **先做**：同一條 `printf | pi -p --mode json --no-tools` 重測 pi 的 stdin，貼原始 exit 與輸出；若吃 stdin，重寫 OPEN #6 的建議。
2. 投遞前驗證：`deliver.sh` 在 rename 前驗一次，驗不過把錯誤字串回給呼叫者、寫成一則 `[tool]` 餵回模型；重跑 `{"path":123}`，貼出模型下一回合改成字串的 transcript。並把「aos 沒有只驗證不執行的入口」寫成一句規格請求。
3. tool_call_id ＋ `parallel: true`：每次呼叫用 id 當檔名（`state/calls/<id>.out`），開 `parallel: true` 跑兩個工具，壞與不壞的輸出都貼。
