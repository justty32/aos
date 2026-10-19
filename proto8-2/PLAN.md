# proto8-2 實作計畫：把 CONVENTION 第十節做掉（2026-10-19，fable 規劃）

← [proto8-2](README.md)｜慣例：[CONVENTION.md](CONVENTION.md)（第十節＝要做的四項）｜原話：[thinking/ideas](thinking/2026-10-19-ideas.md)｜衝突裁定：[CONFLICTS.md](CONFLICTS.md)

四項：(1) inst 四種用法；(2) `tools/` 一個範例工具；(3) aos-exec 自己的錯退 1；(4) 單子指到 `$AOS_STACK` 底下的檔。這份只規劃、不寫程式；每條後面括號是依據（§ 幾＝ideas 原話段號、P-xx＝CONVENTION、C-xx／N-xx＝proto8）。proto8 本身一個字都不動。

## 一、三個關鍵決定

**1. aos-inst 不 import proto8、也不整檔複製——新寫一份小的。** 放 `bin/aos_inst.py`（Python 模組，純標準庫）＋ `bin/aos-inst`（三行可執行殼：`import aos_inst; sys.exit(aos_inst.main())`）。aos-loop／aos-fsm 跟它同一個資料夾，直接 `import aos_inst` 在行程內 `run()`（P-30：省得到的只有這種）。執行那一半（起子程式、等、逾時 SIGTERM→SIGKILL、轉訊號；proto8 `aos_inst.py` 的 `_run`／`_start`／`_wait`／`_stop`／`_stream`）原樣搬過來，解單子那一半重寫成一小段。
理由：proto8 的 `aos_inst.py` 綁著 `aos_cli.py`（TARGET `#/位置`、鏡射旗標、`$ref`、`AOS_DIRNAME`、stdin 當設定、N-12 JSON 串流）——那整套正是 CONFLICTS 1～3 已裁定不走的（§ 9「把鐐銬拿掉」）；引用它等於把鐐銬又拿回來，整檔複製等於養兩份一樣的鐐銬。proto8-2 要的只有 P-30 列的四樣。（C-56 KISS；§ 7「可選、想簡單就 shell、複雜才用這套」）

**2. 單子的 key 名照 proto8，但兩個地方照 proto8-2 的規矩。** 認得的 key：`argv`（必填）、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`stdout_append`、`stderr_append`、`timeout_ms`、`grace_ms`（沒寫 2000）；其他 key 一律忽略（N-04、C-48）。差異：
- **沒寫的串流接呼叫者的**（proto8 是接 `/dev/null`、要寫 `*_inherit`）。因為 proto8-2 的 stdout 不是 aos-inst 的 JSON 結果通道（CONFLICTS 3），格的錯要讓人在終端看得到（P-21、拍板點 3「人來看」）。寫了路徑就寫檔，寫什麼就做什麼（C-56）。
- **命令列的結束碼＝子程式的碼**（透明轉交，N-43 唯一允許的例外、同 tasks），不另吐結果 JSON。因為 proto8-2 的 loop／fsm 就是看結束碼走（P-19、CONFLICTS 4）；aos-inst 自己退 0 會把 brain.py 的失敗吞掉。aos-inst 自己的錯（單子壞、程式找不到、`$env` 變數沒設）退 1、stderr 一行 `aos-inst: 原因`（N-43、P-04 同款）。
- 結構化結果 `{"code", "signal", "timed_out", "pid", "ms"}` 由 `run()` 回給行程內的呼叫者（aos-loop／aos-fsm）；aos-fsm 把它一拍一行寫進 `$AOS_STACK/trace.jsonl`（下面步 5）。
這兩處跟 proto8 `lib/inst.md` 不同，屬「proto8 原則 ↔ 今天」那類，§ 9 已一律裁定走今天的，不再問；P-28 改成指 proto8-2 自己的說明，不再指 proto8 inst.md 當語意出處。

