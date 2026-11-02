# 2026-11-02 常駐版 bob：一個 exec（一直跑的 bob）＋一個 loop（外部控制器），掛在 daemon 底下

← [thinking README](README.md)｜月份表 [2026-11](months/2026-11.md)｜前情：[11-01 試驗場 bob](2026-11-01-playground-bob.md)（bob＝`claude -p` 一次跑完）、[11-02 試驗場 daemon](2026-11-02-playground-daemon.md)（bob 用 `execs` 射後不理地掛上去；方向題「常駐的掛法」就是本題）、[10-29 agent-bob 決定 33～35](2026-10-29-agent-bob/04-頂層對八題的再想.md#決定10-30)、[10-30 agent-lifecycle A（queue）、B（納管外部 agent）](2026-10-30-agent-lifecycle.md)｜同日裁定（規劃以裁定後的樣子為準）：[state 窗](2026-11-02-state-window.md)（`daemon_ctl.json`／`daemon_state.json`、log 預設不印）、[loop-stdio](2026-11-02-loop-stdio.md)（身體寫成單子就能指定 stdin／stdout）、[daemon-env](2026-11-02-daemon-env.md)（`AOS_DAEMON_STACK`、`--daemon-stack`；方向題 2「daemon 要不要把變數設給子項」說等常駐 bob 用到）、[exec 像繼承](2026-11-02-exec-inheritance.md)（呼叫＝給小格、變成＝共用 stack；共用時加前綴）｜條文：[N-13、N-14、N-16](../docs/NORMS/05-基礎設施-窗.md)、[N-28、N-54](../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-55、N-57～N-64](../docs/NORMS/10-基礎設施-定義與工作區.md)、[P-11、P-15、P-17、P-19、P-20](../docs/CONVENTION/02-題目stack停錯腦.md)、[P-32～P-38](../docs/CONVENTION/06-巢狀.md)、[C-52、C-56、C-65、C-75](../docs/CONCEPTS.md)｜程式：[aos-daemon](../impls/aos-daemon/README.md)、[aos-loop](../impls/aos-loop/README.md)、[aos-exec／inst](../impls/aos-exec/README.md)、[aos-post](../impls/aos-post/README.md)、[aos-daemon-ctl](../bin/README.md)、[aos-say／listen](../extras/human/README.md)｜場地 `~/code/playground/`（WSL，不在 git）

本檔只記使用者原文（逐字）、決定、實測結論、fable 照原則定的規劃（可翻案）、要使用者看的衝突與方向題（[user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。規劃 11-02 晚依決定與實測改寫成第二版；步驟表在規劃第 6 節。**現況**：第 1 步（daemon 給子項 `AOS_DAEMON_STACK`）在 `1934574e`；第 2 步（試驗場 `agents/resident_bob/` 第一版，不含睡／醒）寫好、在拷貝試驗場實跑過，見[實作時代定](#實作時代定11-02)與[實作結論](#實作結論11-02)；第 3 步（睡／醒）以後的還沒做。

## 使用者原文（11-02，逐字）

前文：使用者先前說「bob 可以掛著」，頂層問要不要做常駐版，使用者說這是他接下來的目標。

> 常駐版bob這塊，我預期是一個exec加一個loop，exec就是我們現有的bob，但是會一直跑，不會自己結束，然後loop就是外部控制器，負責控制bob結束與否，以及把我們的訊息丟進去，把bob的歷史拉出來這樣

接著補一句（11-02，逐字）：

> 這應該會是一個aos資料夾函數，需要配合daemon進行exec和loop的掛起，同時loop所執行的各種東西也會需要另外定義。

頂層問「要先照建議走、先實測 claude 的一直跑模式嗎？」，使用者（11-02，逐字）：

> 照建議先實測

實測進行中陸續補的（11-02，逐字）：

> claude code cli這塊，其實是可以不斷往他的stdin丟東西的，claude code cli自己會處理。

> 然後要小心slash command

> 然後所謂「讀一行題目、答一題、再等下一行」，其實不用，我們就是一直丟，claude code cli會自己一直處理。就是loop那邊要每隔一段時間去取claude code cli的輸出，並同步各種東西。我是希望bob答完手上這道題後仍能繼續做，控制器控制bob結不結束，應該是要用sigterm，或是/exit的。

> 兩邊一起活一起死，我確實想要這個效果，得再想想是否有啥機制可以達到這樣。turn這個指令...turn應該還有別的意思，換個名字吧。

> 主要是後續我想要這麼一個功能：長時間沒有動作，或是使用特定指令後，loop仍會持續運行，但是它會讓bob停掉，等下次有指令了，再用resume把他叫回來，節省負載

> 除此之外，我也會想要能夠resume對話，也就是偵測到stack有先前的殘留時就續接，用--resume這個flag。

頂層回報「連續丟會被併成一題、第三句沒被答到」後（11-02，逐字）：

> 連續丟會被併，正常，我使用的時候也是，他是會一起處理的。你要隔一段時間丟，他才會分開。不過我也擔心是不是你丟進stdin的時候沒有加上換行。

實作進行中（第 1 步已 commit、試驗場第一版已實跑完），使用者叫停（11-02，逐字；頂層轉述：說「照建議走」時在忙、沒細看，想先弄清楚規劃再動工）：

> 先讓他停下來吧

看完隊長的停下報告（做到哪、四件要帶給他的事）後（11-02，逐字）：

> 收尾

## 決定（11-02，使用者）

- 常駐 bob＝**一個 exec**（現有 bob，一直跑、不自己結束）＋**一個 loop**（外部控制器：管 bob 結束與否、把訊息丟進去、把歷史拉出來）。
- 整體是**一個 aos 資料夾函數**，要**配合 daemon** 把 exec 與 loop 掛起來；**loop 每次跑的東西另外定義**。
- **不做一次一題**：控制器有信就直接丟進 bob 的 stdin（方向題 1 定案；推翻規劃第 2 節「等 `result` 才送下一封、信留 `cur/` 直到答完」與方向題 1 的 fable 定案）。
- **控制器 loop 每隔一段時間去取 claude 的輸出、同步歷史等**，不是等 `result` 才動（推翻規劃第 2 節「看到 `result`＝這題答完 → finish 那封信」的對應方式；信跟 `result` 怎麼對，之後規劃再定）。
- **bob 答完手上的題仍繼續活著做事**；**結束由控制器明確送 SIGTERM 或 `/exit`**，不是靠關管子（推翻規劃第 0 節與第 2 節「控制器收工 → FIFO 寫端關 → bob 讀到 EOF 自己退」那條收尾路；`/exit` 實測不可用，見[結論](#結論11-02-實測) ⑨）。
- **同生共死是使用者要的效果**，機制待規劃（規劃第 2 節的「bob 先死→控制器 EPIPE」只蓋一半，實測也發現超預算時 bob 不死，見結論 ③）。
- **控制器每輪的身體不叫 `turn`**（eca 已有 turn 的意思），名字待定。
- **後續功能（不是第一版），規劃要預留**：控制器 loop 一直活著；bob 閒置太久或收到特定指令時被停掉；有新信再以 `--resume <session_id>` 起回來接同一段對話（實測可行，見結論 ⑩）。
- **起來時續接殘留的對話**：bob 起來時若 stack 裡有先前留下的 session（例如記下的 `session_id`），就用 `--resume <id>` 續接；沒有就開新的（推翻方向題 4 的 fable 定案「重掛第一版不接」；實測支撐見結論 ⑩，存放處建議見結論末段）。
- **多封併成一題是正常、可接受的行為**，不是要避免的 bug（11-02 晚；換行有加，見結論 ⑥ 補）：queue 對帳要做成「**一個 `result` 可以結掉好幾封信**」，不為了一封一答刻意等 `result` 才送下一封；aos-listen 看到的回答可能同時回好幾封。併進去的某句被忽略（結論 ⑥ 第三句）算模型的事，不另外補救（覺得原則上該處理就列方向題，見[方向題 4](#方向題-4併題時被忽略的那句6-第三句要不要補救)）。

### 衝突與方向題的裁定（11-02 晚，使用者）

頂層把第二版的衝突 8 條、方向題 5 題白話摘要給使用者後，使用者回（11-02，逐字）：

> 照建議走

所以[衝突與方向題](#要使用者看的衝突與方向題11-02-晚第二版)每條都照檔內的建議定案；規劃第 0～6 節就是定案後的樣子（兩條頂層代定標在各自那條）：

- [衝突 1](#衝突-1用-fifo-接兩個兄弟aos-標準沒有的交流方式)：bob 與控制器之間用 FIFO，由 inst 單子的 `stdin`／`stdout` 指定，算「proc 自己定」那一類，不立條文、不改 C-75，只在 resident_bob 的 README 說明。
- [衝突 2](#衝突-2兄弟要共用位置--daemon-得把-aos_daemon_stack-設給子項)：daemon 起子項（loop 型、exec 型）時 `setenv AOS_DAEMON_STACK`，只設這一個（步驟表第 1 步）。
- [衝突 3](#衝突-3歷史兩份原汁-outjsonl-跟-openai-形的-historyjsonl)：歷史兩份都留——`out.jsonl` 原汁、`history.jsonl` 由 `relay` 轉成 OpenAI 形給 aos-listen；決定 35 的 symlink 本題不做。
- [衝突 4](#衝突-4n-28子項結束不重起vs常駐)：照 N-28 不自動重起；bob 或控制器死了看 `stderr.txt`，人再跑一次 install（會 `--resume` 接回）。
- [衝突 5](#衝突-5控制器用-exec-型包一支-aos-loop掛的目標指到-_entryjson-檔)：不改程式，控制器以 exec 型掛 `ctl/_entry.json` 這個檔（不掛資料夾），README 說明這個眉角；daemon 的 loop 型子項認 `stdout` 等第二個用到的再做。
- [衝突 6](#衝突-6exec-就是我們現有的-bob但要加旗標處理預算)：另開 `agents/resident_bob/bob/`，`agents/bob` 原封不動。**預算（頂層代定、可翻案）**：檔內只寫「使用者定」、沒給建議值，頂層代定保留 `--max-budget-usd`，從現有 bob 的 0.3 改成 **2**（整個 session 的總額，`--resume` 重起後從頭算 ⑩）；超了 bob 不退、每題回 `error_max_budget_usd`（⑦），`relay` 照規劃第 1 節 3 `rm bob`、退 1。實作時規劃第 2 節那張 `bob/_entry.json` 的 `argv` 加 `"--max-budget-usd", "2"`。
- [衝突 7](#衝突-7控制器建-bob-小格裡的-fifo讀-bob-小格的-outjsonl)：FIFO 與 `out.jsonl` 放 bob 自己的小格，控制器當 P-17 的呼叫方替它建 FIFO（只在 bob 起來之前寫這一個檔）、之後只讀 `out.jsonl`。
- [衝突 8](#衝突-8使用者結束不是靠關管子vs-規劃仍用-eof-當控制器沒了--bob-跟著走的保險)：留 EOF 當「控制器沒了 → bob 跟著走」的保險；控制器主動要 bob 停（超預算、睡）才用 `aos-daemon-ctl rm bob`（SIGTERM）。
- [方向題 1](#方向題-1控制器自己被停時bob-走-eof答完退還是先-rm-bob立刻退)：控制器自己被停時 bob 走 EOF（答完手上那題退 0），不先 `rm bob`；history 少的最後一則由下次 install 續接時 `relay` 從 `out_offset` 補讀。
- [方向題 2](#方向題-2-開頭的訊息拒收還是轉義送進去控制器自己的指令用什麼字頭)：`/` 開頭的訊息拒收（當壞信收掉、警告檔記一行），不轉義送進去；控制器自己的指令照規劃第 3 節第 2 步用同一個 `/` 字頭——認得的自己吃（第二版 `/sleep`）、不認得的擋掉。
- [方向題 3](#方向題-3relay-放哪叫什麼)：`relay` 先放試驗場 `agents/resident_bob/ctl/relay/`、身體名就叫 `relay`；跑順了再升成 `proto8/bin/aos-claude-relay`（步驟表第 5 步那時才做），不做成 aos-eca-turn 的模式。
- [方向題 4](#方向題-4併題時被忽略的那句6-第三句要不要補救)：控制器不補救；`system.txt` 加一句「一則訊息裡有好幾個要求時每個都要回」，其餘不做。
- [方向題 5](#方向題-5閒置多久睡要不要有睡的指令第二版)：照規劃第 3 節第 4 步——睡是第二版；`relay` 收 `--idle-ms`（沒給＝不睡，例 `600000`＝10 分鐘）＋ `/sleep` 指令。
- **壞信警告檔改名（頂層代定、可翻案）**：規劃原寫 `letter_warning.txt`；使用者 11-02 已把 daemon 的 `letter_warning` 改名 `mailbox_warning`（[state 窗 § 決定（11-02 晚）](2026-11-02-state-window.md#決定11-02-晚使用者實作中陸續裁的)），所以 relay 的警告檔跟著叫 **`mailbox_warning.txt`**；規劃節與方向題 2 內文已一併改成新名。
- **收尾（11-02，使用者「收尾」）**：停下時已做的保留（第 1 步 `1934574e`、試驗場第一版），不往第二版走；停下報告列的四件由頂層代定（可翻案），見[實作時代定](#實作時代定11-02)最後四條。
- **什麼時候開工**：實作要等 state 窗隊長那一輪（aos-daemon-ctl 拿掉 `--kind`、`-- 參數`、`execs` 收單子、`AOS_DAEMON`→`AOS_DAEMON_STACK`、`--daemon-stack`）commit 進 main、`git pull` 之後才開工（同規劃第 6 節「前提」）。11-02 寫這條時：前三項已在 `278b7bd1`，改名 `AOS_DAEMON_STACK`／`--daemon-stack` 還在隊長的工作區、沒 commit。

## 現況（查清的，不是規劃）

- **現有 bob**（`~/code/playground/agents/bob/`，兩個檔、沒程式碼）：`_entry.json`＝argv 陣列 `claude -p --model haiku --tools Read,Write,Edit,Glob,Grep --permission-mode acceptEdits --strict-mcp-config --max-budget-usd 0.3 --add-dir {$env AOS_WS} --append-system-prompt-file system.txt`；`system.txt` 說明 `AOS_WS`／`AOS_CD`／`AOS_STACK` 各指什麼、`env:XXX` 寫法、做完說一兩句。**怎麼收題**：題目是 `aos-exec ../agents/bob -- "題"` 的參數（`--` 與題原樣到 claude）。**怎麼跑**：aos-exec cd 進 `agents/bob/`、exec 成 claude；一題答完 claude 自己退出。**歷史放哪**：aos 這邊沒有——bob 沒開窗、沒寫 stack；claude 自己把 session 存在 `~/.claude/projects/<cwd 雜湊>/`（決定 35 說這類要 symlink 或複製過來管，還沒做）。stdout 那句「我做了什麼」在手動叫時印到終端機；掛在 daemon 底下時被丟掉（N-28）。
- **掛在 daemons/main 底下的射後不理版**（11-02 已做）：`execs_added: {"bob": ["../../agents/bob", "--", "題"]}` 一封信一題，做完 `done`、不重起；同名再問要先 `rm`。
- **「停著等」已有兩條現成路**，都不是「claude 一直跑」：① aos agent 範本＝agent 是函數、停著等交給 aos-loop（決定 34；round 的 `--on-empty idle`）；② 外部 CLI＝aos-eca-turn 每輪 `claude -p --resume <id>`（每題起一支新的 claude 行程、靠 session 接回），畫面版在 eca-hub（使用者說先不討論，本題不綁它）。
- **`claude -p` 有「一直跑」的模式**：`--input-format stream-json`（stdin 一行一則 `{"type": "user", "message": {"role": "user", "content": "…"}}`，讀到 EOF 才結束；同一個行程、同一段對話），要配 `--output-format stream-json --verbose`（cli_session 已在用 stream-json 輸出）；stdout 一行一事件（`system`／`assistant`／`result`…）。**要實測**（步驟 0）：這是 fable 憑 Claude Code 文件的記憶，沒在試驗場跑過。11-02 已實測，見[結論](#結論11-02-實測)。
- **inst 單子的 `stdin`／`stdout`**：`inst_exec.c` 在 fork 之前、aos-exec 自己的行程裡 `open()` 路徑（stdin `O_RDONLY`；stdout `O_WRONLY|O_CREAT|O_TRUNC`，`stdout_append` 改 `O_APPEND`），上層資料夾要已存在。路徑是 FIFO 時就是 Linux 的 FIFO 語意：開讀端等到有寫端、開寫端等到有讀端；**讀端在所有寫端關掉後讀到 EOF**。
- **daemon 的子項**：loop 型＝daemon 自己起 `aos-loop <小格>/loop.json`，**行程本身的 stdin／stdout 接 `/dev/null`**（身體可以用單子另外指）；exec 型（`execs`）＝直接 `aos-exec 目標` 一次，stdin／stdout 同樣 `/dev/null`、stderr 到小格 `stderr.txt`，目標是資料夾時入口可以是 inst 單子（C-73），單子裡的 `stdin`／`stdout` 由 aos-exec 開。兩種子項各有自己的小格 `$AOS_STACK/loops/<名字>/`，環境只繼承 daemon 的（`AOS_WS` 可用 `ws` 另給）；**daemon 不給子項任何指到自己的變數**（daemon-env 方向題 2 留著）。`aos-daemon-ctl add [--name N] [--ws WS] XXX [-- 參數...]`（11-02 晚使用者拿掉 `--kind`、加 `-- 參數`）：XXX 是有 `loop.json` 的資料夾＝loop 型，其他（含單子檔）＝exec 型；`--` 之後的參數原樣接給 aos-exec（loop 型帶參數＝錯）。11-02 晚起 `execs` 也收 `{"exec": 內嵌單子}`；子項結束就從表上拿掉、同名再 add＝重新起。
- **aos-say／aos-listen**：只碰一個 stack——`aos-say [--stack S] 話`＝`aos-post send --ordered S/queue`（body `{"role": "user", "content": 話}`，沒 queue 就建）；`aos-listen [--stack S] 信號`＝信還在 `queue/new/`／`cur/` 就等，不見了印 `S/history.jsonl` 最新那則 assistant；`--follow`／`--last N`；`--status` 讀 `S/state.json` 的 `phase`（沒有就不印）。

## 規劃（fable 11-02 晚第二版，照使用者決定與實測改寫；可翻案）

第一版（bob 讀到 EOF 自己退、一次一題、等 `result` 才送下一封、重掛不接舊對話）被[決定](#決定11-02使用者)推翻的部分已改掉；本節只留現行規劃。條文與實測編號照[結論](#結論11-02-實測)的 ①～⑫。

### 0. 一句話

**bob＝daemon 的一個 exec 型子項**：`claude -p` 的 stream-json 模式一直跑，stdin 是它自己小格裡的一條 FIFO、stdout 是小格裡的追加檔。**控制器＝daemon 的另一個子項**，一支 aos-loop，行程的 stdout 握著那條 FIFO 的寫端；每 300 ms 跑一次身體 `relay`（不叫 turn）：把 queue 裡的信**立刻**倒進管子、把 bob 吐出來的事件同步成 `history.jsonl`、盯 bob 死活、該停就請 daemon 收 bob。**bob 的起、停、睡、醒全由控制器決定，但動手的是 daemon**（`aos-daemon-ctl add／rm`）——控制器是頭、daemon 是手。訊息走 aos-say 的 queue、回答走 aos-listen 的 history，兩支工具一行不改。要新寫的程式只有 `relay`（＋install 小殼）；repo 要動的只有 daemon 把 `AOS_DAEMON_STACK` 設給子項。

### 1. 誰當父：daemon 當父、控制器經 daemon 管（頂層「控制器當父」案的評估）

頂層的初步看法是「起停睡醒都歸控制器，控制器當 bob 的父程式最自然、pid 在手、同生共死好做」。三案比過，**建議 (B)**：

- **(A) 控制器當 bob 的父程式**。aos-loop 的身體是每輪一支新行程，活不過一輪，當不了長壽子程式的父；要當父，控制器的 `_entry` 得改成一支自己寫的常駐 Python（開管子、`Popen` claude、自己輪詢 queue、自己讀 ctl、自己收屍）——這等於重寫一個小 daemon＋小 loop（起子程式、記 pid、SIGTERM、等退、表、`interval_ms`、`paused`／`stopped`），跟 aos-daemon、aos-loop 做的事重疊（C-56「不多造」；使用者 11-01「明明現有的機制組合一下就能搞定」）。aos 裡「叫別人」＝給小格、**等它做完**（P-17）；「起一個不等它、長壽的」就是 daemon 的工作（C-74 基礎層）。pid 在手的好處其實用不到：收 bob 用 `aos-daemon-ctl rm bob`＝daemon 送 SIGTERM，不必知道 pid；bob 死活讀 daemon 的 `loops_state.json`（窗，N-14「最新那份算數」）。結構上也變成「一個 exec（裡面偷偷包著 bob）」，不是使用者說的「一個 exec 加一個 loop」。
- **(B) daemon 當兩個的父，控制器經 daemon 管 bob**（建議）。bob、控制器都是 daemon 表上的一列（`aos-daemon-ctl ls` 一眼看到），各有小格；控制器起 bob＝`aos-daemon-ctl add --name bob … [-- --resume ID]`，收 bob＝`aos-daemon-ctl rm bob`，看 bob＝讀 `$AOS_DAEMON_STACK/loops_state.json` 的 `execs` 表有沒有 `bob`。**同生共死不靠一條機制，靠三個方向各自現成的路**：
  1. **控制器沒了 → bob 跟著走**：控制器行程（aos-exec 監工＋aos-loop）握著 FIFO 唯一的寫端，不論它怎麼死（`stopped`、`rm`、崩掉、SIGKILL），寫端一關 bob 就讀到 EOF，**答完手上那題以 0 結束**（⑫）、daemon 從表上拿掉。不用控制器做任何事，SIGKILL 也擋不住。
  2. **bob 沒了 → 控制器跟著停**：`relay` 每輪讀一次 `loops_state.json`；它認為 bob 該在（不是自己哄睡的）卻不在表上＝bob 死了（崩、被人 `rm`、`--resume` 接不回）→ stderr 一行、退 1 → aos-loop 以 1 結束（P-20 停下等人）→ daemon 表上 `bob_ctl` 走掉。不等寫信時 EPIPE 才發現（bob 死了而沒信進來時 EPIPE 永遠不會來）。
  3. **bob 活著卻沒用 → 控制器收它、自己也停**：超預算（⑦）bob 不退，`relay` 看到 `result.subtype` 是 `error_max_budget_usd`＝這題起沒答、之後也不會答 → `aos-daemon-ctl rm bob`（daemon 送 SIGTERM）、stderr 一行、退 1。
  4. daemon 沒了 → 它收工時全部送 SIGTERM（P-36），兩個一起走。
  
  **「結束由控制器明確送 SIGTERM」**（使用者決定）落在控制器**主動**要 bob 停的場合（3 與第二版的睡）；控制器**自己**被停時 bob 走的是 1 的 EOF 路——這條比 SIGTERM 溫和（SIGTERM 會丟掉手上那題 ⑧，EOF 讓它答完），但跟使用者「不是靠關管子」那句有出入，列成[方向題 1](#方向題-1控制器自己被停時bob-走-eof答完退還是先-rm-bob立刻退)。
- **(C) daemon 綁組**：aos-daemon 多一個「這幾個子項同組、一個退了全收」的 key。要改 C++、立新條文（N-28 補），而且「活著卻沒用」（3）它看不出來，還是得控制器自己判；等第二個需要綁組的場合出現再做（C-56 最後一步減法）。不做。

### 2. 「exec」那半：bob 怎麼變成一直跑的

- **還是 `claude -p`，多三個旗標** `--input-format stream-json --output-format stream-json --verbose`；其餘旗標照現有 bob；`system.txt` 多兩句（「你會一直在，一題接一題，答完等下一題」「每題答完用一兩句說你做了什麼」）。**`--max-budget-usd` 是整個 session 的總額、超了不退只報錯**（⑦）：拿掉或調大是錢的事（[衝突 6](#衝突-6exec-就是我們現有的-bob但要加旗標處理預算) (c)），控制器照第 1 節 3 處理超預算。
- **入口是一張靜態單子**，`stdin`／`stdout` 都指自己的小格（`$AOS_STACK`＝daemon 給的 `loops/bob/`）；題目與 `--resume` 都靠 aos-exec 把 args 接在 `argv` 後面（inst「args 接在後面」），**不用小殼**：

  ```json
  // agents/resident_bob/bob/_entry.json
  {"argv": ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            "--model", "haiku", "--tools", "Read,Write,Edit,Glob,Grep", "--permission-mode", "acceptEdits",
            "--strict-mcp-config", "--add-dir", {"$env": "AOS_WS"}, "--append-system-prompt-file", "system.txt"],
   "stdin":  {"$env": "AOS_STACK", "$path": "in.fifo"},
   "stdout": {"$env": "AOS_STACK", "$path": "out.jsonl"}, "stdout_append": true}
  ```

  `aos-daemon-ctl add --name bob <abs>/bob -- --resume <id>` → daemon 起 `aos-exec <abs>/bob --resume <id>`（aos-daemon-ctl 剝掉 `--`）→ `claude … --resume <id>`。沒有 `--` 參數就是新對話。`stderr` 不寫＝daemon 給的小格 `stderr.txt`。
- **bob 的小格 `$AOS_DAEMON_STACK/loops/bob/`** 裡有：`in.fifo`（控制器在 add 之前 `mkfifo`——inst 的 `open` 不建 FIFO、路徑不在＝`OpenFailed` 退 1；aos-daemon-ctl `--ws` 也是先替子項把小格建好，同一個慣例）、`out.jsonl`（claude 原汁事件流，一行一事件、追加不重寫；bob 的紀錄、不是成果，決定 26）、`stderr.txt`。**控制器寫進 bob 小格的只有 FIFO 這一個檔，而且是在 bob 存在之前**——叫人的那一方替被叫的準備小格（P-17），bob 自己只看 `$AOS_STACK`、不知道上面有誰（[衝突 7](#衝突-7控制器建-bob-小格裡的-fifo讀-bob-小格的-outjsonl)）。
- **等新訊息＝stdin 阻塞在 FIFO 上**：沒讀到下一行就什麼都不做、不花錢（②）。沒有輪詢、沒有自己寫的循環。**只要寫端還開著它就一直在**（②）；寫端全關才 EOF 退 0（⑫）；SIGTERM 立刻退 143（⑧）。
- **為什麼 FIFO 不會在睡醒之間出事**：FIFO 的寫端被控制器行程握著整個壽命；bob 被收掉（睡）時只是沒有讀端——這時寫會 EPIPE，所以 `relay` 只在 bob 在表上、而且探針成功時才寫（第 3 節 ②）；bob 再起來 `open(O_RDONLY)` 時已有寫端，立刻回來、接著讀。管子裡不會留下沒人讀的半截（沒有讀端時 `relay` 根本不寫）。

### 3. 「loop」那半：控制器

- **定義在 `agents/resident_bob/ctl/`**，是一支 aos-loop，用 exec 型子項掛、入口是單子，讓 aos-loop **這個行程**的 fd 1 就是 FIFO 寫端（loop 型子項的行程 fd 由 daemon 定成 `/dev/null`，拿不到；[衝突 5](#衝突-5控制器用-exec-型包一支-aos-loop掛的目標指到-_entryjson-檔)）：

  ```json
  // ctl/_entry.json —— aos-exec 在 fork 前開 FIFO 寫端（等到 bob 開了讀端）、起 aos-loop；兩個行程都握著 fd 1 直到結束
  {"argv": ["aos-loop", "loop.json"],
   "stdout": {"$env": "AOS_DAEMON_STACK", "$path": "loops/bob/in.fifo"}, "stdout_append": true}
  // ctl/loop.json —— 每 300 ms 跑一次 relay；窗加前綴 loop_（exec 像繼承：共用 stack 的名字各自加前綴）
  {"exec": "relay", "interval_ms": 300, "ctl": "loop_ctl.json", "state": "loop_state.json"}
  ```

  log 預設不印（loop-stdio 決定），fd 1 上只有 `relay` 寫的東西。`relay` 繼承 fd 1（aos-loop 跑資料夾目標＝fork＋`run_cli`，不另開串流），往 stdout 寫一行＝送進 bob 的 stdin。**`ctl/` 裡有 `loop.json`，`aos-daemon-ctl add <ctl 資料夾>` 會自動認成 loop 型**（它看「資料夾有 `loop.json`」）、單子的 `stdout` 就沒了——所以掛的目標指到**檔** `ctl/_entry.json`（C-73 入口可以是單子檔；XXX 不是帶 `loop.json` 的資料夾＝exec 型），`--name bob_ctl`。
- **控制器的小格 `$AOS_DAEMON_STACK/loops/bob_ctl/`**＝`relay` 的 `$AOS_STACK`，裡面：`queue/`（aos-say 建，N-16 有順序）、`history.jsonl`（`relay` 寫，OpenAI 形，P-41／P-42）、`loop_ctl.json`／`loop_state.json`（aos-loop 的窗）、`relay_state.json`（`relay` 自己的，前綴 `relay_`）、`mailbox_warning.txt`（壞信，同 agent 範本）、`stderr.txt`。**人對話的 stack 就是這一格**：`aos-say --stack $AOS_DAEMON_STACK/loops/bob_ctl 話`。
- **`relay` 每輪的身體**（Python；`ctl/relay/_entry`；一輪＝下面五步，有沒有事都退 0，失敗退 1、stderr 一行〔P-20、P-21〕）：
  1. **看 bob**：讀 `$AOS_DAEMON_STACK/loops_state.json`（分檔的 `$ref` 解回來，表 >100 列才會有）→ `execs` 表有沒有 `bob`。`relay_state.json` 的 `bob` 欄＝`up`／`asleep`／`waking`（第二版）；`up` 卻不在表上＝死了 → 退 1（第 1 節 2）。第一輪 `bob` 欄還沒有：控制器的 aos-exec 要等 bob 開了 FIFO 讀端才起得來，所以 `relay` 跑到時 bob 一定在表上（或剛死）→ 在就記 `up`。
  2. **送信**（一直丟，不等 `result`）：bob 在表上才做。先探針 `os.open(in.fifo, O_WRONLY|O_NONBLOCK)`——沒有讀端＝`ENXIO`（bob 的 aos-exec 還沒開到 stdin）＝這輪不送；探到就關掉探針。然後 `aos-post claim-all` 把 `new/` 全認領進 `cur/`，每封 `aos-post check` 讀 body：
     - body 不是 `{"role": "user", "content": 非空字串}`＝壞信：`finish` 收掉、`mailbox_warning.txt` 寫原因（同 aos-eca-turn）。
     - `content` 去掉開頭空白後以 `/` 開頭＝**不轉送**（⑪：`/clear` 會清對話、`/cost` 會吐帳號用量、`/compact` 多半真的執行）：第一版沒有控制器自己認的指令，一律當壞信收掉、`mailbox_warning.txt` 記「以 / 開頭的訊息不轉送」；第二版認 `/sleep`（第 4 步）；要不要改成轉義後照送見[方向題 2](#方向題-2-開頭的訊息拒收還是轉義送進去控制器自己的指令用什麼字頭)。
     - 好信：`{"role": "user", "content": …}` 原樣追加 `history.jsonl`（agent-lifecycle A-3：一封信＝一行），再寫一行 `{"type": "user", "message": {"role": "user", "content": …}}` 到 stdout＝FIFO（實測的輸入形狀，`content` 字串就行）、flush。信**留在 `cur/`**，信號記進 `relay_state.json` 的 `sent`（寫到管子裡、還沒被 `result` 結掉的）。寫 stdout `BrokenPipeError`（探針到寫之間 bob 剛好沒了）＝這封留 `cur/`、不記 `sent`，下一輪重送（`cur/` 裡不在 `sent` 的＝沒送成的）；bob 真死了下一輪第 1 步會退 1。
  3. **同步輸出**：從 `relay_state.json` 的 `out_offset` 讀 `loops/bob/out.jsonl` 新的整行（每行都是完整的 JSON，⑧；讀到沒有換行結尾的半行就留到下輪），逐行：
     - `system`／`init`（每題一次，④）：**把 `sent` 裡現在的信號快照成這題的 `answering`**——claude 開一題時把到那一刻為止排在 stdin 的訊息併成一則（⑥），之後進來的歸下一題；記下 `session_id`。
     - `assistant`：`message.content` 是 Anthropic 區塊陣列（⑤）→ 轉成一則 OpenAI message 追加 history：`text` 區塊接成 `content` 字串；`tool_use` 區塊→`tool_calls: [{"id", "type": "function", "function": {"name", "arguments": JSON 字串}}]`（有 tool_calls 時 aos-listen 不當回答，正好）；`thinking` 區塊丟掉。
     - `user`（用工具時 claude 回吐的 `tool_result` 區塊；形狀沒測）→ 每個區塊一行 `{"role": "tool", "tool_call_id", "content"}`；不是 tool_result 的 `user` 行（`--replay-user-messages` 沒開，應該不會有）略過。
     - `result`：`answering` 裡的信全部 `aos-post finish`（**一個 result 結掉好幾封**，使用者決定「併題正常」）、從 `sent` 拿掉；`subtype` 是 `error_max_budget_usd` → 第 1 節 3（`rm bob`、退 1）；`error_during_execution`（被 `interrupt` 打斷，⑨）→ 信照樣結掉、`mailbox_warning.txt` 記一行；`session_id` 寫進 `relay_state.json`（以**最後一行**為準——`/clear` 過 id 會換 ⑪，雖然 `/` 已經擋掉）。
     - `rate_limit_event`、`system`／其他 subtype、`conversation_reset`：略過。
     - 寫完 `out_offset`。history 於是「幾則 user、一則 assistant」一段段——`aos_ws.exchanges` 本來就把一則回答前的所有 user 收成一段，aos-listen `--last N` 直接對；`aos-listen 信號`「信不在 `new/`／`cur/` 了就印最新那則回答」照樣成立，只是那則回答可能同時回了好幾封（使用者決定接受）。
  4. **睡／醒**（**第二版**，第一版只預留 `relay_state.json` 的欄位與第 1 步的 `asleep`／`waking` 分支）：`relay_state.json` 記 `last_activity_at`（最後一次送信或 `result`）；閒置超過 `--idle-ms`（`loop.json` 的 `exec` 寫成 `["relay", "--idle-ms", "600000"]`；11-01 使用者「旋鈕走 argv」；沒給＝不睡）、或收到 `/sleep`（第 2 步攔下、不進 bob）→ `aos-daemon-ctl rm bob`、`bob`＝`asleep`。之後每輪：`asleep` 而 `new/` 有信 → `aos-daemon-ctl add --name bob <abs>/bob -- --resume <session_id>`、`bob`＝`waking`；`waking` 而 bob 在表上 → `up`、照第 2 步送（探針擋住「進程在了、stdin 還沒開」那幾毫秒）；`waking` 滿 10 秒還不在表上＝起不來 → 退 1。睡著時信在 `new/` 排著、`history.jsonl` 不動、aos-listen 照等。
  5. **收工**：`relay` 自己不決定收工（收工是人的事：`loop_ctl.json` 寫 `{"stopped": true}` 或 `aos-daemon-ctl rm bob_ctl`）。aos-loop 結束→aos-exec 結束→FIFO 寫端全關→bob 答完手上那題退 0（第 1 節 1）。`paused`＝aos-loop 不起 `relay`：信在 `new/` 排著、bob 閒著、已送進去的照答（N-07 原義）。
- **`relay_state.json`**（只有 `relay` 寫，先寫 `.relay_state.json` 再改名，N-05）：`{"bob": "up"|"asleep"|"waking", "session_id", "out_offset", "sent": [信號...], "answering": [信號...], "last_activity_at", "updated_at"}`。它同時是**「stack 有沒有殘留對話」的小窗**：install 看它有 `session_id` 就用 `--resume`。
- **底下全叫現成的**：`aos-post claim-all／check／finish`（不自己 rename，agent-lifecycle A-9）、`aos-daemon-ctl add／rm`（不自己投信、不自己 kill）；`loops_state.json` 用 `aos-directive` 解或自己照 `$ref` 讀（表 ≤100 列時就是一份物件）。
- **各身體另外定義**（使用者原文）：`relay` 放控制器自己的資料夾 `ctl/relay/`（N-50／P-25，相對路徑零個 `..`）；以後要加別的身體（定時摘要、定時問一句）＝`ctl/` 底下再一個資料夾、`loop.json` 的 `exec` 改指一張 aos-fsm 表各身體一格。本題一個身體，不先鋪 fsm（C-56）。

### 4. 資料夾程式長什麼樣、怎麼請 daemon 掛起

```
agents/resident_bob/            ← C-54：資料夾名小寫加底線
  _entry                        ← install（Python 小殼，十幾行）：建 bob 小格與 FIFO、add bob（有殘留就 --resume）、add bob_ctl
  README.md                     ← 玩法（第 5 節）
  bob/
    _entry.json                 ← 第 2 節那張單子
    system.txt                  ← 現有 bob 的，多兩句
  ctl/
    _entry.json                 ← {"argv": ["aos-loop", "loop.json"], "stdout": FIFO}
    loop.json                   ← {"exec": "relay", "interval_ms": 300, "ctl": "loop_ctl.json", "state": "loop_state.json"}
    relay/
      _entry                    ← 第 3 節的身體（Python）
```

- **`_entry`（install）做四件事然後結束**——這就是「配合 daemon 進行 exec 和 loop 的掛起」：① `D=$AOS_DAEMON_STACK`（沒設＝退 1 `DaemonMissing`，同 aos-daemon-ctl、N-63）；`mkdir -p $D/loops/bob`、`mkfifo $D/loops/bob/in.fifo`（已在就跳過）。② 讀 `$D/loops/bob_ctl/relay_state.json` 的 `session_id`：有＝`aos-daemon-ctl add --name bob <自己>/bob -- --resume <id>`（**起來時續接殘留**，使用者決定；⑩）、沒有＝`aos-daemon-ctl add --name bob <自己>/bob`。③ `aos-daemon-ctl add --name bob_ctl <自己>/ctl/_entry.json`。④ stdout 印兩個信號與一句「掛上了：`aos-say --stack $D/loops/bob_ctl 話`」。它不跑 bob、不跑 loop、不留行程；跑第二次＝重掛（表上已有的照 N-54「已在跑的不重起」，等於沒事；兩個都做完了就重新起）。寫 Python 不寫 sh（user/03）。
  - 先 add bob 再 add bob_ctl：控制器的 aos-exec 開 FIFO 寫端會**等到 bob 開了讀端**，bob 的 aos-exec 開讀端會等到有寫端——兩個都在 daemon 底下並行，誰先誰後都接得上；但只掛了控制器沒掛 bob，控制器會一直卡在 `open`，表上 `running` 卻什麼都沒做。
  - 殘留的 session 接不回（claude 那邊刪了）：bob 起來就退非 0 → `relay` 第 1 步看到 bob 不在 → 退 1；人刪掉 `relay_state.json`（或只刪 `session_id`）重跑 install 就是新對話。
  - 工作區：兩個子項都不給 `--ws`＝繼承 daemon 的 `AOS_WS`（bob 的 `--add-dir` 拿到 `ws/`）。要服務別的工作區＝install 多收 `--ws` 原樣轉給兩個 add（第二版；`<WS>/.stack` 的捷徑只會指到先 add 的那一隻——指到 `bob_ctl` 才有用，所以那時改成先 add bob_ctl）。
  - 為什麼不讓 install 自己 `aos-post send` 一封 `execs_added`：aos-daemon-ctl 已包好轉絕對路徑、`--name`、`-- 參數`；`execs` 雖然 11-02 晚起收內嵌單子，但本題兩個目標都是現成的檔，不需要。
- **daemon 要給子項 `AOS_DAEMON_STACK`**：控制器的單子（FIFO 路徑）、`relay`（讀 `loops_state.json`、叫 `aos-daemon-ctl`）都要知道 daemon 的 stack 在哪；兄弟之間沒有父子交代，只有共同的上一代能告訴他們（N-64 ④「用 hub 型變數」）。daemon-env 方向題 2 使用者裁「等常駐 bob 用到再說」——就是現在（[衝突 2](#衝突-2兄弟要共用位置--daemon-得把-aos_daemon_stack-設給子項)）。只設這一個（不設定義資料夾與 ws 三名，使用者 11-02 定）。
- **daemons/main 的 `daemon.json` 不用改**（state-window 裁定後的 `daemon_ctl.json`／`daemon_state.json`、`loops_ctl_mailbox`）；bob 與 bob_ctl 用信掛、不寫進 daemon.json，daemon 重起不會自動回來（[衝突 4](#衝突-4n-28子項結束不重起vs常駐)）。要開機就掛可以寫死 `"execs": {"bob": "../../agents/resident_bob/bob", "bob_ctl": "../../agents/resident_bob/ctl/_entry.json"}`（FIFO 仍要先建一次；`--resume` 寫不進靜態的 daemon.json，開機掛＝新對話）。

### 5. 使用者在 shell 怎麼用

```sh
# 視窗一：起 daemon（照 11-02 試驗場 daemon）
cd ~/code/playground && source env.sh && cd ws
aos-exec ../daemons/main

# 視窗二
cd ~/code/playground && source env.sh && cd ws
export AOS_DAEMON_STACK=$PWD/.stack            # daemon-env 定案的名字

aos-exec ../agents/resident_bob                # 掛上：mkfifo、add bob（有殘留就 --resume）、add bob_ctl
aos-daemon-ctl ls                              # bob exec running、bob_ctl exec running（兩個都 running 才算掛好）

S=$AOS_DAEMON_STACK/loops/bob_ctl              # 之後都對控制器的小格說話
N=$(aos-say --stack $S "在 env:AOS_WS 寫一首詩，詠桃花，檔名 peach.txt。")
aos-listen --stack $S "$N"                     # 等這題答完、印 bob 的回答
aos-say --stack $S "再把它改成七言。"; aos-say --stack $S "加個標題。"   # 連丟兩句：忙時會被併成一題、一個回答回兩封（正常）
aos-listen --stack $S --last 3                 # 最近三段（幾則 user＋一則回答）
aos-listen --stack $S --follow                 # 像 tail -f 跟著看
tail -f .stack/loops/bob/out.jsonl             # 原汁事件流（工具呼叫、花費、session_id）
cat .stack/loops/bob/stderr.txt .stack/loops/bob_ctl/stderr.txt   # 出錯看這裡
cat $S/relay_state.json                        # bob up/asleep、session_id、還在答的信

echo '{"paused": true}'  > $S/loop_ctl.json    # 暫停：新信排著、bob 閒著
echo '{"paused": false}' > $S/loop_ctl.json    # 續

# 停掉（都會讓兩個都走）
echo '{"stopped": true}' > $S/loop_ctl.json    # 控制器收工 → 管子關 → bob 答完手上那題退 0（最溫和）
aos-daemon-ctl rm bob_ctl                      # 同上，由 daemon 送 SIGTERM 給控制器
aos-daemon-ctl rm bob                          # 急停：bob 立刻退 143、丟掉手上那題；控制器下一輪看到它不在、退 1

# 再起來＝續接同一段對話（relay_state.json 還在、有 session_id）
aos-exec ../agents/resident_bob
rm $S/relay_state.json && aos-exec ../agents/resident_bob     # 要開新對話就先把殘留刪掉
```

### 6. 要動的程式與步驟表（不實作）

**前提**：隊長的 state 窗那輪（`daemon_ctl.json`、log 預設不印、`AOS_DAEMON_STACK`／`--daemon-stack`、`--kind` 拿掉、`execs` 收單子）commit 進 main、`git pull` 之後再開工。本題的 C++ 只碰 `child.cpp`。

| # | 改哪 | 做什麼 | 怎麼驗 |
|---|---|---|---|
| 0 | 試驗場（已做） | 實測 claude 一直跑模式 | 見[結論](#結論11-02-實測) |
| 1 | `proto8/impls/aos-daemon/src/child/child.cpp`（`run_child`）、`daemon.hpp` 把 stack 傳進去、impls README「子項的環境」一段、N-64 ④ 加 daemon 例子、N-63 實例補一句「daemon 起子項時設給它」、code map `code-map/proto8/14-aos-daemon.md` | 起子項（loop 型、exec 型都設）時 `setenv("AOS_DAEMON_STACK", stack_)`，只這一個 | `tests/test_daemon.py` 加 1 案：exec 子項把 `env` 寫進檔、驗值＝daemon 的 stack；`impls/aos-daemon` ctest、repo 根 ctest 全綠（鐵律 1） |
| 2 | 試驗場 `~/code/playground/agents/resident_bob/`（第 4 節的樹） | 寫 `bob/_entry.json`、`bob/system.txt`、`ctl/_entry.json`、`ctl/loop.json`、`ctl/relay/_entry`（第 3 節 1～3、5；4 只留欄位）、`_entry`（install）、README | 第 5 節從頭跑（haiku）：掛上→兩個 running→say／listen 兩題同一段對話→連丟三句看併題與對帳（`cur/` 清空、history 幾則 user 一則回答）→`paused` 時信排著→`/cost` 不轉送（`mailbox_warning.txt`）→`stopped` 後 bob 答完 `done 0`、bob_ctl `done 0`→`rm bob` 時 bob_ctl 下一輪退 1→`--max-budget-usd 0.001` 跑兩題看 `rm bob`＋退 1→再 install 續接（問「我剛才叫你做什麼」）；驗完 `ws/` 只剩使用者原本的檔 |
| 3 | 同上 `ctl/relay/_entry`、`ctl/loop.json` | **第二版**：`--idle-ms`、`/sleep`、`asleep`→`waking`→`up` | 設 `--idle-ms 15000`：閒 15 秒後 `ls` 沒有 bob、`relay_state` `asleep`；再 say 一句→bob 回來（`--resume`）、答得出前文；`/sleep` 同 |
| 4 | `proto8/thinking/2026-11-02-playground-daemon.md` 方向題、[11-02 daemon-env 方向題 2](2026-11-02-daemon-env.md) | 補「常駐版見本檔」「方向題 2 已用到、做了」；本檔「決定」補使用者對衝突／方向題的裁定 | — |
| 5 | （[方向題 3](#方向題-3relay-放哪叫什麼) 選「進 repo」才做）`proto8/bin/aos-claude-relay`、bin README、`tests/test_aos_claude_relay.py`、code map | 把試驗場的 `relay` 升成 bin 指令、`ctl/loop.json` 改指它 | unittest 用假的 `out.jsonl`、假 FIFO、假 `loops_state.json` 驗一輪 |
| 6 | `wf/WAIT_USER.md` 一條 | 使用者在試驗場親手跑第 5 節 | 使用者回報 |
| 7 | 收尾 | 日誌一行、months 那列補結果；一個 commit（程式＋測試＋README＋條文＋code map 同一個） | `/wf-lint` |

## 結論（11-02 實測）

步驟 0 做完（claude 2.1.316、haiku；場地 `~/code/playground/tmp-stream-test/`，腳本 `t1.sh`／`t2.sh`／`run.sh`／`seq.py` 與每輪的 `out_*.jsonl` 都留著）。**「一支 claude 一直跑、從 stdin 收話」成立，不用翻案成每題 `--resume`**；但幾個細節跟規劃不同，加上使用者實測中的新決定（見[決定](#決定11-02使用者)），規劃要跟著改的地方列在最後。

**實際指令**（現有 bob 的旗標，拿掉 `--max-budget-usd`，`--add-dir` 改指測試用的 `ws/`；system prompt 直接讀 `agents/bob/system.txt`，沒改它）：

```sh
mkfifo in.fifo
claude -p --input-format stream-json --output-format stream-json --verbose \
  --model haiku --tools Read,Write,Edit,Glob,Grep --permission-mode acceptEdits \
  --strict-mcp-config --add-dir "$PWD/ws" \
  --append-system-prompt-file ../agents/bob/system.txt \
  < in.fifo > out1.jsonl 2> err1.txt &
exec 3> in.fifo                     # 寫端一直開著
echo '{"type":"user","message":{"role":"user","content":"回答 1+1，只回數字"}}' >&3
```

**輸入形狀**：一行一則 `{"type":"user","message":{"role":"user","content":"…"}}`，`content` 給字串就行（規劃第 1 節寫的形狀對）。加 `--replay-user-messages` 時，claude 會把它真的拿去答的那則 user 訊息回吐一行 `type:"user"`（看得出幾則被合成一題，見 ⑥）。

### 實測到的行為

1. **連答多題、記得前文**：「回答 1+1」答 `2`；閒 8 秒後「我剛才問你什麼？」答「你剛才問我 1+1 等於多少，要求只回數字。」；同一個 `session_id`。stderr 全空。
2. **寫端開著就一直等**：答完一題後行程還在、不花錢、不退；送下一行就接著答（第一題約 4 秒、之後每題 1 秒左右）。
3. **stdout 每題吐的事件**（一行一個）：`system`/`init` → `assistant` → （偶爾 `rate_limit_event`、`system`/`thinking_tokens`）→ `result`。`result` 一題一行：`subtype: "success"`、`is_error: false`、`result`＝回答純文字、`result_index` 從 0 起逐題加一、`terminal_reason: "completed"`。`session_id` 每一行事件上都有，同一段對話不變。節錄（第二題，欄位刪減）：
   ```
   {"type":"system","subtype":"init","session_id":"532e…","cwd":"…/tmp-stream-test","model":"claude-haiku-5-5",…}
   {"type":"assistant","session_id":"532e…","message":{"type":"message","role":"assistant","id":"msg_…","content":[{"type":"text","text":"你剛才問我 1+1 等於多少，要求只回數字。"}],"stop_reason":"end_turn","usage":{…}},…}
   {"type":"result","subtype":"success","is_error":false,"result":"你剛才問我 1+1 等於多少，要求只回數字。","result_index":1,"total_cost_usd":0.00084608,"session_id":"532e…","terminal_reason":"completed",…}
   ```
4. **`system`/`init` 每題都吐一次**（不只開頭），讀輸出時跳過即可。
5. **`assistant` 的 `message` 是 Anthropic Messages 形、不是 OpenAI 形**（規劃第 2 節寫「已經是 OpenAI 形」不對）：`content` 是區塊陣列（`text`、`thinking`，用工具時有 `tool_use`；被中斷時有一行 `type:"user"` 帶 `[Request interrupted by user]`），還帶 `id`／`model`／`usage`。aos-listen 認的 `history.jsonl` 是 OpenAI 形（`content` 字串、`tool_calls`、`role:"tool"`），控制器要轉。工具事件的實際形狀沒測（題目都沒用工具）。
6. **一直丟、不等 `result`**：開頭一口氣寫三行（「1+1」「2+2」「把前兩個答案相加」）。claude **不插話、不打斷**；第一行先被拿去答（`2`），**答的時候進來的第二、三行被合成一則**（replay 出來是 `"回答 2+2，只回數字\n把你前兩個答案相加，只回數字"`）、只答一次、**只有一個 `result`**——三則話兩個 `result`。而且這一次 haiku 只答了 `4`，合併進來的第三句被忽略。順序沒亂、對話記憶沒壞。
   → **控制器可以有信就直接倒進管子**（使用者「一直丟，claude 會自己處理」成立：不會丟、不會亂序、不會打斷）；但**信跟 `result` 不是一對一**，忙的時候進來的幾封會併成一題，所以「一封信等一個 `result` 才 finish」對不起來，也看不出合併裡哪句有被理會。要靠 `--replay-user-messages` 那行（合併後的原文）或別的方式對帳，留給規劃。**11-02 晚補**：頂層查過實測腳本 `seq.py`，每則都是 `json.dumps(...) + "
"` 再 flush——**換行有加，併題不是格式問題**；那輪三則只出兩個 `result`（`2`、`4`），第三則併進去後沒被答到。使用者裁「併題正常、可接受」（見決定）。
7. **`--max-budget-usd` 是整個 session 的總額**：`total_cost_usd` 是累計（0.00069、0.00085、0.00094），這題自己的在 `model_usage_since_last_result.<模型>.costUSD`。上限設 0.00025 跑四題：第一題 `success`；第二題答案照樣吐出，但 `result` 變 `subtype: "error_max_budget_usd"`、`is_error: true`、沒有 `result`、`errors: ["Reached maximum budget ($0.00025)"]`（答完才檢查，會超一點）；之後每題**立刻**回同樣的錯誤 `result`、不花錢、沒有 `assistant`。**超預算時 claude 不退出**（規劃第 1 節與衝突 6 寫「撞到、claude 自己退出」不對），寫端關掉時才退、**結束碼 1**。所以預算用完時 bob 變成活著卻沒用，控制器要自己看 `result` 的 `subtype`。
8. **SIGTERM**：閒著時送＝立刻退、**結束碼 143**（claude 自己接住訊號以 128+15 結束，不是被殺）。正在答時送（「從 1 數到 1500」答到一半）＝**也立刻退 143，手上那題直接丟掉**：沒有 `assistant`、沒有 `result`，輸出檔最後一行是那題的 `system`/`init`。**輸出檔每一行都是完整的**（沒有寫一半的行）。
9. **`/exit` 不能用**：stream-json 裡送 `/exit`，claude 回一則 `result`「/exit isn't available in this environment.」、**不退**，之後照常答題。stream-json 有對應的**控制訊息** `{"type":"control_request","request_id":"r1","request":{"subtype":"interrupt"}}`：實測它**中斷正在答的題**（輸出 `control_response` success、已吐的半截 `assistant`、一則 `result` `subtype: "error_during_execution"`），**行程不退**、對話記得（下一題問「我剛才叫你做什麼」答「…你只寫到 13 就被我中斷了」）。它是「打斷這題」，不是「收工」。
10. **停掉後 `--resume` 叫回來**：「記住暗號 9」→ SIGTERM（退 143）→ 用第一行事件（`system`/`init`；每行都有、哪行都一樣）的 `session_id` 跑 `claude -p --resume <id> --input-format stream-json --output-format stream-json --verbose …`（其餘旗標同上）→ 問「我剛才叫你記住什麼」答「暗號 9」。**重起後 `session_id` 不變**，`result_index` 從 0 重數；`total_cost_usd` **接著同一個 session 的累計**（11-02 實作時實跑改正：0.00195 → 重掛後第一題 0.00206；步驟 0 當時寫成「從新行程重算」不對），但 `--max-budget-usd` 是照這一支行程算的，所以重起後預算從頭算。（`/clear` 之後 `session_id` 會換，見 ⑪。）
11. **slash command 會被執行，要小心**（使用者「要小心slash command」成立）：
    - `/help`：被 claude 攔下、不給模型，回「/help isn't available in this environment.」，不花錢。
    - `/cost`：**真的執行**，回訂閱用量（「Current session: 3% used · resets …」），不花錢——會把帳號用量吐進輸出。
    - `/clear`（在丟棄的 session 測）：**真的清掉對話**——吐一行 `{"type":"conversation_reset","trigger":"clear","new_conversation_id":…}`、一則空的 `result`，之後 **`session_id` 換成新的**、問「暗號是多少」答「不知道」。
    - `/foo`（不存在）：當一般文字給模型，模型答「`/foo` 在這個 session 裡不存在…」。
    - 句子中間有 `/`（「a/b.txt 的副檔名」）：正常答 `txt`，不受影響。之後問暗號仍答 `7`（`/help`、`/cost`、`/foo` 都沒清記憶）。
    - `/compact` 沒測（會花錢、會改對話）；照 `/clear` 的樣子推，它多半也會真的執行。
    → **控制器丟進去前要擋或轉義開頭的 `/`**（例如前面加一個空白或全形字，或直接拒收）：不然任何能 `aos-say` 的人都能清掉 bob 的對話（`/clear`）、看到帳號用量（`/cost`）。對**方向題 5**（`aos-say /stop` 當收工）的影響：用 `/` 開頭當給控制器的約定正好跟 claude 自己的 slash command 撞在同一個字頭——控制器認得的（`/stop`）自己吃掉、認不得的一律轉義，或約定改用別的字頭，兩種都要在控制器那層做，不能直接漏進 claude。
12. **寫端關掉（EOF）＝非主要收工方式**（使用者定 SIGTERM 才是）：第三題送出後立刻關寫端，claude **照樣答完手上那題**、約 2 秒後退出，**結束碼 0**（超過預算過的 session 則退 1）；閒著時關也直接退 0。

### 規劃要跟著改的地方（實測當下列的；11-02 晚的規劃第二版已逐條處理，留作對照）

- **收尾路**（第 0、2、4 節）：「控制器收工 → FIFO 寫端關 → bob 自己退」改成**控制器送 SIGTERM 給 bob**（`/exit` 不可用；要「只打斷這題」才用 `interrupt` 控制訊息）。SIGTERM 會丟掉正在答的那題（⑧），要先等到手上沒題、或接受丟題。
- **控制器怎麼拿到 bob 的 pid**：bob 與控制器是 daemon 的兄弟子項，控制器自己沒有 bob 的 pid。現成可能的路：① 讀 daemon 的狀態窗（`$AOS_DAEMON_STACK/…/daemon_state.json`，若表上有子項 pid）；② 改請 daemon 收（控制器 `aos-daemon-ctl rm bob`＝daemon 送 SIGTERM，不用知道 pid）；③ 讓 bob 的入口把自己的 pid 寫進公用資料夾。哪條合原則留給規劃。
- **一次一題 → 一直丟**（第 2 節 `turn` 的 ②、方向題 1）：照使用者決定改成有信就倒；同時要處理 ⑥「忙時多封併成一題、`result` 少於信數」——`aos-listen 信號` 的「信在 `cur/`＝還沒答」契約要重想。
- **同步方式**（第 2 節 `turn` 的 ①）：改成每隔一段時間讀 `bob_out.jsonl` 新行同步；轉成 OpenAI 形時要處理 ⑤ 的區塊陣列、跳過 ④ 的 `system`/`init`、看 ⑦ 的 `error_max_budget_usd` 與 ⑨ 的 `error_during_execution`。
- **slash command 過濾**（新加）：控制器倒進管子前擋／轉義開頭的 `/`（⑪）。
- **同生共死**：EPIPE 那條只在 bob 真的死了才成立；超預算（⑦）bob 不死，要另找機制（使用者決定：機制待規劃）。
- **起來時續接殘留的對話**（使用者決定，推翻方向題 4「第一版不接」）與**停掉再叫回**（後續功能預留）：⑩ 直接支撐這兩條——`--resume <session_id>` 重起記得前文、id 不變。`session_id` 從 `bob_out.jsonl` 任一行事件都拿得到；但 bob 若被 `/clear` 過 id 會換（⑪），要以**最後一行**的為準。**建議存放處**：控制器每次同步時把最新的 `session_id` 寫成公用資料夾裡的一個小窗，例如 `$AOS_DAEMON_STACK/resident_bob/bob_session.json`（`{"session_id": "…"}`，前綴 `bob_`、主題前置）；起 bob 時「有這個檔＝殘留，用 `--resume`；沒有＝開新的」。不直接從 `bob_out.jsonl` 撈，是因為那檔會長、還可能被人清掉；兩者都在 stack 裡，偵測「有沒有殘留」看小窗最便宜。`bob/_entry.json` 是靜態單子，塞不進 id——bob 的入口要變成能讀這個檔的小殼（或由控制器組 argv 起 bob），由規劃定。
- **衝突 6 (c)**：預算是 session 總額、超了不退只報錯（⑦），設不設、設多少仍是使用者定。
- **身體改名**：`turn` 換名字（使用者決定），名字待定。

**沒測的**：用工具時的事件形狀；`/compact`；超過一個寫端時的行為。花費：十三輪合計約 0.0043 美元（各輪最後的 `total_cost_usd` 加總；SIGTERM 打斷的那題沒記到帳，量很小）。

## 實作時代定（11-02）

工人照原則定的小決定，每條可翻案。

- **bob 多開 `--replay-user-messages`，對帳靠回吐的那行**（規劃第 2 節只寫三個旗標、第 3 節是「`init` 時把 `sent` 快照成 `answering`」）：實測三封同時在管子裡時，第一個 `init` 出來那刻三封都已寫進去、但第一題只答第一封，快照會把三封都算進第一題。回吐的 user 行（`isReplay: true`，緊接在 `init` 後面）內容＝這題併進去的訊息以 `\n` 接起來，照 `sent` 的順序比前綴就知道是哪幾封；對不上＝當成只答第一封、`mailbox_warning.txt` 記一行。
- **每輪順序是 看 bob → 同步輸出 → 送信**（規劃是 ①②③：先送再同步），縮小「送進去的新信跟正在開的那題」交錯的窗口。
- **user 行等回吐時才寫進 `history.jsonl`**（規劃：送出時寫）：送出時寫，連丟三句會變成「user user user、assistant assistant」，`aos-listen --last` 把三句都配給第一個回答（實跑第一次就這樣）；回吐時寫才是「幾則 user＋一則回答」一段段。
- **同一個 `message.id` 的 `assistant` 事件合成一則**；`out.jsonl` 最後一行是 `assistant` 時先不寫、等下一行出現（同一則可能還沒吐完；不另存狀態）。只有 `tool_use` 的那則 `content` 是 `null`＋`tool_calls`；`tool_result` 的內容是陣列時只接 `text` 區塊。
- **bob 在不在：直接讀 `loops_state.json`**（`$ref` 陣列照 aos-daemon-ctl 的讀法合回來），不叫 `aos-daemon-ctl ls --json`（每 300 ms 少起一支 Python）；不在表上一律退 1 `BobGone`（第一版沒有 `asleep`，不看 `bob` 欄）。
- **`relay_state.json` 多一欄 `bob_pid`**：表上 bob 的 pid 跟上次記的不同＝換了一支 bob（重跑 install）→ 先把舊輸出同步完，還沒結掉的 `sent` 全當沒送過、這輪重送。為的是 `rm bob`／超預算之後重掛時，卡在 `cur/` 的信會被答到。
- **超預算那個 `result` 照樣結掉 `answering`**（那題答案有吐，⑦），再 `aos-daemon-ctl rm bob`、退 1 `BudgetOut`；之後才送進去的信留在 `cur/`、重掛時重送。第一版寫成不結掉，實跑看到重掛後同一題答兩次才改。其他不是 `success` 的 `result`（`error_during_execution`）照樣結掉、警告檔記一行。
- **`mailbox_warning.txt` 照 agent 範本 queue 的 `letter_warning.txt`**：一行「信 <信號> 不採用：原因」、只留最後一封、暫存改名。
- **錯誤代號**：relay `ArgumentsBad`（給了任何參數，含 `--idle-ms`）、`DaemonMissing`、`BobGone`、`BudgetOut`、`PostFailed`；install `DaemonMissing`、`ArgumentsBad`（不收參數）、`SendFailed`（aos-daemon-ctl 的 stderr 照轉）。
- **寫管子斷了**（`BrokenPipeError`）：把 fd 1 `dup2` 成 `/dev/null` 再結束這輪，不然 Python 結束時 flush 緩衝會再炸、退 120。
- install 的位置用 `__file__`（realpath）算；`system.txt` 的 AOS_STACK 那句改成「執行中的狀態，不要動它」（掛在 daemon 底下時不在 `ws/.stack/`）。

以下四條是使用者「收尾」後**頂層代定、可翻案**（停下報告帶給他的四件）：

- **install 自己清掉殘留的 `stopped`**：add bob_ctl 之前讀控制器小格的 `loop_ctl.json`，有 `stopped` 這個 key 就只拿掉它（其他 key 如 `paused`、`interval_ms` 照留——`paused` 不會讓新控制器收工，留著是使用者自己的意思）；拿掉後沒東西就刪檔（N-06 沒寫＝回初始值），否則照 N-05 先寫 `.loop_ctl.json` 再改名。檔不在、讀不懂＝不動。理由：最小做法，只動「會讓新控制器一起來就收工」那一格；不改 N-28「daemon 不清小格」——清的是 install（掛它的那一方），不是 daemon。眉角：控制器還在跑時寫了 `stopped` 又立刻跑 install，可能把那次收工取消（aos-loop 每 300 ms 讀一次 ctl，實際上碰不到），不另處理。README 的「先 `rm -f $S/loop_ctl.json`」那步拿掉。
- **`aos-listen --status` 看得到控制器的 phase：讓讀的那一方也認 `loop_state.json`**（不把控制器的窗改回 `state.json`）。改回 `state.json` 跟「共用 stack 時名字加前綴」（[exec 像繼承 § 結論](2026-11-02-exec-inheritance.md#結論11-02跟使用者討論後)）衝突——控制器小格是 aos-loop 跟 relay 共用的 stack；讓 aos-listen 認前綴名不違背它，而且改動最小（`proto8/lib/aos/aos_ws.py` 的 `loop_state` 先找 `state.json`、沒有再找 `loop_state.json`，先找到的算數；aos-listen `--status` 那行標出讀的是哪份；ai_tools 的 `loop_phase` 用同一個函式，跟著認）。壞信那行 aos-listen 仍只讀 agent queue 的 `letter_warning.txt`，relay 的 `mailbox_warning.txt` 看不到——這輪沒動（N-16 agent queue 照舊叫 `letter_warning`），README 寫「`cat $S/mailbox_warning.txt`」。
- **N-28 補一句**「子項的環境多 `AOS_DAEMON_STACK`」（11-02 補），連 N-63 的 11-02 補與 N-64 ④。
- **結論 ⑩ 的 `total_cost_usd` 改正**：接著 session 的累計，不是從新行程重算（預算從頭算仍成立）。

## 實作結論（11-02）

**試驗場 `~/code/playground/agents/resident_bob/`**（照規劃第 4 節的樹，`agents/bob` 沒動）：`_entry`（install，Python 60 多行）、`README.md`（玩法＋眉角：掛 `ctl/_entry.json` 檔、FIFO 是 proc 自己定的、先 add bob、install 會拿掉殘留的 `stopped`）、`bob/_entry.json`（第 2 節的單子＋`--replay-user-messages`＋`--max-budget-usd 2`）、`bob/system.txt`、`ctl/_entry.json`、`ctl/loop.json`（照第 3 節）、`ctl/relay/_entry`（Python 約 290 行）。**relay 一輪**：讀 daemon 的表看 bob → 從 `out_offset` 讀 `out.jsonl` 新的整行，回吐的 user 行對 `sent` 定出這題答哪幾封、寫 user 行，`assistant`／`tool_result` 轉 OpenAI 形寫 history，`result` 把那幾封 `finish` → 探針開得到 FIFO 才 `claim-all`、逐封 `check`，`/` 開頭與壞信收掉記警告，好信寫一行 stream-json 到 stdout（只有這一行進 stdout，子程式全 `capture_output`）。

**實跑**（拷貝試驗場 `~/.cache/aos-c8a7-f-tools/pg-rbob/`，P8 指 `~/.cache/aos-c8a7-f/proto8`、daemon 加 `--enable-logs`；haiku；daemon 的 log 在 `pg-rbob/daemon.log`，bob 的原汁在 `pg-rbob/ws/.stack/loops/bob/out.jsonl`）：

1. **掛上**：install 印兩個信號，`aos-daemon-ctl ls` 有 `bob exec running`、`bob_ctl exec running`。
2. **兩題接前文、併題**：「回答 1+1」→`2`，「記住暗號 7」→`好`，「我第一題問你什麼」答得出。連丟三句（5+5、6+6、7+7）：第一句單獨答 `10`，後兩句併成一題答 `12\n14`；`cur/`、`new/` 清空；history「user、assistant、user、user、assistant」；三封 aos-listen 各拿到 `10`、`12 14`、`12 14`；`--last 2` 分段對。
3. **用工具寫檔**：`a.txt` 內容 `hi` 寫進 ws；history 是 user → `{"role": "assistant", "content": null, "tool_calls": [{"id": "toolu_…", "type": "function", "function": {"name": "Write", "arguments": "{…}"}}]}` → `{"role": "tool", "tool_call_id": "toolu_…", "content": "File created successfully…"}` → 最後的文字回答。claude 的工具事件：`assistant`（`tool_use` 區塊）、`user`（`tool_result` 區塊，沒有 `isReplay`）、`assistant`（文字），一則一個 `message.id`。
4. **paused**：信停在 `queue/new/`、`cur/` 空；改回 `false` 後送出、答到。
5. **`/cost`、`  /clear`**：沒進 bob（`out.jsonl` 沒有這兩個字），`mailbox_warning.txt` 一行「…以 / 開頭的訊息不轉送…」；aos-listen 那封印到上一則回答（規劃預料的不完美）。
6. **stopped**：送一題後立刻 `{"stopped": true}`：daemon log `bob_ctl done 0`、約 1.4 秒後 `bob done 0`，bob 答完那題（`20` 在 `out.jsonl`），信留在 `cur/`。
7. **重掛續接**：install 印「續接 session …」，bob 的 argv 尾巴是 `--resume ebcc…`，`out.jsonl` 全部只有這一個 `session_id`；第一輪就從 `out_offset` 補讀上次答完的 `20`、把留在 `cur/` 那封結掉；問「我剛才叫你記住什麼暗號」答 `暗號是 7。`。
8. **`rm bob`**：log `bob stopped 143`、0.4 秒後 `bob_ctl done 1`；`bob_ctl/stderr.txt` 是 relay 一行「`relay: BobGone bob 不在 daemon 的表上…`」加 aos-loop 自己一行「第 76 次 relay 失敗，結束碼 1」。
9. **超預算**：拷貝裡改 `0.0003`、重掛：前兩題 `31`、`32`，第三題答 `33` 後 `result` 是 `error_max_budget_usd` → 那封結掉、aos-listen 拿到 `33`，`relay: BudgetOut …`、`bob_ctl done 1`、bob 被收掉 `stopped 1`（超過預算的 session 收 SIGTERM 退 1，不是 143）；`cur/` 空。改回 2、重掛、問「第一個暗號」答 `7`，`stopped` 收工兩個都 `done 0`。修正前那一輪（`0.001`）還驗到：卡在 `cur/` 的信重掛後會重送並答到（`bob_pid` 那條）。

收尾那輪又花約 0.0003 美元（兩題）。驗完 daemon 收工、沒有殘留的 aos-／claude 行程；使用者試驗場的 `ws/`、`daemons/` 沒動。**花費**：這段對話共 26 個 `result`，最後的 `total_cost_usd` 約 0.0038 美元；另外先單獨實測回吐與工具事件一次約 0.0012 美元。

**跟規劃或先前結論不同的**：

- 對帳改用 `--replay-user-messages`、user 行回吐時才進 history、每輪先同步再送（見代定）。
- **`--resume` 之後 `total_cost_usd` 接著舊的累計**（0.00195 → 重掛後第一題 0.00206），跟結論 ⑩「從新行程重算」不同；但 `--max-budget-usd` 是照**這一支行程**算的（第三支行程設 0.0003，在累計 0.0037 時才撞到）——所以「重跑 install 預算從頭算」仍成立，只是 `total_cost_usd` 不能拿來看這一支花了多少。
- **`stopped` 會留在 `loop_ctl.json`**：規劃第 5 節「`stopped` 之後再 `aos-exec ../agents/resident_bob` 就續接」少一步——小格不清（N-28），新的控制器第一次就讀到 `stopped`、立刻收工、bob 跟著 EOF 退。**收尾時改成 install 自己拿掉殘留的 `stopped`**（代定）；實跑：`stopped` 收工（`bob_ctl done 0`、`bob done 0`）後 `loop_ctl.json` 還是 `{"stopped": true}`，直接再跑 install → 檔被拿掉、兩個 running、續接同一個 session，問「剛才叫你記住什麼暗號」答 `42`；再 `stopped` 兩個都 `done 0`。
- `aos-listen --status` 讀 `state.json`，控制器的窗叫 `loop_state.json`（規劃的前綴），所以 status 看不到 loop 的 `phase`。**收尾時改成 aos-listen 也認 `loop_state.json`**（代定）；實跑 `--status` 印 `loop     phase running（loop_state.json）`。test_human 加 1 案。
- 「控制器下一輪退 1（stderr 一行）」實際 `stderr.txt` 是兩行：relay 一行、aos-loop 自己一行。

## 要使用者看的衝突與方向題（11-02 晚第二版）

第一版的方向題 1（一次一題）、4（重掛接不接）、5（收工的話）已被[決定](#決定11-02使用者)裁掉或改寫，不再列；衝突 1～6 保留（有的改了後果），新加衝突 7、8 與方向題 1～5。

### 衝突 1：用 FIFO 接兩個兄弟＝aos 標準沒有的交流方式

- **條文**：C-75「proc 之間的交流」只有投遞、窗、父子交代三種；N-16 10-28 把「檔案串流」從標準刪掉（「要用由 proc 自己定」）。
- **衝突在哪**：bob 跟控制器之間那條 `in.fifo` 是 Linux 的管子——不是信箱、不是窗、不是父子交代（兩個是兄弟）。aos 看不見它、aos-daemon-ctl 不知道這兩個子項綁在一起。
- **各自後果**：(a) **照規劃**（fable 建議）：FIFO 由 inst 的 `stdin`／`stdout` key 指定，算「proc 自己定」那一類，不立條文、不改標準，只在 resident_bob 的 README 說明；代價是「一支 claude 一直跑」只有這條路。(b) 不用 FIFO＝每題 `claude -p --resume`（aos-eca-turn 那條），bob 這個「exec」就不存在、不符使用者原文「會一直跑」。(c) 把「管子」加進 C-75 當第四種——條文要動、aos 什麼都不必替它做，不值得。

### 衝突 2：兄弟要共用位置 → daemon 得把 `AOS_DAEMON_STACK` 設給子項

- **條文／裁定**：使用者 11-01「環境變數只在必要時用」；daemon-env 方向題 2 使用者「照 fable 建議先不做，等常駐 bob 用到再說」。
- **衝突在哪**：控制器要找 bob 的小格（FIFO、`out.jsonl`）、讀 `loops_state.json`、叫 `aos-daemon-ctl`，全要知道 daemon 的 stack；兄弟之間沒有父子交代，`_entry.json` 是靜態檔。
- **各自後果**：(a) **daemon 起子項時 `setenv AOS_DAEMON_STACK`**（fable 建議；`child.cpp` 幾行、一個測試）：hub 型變數（N-63），跟使用者 shell 裡 export 的同名同值，子項裡的 `aos-daemon-ctl` 順便能用；就是方向題 2 說的「用到的時候」。(b) 不改 daemon：路徑寫死在兩個 `.env`，搬家就改檔。(c) 控制器自己起 bob（第 1 節 (A)），不需要新變數但重做 daemon。

### 衝突 3：歷史兩份——原汁 `out.jsonl` 跟 OpenAI 形的 `history.jsonl`

- **條文**：C-56「不多造格式」；P-41 history 一行一則 OpenAI message；決定 35「claude 自己存的 session，aos 弄一份 symlink 或複製過來管」。
- **衝突在哪**：claude 吐的是自己的事件流（⑤：`assistant` 的 `message` 是 Anthropic 區塊陣列，不是 OpenAI 形）；aos-listen 只認 OpenAI 形。要 aos-listen 能用就得由 `relay` 轉一份。
- **各自後果**：(a) **兩份都留**（fable 建議）：`history.jsonl` 給 aos-listen 與人看、`out.jsonl` 留工具呼叫、花費、`session_id`；代價是 `relay` 多十幾行轉換。(b) 只留原汁：aos-listen 不能用。(c) 只留轉過的：丟掉花費與事件細節。決定 35 的 symlink `~/.claude/projects/<雜湊>/` 本題仍沒做（要的話 install 多一步）。

### 衝突 4：N-28「子項結束不重起」vs「常駐」

- **條文**：N-28「子項結束後不自動重起……要『結束了怎麼辦』自己在鏈上接工具」；P-20 失敗停下等人。
- **衝突在哪**：bob 死了（崩、網路斷、`--resume` 接不回）控制器跟著退 1；daemon 重起時兩個也不回來（用信掛的，`adopt` 只接活著的）。「常駐」在 aos 裡只到「沒人弄死它就一直在」。
- **各自後果**：(a) **照條文不自動重起**（fable 建議）：`ls` 看不到了、`stderr.txt` 有原因，人再跑一次 install 重掛（會 `--resume` 接回對話）。(b) 要自動回來：install 外面再包一層沒有 `max` 的 aos-loop——失敗也會無限重起、燒預算。(c) 寫進 `daemon.json` 的 `execs`：daemon 重起會起，但接不了 `--resume`。

### 衝突 5：控制器用 exec 型包一支 aos-loop，掛的目標指到 `_entry.json` 檔

- **條文／結論**：N-28 loop 型子項的行程 stdin／stdout 由 daemon 接 `/dev/null`（loop-stdio 結論）；aos-daemon-ctl「資料夾有 `loop.json`＝loop 型」。
- **衝突在哪**：控制器要 aos-loop **行程本身**握著 FIFO 寫端，loop 型做不到，只好入口寫單子、當 exec 型掛；而 `ctl/` 有 `loop.json` 會被 aos-daemon-ctl 認成 loop 型，所以掛的目標得指到 `ctl/_entry.json` 這個檔。表上它是 `exec`，看不出是一支 loop。
- **各自後果**：(a) **照規劃**（fable 建議）：不改程式，README 說明「掛 `_entry.json` 檔、不要掛資料夾」；代價是表上種類不準、要記得這個眉角。(b) 改 aos-daemon：loop 型子項物件多認 `stdout`（或 `stdio`），daemon 起子 loop 時照它開；N-28 要補、`child.cpp` 要改，以後任何「loop 行程要握著一個檔」都能用——正好對上使用者 loop-stdio 原文「daemon 的子 loop……應該可以自行指定 stdin/out 吧」。可以先 (a)，等第二個用到的再 (b)。

### 衝突 6：「exec 就是我們現有的 bob」——但要加旗標、處理預算

- 使用者原文「exec 就是我們現有的 bob」。實際上要加三個旗標、`system.txt` 改「做完就結束」那句；`--max-budget-usd` 是 session 總額、超了不退只報錯（⑦）。
- **各自後果**：(a) **另開 `agents/resident_bob/bob/`**（fable 建議）：`agents/bob` 原封不動、射後不理版照舊；代價是 `system.txt` 兩份要同步。(b) 直接改 `agents/bob`：手動 `aos-exec ../agents/bob -- 題` 會卡在等 stdin。(c) **預算**：拿掉（控制器反正會在 `error_max_budget_usd` 時收 bob）或設一個 session 上限（例 `--max-budget-usd 3`；`--resume` 重起後從頭算 ⑩）——錢的事，使用者定。

### 衝突 7：控制器建 bob 小格裡的 FIFO、讀 bob 小格的 `out.jsonl`

- **條文／結論**：exec 像繼承結論「各格自己管好自己的手」；P-17 叫別人時由呼叫方給小格、「留著給人看」；C-52 被叫的只看自己的 stack。
- **衝突在哪**：bob 的小格是 daemon 建的，控制器在 bob 起來前進去 `mkfifo`、之後一直讀裡面的 `out.jsonl`——一個兄弟在另一個兄弟的小格裡動手。
- **各自後果**：(a) **照規劃**（fable 建議）：控制器是「請 daemon 起 bob」的那一方，實質上就是 P-17 的呼叫方——替被叫的準備小格、看它的 stack、叫完由它收；bob 自己只看 `$AOS_STACK`、不知道上面有誰（C-52 守住）。寫進去的只有 FIFO 一個檔、而且在 bob 存在之前。(b) 把 FIFO 與 `out.jsonl` 放控制器的小格：bob 的單子要寫 `loops/bob_ctl/…`——換成 bob 得知道控制器叫什麼、知道上面有誰，更糟。(c) 開第三個共用資料夾 `$AOS_DAEMON_STACK/resident_bob/`（第一版）：誰都不是誰的，但多一處、而且 `loops` 旁邊多一個頂層名字（daemon stack 的保留名之外使用者要自己小心）。

### 衝突 8：使用者「結束不是靠關管子」vs 規劃仍用 EOF 當「控制器沒了 → bob 跟著走」的保險

- **決定**：「結束由控制器明確送 SIGTERM 或 `/exit`，不是靠關管子」。
- **衝突在哪**：規劃裡控制器**主動**要 bob 停（超預算、睡）用 `aos-daemon-ctl rm bob`（SIGTERM），合決定；但控制器**自己**被停或死掉時，bob 走的是 EOF（⑫：答完手上那題退 0）——沒有任何程式送 SIGTERM，因為控制器已經不在了。
- **各自後果**：(a) **留 EOF 當保險**（fable 建議）：零成本、SIGKILL 也擋不住、而且比 SIGTERM 溫和（不丟題）。(b) 一律 SIGTERM：控制器收工前先 `rm bob`——`stopped` 那條做得到（`relay` 看 `loop_ctl.json`？不，ctl 是 aos-loop 讀的，身體看不到「下一輪不會來」），控制器被 `rm`／崩掉／SIGKILL 時做不到，仍要 EOF 兜底。所以 (b) 只是在 (a) 之上多一條、不能取代。→ [方向題 1](#方向題-1控制器自己被停時bob-走-eof答完退還是先-rm-bob立刻退)。

### 方向題 1：控制器自己被停時，bob 走 EOF（答完退）還是先 `rm bob`（立刻退）

- 原則推不出：P-36 說收工先收子程式，但 bob 不是控制器的子程式；兩種都合 N-28。
- 例子：使用者 `echo '{"stopped": true}' > loop_ctl.json` 時 bob 正在寫詩。**EOF**（fable 建議）：bob 寫完、`done 0`、答案進 `out.jsonl`（但 `relay` 已經停了，history 少最後一則、信留在 `cur/`；下次 install 續接時 `relay` 從 `out_offset` 補讀、把信結掉）。**先 `rm bob`**：詩丟掉、`done 143`、乾淨但粗暴；而且只有 `stopped`／`rm bob_ctl` 這兩條做得到，崩掉時仍是 EOF。

### 方向題 2：`/` 開頭的訊息——拒收，還是轉義送進去；控制器自己的指令用什麼字頭

- 原則推不出：⑪ 證明 `/` 開頭會被 claude 當 slash command 執行（`/clear`、`/cost`），一定要在控制器擋；怎麼擋是取捨。
- 例子：使用者說「/tmp 底下有什麼」。**拒收**（fable 第一版）：當壞信收掉、`mailbox_warning.txt` 記一行，aos-listen 會印到上一則回答（跟 aos-eca-turn 壞信同一種不完美）；優點是不猜 claude 怎麼判 slash。**轉義送進去**：前面加一個空白或「請看：」再送——claude 會不會先 trim 再判沒測，要測。**控制器自己的指令**（第二版 `/sleep`、以後的 `/stop`）跟 claude 的 slash 撞同一個字頭：認得的自己吃、不認得的擋掉，或換字頭（例 `!sleep`、`@ctl sleep`）——使用者偏好哪種字頭。

### 方向題 3：`relay` 放哪、叫什麼

- 原則推不出：跟 aos-eca-turn 同一類（外部 CLI 的一輪），但對著一支活著的 claude 寫管子、不起新行程。
- 例子：**先放試驗場 `agents/resident_bob/ctl/relay/`**（fable 定）；跑順了升成 `proto8/bin/aos-claude-relay`（C-54 R13 `aos-<領域>-<功能>`；stream-json 是 claude 專屬格式）。另一條：做成 aos-eca-turn 的一個模式——eca-turn 綁著 cli_session／tmux，塞進去會變重。身體名 `relay` 是 fable 挑的（每輪搬一趟：信進、答出；eca 的 turn 讓開），使用者可換。

### 方向題 4：併題時被忽略的那句（⑥ 第三句）要不要補救

- 使用者 11-02：「第三句被忽略那種情況算模型的事，不另外補救（若你認為原則上該處理，列成方向題）」。fable 看：原則上**不該由控制器補救**——控制器不看內容（C-52 上層不知道下層是什麼），判「哪句沒被理會」要讀懂回答，那是腦的事。可做的只有讓它少發生：`system.txt` 加一句「一則訊息裡有好幾個要求時每個都要回」；或 `relay` 第 2 步一輪只送一封、其餘留到下一輪（每輪 300 ms，忙時仍會併，只是少併）。**fable 建議：system.txt 加一句，其餘不做**。
- 例子：三句「1+1」「2+2」「前兩個相加」→ `2`、`4`，第三句沒答。aos-listen 第三封印到的是 `4`。

### 方向題 5：閒置多久睡、要不要有睡的指令（第二版）

- 原則推不出：使用者說「長時間沒有動作，或是使用特定指令後」，數字與字頭是偏好。
- 例子：`--idle-ms 600000`（10 分鐘）＋ `/sleep`；睡著的 bob 不花錢也不佔記憶體，醒來多等約 4 秒（第一題的啟動時間①）。要不要預設就睡（沒給 `--idle-ms` 也睡）、閒置多久算久——使用者定。
