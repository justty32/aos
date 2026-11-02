# 2026-11-02 常駐版 bob：一個 exec（一直跑的 bob）＋一個 loop（外部控制器），掛在 daemon 底下

← [thinking README](README.md)｜月份表 [2026-11](months/2026-11.md)｜前情：[11-01 試驗場 bob](2026-11-01-playground-bob.md)（bob＝`claude -p` 一次跑完）、[11-02 試驗場 daemon](2026-11-02-playground-daemon.md)（bob 用 `execs` 射後不理地掛上去；方向題「常駐的掛法」就是本題）、[10-29 agent-bob 決定 33～35](2026-10-29-agent-bob/04-頂層對八題的再想.md#決定10-30)、[10-30 agent-lifecycle A（queue）、B（納管外部 agent）](2026-10-30-agent-lifecycle.md)｜同日裁定（規劃以裁定後的樣子為準）：[state 窗](2026-11-02-state-window.md)（`daemon_ctl.json`／`daemon_state.json`、log 預設不印）、[loop-stdio](2026-11-02-loop-stdio.md)（身體寫成單子就能指定 stdin／stdout）、[daemon-env](2026-11-02-daemon-env.md)（`AOS_DAEMON_STACK`、`--daemon-stack`；方向題 2「daemon 要不要把變數設給子項」說等常駐 bob 用到）、[exec 像繼承](2026-11-02-exec-inheritance.md)（呼叫＝給小格、變成＝共用 stack；共用時加前綴）｜條文：[N-13、N-14、N-16](../docs/NORMS/05-基礎設施-窗.md)、[N-28、N-54](../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-55、N-57～N-64](../docs/NORMS/10-基礎設施-定義與工作區.md)、[P-11、P-15、P-17、P-19、P-20](../docs/CONVENTION/02-題目stack停錯腦.md)、[P-32～P-38](../docs/CONVENTION/06-巢狀.md)、[C-52、C-56、C-65、C-75](../docs/CONCEPTS.md)｜程式：[aos-daemon](../impls/aos-daemon/README.md)、[aos-loop](../impls/aos-loop/README.md)、[aos-exec／inst](../impls/aos-exec/README.md)、[aos-post](../impls/aos-post/README.md)、[aos-daemon-ctl](../bin/README.md)、[aos-say／listen](../extras/human/README.md)｜場地 `~/code/playground/`（WSL，不在 git）

本檔只記使用者原文（逐字）、決定、fable 照原則定的規劃（可翻案）、要使用者看的衝突與方向題（[user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。**只規劃，程式與試驗場都還沒動**；步驟表在最後。

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

## 現況（查清的，不是規劃）

- **現有 bob**（`~/code/playground/agents/bob/`，兩個檔、沒程式碼）：`_entry.json`＝argv 陣列 `claude -p --model haiku --tools Read,Write,Edit,Glob,Grep --permission-mode acceptEdits --strict-mcp-config --max-budget-usd 0.3 --add-dir {$env AOS_WS} --append-system-prompt-file system.txt`；`system.txt` 說明 `AOS_WS`／`AOS_CD`／`AOS_STACK` 各指什麼、`env:XXX` 寫法、做完說一兩句。**怎麼收題**：題目是 `aos-exec ../agents/bob -- "題"` 的參數（`--` 與題原樣到 claude）。**怎麼跑**：aos-exec cd 進 `agents/bob/`、exec 成 claude；一題答完 claude 自己退出。**歷史放哪**：aos 這邊沒有——bob 沒開窗、沒寫 stack；claude 自己把 session 存在 `~/.claude/projects/<cwd 雜湊>/`（決定 35 說這類要 symlink 或複製過來管，還沒做）。stdout 那句「我做了什麼」在手動叫時印到終端機；掛在 daemon 底下時被丟掉（N-28）。
- **掛在 daemons/main 底下的射後不理版**（11-02 已做）：`execs_added: {"bob": ["../../agents/bob", "--", "題"]}` 一封信一題，做完 `done`、不重起；同名再問要先 `rm`。
- **「停著等」已有兩條現成路**，都不是「claude 一直跑」：① aos agent 範本＝agent 是函數、停著等交給 aos-loop（決定 34；round 的 `--on-empty idle`）；② 外部 CLI＝aos-eca-turn 每輪 `claude -p --resume <id>`（每題起一支新的 claude 行程、靠 session 接回），畫面版在 eca-hub（使用者說先不討論，本題不綁它）。
- **`claude -p` 有「一直跑」的模式**：`--input-format stream-json`（stdin 一行一則 `{"type": "user", "message": {"role": "user", "content": "…"}}`，讀到 EOF 才結束；同一個行程、同一段對話），要配 `--output-format stream-json --verbose`（cli_session 已在用 stream-json 輸出）；stdout 一行一事件（`system`／`assistant`／`result`…）。**要實測**（步驟 0）：這是 fable 憑 Claude Code 文件的記憶，沒在試驗場跑過。11-02 已實測，見[結論](#結論11-02-實測)。
- **inst 單子的 `stdin`／`stdout`**：`inst_exec.c` 在 fork 之前、aos-exec 自己的行程裡 `open()` 路徑（stdin `O_RDONLY`；stdout `O_WRONLY|O_CREAT|O_TRUNC`，`stdout_append` 改 `O_APPEND`），上層資料夾要已存在。路徑是 FIFO 時就是 Linux 的 FIFO 語意：開讀端等到有寫端、開寫端等到有讀端；**讀端在所有寫端關掉後讀到 EOF**。
- **daemon 的子項**：loop 型＝daemon 自己起 `aos-loop <小格>/loop.json`，**行程本身的 stdin／stdout 接 `/dev/null`**（身體可以用單子另外指）；exec 型（`execs`）＝直接 `aos-exec 目標` 一次，stdin／stdout 同樣 `/dev/null`、stderr 到小格 `stderr.txt`，目標是資料夾時入口可以是 inst 單子（C-73），單子裡的 `stdin`／`stdout` 由 aos-exec 開。兩種子項各有自己的小格 `$AOS_STACK/loops/<名字>/`，環境只繼承 daemon 的（`AOS_WS` 可用 `ws` 另給）；**daemon 不給子項任何指到自己的變數**（daemon-env 方向題 2 留著）。`aos-daemon-ctl add [--kind loop|exec|max1] [--name N] [--ws WS] XXX`：`--kind` 沒給、XXX 有 `loop.json`＝loop 型；給 `--kind exec` 就是 exec 型。
- **aos-say／aos-listen**：只碰一個 stack——`aos-say [--stack S] 話`＝`aos-post send --ordered S/queue`（body `{"role": "user", "content": 話}`，沒 queue 就建）；`aos-listen [--stack S] 信號`＝信還在 `queue/new/`／`cur/` 就等，不見了印 `S/history.jsonl` 最新那則 assistant；`--follow`／`--last N`；`--status` 讀 `S/state.json` 的 `phase`（沒有就不印）。

## 規劃（fable，照原則定的細節，可翻案）

### 0. 一句話

**bob 的 stdin 是一條 FIFO、stdout 是一個追加檔；控制器是一支 aos-loop，它的 stdout 就是那條 FIFO**——控制器活著，FIFO 的寫端就一直開著，bob 就一直等下一句；控制器收工，寫端關掉，bob 讀到 EOF、答完手上那題就自己結束。訊息走 aos-say 的 queue、歷史走 aos-listen 的 `history.jsonl`，控制器每輪只做「把 queue 的一則倒進 FIFO、把 bob 吐出來的接進 history」。**不加新機制，只組合現成的**（inst 的 `stdin`／`stdout`、aos-loop、aos-post、aos-say／listen、daemon 的 `execs`），要寫的程式只有控制器每輪跑的那支小程式（使用者「loop 所執行的各種東西也會需要另外定義」）。

### 1. 「exec」那半：現有 bob 怎麼變成一直跑

- **還是 `claude -p`，加三個旗標**：`--input-format stream-json --output-format stream-json --verbose`。其餘旗標照現有 bob；`system.txt` 多兩句（「你會一直在，一題接一題，答完等下一題」「每題答完用一兩句說你做了什麼」）。**`--max-budget-usd 0.3` 要拿掉或調大**：那是一個 session 的總預算，常駐的 bob 一個 session 跑好幾題，0.3 幾題就撞到、claude 自己退出（衝突 6）。
- **等新訊息的方式＝stdin 阻塞在 FIFO 上**：claude 沒讀到下一行就什麼都不做、不花錢（空閒時什麼都不做；N-28「aos 不保證子項輸出不無限長」照舊）。沒有輪詢、沒有 sleep、沒有自己寫循環（agent-bob 10-29 的教訓：停著等不自己做）。
- **入口寫成 inst 單子**（C-73；loop-stdio 結論「身體寫成單子就能指定 stdin／stdout」），所以不必等「`execs` 收單子」那題：

  ```json
  // agents/resident-bob/bob/_entry.json
  {"argv": ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            "--model", "haiku", "--tools", "Read,Write,Edit,Glob,Grep", "--permission-mode", "acceptEdits",
            "--strict-mcp-config", "--add-dir", {"$env": "AOS_WS"}, "--append-system-prompt-file", "system.txt"],
   "stdin":  {"$env": "AOS_DAEMON_STACK", "$path": "resident_bob/in.fifo"},
   "stdout": {"$env": "AOS_DAEMON_STACK", "$path": "resident_bob/bob_out.jsonl"}, "stdout_append": true}
  ```

  `stderr` 不寫＝照 daemon 給的小格 `stderr.txt`。`bob_out.jsonl`＝claude 原汁的 stream-json（一行一事件），**追加、不重寫**；這是 bob 的紀錄、不是給上層的成果（決定 26），所以不在工作區。
- **共用的位置 `$AOS_DAEMON_STACK/resident_bob/`**：bob 與控制器是 daemon 底下的**兩個兄弟子項**，各有小格；它們要共用一條 FIFO 跟兩個檔，照 [exec 像繼承 § 結論](2026-11-02-exec-inheritance.md#結論11-02跟使用者討論後)「共用 stack 時加自己的前綴或自己開資料夾」，在 daemon 的 stack 底下開一個 `resident_bob/`（底線、主題前置，C-54），裡面 `in.fifo`、`bob_out.jsonl`、`queue/`（aos-say 建）、`history.jsonl`（控制器寫）。**這需要 daemon 把 `AOS_DAEMON_STACK` 設給子項**——daemon-env 方向題 2 說「等常駐 bob 用到再說」，現在就是那個時候（衝突 2，另列替代）。daemon 的 stack 整個公開（使用者 11-02 daemon-env 定案），所以放這裡不多開權限。
- **誰建 FIFO**：資料夾函數的入口（第 3 節的 install）建；bob 起來時 FIFO 一定要已經在（inst `open` 不建 FIFO、路徑不在＝`OpenFailed` → bob `done` 退 1、不重起）。

### 2. 「loop」那半：外部控制器

- **控制器＝一支 aos-loop**，定義在 `agents/resident-bob/ctl/`：

  ```json
  // ctl/_entry.json    —— 讓 aos-loop 這個行程本身的 stdout 握著 FIFO 的寫端
  {"argv": ["aos-loop", "loop.json"],
   "stdout": {"$env": "AOS_DAEMON_STACK", "$path": "resident_bob/in.fifo"}, "stdout_append": true}
  // ctl/loop.json      —— 每 300 ms 跑一次 turn；ctl／state 窗照 aos-loop 慣例、前綴 loop_（exec 像繼承）
  {"exec": "turn", "interval_ms": 300, "ctl": "loop_ctl.json", "state": "loop_state.json"}
  ```

  aos-exec 跑這張單子：開 FIFO 寫端（會等到 bob 那邊開了讀端）、起 aos-loop，aos-loop 的 fd 1＝FIFO、**整個行程期間都開著**；log 預設不印（loop-stdio 決定），所以 fd 1 上只有身體 `turn` 寫的東西。身體 `turn` 繼承 fd 1（aos-loop 跑資料夾目標＝fork＋`run_cli`、不另開串流），往 stdout 寫一行＝送進 bob 的 stdin。
- **為什麼控制器要用 exec 型子項掛、不用 loop 型**：loop 型是 daemon 自己起 `aos-loop`、行程的 stdout 接 `/dev/null`（loop-stdio 結論：子 loop 程序本身的 fd 是 daemon 定的），沒地方讓它握住 FIFO；每輪身體自己開 FIFO 寫完就關＝bob 每題都讀到 EOF、答完就退。所以 `ctl/` 是一個入口為單子的資料夾程式，用 `aos-daemon-ctl add --kind exec` 掛（衝突 5 另列「改 aos-daemon 讓 loop 型子項指定自己的 stdout」）。
- **控制 bob 結束與否＝控制器的生死**：
  - 控制器收工（`loop_ctl.json` 寫 `{"stopped": true}`、或 daemon `rm bob-ctl` 送 SIGTERM）→ aos-loop 結束、aos-exec 結束 → FIFO 沒有寫端 → bob 讀到 EOF → claude 答完手上那題自己退出、結束碼 0 → daemon 表上 bob `done 0`。**優雅收尾**，不送訊號給 claude。
  - bob 先死（預算用完、崩掉、`rm bob`）→ 控制器下一次往 FIFO 寫＝EPIPE → `turn` 失敗退 1 → aos-loop 以 1 結束（P-20：失敗就停、不重試）→ 表上 `bob-ctl done 1`。兩邊**同生共死**，不會剩一個孤兒等著。
  - 暫停＝控制器 `loop_ctl.json` `{"paused": true}`：訊息在 queue 排著、bob 閒著（N-07 的 `paused` 原義；一次＝一則）。
- **把訊息丟進去**：使用者 `aos-say --stack $AOS_DAEMON_STACK/resident_bob "題"`（＝`aos-post send --ordered …/queue`，有順序，N-16）。`turn` 每輪：手上沒有在答的題、`queue/new/` 有信 → `aos-post claim` 一封 → `aos-post check` 讀 body（`{"role": "user", "content": …}`）→ 把 `{"role","content"}` 原樣接進 `history.jsonl`（agent-lifecycle A-3：queue 的一則＝history 的一行）→ 改寫成 claude 的輸入形狀 `{"type": "user", "message": {"role": "user", "content": …}}` 一行寫到 stdout（＝FIFO）。信**留在 `cur/`**，直到 bob 答完。**一次一題**（A-5；方向題 1）。
- **把歷史拉出來**：`turn` 每輪先讀 `bob_out.jsonl` 從上次讀到的位置（偏移記在控制器自己的小格 `$AOS_STACK/turn_offset.json`，前綴 `turn_`）往後的新行：`type: "assistant"` 的把 `message`（已經是 OpenAI 形的 `{"role": "assistant", "content": [...], …}`）接進 `history.jsonl`；看到 `type: "result"` ＝這題答完 → `aos-post finish` 那封信。於是 **`aos-listen --stack $AOS_DAEMON_STACK/resident_bob 信號` 原樣可用**（信在 `cur/` 就等、不見了印最新那則 assistant 的文字），`--last N`／`--follow` 也是。原汁的 `bob_out.jsonl` 照留（工具呼叫、花費、session id 都在裡面）；只要「bob 說了什麼」看 `history.jsonl`（衝突 3）。
- **bob 是控制器的子程式還是兄弟**：照「呼叫＝給小格（組合）、變成＝共用 stack（繼承）」——控制器**沒有呼叫 bob**（不是 `AOS_STACK=$AOS_STACK/tools/bob aos-exec …`，P-17），bob 也不是控制器「變成」的（不共用控制器的 `$AOS_STACK`）；兩個都是 **daemon 的子項、互為兄弟**，各有自己的小格，只共用 daemon stack 底下那一個加了前綴的資料夾。這也是為什麼要 daemon 給 `AOS_DAEMON_STACK`——兄弟之間沒有父子交代（N-64），只能靠共同的上一代告訴他們「公用的地方在哪」。
- **控制器與 bob 之間靠的檔**（全在 `$AOS_DAEMON_STACK/resident_bob/`）：

  | 檔 | 誰寫 | 誰讀 | 是什麼 |
  |---|---|---|---|
  | `in.fifo` | 控制器（aos-loop 的 fd 1，`turn` 寫） | bob 的 stdin | 一條管子；不是窗也不是信箱（衝突 1） |
  | `bob_out.jsonl` | bob 的 stdout（追加） | `turn` | claude 原汁的 stream-json 事件流 |
  | `queue/` | aos-say（任何人） | `turn` 認領、收掉 | N-16 有順序的信箱（agent-lifecycle A） |
  | `history.jsonl` | `turn` | aos-listen、人 | 一行一則 OpenAI message（P-41 形） |

  控制器自己的小格（`loops/bob-ctl/`）：`loop_ctl.json`、`loop_state.json`、`turn_offset.json`、`stderr.txt`。bob 的小格（`loops/bob/`）：只有 `stderr.txt`。

### 3. 資料夾函數長什麼樣、怎麼請 daemon 掛起

```
agents/resident-bob/
  _entry             ← install：建公用資料夾與 FIFO、請 daemon 掛起 bob 與 bob-ctl（Python 小殼，十幾行；見下）
  README.md          ← 玩法（指令照第 4 節）
  bob/
    _entry.json      ← 第 1 節那張單子（現有 bob＋三旗標＋stdin／stdout）
    system.txt       ← 現有 bob 的，多兩句
  ctl/
    _entry.json      ← {"argv": ["aos-loop", "loop.json"], "stdout": FIFO}
    loop.json        ← {"exec": "turn", "interval_ms": 300, "ctl": …, "state": …}
    turn/
      _entry         ← 控制器每輪跑的一支小程式（Python；見下）
```

- **`_entry`（install）做四件事**，然後結束——這就是「配合 daemon 進行 exec 和 loop 的掛起」：① `mkdir -p $AOS_DAEMON_STACK/resident_bob`、`mkfifo …/in.fifo`（已在就跳過）；② `aos-daemon-ctl add --kind exec --name bob <自己的絕對路徑>/bob`；③ `aos-daemon-ctl add --kind exec --name bob-ctl <自己的絕對路徑>/ctl`；④ stdout 印兩個信號與一句「掛上了，`aos-say --stack … 話`」。daemon 哪一隻＝`$AOS_DAEMON_STACK`（跟 aos-daemon-ctl 同一條，N-63），沒設＝退 1 `DaemonMissing`。它不跑 bob、不跑 loop、不留行程；跑第二次＝重掛（daemon 表上已有同名的照 N-54「已在跑的不重起」，等於沒事）。寫成 Python 不寫 sh（user/03「少用 sh」；amy 的 `_entry` 同一種小殼）；四步只是 `os.mkdir`／`os.mkfifo`／兩次 `subprocess.run(["aos-daemon-ctl", …])`。
  - 為什麼不讓 install 自己 `aos-post send` 一封 `{"execs_added": {...}}`：路徑得寫絕對、信裡的指示詞是 daemon 在解——aos-daemon-ctl 已經把這些包好（轉絕對、`--kind`、`--name`、建 `.stack` 捷徑），不重做。
  - 工作區：兩個子項不給 `--ws`＝繼承 daemon 的 `AOS_WS`（跟射後不理版一樣，bob 的 `--add-dir` 拿到 `ws/`）。要讓 bob 服務別的工作區＝install 多收 `--ws` 原樣轉給兩個 add（第二版再說）。
- **`turn`（控制器每輪的身體）**：Python，一輪＝① 讀 `bob_out.jsonl` 新行→接 history／看到 `result` 就 `finish`；② 手上沒題、queue 有信→`claim`→接 history→寫一行到 stdout；③ 退 0（有沒有事都退 0，由 loop 的 `interval_ms` 隔一下再來；不用 10——收工是人的事，見方向題 5）。底下全叫 aos-post 的子命令、不自己 rename（agent-lifecycle A-9）。失敗（寫 stdout EPIPE、`bob_out.jsonl` 讀不到、aos-post 失敗）＝stderr 一行、退 1（P-20、P-21）。狀態只有 `turn_offset.json`（讀到第幾個 byte）與「正在答的那封信號」（寫在同一份）。**這是唯一要新寫的程式**，先放試驗場（方向題 3）。
- **各身體「另外定義」**：使用者說 loop 執行的東西要另外定義——照 N-50／P-25 放在控制器自己的資料夾底下（`ctl/turn/`，相對路徑 `turn`、零個 `..`）；以後要加別的（例如每 N 輪把 `history.jsonl` 壓成摘要、或定時問 bob 一句）就是 `ctl/` 底下再一個資料夾、`loop.json` 的 `exec` 改指一張 fsm（`aos-fsm`，各身體一格）——本題只有一個身體，不先鋪 fsm（C-56 最後一步減法）。

### 4. 掛進 daemons/main，使用者在 shell 怎麼用

`daemons/main/daemon.json` **不用改**（照 state-window 裁定後的樣子，窗名 `daemon_ctl.json`／`daemon_state.json`、信箱 `loops_mailbox`）；bob 與 bob-ctl 都是用信掛上去的、不寫進 daemon.json（重起 daemon 不會自動回來——方向題 4）。

```sh
# 視窗一：起 daemon（照 11-02 試驗場 daemon）
cd ~/code/playground && source env.sh && cd ws
aos-exec ../daemons/main

# 視窗二
cd ~/code/playground && source env.sh && cd ws
export AOS_DAEMON_STACK=$PWD/.stack            # daemon-env 定案的名字

aos-exec ../agents/resident-bob                # 掛上：建 .stack/resident_bob/in.fifo、add bob、add bob-ctl
aos-daemon-ctl ls                              # bob exec running、bob-ctl exec running（兩個都 running 才算掛好）

S=$AOS_DAEMON_STACK/resident_bob               # 之後都對這個 stack 說話
N=$(aos-say --stack $S "在 env:AOS_WS 寫一首詩，詠桃花，檔名 peach.txt。")
aos-listen --stack $S "$N"                     # 等這題答完、印 bob 的回答
aos-say --stack $S "再把它改成七言。" ; aos-listen --stack $S --last 3   # 同一段對話接著問
aos-listen --stack $S --follow                 # 像 tail -f 跟著看
tail -f $S/bob_out.jsonl                       # 原汁事件流（工具呼叫、花費、session_id）
cat .stack/loops/bob/stderr.txt                # bob 出錯看這裡；控制器的在 .stack/loops/bob-ctl/stderr.txt

echo '{"paused": true}'  > .stack/loops/bob-ctl/loop_ctl.json   # 暫停：題排著、bob 閒著
echo '{"paused": false}' > .stack/loops/bob-ctl/loop_ctl.json   # 續

# 停掉（三選一；都會讓兩個都 done）
echo '{"stopped": true}' > .stack/loops/bob-ctl/loop_ctl.json   # 控制器收工 → FIFO 關 → bob 答完手上那題自己退出（最溫和）
aos-daemon-ctl rm bob-ctl                                       # 同上，但由 daemon 送 SIGTERM 給控制器、並從表上拿掉
aos-daemon-ctl rm bob                                           # 直接收 bob；控制器下一輪 EPIPE 失敗、自己停
aos-daemon-ctl rm bob bob-ctl 2>/dev/null; aos-daemon-ctl ls    # 表上清乾淨（rm 一次只收一個名字就分兩次）
```

daemon.json 要是想**開機就掛**（不用 install），可以寫死（路徑從 daemon 的 cwd `daemons/main/` 算；FIFO 仍要先建一次，`mkfifo` 一行）：

```json
{"ctl": "daemon_ctl.json", "state": "daemon_state.json", "loops_mailbox": "loops_mailbox",
 "loops": {"clock": {…}},
 "execs": {"bob": "../../agents/resident-bob/bob", "bob-ctl": "../../agents/resident-bob/ctl"}}
```

### 5. 要動到的程式與步驟表（不實作）

**前提**：等另一位隊長的 state 窗那輪（`daemon_ctl.json`／`daemon_state.json`、log 預設不印、`AOS_DAEMON_STACK`／`--daemon-stack`）commit 進 main、`git pull` 之後再開工；本題的 C++ 只碰 `child.cpp`，跟那輪的 `daemon.cpp`／`windows.cpp` 不重疊，但 README 同一份要排隊。

| # | 改哪 | 做什麼 | 怎麼驗 |
|---|---|---|---|
| 0 | 試驗場（不動 repo） | **先實測 claude 的一直跑模式**：手動 `mkfifo f; claude -p --input-format stream-json --output-format stream-json --verbose < f` 另一邊 `exec 3>f; echo '{"type":"user","message":{"role":"user","content":"hi"}}' >&3`，看它答完是否等下一行、`exec 3>&-` 之後是否退出；順便確認 `result` 事件與 `assistant` 行的形狀 | 行為跟第 1、2 節寫的一致；不一致就回來翻案（例如改成 aos-eca-turn 那條「每題 `--resume`」） |
| 1 | `proto8/impls/aos-daemon/src/child/child.cpp`（`run_child`）、`daemon.hpp` 傳 stack 進去、impls README「子項的環境」一段、N-64 ④ 加 daemon 例子、code map `code-map/proto8/14-aos-daemon.md` | 起子項時 `setenv("AOS_DAEMON_STACK", stack_)`（只這一個，不設定義資料夾與 ws——daemon-env 衝突 1 使用者定不定三名）；loop 型、exec 型都設 | `tests/test_daemon.py` 加 1 案：exec 子項把 `env` 寫進檔，驗值＝daemon 的 stack；`impls/aos-daemon` ctest、repo 根 ctest 全綠（鐵律 1） |
| 2 | 試驗場 `~/code/playground/agents/resident-bob/`（第 3 節的樹） | 寫 `bob/_entry.json`、`bob/system.txt`、`ctl/_entry.json`、`ctl/loop.json`、`ctl/turn/_entry`（Python）、`_entry`（install，Python）、README | 第 4 節的指令從頭跑一遍（haiku）：掛上→兩個 running→say／listen 兩題同一段對話→paused 時題排著→`stopped` 後 bob 答完自己 `done 0`、bob-ctl `done 0`；`rm bob` 時 bob-ctl 下一輪 `done 1`；驗完 `ws/` 只剩使用者原本的檔 |
| 3 | `proto8/thinking/2026-11-02-playground-daemon.md` 方向題、本檔「決定」 | 補「常駐版見本檔」；補使用者對衝突 1～6、方向題 1～5 的裁定 | — |
| 4 | （方向題 3 選「進 repo」才做）`proto8/bin/aos-claude-turn`（名字待定）、bin README、`tests/test_aos_claude_turn.py`、code map | 把試驗場的 `turn` 升成 bin 指令、`ctl/loop.json` 改指它 | unittest 用假的 `bob_out.jsonl` 與 FIFO 驗一輪 |
| 5 | `wf/WAIT_USER.md` 一條 | 使用者在試驗場親手跑第 4 節 | 使用者回報 |
| 6 | 收尾 | 日誌一行、months 那列補結果；一個 commit（程式＋測試＋README＋條文＋code map 同一個） | `/wf-lint` |

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
   → **控制器可以有信就直接倒進管子**（使用者「一直丟，claude 會自己處理」成立：不會丟、不會亂序、不會打斷）；但**信跟 `result` 不是一對一**，忙的時候進來的幾封會併成一題，所以「一封信等一個 `result` 才 finish」對不起來，也看不出合併裡哪句有被理會。要靠 `--replay-user-messages` 那行（合併後的原文）或別的方式對帳，留給規劃。
7. **`--max-budget-usd` 是整個 session 的總額**：`total_cost_usd` 是累計（0.00069、0.00085、0.00094），這題自己的在 `model_usage_since_last_result.<模型>.costUSD`。上限設 0.00025 跑四題：第一題 `success`；第二題答案照樣吐出，但 `result` 變 `subtype: "error_max_budget_usd"`、`is_error: true`、沒有 `result`、`errors: ["Reached maximum budget ($0.00025)"]`（答完才檢查，會超一點）；之後每題**立刻**回同樣的錯誤 `result`、不花錢、沒有 `assistant`。**超預算時 claude 不退出**（規劃第 1 節與衝突 6 寫「撞到、claude 自己退出」不對），寫端關掉時才退、**結束碼 1**。所以預算用完時 bob 變成活著卻沒用，控制器要自己看 `result` 的 `subtype`。
8. **SIGTERM**：閒著時送＝立刻退、**結束碼 143**（claude 自己接住訊號以 128+15 結束，不是被殺）。正在答時送（「從 1 數到 1500」答到一半）＝**也立刻退 143，手上那題直接丟掉**：沒有 `assistant`、沒有 `result`，輸出檔最後一行是那題的 `system`/`init`。**輸出檔每一行都是完整的**（沒有寫一半的行）。
9. **`/exit` 不能用**：stream-json 裡送 `/exit`，claude 回一則 `result`「/exit isn't available in this environment.」、**不退**，之後照常答題。stream-json 有對應的**控制訊息** `{"type":"control_request","request_id":"r1","request":{"subtype":"interrupt"}}`：實測它**中斷正在答的題**（輸出 `control_response` success、已吐的半截 `assistant`、一則 `result` `subtype: "error_during_execution"`），**行程不退**、對話記得（下一題問「我剛才叫你做什麼」答「…你只寫到 13 就被我中斷了」）。它是「打斷這題」，不是「收工」。
10. **停掉後 `--resume` 叫回來**：「記住暗號 9」→ SIGTERM（退 143）→ 用第一行事件（`system`/`init`；每行都有、哪行都一樣）的 `session_id` 跑 `claude -p --resume <id> --input-format stream-json --output-format stream-json --verbose …`（其餘旗標同上）→ 問「我剛才叫你記住什麼」答「暗號 9」。**重起後 `session_id` 不變**，`result_index` 從 0 重數，`total_cost_usd` 也從新行程重算。（`/clear` 之後 `session_id` 會換，見 ⑪。）
11. **slash command 會被執行，要小心**（使用者「要小心slash command」成立）：
    - `/help`：被 claude 攔下、不給模型，回「/help isn't available in this environment.」，不花錢。
    - `/cost`：**真的執行**，回訂閱用量（「Current session: 3% used · resets …」），不花錢——會把帳號用量吐進輸出。
    - `/clear`（在丟棄的 session 測）：**真的清掉對話**——吐一行 `{"type":"conversation_reset","trigger":"clear","new_conversation_id":…}`、一則空的 `result`，之後 **`session_id` 換成新的**、問「暗號是多少」答「不知道」。
    - `/foo`（不存在）：當一般文字給模型，模型答「`/foo` 在這個 session 裡不存在…」。
    - 句子中間有 `/`（「a/b.txt 的副檔名」）：正常答 `txt`，不受影響。之後問暗號仍答 `7`（`/help`、`/cost`、`/foo` 都沒清記憶）。
    - `/compact` 沒測（會花錢、會改對話）；照 `/clear` 的樣子推，它多半也會真的執行。
    → **控制器丟進去前要擋或轉義開頭的 `/`**（例如前面加一個空白或全形字，或直接拒收）：不然任何能 `aos-say` 的人都能清掉 bob 的對話（`/clear`）、看到帳號用量（`/cost`）。對**方向題 5**（`aos-say /stop` 當收工）的影響：用 `/` 開頭當給控制器的約定正好跟 claude 自己的 slash command 撞在同一個字頭——控制器認得的（`/stop`）自己吃掉、認不得的一律轉義，或約定改用別的字頭，兩種都要在控制器那層做，不能直接漏進 claude。
12. **寫端關掉（EOF）＝非主要收工方式**（使用者定 SIGTERM 才是）：第三題送出後立刻關寫端，claude **照樣答完手上那題**、約 2 秒後退出，**結束碼 0**（超過預算過的 session 則退 1）；閒著時關也直接退 0。

### 規劃要跟著改的地方（本次只列，不改上面各節）

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

## 要使用者看的衝突與方向題

### 衝突 1：用 FIFO 接兩個兄弟＝aos 標準沒有的交流方式

- **條文**：C-75「proc 之間的交流」只有投遞（信箱／queue）、窗、父子交代三種；N-16 10-28 把「JSONL 追加檔＝一條流」從標準刪掉（「檔案串流不寫進 aos 標準、要用由 proc 自己定」）。
- **衝突在哪**：bob 跟控制器之間那條 `in.fifo` 是一條 Linux 的管子——不是信箱（沒有一封封、沒有認領）、不是窗（沒有「最新那份」）、也不是父子交代（兩個是兄弟）。aos 看不見它、aos-daemon-ctl 也不知道這兩個子項綁在一起。
- **各自後果**：(a) **照規劃做**（fable 建議）：FIFO 由 inst 的 `stdin`／`stdout` key 指定，算「proc 自己定」那一類，不立條文、不改標準，只在 resident-bob 的 README 說明；代價是「一隻 claude 一直跑」這件事只有這一條路能做（要不就是 eca-turn 那種每題起一支新 claude、靠 `--resume` 接回，bob 就不是一直跑的 proc，跟使用者原文「會一直跑，不會自己結束」不合）。(b) **不用 FIFO**：控制器每題 `claude -p --resume`（＝aos-eca-turn，現成、不用新寫），bob 這個「exec」就不存在，常駐的只有 loop——結構變成一個 loop、不是 exec＋loop。(c) 把「管子」加進 C-75 當第四種交流——條文要動、而且 aos 什麼都不用替它做，不值得。

### 衝突 2：兄弟要共用位置 → daemon 得把 `AOS_DAEMON_STACK` 設給子項

- **條文／裁定**：使用者 11-01「環境變數像 Janet 的 dyn，只在必要時用」；daemon-env 方向題 2「daemon 要不要現在就把變數設給子項」fable 建議不做、使用者「照 fable 建議先不做，等常駐 bob 用到再說」。
- **衝突在哪**：bob 跟控制器各有小格、各自的 `_entry.json` 是靜態的檔，沒有任何一條現成的路能告訴兩個兄弟「公用的東西放哪」——沒有父子交代（N-64 是父對子）、daemon 不傳自己的任何東西給子項。常駐 bob 就是方向題 2 說的那個「用到的時候」。
- **各自後果**：(a) **daemon 起子項時 `setenv AOS_DAEMON_STACK`**（fable 建議；`child.cpp` 幾行、一個測試）：hub 型變數（N-63，11-01 使用者已裁「hub 型不用改」＝算必要），而且跟外面使用者 shell 裡 export 的是同一個名字、同一個值，子項裡的 `aos-daemon-ctl` 也順便能用。(b) **不改 daemon**：公用路徑寫死在 `bob/.env` 與 `ctl/.env`（`RESIDENT_BOB_DIR=/home/…/ws/.stack/resident_bob`），試驗場搬家、換工作區就得改檔；或用 `${AOS_WS}/.stack/resident_bob`——只在「daemon 的 stack 剛好＝`$AOS_WS/.stack`」時對（playground 剛好是，一般不是）。(c) 把兩個子項改成一個：讓控制器自己起 bob（控制器的 `_entry` 變成「開 FIFO、fork claude、再跑 loop」的 Python），共用控制器的 `$AOS_STACK`——不需要新變數，但 bob 不再是 daemon 表上的一列、daemon 看不到它的 pid，跟使用者「一個 exec 加一個 loop」不合。

### 衝突 3：歷史兩份——原汁 `bob_out.jsonl` 跟 OpenAI 形的 `history.jsonl`

- **條文**：C-56「不多造格式」；P-41 agent 的 history 一行一則 OpenAI message；決定 35「claude 這類自己存 session 的，aos 弄一份 symlink 或複製過來管」。
- **衝突在哪**：claude 吐的是它自己的事件流（`system`／`assistant`／`result`，`assistant` 行裡才包著 OpenAI 形的 message）。aos-listen 只認 `history.jsonl` 的 OpenAI 形。要 aos-listen 能用就得由 `turn` 轉一份；於是同一段對話有兩個檔。
- **各自後果**：(a) **兩份都留**（fable 建議）：`history.jsonl` 給 aos-listen 與人看「說了什麼」、`bob_out.jsonl` 留工具呼叫、花費、`session_id`（重掛要 `--resume` 就靠它）；代價是 `turn` 多十幾行轉換、多一個檔。(b) **只留原汁**：aos-listen 不能用，看歷史要 `jq`／自寫；「把歷史拉出來」變成人自己拉。(c) **只留轉過的**：丟掉花費與 session id，重掛接不回舊對話。另外決定 35 說的 symlink claude 的 `~/.claude/projects/<雜湊>/` 這份本題沒做（跟射後不理版一樣沒做），要的話是 install 多一步。

### 衝突 4：N-28「子項結束不重起」vs「常駐」

- **條文**：N-28「子項結束後不自動重起……要『結束了怎麼辦』自己在鏈上接工具」；P-20「失敗＝停下來等人、不自動重試」。
- **衝突在哪**：bob 一旦退出（預算用完、claude 崩掉、網路斷）就停在 `done`，控制器跟著停；「常駐」在 aos 裡只到「沒人弄死它就一直在」，不是「死了會回來」。daemon 重起時這兩個也不會回來（它們是用信掛的、`adopt` 只接活著的）。
- **各自後果**：(a) **照條文，不自動重起**（fable 建議）：死了 `aos-daemon-ctl ls` 看得到 `done 1`、`stderr.txt` 有原因，人再跑一次 `aos-exec ../agents/resident-bob` 重掛（install 可重跑）。(b) **要自動回來**：`ctl/_entry.json` 外面再包一層沒有 `max` 的 aos-loop（退 0 就再起）——N-28 允許（「鏈上接工具」），但失敗也會無限重起、燒預算，要人另外看。(c) 寫進 `daemon.json` 的 `execs`（第 4 節末那段）：daemon 重起時會跟著起，但 bob 自己死了還是不重起。

### 衝突 5：控制器是「用 exec 型子項跑一支 aos-loop」，繞過了 loop 型子項

- **條文／結論**：N-28 loop 型子項＝daemon 自己起 `aos-loop`，行程 stdin／stdout 接 `/dev/null`；loop-stdio 結論「子 loop 程序本身的 fd 仍是 daemon 定的」。
- **衝突在哪**：控制器需要 aos-loop 這個行程**本身**握著 FIFO 的寫端（不是每輪的身體），loop 型子項做不到，只好把它包成資料夾程式、入口寫單子指定 stdout、用 `--kind exec` 掛——daemon 表上它是 `exec`，看不出是一支 loop；`aos-daemon-ctl ls` 的 kind 欄會誤導。
- **各自後果**：(a) **照規劃**（fable 建議）：不改 aos-daemon，一個檔 `ctl/_entry.json` 就解；代價是表上種類不準、小格裡沒有 daemon 補的 `ctl`／`state`（控制器自己的 `loop.json` 開了窗，所以還是看得到）。(b) **改 aos-daemon**：loop 型子項的物件多認 `stdout`（或整個 `stdio`）、daemon 起子 loop 時照它開——條文 N-28 要補、`child.cpp` 要改，但以後任何「loop 行程要握著一個檔」的情況都能用。可以先做 (a)，等第二個用到的再做 (b)。

### 衝突 6：「exec 就是我們現有的 bob」——但要加三個旗標、拿掉預算

- 使用者原文「exec 就是我們現有的 bob」。實際上 `_entry.json` 要加 `--input-format stream-json --output-format stream-json --verbose`（沒有這三個 claude 答一題就退）、要拿掉或調大 `--max-budget-usd 0.3`（一個 session 的總預算，常駐會撞到）、`system.txt` 要改「做完就結束」那句。bob 的工具、模型、`--add-dir`、system prompt 其餘都不動。
- **各自後果**：(a) **另開 `agents/resident-bob/bob/`**（fable 建議）：`agents/bob` 原封不動，射後不理版照舊能用，兩個 bob 各自一份；代價是 `system.txt` 兩份要同步。(b) **直接改 `agents/bob`**：只剩常駐版，`aos-exec ../agents/bob -- "題"` 手動叫會卡在等 stdin。(c) 預算：拿掉（claude 不限）或調到例如 `--max-budget-usd 3`，是錢的事、使用者定。

### 方向題 1：一次一題，還是來幾題灌幾題

- 原則推不出：N-16 有順序的信箱只保證順序；claude 的 stream-json 模式收到好幾行會排隊逐題答，兩種都做得到。
- 例子：使用者連說三句「寫詩」「改七言」「加標題」。**一次一題**（fable 定）：`turn` 等 `result` 才送下一封，`aos-listen 信號` 的契約（信在 `cur/`＝還沒答）成立、暫停時排著的題一封都不會漏進去；代價是 bob 每題之間多等最多一個 `interval_ms`。**全部灌**：少等，但 `cur/` 裡會同時有三封、aos-listen 分不清哪封答完，暫停也擋不住已經灌進去的。

### 方向題 2：掛的單位——兩個子項掛到 daemons/main，還是 resident-bob 自己是一隻小 daemon

- 原則推不出：兩種都合 N-28。
- 例子：fable 照使用者原文「配合 daemon 進行 exec 和 loop 的掛起」做成**兩個子項掛到現有的 daemons/main**（`bob`、`bob-ctl` 兩列，`aos-daemon-ctl ls` 一眼看到），install 只是投兩封信。另一條：`agents/resident-bob/_entry.json`＝`["aos-daemon", "daemon.json"]`，自己是一隻小 daemon、底下掛那兩個——一掛一個、停一個 daemon 就全停，但多一個常駐行程、多一組窗，而且兩個子項仍然是兄弟、仍然要衝突 2 那個變數（小 daemon 的 stack 就是公用處）。

### 方向題 3：`turn` 這支小程式放哪、叫什麼

- 原則推不出：它是「把 queue 的一則倒進 claude 的 stdin、把 claude 的事件流接進 history」——跟 aos-eca-turn 同一類（外部 CLI 的一輪），但 eca-turn 每輪起一支新 claude、這支是對著一支活著的 claude 寫管子。
- 例子：**先放試驗場 `agents/resident-bob/ctl/turn/`**（fable 定）；跑順了再升成 `proto8/bin/aos-claude-turn`（C-54 R13 `aos-<領域>-<功能>`；stream-json 是 claude 專屬格式，所以領域寫 claude 不寫 eca）。另一條：直接做成 aos-eca-turn 的一個模式（`--via fifo`），一支程式兩種接法——但 eca-turn 綁著 cli_session／tmux 那套，塞進去會變重。

### 方向題 4：重掛之後要不要接回舊對話

- 原則：決定 35 說 claude 的 session 要「symlink 或複製一份過來管」，但沒說重掛要不要續。
- 例子：bob 預算用完 `done`，使用者重跑 install。**不接**（fable 定第一版）：新 session、`history.jsonl` 照舊追加（人看得到前面聊了什麼，bob 不記得）。**接回**：`bob/_entry.json` 多 `--continue`（接這個 cwd 最近一段對話，不用知道 id），或 install 從 `bob_out.jsonl` 撈上次的 `session_id` 用 `--resume`——後者 `_entry.json` 是靜態檔塞不進 id，得改成讀檔的小殼。

### 方向題 5：要不要給使用者一句「收工」的話

- 原則推不出：停 bob 現在有三條路（第 4 節），都是寫 ctl 或 `aos-daemon-ctl rm`，不經過對話。
- 例子：使用者習慣在對話裡說「好了，下班」。可以讓 `turn` 認一句約定（例如 `aos-say --stack $S /stop`）＝退 10 → loop 以 0 收工 → FIFO 關 → bob 答完自己退出；代價是 queue 裡多一種不是給 bob 的訊息、`history.jsonl` 要不要記它。fable 第一版**不做**，照 ctl 與 aos-daemon-ctl 停。