**3. 第 (4) 項的拼接寫法：`{"$env": "AOS_STACK", "path": "plan"}`。** 意思＝「那個環境變數指的資料夾底下的 `plan`」，照 `os.path.join` 接（`AOS_STACK` 結尾有 `/`、`AOS_WS` 沒有，join 兩種都對；`path` 寫絕對路徑就是絕對路徑，照 join 本來的規矩，不另發明）。只有 `$env` 一個指示詞；`$ref` 不做（N-45「設計不靠 `$ref`」；P-30 單子本來就能內嵌，不必拆檔）。變數沒設＝aos-inst 自己的錯、退 1。
理由：N-45 定 `$env` 可當正式機制、原例子就是 `"cwd": {"$env": "AOS_WS"}`；加一個同層 key 是 C-48／C-55「值長成物件、同層加屬性」的既有長法；不用 `"$AOS_STACK/plan"` 字串內插——那是把規則埋進字串裡的暗規則（C-56「寫什麼就做什麼」，10-16 否決過 `"cwd": "WS"` 字面替換）；也不用 `"+"`——純字串相接要人記哪個變數結尾有沒有 `/`。

## 二、每項怎麼做

### (3) aos-exec 自己的錯退 1 ← P-04

- 動：`bin/aos-exec` 的 `die()` 改 `exit 1`（所有 `|| exit 2` 一併改 1）。入口本身的碼照舊透明轉交（`exec`）。
- 測：`tests/test_proto8_2.py` 的 `test_missing_entry`、`test_not_executable` 改期望 1。
- CONVENTION：P-04 刪「現為結束碼 2，見第十節」；第十節第 1 條劃掉。README 的 aos-exec 條「結束碼 2」改 1。

### (1A)＋(4) `bin/aos-inst`：跳過 `#!`、`$env`、透明轉交 ← P-28 (A)、P-30、第十節第 2、4 條

- 新增：`bin/aos_inst.py`、`bin/aos-inst`。
- 介面：`aos-inst FILE [args...]`。讀 FILE 全文，第一行是 `#!` 開頭就丟掉那一行，剩下 `json.loads`；多的 args 接在 `argv` 後面（像 shebang 腳本收參數；P-26 args 原樣送到）。單子裡任何位置的 `{"$env": 名}`／`{"$env": 名, "path": 子路徑}` 先換成字串再驗 key。相對路徑基準：`cwd` 從呼叫者的 cwd 算（aos-exec 已 `cd DIR`，所以就是定義資料夾，CONFLICTS 2）；`stdin`／`stdout`／`stderr` 從解出來的 `cwd` 算（照 proto8）。
- 模組 API：`parse(doc, base)`→填好的 dict、`run(doc_or_path)`→結果 dict（子程式回幾號、被逾時收掉都算正常跑完）、`main(argv)`→退出碼；單子有問題丟 `InstError`。
- (A) 的樣子：`.aos/exec` 第一行 `#!/usr/bin/env aos-inst`、第二行起 JSON，`chmod +x`。kernel 會以 `aos-inst ./.aos/exec` 起它，cwd＝定義資料夾，PATH 裡有 `bin/`（P-03），不必 `env -S`、沒有旗標。
- 測（新檔 `tests/test_inst.py`）：`argv` 跑起來、結束碼透明轉交（子程式退 7→7、退 10→10）、自己的錯退 1 且 stderr 一行（單子不是物件、`argv` 缺、程式找不到、`$env` 變數沒設）、`timeout_ms` 到了收掉（`run()` 的 `timed_out` 為 true、命令列退非 0）、`stdout` 寫路徑→檔有內容、`stdout_append`、沒寫串流＝接呼叫者的（stderr 看得到子程式的話）、`#!` 行被跳過、整個 (A) 入口經 `aos-exec` 跑通、`$env`＋`path` 對 `AOS_STACK`（結尾有 `/`）與 `AOS_WS`（沒有）都接對、不認得的 key 被忽略、args 接在 argv 後面。
- CONVENTION：P-28 (A) 標已做並改指本檔第一節的 key 表；新增 **P-31**（§ 八）：單子要指到 stack／工作區的檔寫 `{"$env": "AOS_STACK", "path": "…"}`，只有 `$env`、沒有 `$ref`；第十節第 4 條劃掉、第 2 條改成只剩 (B)(2)。README「原型怎麼跑」加 `bin/aos-inst` 一條（key 表、兩處差異）。

### (1B)＋(1) aos-exec 認 `.aos/exec.json`、小殼寫法 ← P-28 (B)(1)、P-01、P-03

