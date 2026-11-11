# carry-over：11-10「明天順序」逐項盤點（11-11，線 J）

← [2026-11-11](README.md)｜[thinking](../../README.md)

使用者 11-11 選了「昨天裁好的施工」。來源是 SESSION-LOG 裡 11-10 傍晚寫的兩行「明天順序」（「以這行為準」那行與它上面那行），以及它們連到的 [cli-sweep](../10/cli-sweep/README.md)、[two-machines](../10/two-machines/README.md)、[templates-cp](../10/templates-cp/README.md)。

## 結論

**兩行列的東西 11-10 晚～深夜在家機都已經做完，這次沒有東西要施工。** 逐項對了程式現況（`aos-agent ctl --help`、`ctl rm --help`、`~/.local/bin`、範本檔）、11-10／11-11 日誌與 `git log`。剩下的都是**沒裁的題**（下面「待裁」）或**排在大修／整理階段**的，照任務書不硬做。這次只改記錄：next_todo 三列狀態、SESSION-LOG 過時行、WAIT_USER 一條、各夾 README 加現況註。

## 盤點表

| 項 | 狀態 | 在哪做的 |
|---|---|---|
| B01 前半（`--*-json` 的 `$env` 寫法進表） | 已做 | `7c1791e6e`、修 add `c2a6aa976` |
| B01 後半（命令列打的絕對路徑原樣存、`--ws-json`／`--stack-json` 純字串照字面送；動 aos-daemon 存表） | 已做 | `4a5a81986`；不在這台＝退回相對那份 `1cc03ab86` → [16](../10/two-machines/16-B01後半施工結果.md) |
| templates-cp（範本 `AOS_HOME` 寫法、拿掉 `tools/` 夾、自帶 `.env`、刪 copy-out 與 `copy_def.py`、`agents new` 整夾抄） | 已做 | `0ae02d7b0`、實跑 `862958edc` → [05](../10/templates-cp/05-施工結果.md)；這台 `~/.local/bin/copy-out` 已不在 |
| cli-sweep 甲6（寄信前先核 daemon） | 已做 | `8e13d0dd3` → [10c](../10/cli-sweep/10c-施工結果-甲6Q3Q6.md) |
| cli-sweep Q3（`aos-agent ctl rm` 預設留 stack、`--purge` 才刪） | 已做 | `8e13d0dd3`（help 現況已對過） |
| cli-sweep Q6（不動、對照表放 help 第一屏） | 已做 | `8e13d0dd3`（兩支 `--help` 第一屏有三對停與起表） |
| cli-sweep Q1（旗標寫在那層名字之後任何位置）＋Q2、Q3 讀法 | 已做（六支） | `4106d3853`、`0f16b5200`、`b224b50f6`、條文 P-44 續 `d8bdde157` → [10d](../10/cli-sweep/10d-施工結果-Q1旗標位置.md) |
| Q1 其餘指令（aos-mcp、aos-sandbox、aos-clock、aos-sweeper、aos-feedback、aos-eca-turn／screen、C++ `aos::parse_cli`） | 沒做：**沒裁** | P-44 續寫「之後要不要一起改，沒裁」→ 待裁 1 |
| cli-sweep Q4、Q7、Q8、甲3～5；Q5 改裁不修 | 已做 | 10a、10b；Q5 `00288480e` |
| aos-tools lv6 連帶 | 已做 | 11-10 晚 → [aos-tools-cli 08](../10/aos-tools-cli/08-施工結果.md) |
| two-machines B02～B04、B13 | 已做 | `55bc1205b` |
| B07～B10 | 已做 | → [17](../10/two-machines/17-B07到B10施工結果.md)；17 留的三題使用者 11-11 已裁（待裁 3～5），施工見下「追加」 |
| B11 | 已裁（照帶、不擋） | — |
| B17、B18、B23 | 已做 | — |
| B19 | 已做（這次確認 dev-env 那句已改成 `cp -r`，next_todo 改狀態） | templates-cp |
| B12（env 模式 tooldef 是快照） | **自然消失**（這次改狀態）：copy-out 與 env 模式刪了、範本不帶 `tools/`，沒有快照了 | — |
| B05、B06（追蹤檔裡的本機路徑：sender、ledger、使用者寫的絕對路徑） | 沒做：**沒裁**（兩條路都寫在 direction） | 待裁 2 |
| B14（aos-lock 認主給 token） | 沒做：對外加法、沒裁 | 待裁 6 |
| B15、B16、B20、B21 | 沒做：next_todo 標「大修」 | — |
| B22（檔太長） | 沒做：使用者 10-09「開發階段不設行數上限」，排成果整理階段（next_todo 已註） | — |
| templates-cp 剩的：defs 分群不看知識庫那格的 env | 沒做：**沒裁** | 待裁 7 |

## 待裁

