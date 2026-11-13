# 線乙（11-13 上午，fable 隊長）：舊路徑、agent-fsm 重複收一支、說明清舊、do_task 摺疊被砍重複

← [11-13 日索引](README.md)｜前情：[11-12 程式碼庫整理](../12/codebase-cleanup/README.md)、[tidy 11-12 收尾報告](../../../../wf/workflows/tidy/reports/2026-11-12-收尾.md)、[do_task 02](../11/fork-and-do-task/02-do_task.md)

現場條件（調度者交代）：`~/aos-home` 那棵樹開著、使用者正在用，所以不改 C／C++、不 build、不重跑 install、不碰 `~/aos-home`；impls 只改說明。

## 結論

| 批 | 做了什麼 | commit |
|---|---|---|
| 1 舊路徑 | proto8 裡示範舊 repo 路徑的 11 處改成 `~/repo/aos`：五份 `.env` 的 `AOS_HOME` 示範註解（kernel 四份、`templates/daemon-root`）、`test_paths_move` 對那行的斷言、aos-agent 搬家 03、`templates/docs/02` 兩處、`kernel/docs/03`、`extras/langs/lua` README | `20d0f7f57` |
| 2 整理續做 | `templates/agent-fsm` 四格的 on_clock 段與 brain／act 相同的兩段收成夾內 `cell_common.py`（`clock_tick(hooks, stack, warn, die)`、`read_history(history_path, die)`、`tools_file(opts, files, stack, die)`）；`templates/docs/02` 檔案清單與 knowledge `aos/definition` 補新檔。行為不變（新舊版 19 種情境輸出、結束碼、stack 檔全同） | `041df518b` |
| 3 說明清舊 | `impls/aos-json`（README、docs/01、docs/02）、`impls/aos-directive` docs/01 照「沿革只留結論」過一遍；`py/README` 兩列「誰在用」跟上現況；`cmd/aos-mcp/README` 的 `mcp_argv` 改指 `lib/agent/cli_mcp.py`。沒刪使用者原話 | `1f6422272` |
| 4 do_task | 修了：`end` 帶 `keep_others` 要挪訊息時，先把「留哪幾則」記進 `tasks.json` 的 `moving`，act 重跑同一個 call 時照它重放再摺。只動 `lib/agent/do_task`，`tasks.json` 只加一個鍵 | `4696428dd` |

- 全套（`041df518b`，從空的短暫存目錄跑）：66 夾 1357 例（比基準多的 3 例是 do_task 新測試），只紅既有 4 支（aos-agent `test_daemon_down` 的 test_add、test_stop；box_check `test_acceptance` 兩支）。
- 前提跟現況對不上、所以沒動的：
  - `aos-eca-turn` 這支指令還在（`cmd/aos-eca/bin/aos-eca-turn`，本體在 `aos_eca/` 套件），`cmd/docs/01` 那段的指令名、用法、錯誤行程式名都跟程式一致。
  - `py/README`「N-17 的 11-10 例外」、`cmd/docs/03`「N-28 的 10-29 補」前一輪已改掉。
  - `lib/aos/knowledge_check` 已不存在，knowledge 改完只驗了 JSON 合法。

## 要重建什麼

持久檔格式沒變；`tools/do_task/tasks.json` 多一個選填鍵 `moving`，舊檔照讀。抄出去的 `templates/agent-fsm` 複本要整夾重抄（多一支 `cell_common.py`，只抄四格會缺模組）。impls 執行檔沒變、不用重 build、不用重跑 install。

## 代定（可翻案）

1. 舊路徑只改 proto8 裡的 11 處；`proto8/feedback/*.jsonl` 的 `cwd` 欄（當時的紀錄）、`proto8/archive/` 不改。
2. `aos-json` docs/01 的 aos-lock 那句：實測經過（20 個同時跑只剩 1 個 key）改寫成一個坑「不配鎖時同時跑的 set 互相蓋掉」。
3. do_task 重放時，目標行內容已經一樣就不再 `set`（`history_removed.jsonl` 不多記一筆）；記下的行數／範圍跟現在的 history 對不上＝`StateBad`、不摺。
4. brain、act 把 `sys.dont_write_bytecode = True` 提早到 import `cell_common` 之前（跟 idle、wait import `atomic_file` 同一寫法）；brain 留著用不到的 `history_path` 一行（NORMS 附錄 4 的 evidence 指著這個名字）。

## 未決（要使用者裁）

1. **do_task 的 `interrupt: unsafe` 要不要改 `safe`**：(a) 維持（建議；下一題的窗口還在）；(b) 改 safe。
2. **do_task 剩的窗口**：挪到一半是 aos-agent 回錯（不是被砍），腦再叫一次 end 是新的 call，留下的訊息仍會多一份。(a) 先不補（建議；要 aos-agent 寫檔失敗才碰得到）；(b) 改看 history 形狀認沒做完的計畫（程式複雜、容易認錯）；(c) aos-agent 提供一步完成的「挪＋摺」（動設計）。
3. **`cmd/docs/01` 的 aos-eca-turn 錯誤代號清單少三個**（`HooksBad`、`ToolsBad`、`SessionBad`，程式會報）：(a) 補上（建議；照程式寫）；(b) 不補。
4. **`cmd/aos-mcp/README` 例子指 `~/code/playground/agents/bob-cathy/mcp.json`**：公司機遊樂場已刪。(a) 刪掉這個例子（建議）；(b) 留著（家機若還有）。
5. **`impls/aos-directive` docs/01 的「D9」「ideas § 9」這類出處標籤**指向已封存的 ideas：(a) 留著（建議；是出處不是沿革）；(b) 清掉。
6. **wf 裡還寫舊路徑的現行說明**（不在這條線的可寫範圍）：`wf/tools/progress_board/` 的 README、`config.json`、`designs.py`、web 兩檔寫 `~/repo/simple_tools/aos`；`wf/workflows/dev-env/01` 寫家機 repo 在 `~/repo/simple_tools/aos`。(a) 另派一條線改成兩台各自的現況（建議）；(b) 不管。

## 沒做

- [codebase-cleanup](../12/codebase-cleanup/README.md)「待使用者裁」各題一題沒做；它「下次可接的」三點裡，第一點（agent-fsm）與第三點的 `mcp_argv` 這次做掉，第三點的 aos-eca-turn 段查過不用改，第二點（lib/aos 找 lib）是待裁題。那份 README 與日索引沒改（不在可寫範圍）。
- `templates/agent-fsm` 看到沒收的：idle 的 `history_empty()` 自己讀一次 history（只看空不空，跟收掉的那段不同）；`atomic_file.py` 檔頭仍寫「idle、wait 共用」。
- do_task 的 `StateBad`（計畫對不上）那條沒有測試格；真 daemon 下真的被砍沒實跑，只在單元測試用假 aos-agent 讓那一步失敗來模擬。
