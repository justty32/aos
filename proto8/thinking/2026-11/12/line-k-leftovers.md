# line-k-leftovers：線 K 剩兩件——gitignore 分類漏列、history 結果行帶絕對路徑；之後再修出錯時的錯誤行（11-12）

← [2026-11-12](README.md)｜[thinking](../../README.md)｜前情 [fork-and-do-task § 新持久檔分類](../11/fork-and-do-task/README.md#新持久檔分類11-11-稍後線-k)

11-11 線 K 留下的兩件（使用者已知、沒裁；11-11 晚認可線 K 五條代定時原話「沒啥好翻的，我覺得都OK」）。這次照專案既有原則自己定，下面的代定都可以翻。

## 結論

**1. gitignore 分類漏列兩處：已補。**
- 分類表 [gitignore_classes.json](../10/two-machines/gitignore_classes.json)：G063 從改名前的 `children.json` 改成 `stacks/**/subagents.json`（工具小格的記帳、stack 根的配額設定，同名不同處，都進 git）；新列 G099 `stacks/**/tools/fork/children/*/state`（進）。舊名 `children.json` 不留（proto8 當沒有舊版）。
- [NORMS 附錄 4](../../../docs/NORMS/附錄4-持久檔.md) 補 fork 那份 state 一列（持久、進）；`subagents.json` 兩列原本就有。
- [stack.gitignore](../../../cmd/aos-agent/stack.gitignore) 沒改規則（本來就沒擋 `tools/`），只在「都要留」那句加名字；[gitignore 指南](../../../cmd/aos-agent/docs/05-gitignore指南.md)的表加一列。
- 測試：`extras/gitignore-check` 的實跑多做一段 fork（`keep: true`），真的長出 `tools/fork/children/<分身>/state`；沒補 G099 前這條路徑報 unknown、補了過。另加 `tests/test_classes.py`，直接查幾條路徑分到哪一列。

**2. 外洩：實跑確認有，已修。**
- 查法：gitignore-check 的假腦劇本多做「裡層 do_task start → todo add → end」，讓 end 的結果行真的進 history，再跑它的敏感內容檢查。修之前紅：`stacks/root/procs/worker/history.jsonl` 裡有 `the originals are in /tmp/aos-gitignore-…/something/stacks/root/procs/worker/history_removed.jsonl`（fork 抄過去的分身 history 也一樣）。
- 源頭在 `aos-agent history`（rm／summarize／set 的結果行）；self_history 原樣轉上來、do_task end 取最後一段接上，所以兩支都會帶進 history。
- 改法：只改 `aos-agent history` 這一處——預設那份印相對 stack 的位置：`the originals are in history_removed.jsonl in the stack of bob`；給了 `--keep F` 就照 F 的字面印（self_history 的 `keep` 是相對 `$AOS_WS` 給的，照樣原樣回去）。依據：N-67 ⑦「要記就記…相對 stack／定義的路徑」、KISS「給的值照字面用」。修完 gitignore-check 整套 `ALL CHECKS PASSED`。

**3. 順帶查到並修：fork 分身的 `exec.json` 帶絕對路徑。**
- 實跑 fork 時敏感內容檢查也抓到 `stacks/root/procs/<分身>/exec.json` 的 `/exec/argv/2` 是這台的絕對定義路徑。原因：fork 叫 `ctl add` 時給的定義是 `realpath` 過的絕對路徑；`ctl add` 把絕對路徑當成「使用者寫的，原樣存」（11-10 B01），加上 `--envs` 讓 daemon 把啟動寫成小格裡的 exec.json。
- 改法：fork 給 `ctl add` 的定義、工作區、stack 都改成相對路徑（stack 本來就是），由 `ctl add` 照一般規則換成相對 daemon 的寫法。

## 代定（可翻案）

| # | 代定 | 翻案的話要改哪 |
|---|---|---|
| K1 | fork 的 `tools/fork/children/<分身>/state` 進 git：它記「哪些分身是我的」，跟分身自己那份 stack（在 daemon 的 `procs/` 下，本來就帶走）配成一對；同 subagent 的記帳。running 的租約是這台的牆鐘，換台後會過期，下次 fork 對帳時照既有規則收 | 分類表 G099、附錄 4 那列、stack.gitignore 加一行擋 |
| K2 | 結果行的位置寫成 `history_removed.jsonl in the stack of <名>`（相對 stack，加上是誰的 stack）；`--keep` 照字面 | `proto8/cmd/aos-agent/aos_agent/history.py` 的 `where_said` |
| K3 | 修在 `aos-agent history`（源頭），不在 self_history／do_task 改字串；人在終端看到的也跟著變成相對的，要絕對位置用 `aos-agent ctl where` | 同上 |
| K4 | fork 給 `ctl add` 的定義與工作區改相對（跟 stack 一樣） | `proto8/lib/agent/fork/_entry` 的 `ctl add` 那行 |

**11-12 使用者裁：K1～K4 都認可（Q06 a；同日更早使用者「代定都OK。」）**（[small-rulings](small-rulings.md)）

## 沒處理、只記下

- 錯誤行裡的路徑：`aos-agent history` 寫不進去時的 `WriteFailed`（還有其他指令的錯誤行）會帶絕對路徑，工具會把錯誤行接上去，也就進了 history。只在出錯時才有，這次沒動。**11-12 稍後已修，見下一節。**
- 分類表裡另一個舊名 G062 `agents.json` 沒動（不在這次的範圍）。
- 要重建什麼：不用。只改輸出文字跟分類；已經進 history 的舊結果行要清，得手動 `aos-agent history set` 改那一行。

## 出錯時的錯誤行不帶絕對路徑（11-12 稍後，線 errpath）

使用者 11-12 裁定原話：「出錯時的錯誤行仍待絕對路徑...修。」

**盤點（實跑）**：`extras/gitignore-check` 的假腦多一段故意出錯的劇本（`ERRORS`）：todo、do_task 的小格改唯讀（寫不進）、`history_removed.jsonl` 改唯讀（self_history rm 寫不進旁檔）、read 一個不在的檔、subagent 問一隻不在的子（施工時還有 knowledge_read 問一個不在的節點、沒漏；knowledge 工具同天拿掉後劇本跟著刪）。每支的錯誤行（stdout）跟 act 附的 stderr 尾巴都接進 history，再跑原本的敏感內容檢查。

| 工具 | 修前 | 漏的是什麼 |
|---|---|---|
| todo、do_task | 漏 | 程式自己組的小格路徑 `/tmp/…/stacks/root/procs/worker/tools/todo/todo.json`，加上 `str(OSError)` 自帶的檔名（連暫存檔名 `.todo.json.<pid>.tmp`） |
| self_history（`aos-agent history`） | 漏 | 同上兩種：預設旁檔的絕對路徑＋OSError 檔名；aos-agent 那行、self_history 接上的那行各一份 |
| json_get | 漏（不在這條線修） | json_get 自己那行是相對的；漏的是 aos-json 的錯誤行（stderr 尾巴）：`lib/aos_json.py` 交給 aos-json 的是 `ws_path` 算好的絕對路徑 |
| read、subagent（還有當時的 knowledge_read） | 沒漏 | read 照呼叫者給的字面＋`strerror`；另兩支訊息裡沒有路徑 |

漏的來源只有兩種：① 程式自己組出來的路徑（工具小格、stack 裡的檔）原樣印；② `"…: %s" % e` 把 OSError 整個印出來，它自己又帶一次開檔用的絕對路徑。

**做法（修在共用處＋各源頭改用它）**：
- `lib/tool_io.py` 加 `place(path)`：程式自己算出的路徑在 `$AOS_STACK` 裡＝`$AOS_STACK/相對`、在 `$AOS_DAEMON` 裡＝`$AOS_DAEMON/相對`、在工作區裡＝相對 `$AOS_WS`（同 `shown_path`），同時在幾個裡面取最近的；都不在＝照原樣。加 `os_reason(e)`：有 `strerror` 用它（不帶檔名）。
- `py/aos_flags.py` 加同名 `os_reason`；`aos-agent` 的 `common.py` 加 `in_stack(path, a)`：`<相對> in the stack of <名>`（同線 K 的 K2 結果行）。
- 用到的源頭：lib/agent 的 todo、do_task、fork（含 `fork_copy.py`）、subagent、agents_cmd（`ws` 建不起來照呼叫者字面）、agent_def（含 11-12 小題線新增的 `def_edit.py`）、tools_def、cli_session（claude／codex）、goal_state；aos-agent 的 history（全部錯誤行；`--keep` 照字面）、goal、system；system set／hook add 的 `PathMissing` 不再印 cwd 的絕對路徑。錯誤代號都沒改。
- 順帶修：`aos-agent history` 寫旁檔失敗時暫存檔 `.history.jsonl.tmp` 會留著（實測撞到），現在收掉。
- 修完：修後錯誤行長這樣 `todo: error: WriteFailed cannot write $AOS_STACK/todo.json: Permission denied`、`aos-agent: error: WriteFailed cannot keep the removed messages in history_removed.jsonl in the stack of worker (nothing changed): Permission denied`；gitignore-check 整套 `ALL CHECKS PASSED`。

### 代定（可翻案）

| # | 代定 | 翻案的話要改哪 |
|---|---|---|
| E1 | lib 工具訊息裡程式自己算的路徑寫成 `$AOS_STACK/…`、`$AOS_DAEMON/…`、工作區相對；三個都不在才照原樣（絕對） | `lib/tool_io.py` 的 `place` |
| E2 | OSError 只印原因（`Permission denied`），不印它自帶的檔名 | `tool_io.os_reason`、`aos_flags.os_reason` |
| E3 | aos-agent 的錯誤行同 K2：`<相對> in the stack of <名>`；`--keep` 照字面 | `aos_agent/common.py` 的 `in_stack`、history 的 `keep_said` |
| E4 | 呼叫者（腦）自己給的路徑照字面回印，就算是絕對路徑也不改：那串字本來就在它自己的 tool call 參數裡、一起進 history；base 檔案工具原本就這樣 | — |
| E5 | `PathMissing … (relative to the current directory)` 拿掉 cwd 的值（腦叫的時候 cwd＝工作區，就是絕對路徑） | `aos_agent/system.py`、`hook.py` |
| E6 | goal_state 讀不了寫 `cannot read goal.json: 原因`（跟它其他幾句一樣不帶位置） | `lib/agent/goal_state.py` |

### 沒修、列給之後

- **json 工具一族**（json 線在改，這條線不碰）：`lib/aos_json.py` 把絕對路徑交給 aos-json，aos-json 的錯誤行經 act 的 stderr 尾巴進 history（實跑確認）。改法建議：在 `$AOS_WS` 跑 aos-json、路徑照呼叫者給的字面交下去。劇本沒放 json_get，免得這條線紅。
- knowledge 一族（`knowledge_fs.py` 同型）：同天 knowledge 線整套拿掉，不用修。
- aos-agent 其他會帶絕對路徑的行：`DaemonMissing`／`DaemonFailed`（`at <daemon 路徑>`）、`StateMissing`、`HistoryMissing`／`InterfaceBad`（定義資料夾）、llm 的 `LlmBad`；**成功行**也有：`aos-agent system` 的 `deleted <檔>; back to the definition's <檔>`、`get --json` 的 `file`、`using the definition's <檔>`（self_system 會原樣轉進 history）。
- `py/daemon_ctl` 的幾句（`cannot write`、`cannot access reply mailbox`、`cannot inspect stack`）；`lib/agent/hooks.py`、`mail_notify`（hook，進 fsm 的 stderr，不進 history）；`agent_files.py`。
- 工具轉接下層的行（tools_def 的 `last_line`）照轉，不在轉述端改（K3）。
- 工具當掉時 Python traceback 經 stderr 尾巴進 history，帶 repo 的位置。
- C++ 各支（`aos::fail` 裡印的路徑）沒逐支盤；這次實跑只撞到 aos-json。
- 要重建什麼：不用。只改訊息文字；已經進 history 的舊錯誤行要清，得手動 `aos-agent history set`。