可直接貼選項框；推薦放第一個。**七題使用者 11-11 都裁了**：3～5 見「追加」，1、2、6、7 見「第二批」。

1. ~~（已裁：全部改）~~ **旗標「寫在那層名字之後任何位置」要不要推到其餘指令？**（aos-mcp、aos-sandbox、aos-clock、aos-sweeper、aos-feedback、aos-eca-turn／screen，以及 C++ 零件共用的 `aos::parse_cli`）
   - A 全部改：Python 那幾支換成 `aos_flags.parse(sub="root")`，C++ 只改 `parse_cli` 一處、零件全家跟著（推薦：規則一致，改的都是共用介面）
   - B 只改人會打的 Python 幾支，C++ 零件留舊規則
   - C 都不改，留大修
2. ~~（已裁：改檢查口徑）~~ **追蹤檔裡的本機路徑（B05／B06，gitignore 完整檢查第 ③ 項一直紅）怎麼處理？**
   - A 改檢查口徑：使用者自己寫的絕對路徑、帳本與信封 sender 不算違規（推薦：不動 C++，這些本來就不拿來解路徑）
   - B sender／ledger 改存相對 kernel stack（動 aos-util、aos-llm-kernel），使用者寫的照 A 放過
   - C 先不動，留大修
3. ~~（已裁：從範本拿掉）~~ **kernel 範本 `budget.senders` 的示範 `/tmp/aos-demo-sender` 每次起來印一行 warning，要不要拿掉？**
   - A 從範本拿掉，示範改寫在 kernel/docs/03（推薦）
   - B 留著
4. ~~（已裁：維持現狀）~~ **`$ref` 進來那份檔裡的相對路徑（exec、ws…）從哪算？**
   - A 不改：照舊從 daemon 的 cwd 算，訊息與文件已講清楚（推薦：已寫好的 daemon.json 不會壞）
   - B 改成從那份檔所在的資料夾算（對外語意變）
5. ~~（已裁：跳過那份，推薦被翻）~~ **`procs` 頂層 `$ref` 陣列其中一份讀不到時？**
   - A 照舊整台退 1（推薦：讀不到就不知道裡面有哪些名字）
   - B 那份帶的列都不起、其他份照起，加一行 warning
6. ~~（已裁：留大修）~~ **aos-lock 認主分不出同一工作區的兩方（B14）？**
   - A 留大修（推薦）
   - B 現在做：拿鎖回一個 token，放鎖要帶
7. ~~（已裁：不算，維持現狀）~~ **`defs dup` 分群要不要也看知識庫那格的 `env.AOS_KNOWLEDGE`？**（現在只看工具路徑，兩隻只差知識庫的 agent 會被分成同一群；不影響跑）
   - A 不看，維持現狀（推薦：dup 是比工具的）
   - B 看，只差知識庫也分兩群

## 這次改的記錄

- [next_todo.json](../10/two-machines/next_todo.json)：B12 自然消失、B19 已修、B22 註明排整理階段（open 剩 8）。
- SESSION-LOG：11-10 兩行「明天順序」與 aos-tools-cli done 行拿掉、two-machines／cli-sweep／templates-cp 合成一行只留待裁；11-11 各行「待 push」改成已 push（`23c9544d3`）。
- WAIT_USER：「兩台都重跑 install.sh」改成只剩家機（公司這台 `~/.local/bin/aos-mailbox`、`aos-clock-register` 11-11 已在）。

## 驗證

在 `23c9544d3`（這次只改記錄，程式沒動；impls 先增量 build 過，aos-daemon 重連結一次）逐夾跑全套：**58 夾 968 支，只紅既有 4 支**（aos-agent `test_daemon_down` 2、box_check 2），`templates/tests` 20 支 OK（2 skipped、2 expected failures）。knowledge_check 出廠庫 0 錯誤、41 warning；codemap 0 stale；wf-lint broken 56 與改之前一樣。

## 追加：17 的三題使用者裁了（11-11，頂層轉達選項框結果）

- 題 0（待裁 3）「從範本拿掉」→ `3f4bc4511`：kernel 兩份範本不帶示範預算、示範改寫進 kernel/docs/03 件 5（照抄實跑過）。
- 題 2（待裁 5）「跳過那份」→ `2d7984a24`：aos-daemon 讀 daemon.json 的程序清單時，`$ref` 陣列讀不到的那份跳過、一行 warning、其他照起；`$ref` 機制別處照舊。
- 題 1（待裁 4）維持現狀、不改程式，原話與 docs/05 補的那句見 [17 § 11-11 續記](../10/two-machines/17-B07到B10施工結果.md)。

改完再跑全套：在 `2d7984a24` 上 impls 重建（`nice -n 19`）後逐夾跑：**58 夾 970 支（多的 2 支是 test_two_machines 新的），只紅既有 4 支**；knowledge_check 0 錯誤、41 warning；codemap 0 stale；wf-lint broken 56 不變。