- 動：`bin/aos-exec` 找入口改兩段：`$dir/$entry` 存在→照舊要求可執行、`exec` 它；不存在但 `$dir/$entry.json` 存在→`exec aos-inst "./$entry.json" "$@"`；兩個都沒有→退 1「入口不存在：DIR/.aos/exec（也沒有 .aos/exec.json）」。可執行檔優先（兩個都在就用 `.aos/exec`，不報錯——C-53 誤用不歸組件管）。`$AOS_ENTRY` 改了名就找 `$AOS_ENTRY.json`，同一條規則。
- (1) 小殼不用寫程式：`.aos/exec`＝`#!/bin/sh` ＋ `exec aos-inst .aos/exec.json "$@"`，旁邊放標準 JSON 的 `.aos/exec.json`。(1)、(B) 都是 (A) 的等價寫法，不另給範本（P-29），只各補一個測試。
- 測（`tests/test_proto8_2.py`）：只有 `.aos/exec.json` 的資料夾跑得起來、args 透傳、結束碼透傳；小殼 (1) 跑得起來；兩個都沒有→退 1、訊息提到 exec.json；兩個都在→用可執行檔。
- CONVENTION：P-01「必須是可執行檔」改「可執行檔，或旁邊的 `$AOS_ENTRY.json` 單子」（§ 7「AB 都可以」）；P-03 五件事裡「exec 入口」補「或交給 aos-inst」；P-28 (B)(1) 標已做。README aos-exec 條同步。

### agent-bob 的 think 改 (A) ← P-29「範本先給 (A)」、P-22、P-24

- 動：`demo/agent-bob/fsm/think/.aos/exec` 改成兩段：
  ```
  #!/usr/bin/env aos-inst
  {"argv": ["python3", "brain.py"],
   "stdout": {"$env": "AOS_STACK", "path": "plan"},
   "timeout_ms": 120000}
  ```
  `brain.py` 吸收原本 shell 做的事：挑 inbox 檔名排序最前面的一題（P-12）、題名寫 `$AOS_STACK/current`、沒設 `AOS_BRAIN_URL` 就印假答案、有設就問模型（P-23），答案印到 stdout——重導到 `plan` 的那一步由單子做（原本 shell 的 `>`）。沒設 `AOS_STACK`＝`$env` 找不到→aos-inst 退 1，訊息含 `AOS_STACK`。
- 其他格（入口、fsm、idle、act）照舊 shell：整隻 agent-bob 仍然是 shell 版、`sh demo/run.sh` 與既有測試全部照跑——這就是「保留 shell 版能跑」。think 的 shell 寫法留在 CONVENTION § 八的範例裡當對照（原檔靠 git 歷史）。
- 測：既有 `test_demo_flow`、`test_two_workspaces_concurrently`、`test_bob_state_in_stack_not_ws_or_def` 不改期望、要照樣綠；`test_bob_requires_stack` 的 think 那條改成「退非 0 且 stderr 含 `AOS_STACK`」；加一條：think 的 `.aos/exec` 不是 sh、直接 `exec` 也跑得起來（跟 `test_bob_entry_direct_exec_no_enoexec` 同款）。
- CONVENTION：P-27 改「標準範本＝shell 版；agent-bob 是標準，其中 think 這一格示範 (A)」；P-29 改指實際檔；§ 八範例 (A) 換成實際內容；第二節佈局 `fsm/think/.aos/exec` 那行補「(A) 單子」。README demo 條同步。

### (1-2) `bin/aos-fsm`、aos-loop 內嵌單子、`demo/agent-ann` ← P-28 (2)、P-06、P-07、P-19、第十節第 2 條「aos-fsm 的 state 落在 `$AOS_STACK`」

