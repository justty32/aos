# line-k-leftovers：線 K 剩兩件——gitignore 分類漏列、history 結果行帶絕對路徑（11-12）

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

- 錯誤行裡的路徑：`aos-agent history` 寫不進去時的 `WriteFailed`（還有其他指令的錯誤行）會帶絕對路徑，工具會把錯誤行接上去，也就進了 history。只在出錯時才有，這次沒動。
- 分類表裡另一個舊名 G062 `agents.json` 沒動（不在這次的範圍）。
- 要重建什麼：不用。只改輸出文字跟分類；已經進 history 的舊結果行要清，得手動 `aos-agent history set` 改那一行。
