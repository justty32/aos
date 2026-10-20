# 2026-10-19 重寫順序：daemon、kernel、tasks、tick、工具呼叫

← [討論紀錄](README.md)｜原則：[CONCEPTS](../CONCEPTS.md)、[NORMS](../NORMS.md)、[CONVENTION](../CONVENTION.md)｜待定：[NORMS/08](../NORMS/08-待定.md)｜程式：[bin](../bin/README.md)、[demo](../demo/README.md)｜舊實作：git aa2fec1f（`git show aa2fec1f:proto8/lib/README.md`）

使用者原話（10-19）：「請 fable 先讀過 proto8 的原則，再排出重寫順序（daemon、kernel、tasks、tick、工具呼叫），只把衝突帶給我。」

這份是 fable 通讀 CONCEPTS、NORMS、CONVENTION、bin／demo 說明之後排的順序與結論。前一節是要使用者看的；後面各塊照原則自己定了，使用者裁定後裁定寫回這裡。

## 要你看的（衝突與方向問題）

共五題。沒列出來的地方，原則都推得出答案，寫在下面各塊裡。

### 1. 「跑幾圈」「身體」這兩個 key 各有兩個名字（原則之間的衝突）

daemon 的規範 N-28 說 daemon.json 是 loop.json 的嚴格超集、同名 key 同義，它用的名字是 `times`（跑幾次）和 `inst`（身體）；窗的 N-06、N-07 也寫 `times`，你 10-19 說這些名字「要寫回去，以後重寫的時候這個還會用到」。可是現在跑得動的 aos-loop（P-06，你定了「agent-bob 現在的形狀就是標準」）同一件事叫 `max` 和 `run`。C-54 說同一個詞在全體系要同義、一次記住。

例子：寫一份 daemon.json，daemon 自己跑幾拍叫 `times`，它底下子 loop 的設定卻叫 `max`，同一份檔裡兩個名字講同一件事。

後果：選 `max`／`run`，程式一個字不動，N-06、N-07、N-28 條文裡的 `times`、`inst` 改字（`interval_ms` 沒有對手，照留）。選 `times`／`inst`，aos-loop、兩隻 demo、測試、P-06、bin README 全部改名。

推薦：`max`、`run`，跟著跑得動的程式走。

→ **已定（10-19 晚，[ideas § 22](2026-10-19-ideas.md)）**：使用者「那就用到最新的吧」＝`run`／`max`；N-06、N-07、N-11、N-28 已改字，`interval_ms` 等照上面「日後當 loop 的選填 key 長出來」。

### 2. tasks（seq／par／if）在新做法下還要不要做（方向問題）

10-15 你說 tasks「地位等同於 C 語言的 stdlib」（CONCEPTS § tasks、N-34）。10-19 之後入口和格可以是 shell 檔，而 shell 本來就有這三樣：`aos-exec a && aos-exec b` 是 seq、`aos-exec a & aos-exec b & wait` 是 par、`if aos-exec c; then …; fi` 是 if。你 10-12 也說過「aos seq 那些流程控制的東西，很多其實都是不必要的」。C-56 最後一步要把多餘的清掉。

剩下的價值只有一樣：單子是資料、能內嵌進 fsm.json（你 10-19 說這塊「很好用」）。想在一格裡寫「先跑這兩張單子、再跑那張」，用 shell 就得開資料夾。

後果：做，就是三支幾十行的 bin 指令，只收 JSON 格清單（格的寫法跟 fsm 的 `val` 一樣）；資料夾程式之間的組合一律寫 shell。不做，N-34 和 C-41 那段改成「shell 就是 stdlib」。

推薦：做，但只做 JSON 版，排在 daemon 前面——par 要的「整群一起收」跟 daemon 共用同一段程式。

### 3. LLM kernel 要看 token 用量，但它看不到（需求跟原則的衝突）

你 10-15 定 LLM kernel「根據 token 消耗量是否見底來看看說要不要擋」。10-19 起結束碼是唯一訊號、kernel 跑一封信只看到碼（C-52 不偷看下層；N-37 讀 stdout 已作廢）。腦問完模型拿到的 `usage` 在腦的程式裡，kernel 拿不到。

例子：三隻 agent 共用一顆腦，kernel 排完隊讓它們跑，一天下來只知道跑了幾次，不知道燒了幾個 token。