- `bin/aos-loop`：`run` 可以是字串（子資料夾，照舊 `aos-exec`）或物件（單子，行程內 `aos_inst.run()` 取 `code`）；結束碼規則不變（P-19）。自己的錯（檔讀不到、不是 JSON）退 1、stderr 一行 `aos-loop: …`，不噴 traceback。
- 新增 `bin/aos-fsm FSM.json`（Python，import aos_inst）：
  ```json
  {"start": "idle",
   "states": {"idle":  {"val": "idle", "next": "think"},
              "think": {"val": {"argv": ["python3", "brain.py"], "timeout_ms": 120000}, "next": "act"},
              "act":   {"val": "act", "next": "idle"}}}
  ```
  一拍：沒設 `AOS_STACK`→退 1「aos-fsm: 沒設定 AOS_STACK」；讀 `$AOS_STACK/state`（沒有＝`start`）；查格（查不到＝自己的錯退 1）；`val` 字串＝`aos-exec <它>`（相對路徑從 cwd 算，N-36 10-16 版）、物件＝行程內 `aos_inst.run()`；在 `$AOS_STACK/trace.jsonl` 追加一行 `{"state", "code", "signal", "timed_out", "ms"}`；結束碼 0 才把 `next` 寫進 `$AOS_STACK/state`，然後以那格的碼退出（10 原樣往上、其他非 0 原樣往上、狀態都不動——P-07、P-20）。**state 檔跟 shell 版同一個檔、同一格式**（純文字一行狀態名），人看的地方不變、shell fsm 與 aos-fsm 可以互換（P-16 stack 內自由，本稿定）。不做 `end`（停靠 10，P-19）、不讀格的 stdout（P-09 只看結束碼，跟 proto8 N-37 讀 `next` 不同——CONFLICTS 4 同一件事，走今天的）、不轉述格的錯（P-21）。
- 新增 `demo/agent-ann/`：跟 bob 做同一件事（一題一答），佈局攤平、用 (2) 寫：
  ```
  agent-ann/
    .aos/exec      #!/bin/sh、exec aos-loop loop.json
    loop.json      {"run": {"argv": ["aos-fsm", "fsm.json"]}, "max": 20}     ← loop 內嵌單子
    fsm.json       上面那份                                                    ← fsm 內嵌 think 單子
    idle/.aos/exec、act/.aos/exec   跟 bob 的一樣（shell）
    brain.py       跟 bob 的同一份（複製）
  ```
  三個小檔重複是 demo 的代價，不跨 agent 互指（P-25 地址在自己資料夾裡）。
- 測（新檔 `tests/test_fsm.py`）：state 檔落在 stack、格退 10→fsm 退 10 且 state 不動、格失敗→原碼且 state 不動、字串格走 aos-exec、物件格行程內跑且 `timeout_ms` 有效、`trace.jsonl` 一拍一行、沒設 `AOS_STACK` 退 1、`$env` 在 fsm.json 的單子裡也會解；`tests/test_proto8_2.py` 加 loop 內嵌單子一條、`test_demo_flow` 同款跑 agent-ann（out／done／state 都對、定義資料夾乾淨）。`demo/run.sh` 加跑 agent-ann 一次。
- CONVENTION：P-06 `run` 補「或一張單子」；P-07 補 aos-fsm 版與 `fsm.json` 形狀、`trace.jsonl`；P-28 (2) 標已做；§ 八範例 (2) 換成 agent-ann 實際檔、刪「aos-fsm 還沒接 `$AOS_STACK`」；第十節第 2 條全部劃掉。README 加 `bin/aos-fsm`、`demo/agent-ann` 兩條。

### (2) `tools/stamp/`、act 用它 ← P-17、P-25、P-26、第十節第 3 條

- 新增 `demo/agent-bob/tools/stamp/.aos/exec`（shell）：stdin 原樣印到 stdout，最前面加一行 `# <UTC 時間>`；每用一次把 `$AOS_STACK/runs` 加 1（示範工具有自己的 stack、留著給人看）。不碰工作區（P-25：要不要碰是工具自己的事，這個不碰）。
- 動 `demo/agent-bob/fsm/act/.aos/exec`：先 `sub=$AOS_STACK/stamp/`，再 `AOS_STACK=$sub aos-exec ../../tools/stamp < "$AOS_STACK/plan" > "$AOS_WS/out/$name" || exit 1`，之後照舊搬題到 done/。`../../` 是 P-25「相對路徑、不靠 PATH」的代價：tools 放在 agent 資料夾底下，格從自己所在的位置指過去。子 stack 先算進變數、別靠 `VAR=x cmd < $VAR` 的展開順序。
- 測：單獨 `aos-exec tools/stamp`：stdin→stdout 第一行 `# `、第二行原文、`$AOS_STACK/runs` 為 1、再跑一次為 2；bob 整圈後 `out/q.txt` 第一行 `# `開頭且含題目、`$AOS_WS/.aos/stamp/runs` 存在、`.aos/` 根下沒有 `runs`（子 stack 分開）、定義資料夾乾淨。
- CONVENTION：第二節佈局 `tools/<名>/` 刪「原型還沒有」、寫 `tools/stamp/`；P-17 例子補 act→stamp；第十節第 3 條劃掉。README demo 條補 act 經 stamp。

