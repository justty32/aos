# edge-agent：aos-agent／判官／agent-fsm／eca 的邊緣實測（11-05，C 線）

← [2026-11-05](../README.md)｜同天 A 線 [edge-llm](../edge-llm/README.md)｜昨天測過的（不重測）：[four-elements 09](../../04/four-elements/09-邊緣狀況實測-11-04-夜.md)

使用者 11-05：「你先自己多測試測試各種邊緣狀況，有問題就修。當然，我會時不時回來看一下，有事可以問我。」同天新規矩：「我發現我們做出來的程式，輸出的各種東西，裡面都有中文...全都用英文吧」——這輪新寫的輸出都是英文。

在 WSL `/tmp/edgeC-*`（試驗場 `cp -a` 一份、repo 範本複本）跑：一台總機（llm kernel，假腦 fake）、一台領班；判官另起模式 1、模式 2 各一台。真 claude（eca_bob，haiku）叫了 4 次、共約 0.005 美金；LM Studio 沒開（`curl -m 3` 逾時），沒測真 qwen。

## 要你看的題（推薦放第一）

### 題 1（已裁：留表）：agent 自己出錯結束時，要不要留在 daemon 表上（stopped＋原因），不要直接下表

**白話**：fsm agent 腦設定寫錯代號、覆蓋層的工具不見了、kernel 回錯……身體退 1，daemon 現在把它**從表上擦掉**。擦掉之後 `aos-agent llm reset`、`tools reset`、`ctl start` 全都 `InstanceMissing` 找不到它——要修只能手動去刪 `<stack>/llm.json`、`<stack>/tools.json` 再同名 `ctl add`（試驗場教學「沒開的腦」那段就是這招）。daemon 已經有「wake／start 起不來的留 `stopped`＋原因」，這次是把同樣的待遇給「跑到一半自己出錯退的」。

1. **（推薦）loop 型的子項退非 0＝留 `stopped`、`reason` 寫「退 N：stderr 最後一行」**；退 0（做完）照舊下表。後果：改 aos-daemon（B 線的 C++）；`aos-agent ctl ls` 會多出停著的列，修好 `aos-agent llm reset`／`tools reset` 再 `ctl start` 就回來；不要了 `ctl rm`。
2. 照現況（下表），aos-agent 的訊息已改成說「錯誤在 stderr.txt、同名 ctl add 接著用」。後果：llm／tools 子命令救不了它。

### 題 2（已裁：--reply-to）：判官判「不掛」時，要不要讓 `aos-agent ctl add` 馬上知道

**白話**：設了 `AOS_KERNEL`（走判官）時，`ctl add` 的信經 aos-daemon-ctl 寄出、**不帶回信地址**，判官判不掛（不在白名單、滿額）也回不了信，aos-agent 只能等滿 30 秒 `WaitFailed`。這輪已讓判官每封不掛都在 stderr 印一行、`WaitFailed` 說去哪看。

1. **（推薦）aos-daemon-ctl 加 `--reply-to`**（aos-daemon-ctl 是 B 線的檔），aos-agent add 開一個暫時信箱、等「上表」或「判官的 `applied: false`」先到的那個，不掛就立刻 `AddRejected`＋原因。後果：多一個旗標；daemon 本來就會回 `applied: true`。
2. 照現況：等 30 秒、看判官 stderr。

## 測了哪些類、結果

