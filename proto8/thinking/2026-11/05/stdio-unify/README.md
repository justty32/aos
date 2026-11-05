# 三扇門與結束碼統一（stdio-unify）

← [2026-11-05](../README.md)｜[thinking](../../../README.md)

依據：盤點報告（桌面 `aos-三扇門與結束碼.html`，2026-11-05 盤點 56 支程式＋16 條不一致，各附推薦）。下面「#N」＝報告不一致清單第 N 條（照報告順序 1～16）。

## 使用者原文與裁定（11-05）

1. 退 0 時提醒能不能印 stderr →「可以，固定格式："error:", "warning:"後面接你那個」
2. 給腦用的工具出錯 →「統一 lib 契約 (Recommended)」
3. `--help` →「全都有」，並補「--help要輸出英文」
4. 子命令前不認得的旗標 →「FlagUnknown (Recommended)」

其餘 12 條照報告推薦；推薦不明確的由隊長照原則代定（下面「代定」，都可翻案）。

## 定下來的規矩（施工規格）

**R1 stderr 只有兩種行**（#1、#2、裁定 1）
- 錯誤行：`程式: error: 代號 原因`（例 `aos-post: error: MailboxMissing no mailbox at /x`）。
- 提醒行：`程式: warning: 句子`（不帶代號；取代報告推薦的 `note:`）。
- 退 0 可以有提醒行；**有錯誤行就不准退 0**。其他雜訊（「(…)」、`note:`、`attaching…`、無前綴的 log）一律改成提醒行或拿掉。
- 解析這行的地方（代號＝`error: ` 後第一個字）全部跟著改。
- 透明轉交（exec 交棒、照下層碼結束）不受影響：下層的 stderr 是下層的。

**R2 給腦用的工具出錯**（#3、裁定 2）：lib 契約——錯誤行在 stderr、stdout 各印一次（同一行，含 `error:`），退 1。aos-json/tools 照這個（不再 stdout 印 error 退 0）。被跑的指令自己退非 0 不算工具的錯；bash、run_python 都在**最後一行**寫 `[exit code N]`。

**R3 `--help`**（#4、裁定 3）：每支程式都認 `--help`（英文用法、印 stdout、退 0；放在旗標的位置就認，子命令後也認）。**不給參數**＝照常解析：該有參數卻沒給＝`ArgumentsBad` 退 1，不印說明；說明只在 `--help`。出錯訊息可以說 `see PROG --help`。

**R4 旗標與子命令**（#5、裁定 4）：`程式 [旗標] 子命令 …`；子命令前不認得的旗標＝`FlagUnknown`，子命令本身不認得＝`CommandUnknown`。

**R5 usage 位置**（#6）：錯誤行裡「原因在前、`(usage: …)` 在後」：`程式: error: ArgumentsBad missing CONFIG (usage: aos-fsm [FLAGS] CONFIG.json)`。

**R6**（#7）aos-eca-screen 改成 `aos-eca-screen open [--detach] ECA_DIR`（其他子命令同形），用 aos_flags.parse。〔11-05 隊長代定 D6：ECA_DIR 改旗標，因 aos-exec 動作接最後——現在是 `aos-eca-screen [--eca ECA_DIR] 子命令 [--detach]`，`demo/eca-claude/screen/_entry`＝`["aos-eca-screen", "--eca", ".."]`〕

**R7 驗不過**（#8）：aos-schema 照舊退 0（stdout 的 `valid:false` 就是答案）；aos-json check 有問題＝退 10（問題照舊一行一條印 stdout、stderr 空）——代定 D1。

**R8 轉交的碼**（#9）：不改數字；每支會轉交碼的程式（aos-exec、aos-tools call、aos-sandbox、aos-loop、aos-fsm、fake_slow…）README 寫一句：「退非 0 時 stderr 有 `我的名字: error:` 這行＝我錯；沒有＝下層的碼」。

**R9 10／11**（#10）：N-43 補 (a) 基礎工具的 10＝「查了，沒有」；(b) fsm 格的分岔碼是給 fsm 表看的，被表接住不算錯。