## 三、順序（每步一個 commit、測試全綠）

| 步 | 做什麼 | 相依 | 做完的樣子 |
|---|---|---|---|
| 1 | aos-exec 錯退 1（上面「(3)」） | 無 | `aos-exec 不存在的資料夾` 退 1；18 個測試綠；P-04 乾淨、第十節剩三條 |
| 2 | `bin/aos_inst.py`＋`bin/aos-inst`：`#!` 跳過、`$env`＋`path`、透明轉交（「(1A)＋(4)」） | 無 | 手寫一個 `#!/usr/bin/env aos-inst` 入口、`aos-exec` 它跑得起來；`test_inst.py` 綠；P-31 寫好、第十節第 4 條劃掉 |
| 3 | aos-exec 認 `.aos/exec.json`；小殼 (1) 測試（「(1B)＋(1)」） | 2 | 只放 `exec.json` 的資料夾跑得起來；P-01／P-03 改好；第十節第 2 條剩 (2) |
| 4 | agent-bob think 改 (A)、brain.py 吸收挑題 | 2 | `sh demo/run.sh` 照舊印出答案；bob 既有測試不改期望全綠；§ 八範例 (A)＝實際檔 |
| 5 | `bin/aos-fsm`、aos-loop 內嵌單子、`demo/agent-ann`（「(1-2)」） | 2 | `aos-exec demo/agent-ann ws` 一題一答、`ws/.aos/state`＝idle、`trace.jsonl` 四行；`test_fsm.py` 綠；第十節第 2 條劃完 |
| 6 | `tools/stamp/`、act 用它（「(2)」） | 無（只有 shell，可插隊到任何時候） | bob 的 `out/q.txt` 第一行是時間戳；`ws/.aos/stamp/runs`＝1；第十節整節空、改成一句「已全部做完（10-xx）」 |

每步 commit 前：WSL `python3 -m unittest discover -s proto8-2/tests` 全綠、`sh proto8-2/demo/run.sh` 跑通、`bash wf/tools/wf-lint.sh proto8-2` broken=0；README「原型怎麼跑」那段跟 bin／demo 同步（proto8-2 的逐檔表就是 README，鐵律 3 在這裡落在它身上）。步 4、5 完成後在 wf SESSION-LOG 的 proto8-2 open 條把「inst 四用法程式」拿掉；步 6 後把「tools/」「aos-exec 錯誤碼」也拿掉。

## 四、CONVENTION 要同步的條（彙整）

- 步 1：P-04；第十節 1。
- 步 2：P-28 (A)、新 P-31；第十節 2（部分）、4。README 加 aos-inst。
- 步 3：P-01、P-03、P-28 (B)(1)；第十節 2（部分）。
- 步 4：P-27、P-29、第二節佈局 think 行、§ 八範例 (A)。
- 步 5：P-06、P-07、P-28 (2)、§ 八範例 (2)；第十節 2（劃完）。README 加 aos-fsm、agent-ann。
- 步 6：第二節佈局 tools 行、P-17 例子；第十節 3。全做完後第十節改一句話，README 現況段「程式還沒照它改的地方列在它第十節」改掉、指回本檔當紀錄。

## 五、要使用者決定的

沒有。四項都能從原話與已裁定的六條推出來。兩處差點要問、但 ideas § 9「剩下都用今天的做法」已經涵蓋，列在這裡只是讓他知道、要翻隨時翻：

1. proto8-2 的 aos-inst 跟 proto8 的 `aos inst` 同名、單子 key 同名，但「沒寫的串流接呼叫者的」「結束碼＝子程式的碼」兩處不同（第一節決定 2）。拿 proto8 `lib/inst.md` 來寫 proto8-2 單子的人會踩到這兩處；對策是 P-28 不再指 proto8 inst.md 當語意出處。
2. aos-fsm 只看格的結束碼、不讀格 stdout 的 `next`（P-09），跟 proto8 N-37 相反——CONFLICTS 4 的延伸，同一條裁定。