後果：要 token 數就得開一條明的通道——kernel 跑信時給一個環境變數 `AOS_KERNEL_REPORT`，指向這封信小格裡的一個檔；腦願意的話把 `usage` 寫進去（brain.py 多三行，P-23 加一句）；沒寫就只算次數。不開通道就只能數次數。

推薦：開通道，額度同時認 `calls` 和 `tokens` 兩個上限；第一版 demo 用假腦，只驗次數。

### 4. 工具呼叫被 NORMS 待定「方向問題甲」擋住一半（待定點名）

腦回 `tool_calls` 之後，agent 要有一格把每個呼叫變成 `aos-exec tools/<名>`。這格是通用程式，不會一個工具一個寫法，所以它得用機器看得懂的方式知道「參數怎麼進、結果怎麼出」。這正是待定「agent 當工具時題目怎麼交」——預設 (a)「呼叫方照被叫者自己的說明備題」，到這裡「說明」得變成一個檔。

推薦：每個工具資料夾放 `tool.json`：給模型看的 `description`、`parameters`（OpenAI tool 的 function 物件，照外部 API 原樣、不重寫；名字＝資料夾名，C-54），再加一格 `input`：`stdin`（預設；參數 JSON 從 stdin 進、結果從 stdout 出，stamp 這種）或 `inbox`（參數寫成題目放它的 `ws/inbox/`、答案從 `ws/out/` 拿，cathy 這種，就是 P-32）。這等於把 (a) 落成「說明＝tool.json」，不把 inbox 定成共同形狀（你說「inbox 先不管」）。你若不想在這裡定，工具呼叫第一版就只做 stdin 那種。

### 5. NORMS/08 兩條舊帳，daemon 動工時順手結（不擋）

「argv[0] 程式不自己 setsid」跟 P-36「單子起的程式自成行程群組」不衝突：P-36 的群組是叫的人（aos-inst）給的，N-41 已經寫了「格自己不 setsid」。建議結案、刪那條。「ctl `seq`／state `ctl_seq` 回音」：daemon 重寫照 N-14、N-33 寫就有，不另決定。kernel 的三條待定（公告、`_metainfo` 通用寫法、錯誤路徑評估）第一版都用不到，不擋。

→ **已定（10-20，[ideas § 25](2026-10-19-ideas.md)）**：使用者「照預設」＝setsid 那條結案刪掉、ctl seq 回音保留；daemon 已在 `proto8/bin` 重寫。

## 順序（一行）

tick → 腦的工具呼叫 → tasks → daemon → LLM kernel → 通用 kernel。前兩塊只靠現有的 bin、各自幾十行、各有能跑的 demo，使用者最快能試；tasks 跟 daemon 共用「整群收」那段程式；兩種 kernel 要 daemon 把 agent 和 kernel 同時跑起來才有東西看，所以最後。

## 各塊

### ① tick

做什麼：bin 指令 `aos-tick FILE`——讀回合數、寫 n＋1（先寫暫存再改名，N-05）；FILE 不在＝0；內容壞退 1、stderr 一行。節奏不在它身上，由 loop／daemon 拍（C-44 時鐘只是時鐘；10-12 決定「節奏、停、只走 N 回合交給 daemon」）。做成 bin 指令而不是資料夾程式：三十行、沒狀態，跟 aos-inst、aos-fsm 同是 C-45 的糖；時鐘檔放哪由拍它的人在單子裡寫，例 `{"argv": ["aos-tick", {"$env": "AOS_STACK", "path": "tick"}]}`（P-31 的 `$env` 在 argv 裡也能用），要給大家看就把那個 stack 放在大家讀得到的地方（C-67）。

依據：C-05、C-44、N-01、N-05、N-43、C-45。從舊程式拿：`aos_tick.py` 的讀寫那段。

完成的樣子：`demo/tick/`（loop.json 內嵌單子拍 `aos-tick`、`max` 5）跑完時鐘檔是 5；測試三個（從 0 起、接著加、壞內容退 1）。

### ② 腦的工具呼叫