| 類 | 測了什麼 | 結果 |
|---|---|---|
| ctl 參數 | 每個子指令缺參數、多參數、不認得的旗標、對不存在的名字、`ctl` 不帶／亂帶 | 訊息都對；不改 |
| 名字 | `-x` 開頭（where／state／pause／sleep／wake／rm）、`a b/c`、`中文 名` | 都對（`a b/c`＝`AddRejected`） |
| 找 daemon／對象 | `--daemon`、`AOS_DAEMON`（相對、指到子項 stack、不存在）、`./.stack`、`AOS_AGENT` 與 `--target` 交叉 | 都對；**在不是工作區的地方 `aos-exec 定義`**：aos-exec 先建空的 `./.stack`，原本說「daemon 沒在跑、先起 daemon」→ 已修（改說「這不是 daemon 的 stack」） |
| say／listen／chat × 狀態 | paused、stopped、sleeping、被 rm、自己下表 | stopped／sleeping 提示對；**暫停中一聲不吭地等**、**等到一半被 rm 說「不在 queue、沒回答」**、**下了表說「要重答就再 say」（對 fsm 不對）**、**答到一半被 stop／sleep 立刻 AnswerMissing** → 已修 |
| chat | 管線輸入、空行、Ctrl-C（等答時／提示符時）、聊到一半被 rm | Ctrl-C 退 130、訊息對；**被 rm 後照寄、把刪掉的 stack 建回來、一直等** → 已修 |
| llm | set 各種壞格式、`k=a=b`、空值、reset 兩次、不認得的動作 | 格式檢查對；**代號寫錯→那隻下表→改好 llm.json 再掛，照舊的請求重寄、又錯** → 已修（agent-fsm wait.py） |
| AOS_LLM_KERNEL | 沒設、空、相對、指到別的資料夾、指到 `…/mailbox` | 沒設／空＝`LlmKernelMissing`；**相對路徑從格的 cwd（定義資料夾）算，剛好對上是巧合**；指錯＝aos-llm 自己建信箱寄進去、永遠等（A 線已記進 aos-llm 已知限制） |
| tools 覆蓋層 | add 同名、rm 不存在、rm 兩次、reset 兩次、覆蓋層壞 JSON／空檔／`{}`／`[]`／`add: null`／`rm` 是字串／`path` 空、add 的工具事後刪掉 | 訊息都清楚；**撞名時 aos-tools 說加 `--override`、aos-agent 收不了** → 已修；**壞覆蓋層或工具不見＝整隻退 1 下表**（照 aos-tools 不猜不跳過，只寫文件＋救法） |
| aos-mcp × 覆蓋層 | rm 掉的工具 list／call、覆蓋層壞（啟動時、跑到一半）、登記檔不在只有覆蓋層、`--overlay ""`、兩份登記檔 | 全對；eca 下一題的 mcp.json 自動帶 `--overlay` |
| 判官 | 模式 1 白名單內外、`max_running` 到頂、壞 `judge.json`（整台 daemon 停，已記）、sleep／wake／stop／start／rm 經判官；模式 2 把 0 號 sleep 後 add、wake | **sleep 一隻、add 一隻、再 wake＝超過 max_running**、**不掛的信一點痕跡都沒有** → 已修；**模式 2：0 號睡著後 `ctl wake` 寄給它自己、永遠叫不醒（卡死）**、**0 號睡著時 add 等滿 30 秒才說沒上表** → 已修 |
| eca_bob（haiku） | 一般問答、答到一半 ctl sleep 再 wake、watch、open -d／再開／close／再 close、沒 tty 的 open、stop／rm 時畫面開著、同定義兩隻 | 都照文件；**答到一半 sleep＝那句丟了、wake 後不會答**（已知限制「中途掛掉的那批不重答」的一種）→ sleep 時提醒、文件補一句；watch 在那情形永遠不走（別線） |

## 修了什麼（commit）

- `4a2b067b` 判官：`procs_started`／`procs_woken` 也算進 `max_running`；不掛的每封 stderr 一行 `judge: 代號 letter <名> refused: …`。
- `cf845971` aos-agent 7 處：kernel 本身的 ctl 直接寄 daemon（解模式 2 卡死）；kernel 沒在跑＝立刻 `WaitFailed`、逾時補「判官沒放行也會這樣」；chat 每句重查表；listen 的被 rm／下表／停著／暫停四種提示；`tools add --override／--no-cache`；cwd 的 `.stack` 不是 daemon；say 先找對象再讀 stdin。
- `55ba7550` agent-fsm：wait.py 寄之前比對 `request.json` 的 endpoint／model 跟現在的 llm.json，對不上退 11、fsm.json `wait` 加 `"11": "think"`＝brain 重組再寄。