**R10 讀下層 stderr**（#11）：C-52 列明文例外表（出口給人或外部 agent 看：aos-mcp 給外部 agent 的錯、aos-agent 把 aos-daemon-ctl 的錯換成自己的、aos-llm-kernel 回信的 EndpointFailed 原因）。其他（aos-eca-turn、idle.py 拿 aos-post 的 stderr、cli_session 的 CLI stderr 尾巴、memory／self_tools 的末行）改成：下層的 stderr 原樣透出（不攔），自己只多寫一行自己的錯誤行——代定 D2：cli_session 這類給腦用的工具，透出的下層 stderr 只到 stderr，stdout 只有自己那一行。

**R11 代號與原文**（#12）：lib 的「stdin 不是 JSON」＝`ArgumentsBad stdin is not JSON`（不帶 Python 例外原文）；agents 少了 op＝ArgumentsBad，op 值不認得才 OpUnknown。

**R12 訊號**（#13）：子程式被訊號殺＝128＋N（fake_slow 照 aos-tools 換算）；Python 被 Ctrl-C 不吐 traceback、退 130（aos_flags.py 一個共用小函式；lib 用自己的共用處）。被 TERM 照現狀（有接的 128＋15）。

**R13 install.sh**（#14）：warning 改到 stderr、`install.sh: warning: …`；`note:` 一律 `warning:`；有 skip＝退 1 並補錯誤行 `install.sh: error: LinkFailed N names already taken by something else`——代定 D3。

**R14 過時文件**（#15）：`impls/docs/03-錯誤.md` 開頭改成 `程式: error: 代號 原因`、退 1；`io.hpp` 的 `emit_error` 刪掉（沒人用就刪；有測試小程式用就改成新格式）；N-43 的 trace.jsonl 改指 state 窗或 log。

**R15 表格與前綴**（#16）：給人看的表一律 TAB 分欄（aos-agent ls 改）；P-21 註明錯誤行開頭「可以是 agent 名」（demo agent-fsm 四格照舊用 `agent-fsm:`）。

## 代定（可翻案）

- D1 aos-json check 驗不過退 10（報告兩案：退 0 或退 10；選 10：它的 stdout 沒有像 aos-schema 那樣的 `valid` 欄，退 0 腳本就分不出；10 跟「沒東西」同一種意思＝查完了、結果否定）。
- D2 給腦用的工具：下層 stderr 透到工具 stderr，stdout 只有自己的錯誤行（腦只看 stdout，不會被下層雜訊淹）。
- D3 install.sh 有 skip 照舊退 1（使用者要的名字沒裝上＝沒做成），補錯誤行，代號 `LinkFailed`（10-23 命名：動作＋Failed）。
- D4 aos-loop 身體失敗那行改成錯誤行 `aos-loop: error: RunFailed run N: X failed with exit code C`（它接著照那個碼退出）；aos-daemon 身體失敗／好了（不退出）改成提醒行。
- D5 互動提示符（aos-agent chat 的 `> `）不算一行，照舊在 stderr；其他給人看的狀態句（attaching、watching）改提醒行。
- D6 aos-eca-screen 的 ECA_DIR 改成子命令前的旗標 `--eca`（見 R6 旁註；E 線收尾）。

- D6 aos-eca-screen 的 ECA_DIR 改成子命令前的旗標 `--eca DIR`（aos-exec 把動作接在入口 argv 最後，JSON 入口沒辦法把 `..` 排到動作後面；不用 sh）。
- D7 給腦用的工具（agents、self_tools、aos-json/tools 的 json、json_edit）把下層錯誤行的代號與原因接進自己那行（例 `self_tools: error: ToolExists …`）：腦只看 stdout，不這樣它不知道錯在哪。這算「給腦用的工具把下層錯翻成自己的錯」，寫在 lib/docs/01。
- D8 `[exit code N]` 退 0 也寫；被訊號殺寫 128＋N。
- D9 aos-loop 的 RunFailed 是錯誤行但碼是身體的（R8 的例外，README 與 N-43 續註明）；子命令前的 FlagUnknown 不附 `(usage: …)`。
- D10 install.sh 加 `ImplsMissing`（impls 一支都沒建）；ln 失敗改提醒行、併進最後的 LinkFailed 數字。aos-agent chat 中途印過錯誤行，stdin 結束時退 1。
- D11 aos-daemon 狀態窗寫不了那行也是提醒行（不退出就不寫錯誤行）。

## 使用者原則（11-05 傍晚）

「通常來說，改這種輸出格式，應該是很簡單的，我們人類在手寫程式的時候，都會盡量把這種常見的功能，統一成單一介面，這樣只需要改介面，那就能好。」