做什麼：agent-bob 範本加一格 `tool`，三態變四態 idle→think→tool→act（表明寫，P-08）。brain.py 讀 `tools/*/tool.json` 組成 tools 送給腦，回覆連 `tool_calls` 一起寫進 `$AOS_STACK/history.jsonl`（對話在 stack 累積，C-46）。tool 格（`tool/.aos/exec`）：讀最後一則 assistant 的 tool_calls，每個開小格 `AOS_STACK=$AOS_STACK/<名>/ aos-exec tools/<名>`（P-17），照 `tool.json` 的 `input` 餵參數、收結果，寫成 `tool` 訊息接回 history；工具非 0＝那格失敗、agent 停（P-20、P-35）。沒有 tool_calls 時 tool 格退 0 直接過。think 再被拍時帶著 history 問，直到腦不再叫工具、寫 plan。工具在 agent 根下的 `tools/`，因為 think 是內嵌單子、cwd 是 agent 資料夾（P-33）。

依據：C-19、C-42、C-46、C-52、C-61、P-17、P-25、P-26、P-33；第 4 題。從舊程式拿：`aos_agent_lib.py` 的 think／tool 兩段（tool specs 怎麼組、還沒回的 tool_calls 怎麼挑）。

完成的樣子：agent-bob 多一個 `tools/clock/`（印 UTC 時間、`tool.json` 說它吃 stdin）；假腦看到題目含「幾點」就回 tool_calls、第二輪回答案；demo 跑通；測試四個（有／無 tool_calls、工具失敗停住、history 接法）。

### ③ tasks

做什麼：`aos-seq FILE`、`aos-par FILE`、`aos-if FILE`。FILE 是 JSON：seq／par 是 `{"items": [格…]}`，if 是 `{"cond": 格, "then": 格, "else": 格}`（else 選填）；格＝字串（子資料夾，`aos-exec` 它）或物件（單子，行程內 `aos_inst.run()`），跟 fsm 的 `val` 同一套（C-48 沿用格式族、不開新格式）。只看結束碼（N-34）：seq 第一個非 0 就停、以那個碼退；par 全起、等全部、任一非 0 就以第一個非 0 退，還在跑的整群收掉（P-36）；if 看 cond 的碼，0 走 then、非 0 走 else，退分支的碼。10 一律原樣往上（透明轉交，N-43）。自己的錯退 1。

依據：C-41、N-34、N-43、C-48、P-36；第 2 題。從舊程式拿：`aos_seq`／`aos_par`／`aos_if` 的流程（各三十行）。

完成的樣子：`demo/tasks/`（fsm.json 一格內嵌 `aos-seq`、一格 `aos-par`）跑通；測試六個。做 par 時把 aos_inst「起子程式、整群收」那段拆成 `start()`（不阻塞、回句柄），④ 直接用。

### ④ daemon

做什麼：`aos-daemon DAEMON.json`。daemon.json＝loop.json 的超集（N-28）：`run`（選填，自己每拍串行跑的身體）、`max`、`interval_ms`、`ctl`、`state`、`children`、`policies`、`adopt`。每拍：讀 ctl（N-06～N-08）、跑身體、對 children 名單（起少掉的、收多出來的，N-54）、收屍、寫 state（含 children 表與心跳，N-17、N-32）。children 每項是一份 loop 設定（內嵌或路徑）；是資料夾程式就包成 `{"run": "<絕對路徑>"}`（N-28「沒 inst 有 argv 就包成跑一次」的新版；它的入口本來就是自己的 loop，暫停＝不再起下一次，N-07）。每個子項給小格 `$AOS_STACK/<id>/`（P-17，取代 N-28 的 `work_dir`），daemon 把合好的 loop.json 寫進小格、填上 `ctl`／`state`、再 `aos-loop` 它；子 loop 的 stdout 丟掉、stderr 出錯時 append 到小格的 `stderr`（N-28 方案 B）。`adopt` 照 N-28。收工：收到 SIGTERM 先收子項、寫好 state 再結束，碼非 0（P-36 慣例）。

aos-loop 跟著長三個選填 key：`interval_ms`（每圈之間睡多久，沒寫＝0、就是現在的行為）、`ctl`、`state`（窗的檔名，放 `$AOS_STACK`；沒寫就不開、不提醒，N-09、N-13）。agent-bob 一個字不改。aos-loop 的一拍拆成模組 `aos_loop.py`，daemon 用同一段。

依據：C-36、C-04、C-64、N-06～N-09、N-11、N-13～N-17、N-28、N-32、N-33、N-54、P-17、P-36；第 1、5 題。從舊程式拿：`aos_daemon_table.py` 的 children 六態、接回（pid＋啟動時間）、`child_exit` 策略格；`aos_ctl_state.py` 的 ctl 解析、state 骨架、心跳。