## 第二批：剩下四題也裁了（11-11，頂層轉達選項框結果）

| 題 | 使用者選 | 結果 |
|---|---|---|
| 1 旗標位置推到其餘指令 | 「全部改」 | ``c8e157fc6``：Python 只有一層的程式 `aos_flags.parse(..., anywhere=True)`（aos-mcp、aos-sandbox〔`keep=2`：PROG 起原樣〕、aos-clock、aos-sweeper、aos-eca-turn），子命令程式照 `sub="root"`（aos-eca-screen 的 `--eca` 寫在子命令前後都收；aos-feedback 自己拼的解析換成共用那套）；C++ 只改 aos-util `parse_cli` 一處（新參數 `keep`），零件全家跟著。P-44 續、knowledge（cli/flags、eca、mcp、sandbox、parts）、impls／cmd 文件跟著 |
| 2 追蹤檔本機路徑（B05／B06） | 「改檢查的標準」 | `545af5c54`：gitignore-check 放過使用者寫的絕對路徑（defs/、as_written、程式原樣抄的同一字串）、ledger、sender；不動 C++ |
| 6 aos-lock token（B14） | 「留大修」 | 不做，next_todo 標已裁 |
| 7 defs dup 看不看知識庫 | 「不算，維持現狀」 | 不做，templates-cp README 記已裁 |

**題 1 沒套用、照舊規則的**（語意衝突，不硬套）：
- 子命令程式的頂層（aos-post、aos-lock、aos-json、aos-llm）：解到子命令名為止，子命令那層才收（`aos-post --x send` 照舊 `FlagUnknown`）。頂層本來就沒有旗標，只是位置。
- `aos-exec XXX ARGS`：XXX 起原樣交給它（P-44 續題 3 原本就這樣）。
- `aos-json set`／`append`／`merge`：值什麼字都可以（`--str` 時 `-x`、`--check` 都是合法值），`檔#/指標` 後再認旗標會把值吃掉，所以旗標照舊寫在 `檔#/指標` 前（試過 keep＝2：`set --str F -x` 變成 `FlagUnknown`，舊寫法壞掉，退回）。
- 訊息與內容那類（say、history summarize／set、aos-mailbox send、aos-clock-register add）：使用者先前裁維持，沒動。
- agent-fsm 範本四格（idle、brain、act、wait）：loop 叫的、argv 固定、不是人打的；線 K 在動範本，避開。
- lib 給腦用的工具（tool_io 的 `--a.b` 旗標形）：不是 P-44 的命令列，沒動。

**題 1 代定**：
1. C++ `parse_cli` 加 `keep` 參數（`0`＝旗標前後都收，新的預設；`N`＝第 N 個位置參數起原樣），規則照 Python 的 `tool_io.tokenize_flags`：位置參數後、不認得又像負數（`-3`、`-.5`）或含空白的字照舊當位置參數；`--` 在位置參數前＝丟掉、之後＝連它原樣交出。
2. aos-loop／aos-daemon：設定檔後面的旗標現在收（以前報「flag must come before the config file」），那句錯誤拿掉；`CFG -- ARGS` 照舊。
3. aos-feedback：`--` 之後的字照舊原樣、`--` 本身拿掉（跟舊的自拼解析一樣）；改用共用那套後，PAIN 以 `-` 開頭又含空白也當位置參數。
4. aos-sweeper、gitignore-check 沒有位置參數，改不改都一樣；aos-sweeper 照改（一致），gitignore-check 沒動。

**題 2 代定與剩的**：判準見 [05-gitignore指南](../../../cmd/aos-agent/docs/05-gitignore指南.md) 末節。照新標準整棵實跑還命中兩種**程式自己算出的**絕對路徑——子 daemon 公開 state（`procs_state.json`、`state.json`）的 `daemon` 欄、kernel 在途信小格 `proc.json` 的 `exec`——不在使用者裁的三類裡，照舊算紅（B06 open）。

驗證：impls 重建後逐夾跑全套 **60 夾 986 支，只紅既有 4 支**（新 test_parse_cli 8，對舊版紅 5；test_flags_anywhere 8）；gitignore-check 整棵實跑兩次（照新標準剩上面那兩種命中）；knowledge_check 0 錯誤、41 warning；codemap 0 stale。

## 第三批：B06 剩的兩格也放過（11-11，使用者再裁「放過」）

子 daemon 公開 state（`procs_state.json`、`state.json`）頂層的 `daemon` 欄、kernel 在途信小格 `proc.json` 的 `exec`：程式自己記的絕對路徑，不算外洩。gitignore-check 只放過這兩格（同檔別格、`sk-` 金鑰照查）；新測試 `extras/gitignore-check/tests/test_leaks.py` 4 支；整棵實跑 shutdown／kill9 兩個時點命中 0、ALL CHECKS PASSED。next_todo B06 改已修。