所以：錯誤行／提醒行／`--help`／結束碼的產生，每種語言收斂到一個共用介面，各程式不自己拼字串（寫進 [conventions](../../../../../wf/workflows/common/conventions.md)）。現況：
- C++：`aos-util` 的 `aos::fail`／`aos::warn`（`io.hpp`）、`parse_cli` 的 `--help` 與 `usage_error`（`cli.hpp`）；13 支都走它。例外：aos-daemon 子行程 fork 之後、exec 之前的 5 處 `fprintf`（`child/limits.cpp`、`child/child.cpp`；fork 後不能配記憶體，只能直接印）。
- Python：`proto8/bin/aos_flags.py`（`die`、`warn`、`error_line`、`split_line`、`run`〔Ctrl-C 130〕、`parse(help=…)`）；bin、extras、demo 的格都走它。lib/agent 的工具走 `lib/agent/agent_tool.py`。
- sh：install.sh、sandbox 的 setup.sh 各自 echo（獨立跑：裝之前、root 沙箱裡）。

## 做了什麼

照 R1～R15 改完 56 支（commit 都在 main，11-05）：
- C++ impls（A 線）`9b880578`、`f140b86a`：aos-util 加 `fail`／`warn`／`--help`／`usage_error`、刪 `emit_error`；13 個專案全部重建（15:17:04 起、15:30:50 完，全過）。
- Python 命令列與 install.sh（B 線）`1a85221b`、`3485eb6b`、`aba4aec8`、`b70f44d9`。
- lib 工具、demo、aos-json/tools（C 線）`3a91eaa2`、`988d0c6f`、`c1c1518b`、`c612c811`；demo 的格改走 aos_flags `85138f99`。
- 條文與知識庫（D 線）NORMS `91933c81`（N-43 拆出續篇）、CONVENTION `07421d3a`、CONCEPTS `4e119588`、knowledge `6c3e2338`（errors 改資料夾）、conventions `d6a6bec8`。
- 收尾（E 線）`3780eba5`：aos-eca-screen 照 D6、self_tools 照 D7、setup.sh、act.py 殘留。
- 實跑（WSL `/tmp/stdio-*`）：每支 `--help`（stdout 英文、退 0）、不給參數（ArgumentsBad）、`--bogus`（FlagUnknown）、`bogussub`（CommandUnknown）、典型錯都是新格式一行；抽查 aos-loop RunFailed 照身體碼、aos-json check 退 10、aos-post take 空信箱退 10、bash 退 3 → `[exit code 3]`、fake_slow 被 TERM 143、Ctrl-C 130 無 traceback、install.sh skip → LinkFailed 退 1。

## 剩下的

- demo 的格的 `--help`、Ctrl-C 還是各自寫（頂層腳本、沒 main 交給 `aos_flags.run`）。
- sh 兩支（install.sh、setup.sh）沒有共用函數檔，先算例外。
- 真腦沒跑；json_edit 給模型的 prompt 還是中文；install.sh 沒裝 aos-lua、aos-janet。

## 11-05 晚 lib 共用模組（使用者裁「收成共用模組」）

- 結果：`proto8/lib/tool_io.py`（`start`／`die`／`warn`／`arguments`／`workspace`）；lib/base 19 支、check_inbox、memory、self_tools、agents、pyfix、agent_tool.py 都改用它，各支不再自己拼錯誤行。lib/docs/01 規則 9 改寫成「共用開頭收在 tool_io.py；先找自己資料夾、再找 lib/」。
- 沙箱：bash-boxed 原本只綁 `inner`，改完實跑 `ModuleNotFoundError`；`sandbox.json` 的 `ro` 加 `../../../../lib/tool_io.py` 後通過（stdout `[exit code 0]`、壞 stdin＝ArgumentsBad）。
- 代定（可翻案）：L1 檔名 `tool_io.py`、放 lib 根（base 之下最底層，三層都能用）；L2 找的順序「自己資料夾 → lib/」，複製出 lib 的工具把它一起複製（實測：沒複製＝起不來、複製後通過）；L3 judge 也用、但 `echo=False`（不是給腦用的）；L4 cli_session.py（bin 的 aos-eca-turn 也 import）與 pyfix 子 agent 的格不收；L5 `sys.dont_write_bytecode`（不在庫留 `__pycache__`，沿 pyfix）。