完成的樣子：`demo/daemon/`——一個 daemon 管三個子項：tick（每秒）、agent-bob、agent-ann；跑十秒印時鐘數；改 ctl 暫停 tick 看它停；SIGTERM 收工後沒有殘留行程、stack 樹乾淨。測試約十個。

### ⑤ LLM kernel

做什麼：兩支。`aos-gate FILE`：FILE 是一張單子加私有 key `priority`（C-48 私有 key；形狀照 [10-15 LLM kernel 稿](2026-10-15-llm-kernel.md)：純值或 `{"level", "deadline"}`）。信箱位置從環境變數 `AOS_KERNEL` 來（kernel 的慣例、不是 aos 的三個變數，像 `AOS_BRAIN_*`，呼叫方在叫它那一行綁，P-39）。閘門把單子寫成一封信丟進信箱 `new/`（Maildir，N-16），等回信，把回信裡的 stdout／stderr 原樣吐出、以單子的碼退；排隊等多久由包它的那格 `timeout_ms` 守；收到訊號撤信。`aos-kernel-llm KERNEL.json`：一拍一次身體，給 aos-loop／daemon 拍——認領 `new/`→`cur/` 最該跑的一封（level → deadline → 等了幾拍 → 先來先上）、`aos_inst.run()` 跑（stdout／stderr 落在信的小格）、回信、刪；額度在自己的 state 窗（第 3 題）。agent 這邊：think 那格的單子改成 `{"argv": ["aos-gate", "brain.json"], "stdout": plan, "timeout_ms": …}`，`brain.json` 是原來的 `python3 brain.py` 單子加 `priority`；agent 不知道有 kernel（C-20）。

依據：C-09～C-12、C-20、C-38、C-47、N-42、N-16、N-30、C-48、C-52；10-15 LLM kernel 稿已定的六條照用。從舊程式拿：`aos_gate.py`、`aos_mailbox.py`、`aos_kernel_llm.py`（排序、deadline、aging、額度），去掉 aos_cli 與 JSON 串流那層。

完成的樣子：`demo/kernel-llm/`——daemon 管 kernel loop（`slots` 1、`interval_ms` 200）＋三隻 agent-bob（假腦 sleep 兩秒、一隻 `high`），三題同時丟；看 kernel state 的服務順序（high 先）、每隻 agent 照樣拿到答案。測試約八個。

### ⑥ 通用 kernel

做什麼：`aos-kernel-general KERNEL.json`，身體骨架同 ⑤，排序那步換成問判官。判官＝表上一格（資料夾程式；預設 agent-bob 範本）：kernel 把局面（queue、running、slots、budget）寫成一題放進判官小格的 `ws/inbox/`（P-32）、`aos-exec` 它、從 `ws/out/` 讀 `{"run", "defer", "reject"}`（不讀 stdout，N-37 作廢後就是這條路）；判官非 0、逾時、形狀不對，這拍退回 ⑤ 的規則，state 記 `judge_fails`。資源種類＝信裡 `_metainfo.resource` 一個字、`slots` 每種幾格（[10-15 通用 kernel 稿](2026-10-15-general-kernel.md)已定）。兩支不併（N-42），程式共用 lib（C-50）。

依據：C-15、C-29、N-42、N-20、C-52、P-11、P-32；10-15 通用 kernel 稿已定的六條照用。從舊程式拿：`aos_kernel_general.py`、`aos_kernel_judge*.py`。

完成的樣子：`demo/kernel-general/`——規則判官先把形狀、後援、省判官跑通；再換 agent 判官（假腦照規則回 JSON）。測試約八個。

## 寫到哪

程式：bin 加 `aos-tick`、`aos-seq`、`aos-par`、`aos-if`、`aos-daemon`、`aos-gate`、`aos-kernel-llm`、`aos-kernel-general`；共用的 Python 模組照 `aos_inst.py` 的樣子放 bin（`aos_loop.py`、`aos_window.py`、`aos_mailbox.py`）。每做完一塊：bin README 一段、demo README 一段、CONVENTION 若動到（P-06、P-08、P-23）當批改、NORMS 把那塊的「現無實作」拿掉並照使用者對上面五題的裁定改字（條文由 fable 改）、code map 同步、測試全綠、wf-lint broken 0。
