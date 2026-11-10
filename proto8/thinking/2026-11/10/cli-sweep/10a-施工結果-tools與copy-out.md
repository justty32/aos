← [入口](README.md)｜涵蓋：11-10 傍晚 Q8（aos-agent tools add）與 Q7（copy-out --template）的施工結果；另一位隊長的段在 10-施工結果｜上一份 [09-Q1補-旗標放中間目標放最後](09-Q1補-旗標放中間目標放最後.md)

# 施工結果：Q8 aos-agent tools add、Q7 copy-out（11-10 傍晚，opus 隊長；WSL 本地 main，未 push）

## Q8「改」→ `de18a073b`

- `aos-agent tools add [--name N] [--replace] [--no-cache] [--env-file FILE] [--envs K=V]... (XXX | --path-json JSON)`：旗標與意思跟 `aos-tools add` 一樣（C-86），原樣轉給 aos-tools、寫進這隻自己那份（`$override` 定義那份）。舊的「名 路徑」兩個位置參數寫法不留：給兩個＝`ArgumentsBad add needs one XXX (or --path-json JSON)`；旗標寫在 XXX 後面＝`ArgumentsBad flags go before XXX: --name`。
- lv6 呼叫處照「只改那幾行」的例外：`lib/agent/agents/_entry`、`lib/agent/thought/_entry`、`lib/agent/self_tools/_entry` 組出來的命令列改成 `add --replace --name 名 路徑`（self_tools 只有腦給 `override: true` 時帶 `--replace`）；給腦的工具參數形狀不變。
- 文件：aos-agent README 用法列、docs/01 例子、docs/03 兩處、P-44 加註。
- 測試：`cmd/aos-agent/tests/test_tools_override.py` 改新寫法，加兩支（`--envs`／`--env-file`／`--path-json` 照存；舊兩參數寫法與旗標在後＝`ArgumentsBad`）；aos-agent 13 支、lib/agent（含 agents、thought）全過。

## Q7「範本改成必給的旗標」→ 見下一個 commit

- `copy-out --template NAME [--proto8 MODE] DEST`、`copy-out --list`。沒給 `--template`＝`ArgumentsBad missing --template NAME (copy-out --list shows the names)`，不給預設；`--list` 一行一個（`templates/` 底下有 `_entry` 的資料夾，加 `kernel/<名>`），跟別的參數同給＝`ArgumentsBad`；旗標寫在 DEST 後面＝`ArgumentsBad flags go before DEST: …`。
- help 第一句白話（使用者不熟這支）：「copy a whole template folder out of the repo to start a new agent, root or kernel of your own」。
- 呼叫處與文件：`templates/tests/{test_copy_out,test_daily,test_paths_move}.py`、`templates/README.md`、`agent-fsm/README.md`、`reviewer/README.md`、`templates/docs/02-agent-fsm.md`、`two-machines/11-給使用者的一頁.md`、`15-回家那台開工.md`（照新用法改、尾段加註）。gitignore 指南、搬家文件只提到 `--proto8`，沒有要改的；試驗場 README 沒提到 copy-out。
- **沒改的**：`templates/daemon-root/README.md` 第 19、20 行還是舊寫法——那個資料夾是另一位隊長的範圍，已請頂層轉告。
- 測試：`test_copy_out` 加四支（必給、`--list`、旗標在後、help 第一句）；`test_copy_out`＋`test_paths_move` 20 支過，`test_daily` 結果見回報。

（11-10 傍晚改名 `AOS_HOME`：使用者「AOS_PROTO8改成AOS_HOME，這樣之後大修改版，還可以直接換」；意思不變，指向這台的 aos 本體資料夾，現在是 `<repo>/proto8`。）

改名的範圍：copy-out（env 模式與 needs 行；`--proto8 MODE` 旗標名照頂層傾向先不動）、lib/agent/copy_def.py 與它的測試、agents/_entry（lv6，只換變數名）、aos-tools help 例子、範本 README／docs、NORMS 環境變數表、搬家文件、dev-env、two-machines 11／15 頁與 decided.json。**沒改**：`templates/daemon-root/README.md` 第 39 行（另一位隊長的範圍）、`knowledge/aos/cli/tools.md` 第 14 行（lv6）、`wf/HANDOFF.md` 第 25 行（頂層的交接檔）；這台 WSL 的殼設定檔都沒有 AOS_PROTO8；桌面大修材料沒有用到這個名字；試驗場 `lib/` 已重新 rsync 成 repo 版。