## 代定（可翻案）

1. 對象就是 `AOS_KERNEL` 那個 kernel（`AOS_KERNEL` 落在它的 stack 裡）＝它的 start／stop／sleep／wake／rm 都直接寄 daemon，不只 wake（一律同一條、好記）。
2. kernel（表上的 0 號）不是 running 時，`ctl add` 等等的寄出後立刻 `WaitFailed`（信照樣排著、它回來會判），不等 30 秒。代號沿用 `WaitFailed`，不新開。
3. 判官對 start／wake 只判 `max_running`、不判 `allowed`（add 時判過了）；`procs_slept`／`procs_stopped`／`procs_removed` 照原樣轉。
4. wait.py 比「內容」不比 mtime：人**刪掉** stack 的 llm.json（教學的救法）時 mtime 不會變新，比內容才抓得到。比的只有 endpoint、model（brain 會放進請求的就這兩個）；疊法跟 brain.py 抄同一套（兩處）。
5. 壞覆蓋層／工具不見＝整隻停：不改成略過壞的工具（aos-tools「不符合要求一律報錯、不猜不跳過」），只在 docs/03 寫清楚與救法。（**11-12 裁定註**：使用者 11-12「可以改條文」——`aos-tools ls` 碰到其中一支壞掉（路徑不在、定義缺或壞）改成略過那支、提醒一行、清單少那一支、照跑；`add`／`get`／`call` 壞的那支照舊報錯，登記檔本身壞照舊整份報錯、整隻停。見 [tool-path-broken](../../../2026-11/12/tool-path-broken.md)、[P-41](../../../../docs/CONVENTION/02-題目stack停錯腦/06-P-41.md)。）
6. `ctl sleep` 時最後那句還沒答完＝提醒一聲（eca 會丟那批），不擋；fsm 會從那格接著答。
7. 暫停中 say／listen＝提醒一次、照等（不退）。
8. 模式 1 `judge.json` 壞＝整台 daemon 停：照現況（demo/docs/04 已知限制本來就寫了）。

## 別線的 bug／建議（沒改，給頂層）

- **aos-llm**（A 線）：`AOS_LLM_KERNEL` 相對路徑從格的 cwd（＝定義資料夾）算，不是從人打指令的地方；指到不是 kernel 的資料夾＝自建信箱寄進去、永遠等（A 線已記進已知限制；可考慮 send 時要求 `<AOS_LLM_KERNEL>/mailbox/new` 已存在）。
- **aos-daemon（llm kernel 那台）**：A 線重建 aos-llm-kernel 的當下，總機身體 `LaunchFailed CommandBad aos-llm-kernel 不能執行`、**整台 llm daemon 結束**（今天碰到兩次）；只在重建時會發生，可能算天然。
- **aos-eca-screen watch**：eca 答到一半被 `ctl sleep`，watch 等不到「一次回答結束」、永遠不走。
- **aos-daemon-ctl**：寄的 procs 信沒有 `reply_to`，判官不掛回不了信（題 2）。
- **aos-exec**：跑「把自己掛上 daemon」的 `_entry` 時照樣 `mkdir -p $AOS_WS/.stack`，在不是工作區的地方打會留一個空 `.stack`（文件已寫是旁支）。

## 試驗場教學要改的地方（給頂層統一改）

