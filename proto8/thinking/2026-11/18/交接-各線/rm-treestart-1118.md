# 交接：線 rm-treestart-1118（拿掉 aos-tree-start）

← [2026-11-18](../README.md)｜使用者 11-18：「aos-tree-start這東西就不用了吧，刪掉。」｜16:5x 因關機收手，沒 commit

## 結論

改動都做完了，每個檔都是完整狀態，可以交。只差兩件：`重建步驟單.md` 有兩行跟 cooldown-1118 撞在同一行，我沒改（改法寫在下面）；改後的測試還沒跑。

## 動過的檔

`git rm`（已 staged，這 4 個檔只屬於 aos-tree-start）：
- `proto8/py/aos/apps/tree_start/README.md`
- `proto8/py/aos/apps/tree_start/main.py`
- `proto8/py/tests/apps/tree_start/test_tree_start.py`
- `proto8/knowledge/aos/cli/tree_start.json`

搬家（用一般 `mv`，沒 `git mv`，也沒 `git add`）：
- `proto8/py/tests/apps/tree_start/test_env_sh.py` → `proto8/py/tests/test_env_sh.py`。它測的是 `env.sh`，不是 aos-tree-start，所以搬走不刪。`PROTO = parents[4]` 改成 `parents[2]`。交件時要 `git add` 新路徑、`git rm` 舊路徑。
- `proto8/py/tests/apps/tree_start/` 這個夾只剩一個沒進 git 的 `__pycache__/`，我沒刪。

修改（每個都完整）：
- `proto8/py/entries.json`：拿掉 `aos-tree-start` 那行。**另一條線後來也在這檔拿掉了 `aos-kit`，那行不是我改的。**
- `proto8/py/docs/05-commands.md`：拿掉表上那一列。
- `proto8/knowledge/aos/cli/_index.json`：拿掉 `tree_start.json` 那項（knowledge 是手寫維護）。`flags.json`：拿掉例外清單裡講 aos-tree-start 的那句。
- `proto8/templates/start-api/README.md`、`start-eca/README.md`：`aos-tree-start root` 改成 `aos-exec root`，兩份逐字一樣。
- `proto8/templates/start-api/env.sh`、`start-eca/env.sh`：第 11 行註解改成 `not AOS_*: those belong to aos, which sets them for each proc`，兩份一樣。
- `proto8/templates/tests/test_start.py`：註解裡的路徑改成 `py/tests/test_env_sh.py`。
- `wf/public/行程與環境.md`（標題、那一節）、`wf/public/README.md`（那一列）：起樹改成先 `source env.sh` 再 `aos-exec root`，另外寫明「跳過 env.sh 沒人擋」。
- `wf/tools/index_gen_desc.json`：拿掉 `proto8/py/tests/apps/tree_start` 那個鍵。
- `proto8/thinking/2026-11/17/重建步驟單.md`：只改沒跟人撞的地方。第 6 步視窗 A 改成 `aos-exec root`；說明改成「殼裡別棵樹的 `AOS_*` 由第 5 步的 `source env.sh` 清掉，沒做那步就沒人擋」；更新第 3 步那格記錄補「（這支 11-18 已移除）」。
- `proto8/thinking/2026-11/18/eca-claude-小試驗教學/README.md`（06 那列）、`06-不用aos-tree-start起daemon.md`（檔頭）：各加一句「aos-tree-start 已於 11-18 移除，直接用 aos-exec」。
- `proto8/thinking/2026-11/17/cpp-py-改名/08-要裁的題.md`：在文末補上使用者 11-18 的原話與處理結果。

## 還沒做的

1. **`重建步驟單.md` 第 49 行（「關」那格的「再起＝視窗 A」）和第 61 行（更新第 5 步）**：cooldown-1118 的改動還沒交，跟我要改的在同一行，所以我沒改。等它交了，把這兩行裡的 `aos-tree-start root` 換成 `aos-exec root` 就好，別的字都不動。
2. 改後的測試還沒跑。
3. 下面這些是生成檔，交件時由排隊的 index_gen 重生，我沒手改：`proto8/py/aos/apps/_index.json`、`proto8/py/tests/apps/_index.json`、`wf/public/_index.json`、`wf/knowledge/code-map/`（deps 的 bin.json 和 py.json、proto8 的 py.json 和 knowledge.json）。
4. 範圍外、還提到 aos-tree-start 的地方：`proto8/thinking/2026-11/17/cpp-py-改名/13-安裝腳本與新使用者流程.md`、`14-更新與重新複製.md`（範本 README 有連到 14），其餘 thinking、`archive/`、凍結的 `session_logs` 照規定不改。

## 那道檢查（殼裡有別棵樹的 `AOS_*` 就擋）

照文件做的時候，`env.sh` 已經頂替了它：`$AOS_HOME/env.sh` 會清掉 `AOS_HOME` 以外的所有 `AOS_*`。實測時故意帶著 `AOS_STACK` 和 `AOS_DAEMON` 去 source，結果只剩 `AOS_HOME`。

**缺口（要使用者裁）**：跳過 `source env.sh`，在 agent 的殼裡直接打 `aos-exec root`，就沒人擋了。aos-exec 會照用殼裡帶著的 `$AOS_STACK`，11-13 15:24 那次事故就會再發生。選項：
- 甲、不補，只靠文件寫「先 source env.sh」。後果：一打錯就會起錯樹。
- 乙、補在 daemon-root 範本（根的定義）：根起來時，`AOS_STACK` 不是 `./.stack` 就拒絕。後果：只擋從這個範本起的根；故意在樹裡起樹的測試要另外繞過。
- 丙、補在 aos-exec（C++）：加一個「我在起新樹」的旗標。後果：要改 C++；aos-exec 自己還是分不出哪些是巢狀呼叫，不加旗標就不會擋。

## 測試跑到哪

- 暫存在 WSL 的 `~/.aos/scratch/rm-treestart-1118/`。`base`＝`git archive HEAD`；`after`＝HEAD 加上本線的改動，別線還沒交的改動不放進去（工作樹裡 eca-pi-bc 的 `agentlib/cli_a2a.py` 現在有語法錯，`aos-agent` 會直接壞，所以不能整份 rsync）。
- `bin/` 從 30 支變 29 支，只少了 `aos-tree-start`。
- 照改好的範本 README 和步驟單，用假腦走一遍（在 after 複本）：第 4～6 步、關樹、再起，全部通過。回答是 `FAKE ANSWER to: hello`；再起後 `ann` 自己醒，回 `FAKE ANSWER to: again`；兩台 daemon 都關乾淨。
- 改前基準跑了 18 個夾，全部 OK：py/tests 519 支，apps 從 agent 到 tree_start 那 17 個夾。templates/tests 跑到一半我就收手了，wf/tools/tests 還沒跑。改後的測試沒開始。
- 明天怎麼續：`bash <scratchpad>/rmts1118/setup_mine.sh`（重建 after 複本），再 `setsid bash .../tests.sh base` 和 `.../tests.sh after`，比 `logs-*/fails.txt`。腳本在 Windows 的 scratchpad `C:\Users\WG-Guanyu\AppData\Local\Temp\claude\a5755c4eb10ca875\203cb852-0757-4140-abfc-62516a05abe3\scratchpad\rmts1118\`。重開機可能被清掉，清掉了就照上面的說明重寫。最後在 repo 跑 `grep -rn aos-tree-start`（排除 thinking、archive、frontend），應該只剩上面第 3 項的生成檔，加上 `行程與環境.md` 裡引用的使用者原話。