- 試驗場的 `agents/fsm_ann` 是舊複本：要換成 repo `demo/agent-fsm` 新版的 `wait.py`、`fsm.json`（tools.json 的 clock 路徑照試驗場的 `../../lib/clock`）。
- 「沒開的腦」救法：換新版之後不用 `echo think > $S/stage.txt` 了，刪 `$S/llm.json`、同名 `aos-agent ctl add` 就好。
- tools：跟定義同名的工具要這隻改用自己的＝`aos-agent tools add --override 名 路徑`。
- 走判官（模式 2）的：kernel 自己的 sleep／wake 用 `aos-agent ctl …`（會直接寄 daemon）；直接打 aos-daemon-ctl 要先 `unset AOS_KERNEL`。

## 沒測到的

真 qwen（LM Studio 沒開）；`aos-agent open` 接進畫面後的互動（只測了 `-d`、沒 tty、close）；codex 型 eca。

## 使用者裁定（11-05，頂層轉達，選項原文）

- 題 1 →「留表標 stopped (Recommended)」
- 題 2 →「加 --reply-to 等回信 (Recommended)」

## 裁定落實（11-05 晚，隊長）

- 題 1：`c946aa72` aos-daemon——loop 型退非 0（含被訊號打掉）＝列留 `stopped`＋英文 `reason`（`failed to start: …`／`failed while running: …`），修好 `aos-agent llm reset`／`tools reset` 再 `aos-agent ctl start`；退 0 照舊下表。`d1ed1abe` aos-llm-kernel 認這種列當收尾，不卡死。文件 `1ed1913c`、`c6a332e1`（N-28 11-05 晚補 ⑤）。
- 題 2：`0d2b1c7b` aos-daemon-ctl 六個寄信子命令收 `--reply-to BOX`（只寄不等）；`0fda0628` 判官不掛的原因改英文；`d75bb970` aos-agent ctl 的 add／rm／start／stop／sleep／wake 每封開暫時回信信箱（`$TMPDIR/aos-agent-reply-*`，用完刪），判官回 `applied: false`＝立刻 `AddRejected`／`CtlRejected`＋代號原因。aos-daemon 本來就對帶 `reply_to` 的好信回 `applied: true`，沒改。
- 實測（/tmp/edgeD1-*、edgeD2-*）：跑 2.5 秒退 3＝`stopped`、`start` 再起；3.5 秒失敗、kill -9 也留；模式 1 白名單外 0.4 秒 `AddRejected`、滿額 `SlotMissing`、睡一隻加一隻再 wake＝`CtlRejected SlotMissing`；模式 2 同；沒設 `AOS_KERNEL` 照舊。
- 別線五件：aos-llm 相對 `AOS_LLM_KERNEL` `59395748`（有 `AOS_DAEMON`＝相對它，人殼＝相對 cwd）；aos-eca-screen watch `6519dff2`（loop 不在了就退 0）；aos-exec 空 `.stack` `6f8dc8cd`（自己新建的、跑完還空就收回）；llm daemon 身體重建時整台停 → edge-daemon 題 1 一起解；aos-daemon-ctl 沒 `reply_to` → 題 2 解。

### 落實時代定（可翻案）

1. exec 型退非 0 照舊下表（start 不收 exec 型，留著只能 rm）；adopt 接回的拿不到結束碼，照舊下表。
2. wake／start 後 3 秒內退 0 也下表（原本留 stopped）。
3. 暫時回信信箱放 `$TMPDIR`、不放 daemon 的 stack；ctl 六個寄信子命令都等回信，不只 add；非 add 被拒新開代號 `CtlRejected`。
4. 表上已是結果、回信還沒到：最多再等 1 秒；回信讀不懂＝當「到了、不是拒絕」。
5. 判官／daemon 放在別的帳號（Linux 權限那級）時寫不進暫時信箱，aos-agent 退回舊的等法（寫進 extras/agent docs/02）。
6. aos-llm：只要有 `AOS_DAEMON` 就相對它（人殼 export 了也一樣）。aos-exec：選「回來時收自己建的空資料夾」而非「要用才建」（N-58、N-59 原話「要自動建」）；argv 陣列入口 exec 後收不到，寫已知差異。watch 看定義自己宣告的 state 窗、不問 daemon 表。
