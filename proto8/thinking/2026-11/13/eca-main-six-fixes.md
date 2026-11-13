# eca_main 來信七項（11-13）：四項是 bug、修法與 patch 草稿備好（1 定義檢查找 aos-tools、3 rm／stop 要 ws、6 codex 重複旗標、7 codex 子 agent thread），2、4 是新功能，5 與 AOS_HOME 的意思是設計題；這一階段只評估與重現，repo 程式沒動

← [11-13 日索引](README.md)｜同日：[aos-home 怎麼搭的](aos-home.md)｜搭法十七步：[ops-notes-to-aos](../12/ops-notes-to-aos.md#從零搭一棵小樹一個-daemon一隻懂-aos-的-opus-eca使用者自己做)

看的程式：main `1f6422272`（下面提到的檔與 HEAD 相同，沒有未提交的改動）。重現都在暫存小樹 `~/code/six-try-1113/`（假 claude／codex，照 testing.md 起一台 daemon＋時鐘列），沒碰 `~/aos-home` 的檔與行程；第 1 項唯讀看了它的佈局，第 7 項唯讀看了 gpt-price 的 stack 與它的 codex 對話檔第一行。

路徑的家目錄前綴已改寫成 `~`（含原信引文與指令輸出裡的），其餘逐字不動。

## 原信（逐字，出處）

使用者已裁：eca_main 轉來的普通工作算他的授權。

> 1) agent_def check 誤報 DefBad：它寫死去找 $AOS_HOME/cmd/aos-tools/bin/aos-tools，但 aos-home 裡沒有 cmd/，所以每個定義（包括正常在跑的 eca_main）都會被判 DefBad。建議改成從 PATH 找，或找不到時給清楚訊息。另外，知識庫說 AOS_HOME＝proto8 所在的地方，但這台的 aos-home 和 proto8 是分開的，需要釐清設計。
> 2) 沒有改名指令：aos-agent ctl 沒有 rename，只能 rm 再 add，history 不會帶過去（除非新舊名用同一個 stack）。希望有 ctl rename OLD NEW，保留 history、queue、mailbox、overlay。
> 3) ctl rm 時如果 ws 已經不在會失敗（aos-exec: error: WsMissing），必須先把 ws 資料夾建回來才 rm 得掉。rm 不應該需要 ws 存在。
> 4) 換定義只能 rm（保留 stack）再 add：希望有 ctl set-def NAME DEF（或 add --replace）。
> 5) 換完之後，信箱裡原本就在等的信不會被 mail_notify 提醒（因為算 fresh start）。但 stack 是保留的，這些信就漏了。stack 有之前的紀錄時，應照「睡醒」的規則處理。
> 6) codex eca：aos-eca-turn 自己會加 --skip-git-repo-check，但定義的 print_flags 再寫一次時，codex 因參數重複 exit 2（CliFailed），進入冷卻，信也被丟掉。建議 aos-eca-turn 去掉重複參數，或 check 時警告；文件也要寫清楚哪些參數是 aos 自己會加的。

> 補第 7 項：codex eca 的 session.txt 指到 multi-agent 子 thread，resume 失敗。gpt-price（codex eca，定義 ~/aos-home/ws/defs/gpt-price，stack ~/aos-home/ws/.stack/procs/gpt-price）在使用者開著畫面使用之後，下一輪非畫面回合 resume 失敗：
> Error: thread/resume: thread/resume failed: cannot resume an unloaded multi-agent v2 sub-agent through its parent; resume the parent first, or use thread/read to inspect it (code -32600)
> → CliFailed codex exited 1，進入冷卻（cooldown.json dropped 1）。冷卻結束後，aos-eca-turn 判定 history 有變動，開了新對話，後續正常。
> 推測：畫面的 hook 把 codex 子 agent 的 thread id 當成「換到別段對話」，記進 session.txt（cli_session.py 的 codex /resume 判斷），於是 aos 去 resume 一個子 thread。建議記 session 時排除子 agent 的 thread，或者 resume 遇到這個錯誤時，自動改 resume 父 thread 或開新對話，不要白白進冷卻、丟掉信。stderr.txt 在上面那個 stack 裡。

## 一覽

| 項 | 重現 | 分類 | 根因 | 修法一句 |
|---|---|---|---|---|
| 1 | 有 | bug＋設計題（AOS_HOME 指什麼） | `lib/aos/defs/catalog.py` 的 `AOS_TOOLS`／`stacked()` 用自己的位置往上三層拼 `cmd/aos-tools/bin/aos-tools` | 改成 PATH 找 aos-tools，找不到給一句清楚原因 |
| 2 | 現成寫法驗過 | 新功能 | 沒有 rename；`ctl rm OLD`＋`ctl add -n NEW -s <舊 stack>` 已經什麼都保留 | 最小做法＝把這兩步包成一個指令（先停、再拔、再掛） |
| 3 | 有 | bug | `cmd/aos-agent/aos_agent/decl.py` 的 `close_screen_if_any()` 用表上的 ws 叫 `aos-exec --ws`，ws 不在＝WsMissing，rm／stop 都被擋 | ws 不在就用 stack 當工作區去關畫面、提醒一行 |
| 4 | 不用重現 | 新功能 | 沒有 set-def；daemon 本來就收「同名 procs_added＝換設定、在跑的不重起」（N-54） | `ctl set-def NAME DEF`＝驗定義、送同名 procs_added、要的話 stop＋start |
| 5 | 有（限定條件下） | 設計題 | `lib/agent/mail_notify/_entry` 的 `main()`：`first` 且沒有 `notified.json`＝只記不提（使用者 11-11 晚認可的代定 1） | 待裁；推薦：沒記錄但 stack 有 history＝照睡醒提醒 |
| 6 | 有（真 codex 0.167.2＋假 CLI 整條） | bug | `lib/agent/cli_print.py` 的 `print_codex()` 一律加 `--skip-git-repo-check --json -o`，`cli_cfg.load_cfg()` 沒擋使用者再寫 | `load_cfg()` 遇到 aos 自己會加的旗標＝CfgBad（認領信之前停，信不掉） |
| 7 | 有（實物證據＋假 rollout 重現） | bug | `lib/agent/cli_hook.py` 的 `hook_main()` codex 分支把子 agent thread 的 notify 當成 `/new`：清 history、換 session.txt | hook 認出子 agent thread 就不理；非互動那條遇到記錯的子 thread 改接父 thread |

「CLI 失敗時信該不該丟」：**不是 bug，是現行條文的決定**——[CONVENTION 02 § 失敗後冷卻](../../../docs/CONVENTION/02-題目stack停錯腦/04-五-stack與六-停與錯.md)（使用者 11-10 選項框裁定 5「掉那一封、但自動重起」、額度窗選「失敗後冷卻，只拿一封試」）：eca 交出去之後失敗的那封掉掉，agent-fsm 重寄不掉。但那條講的是「外面服務（腦、Claude）的錯」；第 6、7 項其實是 aos 自己的錯（旗標重複、記錯 thread），修好 6、7 就不會走到「交出去之後失敗」，不必動那條。要不要改那條本身另列設計題 Q3。

## 第 1 項：agent_def check 誤報 DefBad

**重現**（暫存樹照十七步 ② 抄 lib／py／templates／knowledge，`AOS_HOME`＝暫存樹）：

```
echo '{"op":"check","path":"../agents/eca_a"}' | aos-exec $AOS_HOME/lib/agent/agent_def
{"problems": [{"path": ".", "reason": "cannot merge ~/code/six-try-1113/agents/eca_a/tools.json with aos-tools: [Errno 2] No such file or directory: '~/code/six-try-1113/cmd/aos-tools/bin/aos-tools'"}]}
agent_def: error: DefBad 1 definition problems found
```

同一份定義用 repo 那份 `lib/agent/agent_def` 檢查＝`{"problems": []}`、退 0。

**根因**：`lib/aos/defs/catalog.py` 第 83 行 `AOS_TOOLS = Path(__file__).resolve().parents[3] / 'cmd' / 'aos-tools' / 'bin' / 'aos-tools'`，`stacked()`（tools.json 有 `$override` 時）用它。不是讀 `$AOS_HOME`，是「這份 lib 的上一層」；在 aos-home 剛好等於 `$AOS_HOME`，那裡沒有 `cmd/`。範本的 tools.json 都疊 `$override`，所以每份定義都中。同類寫法 lib 裡還有一處：`lib/aos/box_check/_entry` 第 36 行找 `cmd/aos-sandbox/examples/...`（box_check 本來就是既有的紅，不在這次範圍）。

**為什麼算 bug**：lib 被抄到 repo 外是有寫的用法（[code-map 常查表](../../../../wf/workflows/common/code-map.md#常查的東西在哪)「repo 外的複本怎麼 import」、[py/README](../../../py/README.md)）；同一支工具的細動作 `def_edit.py` 叫 `aos-tools` 是從 PATH 找、找不到說「put it on PATH with proto8/install.sh」，`cli_mcp.py` 找 aos-mcp 也一樣。只有 catalog 例外。

**AOS_HOME 到底指什麼——矛盾在哪**：

- 條文：[NORMS 07 § AOS_ 變數的四種性質](../../../docs/NORMS/10-基礎設施-定義與工作區/07-hub-型環境變數與父子交代/03-AOS_-變數的四種性質.md) ③ 人殼預設：「`AOS_HOME`（值＝這台 proto8 資料夾的絕對路徑…沒有程式直接讀它，只在定義檔寫成指示詞 `{"$env": "AOS_HOME", "$path": "/lib/…"}` 時由解指示詞的那一層讀」。[templates/docs/02](../../../templates/docs/02-agent-fsm.md) 範例 `export AOS_HOME=$HOME/repo/aos/proto8`；`templates/daemon-root/.env` 註解「AOS_HOME is the proto8 folder these files point into」。
- 知識庫（`~/aos-home/knowledge/aos`）：`world.json`「`AOS_HOME` (where proto8 is; definitions find tools through it)」；`kernel.json`「In `$AOS_HOME/kernel/` (`AOS_HOME` = where proto8 is)」。
- 這台實際：[ops-notes ②③](../12/ops-notes-to-aos.md#從零搭一棵小樹一個-daemon一隻懂-aos-的-opus-eca使用者自己做) 抄 `lib py templates knowledge` 四夾進 `~/aos-home`，`env.sh` 寫 `AOS_HOME=$(…aos-home)`，原句「最重要的是 `AOS_HOME`＝這棵樹（定義裡的工具路徑都從它算）」；⑯ 寫明「`aos-*` 指令是 symlink，repo 一改就生效；抄進來的四夾不會，要重抄」。所以這台的 `AOS_HOME` 是「proto8 的部分抄本」：有 lib、templates、knowledge、py，沒有 cmd、impls、kernel、docs。
- 矛盾：(a) 條文與知識庫說 AOS_HOME＝proto8，這台是抄本；(b) 知識庫叫 agent 去 `$AOS_HOME/kernel/` 找範例 kernel，這台沒有那夾；(c) 這台跑起來是兩個版本混用——lib 工具、hooks（`{"$env": "AOS_HOME", "$path": "/lib/agent/mail_notify"}`）、知識庫走抄本，`aos-*` 指令（含 `aos-eca-turn` 與它 import 的 `lib/agent/cli_*.py`）、Python 共用模組（`.pth` 指 repo 的 py）走 repo。py 抄本其實沒人用。
- 程式怎麼用 AOS_HOME：條文說沒程式直接讀，實際有兩處讀：`agent_def new {template}` 讀 `$AOS_HOME/templates/<名>`；catalog 沒設時 `setdefault` 成 lib 上一層。其餘都是解指示詞。

**修法（bug 部分，可直接照做）**：patch 在 `~/code/six-try-1113/patches/six-fixes.diff` 的 catalog 段——`import shutil`；`AOS_TOOLS` 換成 `HOME_OF_LIB = Path(__file__).resolve().parents[3]`（只當 AOS_HOME 沒設時的預設）；`stacked()` 用 `shutil.which('aos-tools')`，找不到＝`cannot merge <tools.json>: aos-tools is not on PATH (put it there with proto8/install.sh)`。暫存樹驗過：修後 `{"problems": []}` 退 0；PATH 拿掉 aos-tools＝那句原因、DefBad。
- 跟著改：`lib/aos/defs/README.md` 第 23 行「沒設 `AOS_HOME` 用這份 proto8」改成「aos-tools 從 PATH 找；沒設 `AOS_HOME` 用放這份 lib 的資料夾」。
- 測試（`lib/aos/defs/tests/test_defs.py`）：`call()` 的 env 把 repo `cmd/aos-tools/bin` 放進 PATH 前面（現有 `test_override_packs_are_merged` 才不靠 `~/.local/bin`）；新增 `test_override_merge_from_a_copied_lib_without_cmd`（把 `lib/aos/defs`、`lib/packs`、`lib/base`、`lib/tool_io.py` 抄到暫存夾、沒有 `cmd/`，用抄本的 `_entry` check＝0 problems）、`test_override_merge_needs_aos_tools_on_path`（PATH 沒 aos-tools＝problem 的 reason 有 `aos-tools is not on PATH`）。
- 對跑著的 agent：repo 改了，aos-home 要照 ⑯ 重抄 lib 才生效（aos-home 用的是抄本）；不用停樹、不用重啟 agent（工具每次叫都現讀）。
- 設計題 Q1 裁完再改條文與知識庫字句。

## 第 2 項：沒有 ctl rename（新功能）

**現況驗過**：rename 現在就能做、什麼都保留，只是兩步：

```
aos-agent ctl rm eca_m        # 留 stack
aos-agent ctl add -n eca_r -s $PWD/.stack/procs/eca_m ../agents/eca_m2
eca_r	running	~/code/six-try-1113/ws	0	-
```

history 4 → 6 行接著長、`aos-agent history -t eca_r` 看得到舊的；拔掉期間寄進信箱的信，掛回來後 mail_notify 照提（`notified.json` 在 stack 裡，跟著保留）。原信說「history 不會帶過去」是因為 add 沒給 `-s` 時預設 stack＝`<daemon>/procs/<新名>`（新的空 stack）。

**最小做法** `aos-agent ctl rename OLD NEW`（`cmd/aos-agent/aos_agent/ctl/` 新增 `rename.py`、`ctl/__init__.py` 掛子命令）：
1. 檢查：OLD 在表上、NEW 不在（在＝InstanceExists）、NEW 名字合法；呼叫者自己就是 OLD（`$AOS_STACK`＝OLD 的 stack）＝拒絕（同 rm 的 --no-wait 問題：自己會被一起收掉）。
2. 記下 OLD 那列：def／exec、ws、stack 的寫法（`as_written` 有就照它，否則表上存的相對路徑）、limits、auto_restart、phase。
3. 在跑＝先 `ctl stop` 等到 stopped（daemon 等它這一輪跑完才退；不能用一封信同時 procs_removed OLD＋procs_added NEW——rm 收行程與 NEW 起來會在同一個 stack 上撞兩個行程）。
4. rm OLD（留 stack）→ add NEW，stack 用同一個、其餘照舊；OLD 原本在跑才讓 NEW 跑，原本 stopped 就 add 時一起 stop（N-54：add＋stop 同時＝直接一列 stopped）。
5. 印一行 `renamed OLD to NEW; stack S kept`。

**邊緣狀況**：
- stack 資料夾名還是 `procs/OLD`：要不要順手搬成 `procs/NEW` 是 Q4 的子題（停著時搬：小格的 `stack.txt`、`ws.txt` 是相對的，`.session_home` 記的是 ws 不是 stack，claude 對話檔照 ws 分夾，搬了不壞；但 `--envs` 包的單子在 `procs/<名>/exec.json`，要一起搬）。不搬最簡單。
- queue 裡的信、信箱裡的信：都在 stack 裡，跟著走。
- 別人還寄給 OLD：`aos-mailbox send --to OLD` 報 `InstanceMissing ... not on the daemon table`（暫存樹實測），不會寄到孤兒信箱；`reply_to`／`in_reply_to` 裡寫的 OLD 一樣是寄件那一刻才查表，查不到就明說失敗。
- 子 agent：子 agent 是它自己一列、自己的 stack，不受影響；但父 agent 正在 `subagent ask` 等某個子 agent 回信時把那個子 agent 改名，等的那一方是照名字還是 stack 找，施工時要看 `lib/agent/subagent` 再定（沒驗）。
- 自己的名字：self_* 工具與 mailbox_send 的 from 是照 stack 在表上找名字，改名後自然變新名。
- 畫面開著：先 `close_screen_if_any`（stop 本來就做）。

工作量：半天（含 `cmd/aos-agent/tests/test_rename.py`：`test_rename_keeps_history_queue_mailbox`、`test_rename_running_restarts_under_new_name`、`test_rename_to_existing_name_is_instance_exists`、`test_rename_self_is_refused`）。

## 第 3 項：ctl rm 要 ws 在（bug）

**重現**：

```
aos-agent ctl add -w ../wsb ../agents/eca_b ; mv ../wsb ../wsb.gone ; aos-agent ctl rm eca_b
aos-exec: error: WsMissing workspace does not exist: ~/code/six-try-1113/wsb
```

退 1、eca_b 還在表上；`ctl stop -t eca_b` 一樣被擋。定義資料夾不在時 rm 是過的（`InterfaceMissing` 本來就略過）。

**根因**：`cmd/aos-agent/aos_agent/decl.py` 的 `close_screen_if_any()`（rm 與 stop 都先叫它）→ `run_entry()` 用 `aos-exec --ws <表上的 ws> --stack <stack> <定義>/screen close`；aos-exec 先檢查 ws，不在＝WsMissing，`pass_err` 直接退 1。但 `aos-eca-screen close` 只看 stack 裡的小格（tmux socket 在小格），根本用不到 ws。

**為什麼算 bug**：rm 的 help 寫「Closes its screen first (answering = SessionBad, nothing removed)」，擋下 rm 的只該是「正在答」；[C-56](../../../docs/CONCEPTS/01-設計理念.md) 每層只管自己的——拔掉一隻不該被一個用不到的工作區擋住。

**修法**（patch 的 decl.py 段）：`run_entry()` 多一個選填 `ws`；`close_screen_if_any()` 在 `a.ws` 不是資料夾時：stack 也不在＝沒有畫面可關、略過；stack 在＝提醒一行 `aos-agent: warning: the workspace of NAME is gone (WS); closing its screen from its stack instead`，改用 stack 當 aos-exec 的工作區去 close。暫存樹驗過（抄一份 aos-agent 套 patch）：

```
aos-agent: warning: the workspace of eca_w is gone (~/code/six-try-1113/wsc); closing its screen from its stack instead
no screen (already closed)
removed eca_w; stack ~/code/six-try-1113/ws/.stack/procs/eca_w kept (...)
```

- 跟著改：rm 與 stop 的 HELP 補一句「a workspace that is gone does not block it」；`cmd/aos-agent/README.md` 對應段。
- 測試：`cmd/aos-agent/tests/test_rm_keep.py` 加 `test_rm_and_stop_when_workspace_is_gone`（定義帶一個假的 screen 子介面：`interfaces.json` 宣告 `screen`，`screen/_entry` 印 `closed`；`-w` 給暫存 ws、刪掉後 rm＝退 0、表上沒了、stack 還在，stop 同理）。
- 對跑著的 agent：`aos-agent` 是 symlink 到 repo，下一次打指令就生效；不用重啟任何東西。

## 第 4 項：沒有 ctl set-def（新功能）

**現況**：要換定義只能 rm（留 stack）再 add `-s <同一 stack>`，跟第 2 項同一套，history、queue、信箱、`notified.json` 都保留。daemon 那層其實已經支援直接換：[N-54](../../../docs/NORMS/04-基礎設施-loop與daemon/03-N-54.md)「名單上已有的名字寫進 `procs_added`＝設定換成這份、已在跑的不重起」（`impls/aos-daemon/src/daemon/procs.cpp` 第 352 行同義註解）。

**最小做法** `aos-agent ctl set-def NAME DEF [--restart]`（`ctl/` 新增 `set_def.py`；不做成 `add --replace`，因為 add 的其他旗標〔ws、stack、limits〕在這裡都該照舊，混在一起難講清楚）：
1. DEF 照 add 的規矩驗（`interfaces.json` 宣告 aos-agent、entry 存在）。
2. 從表上那列拿 ws、stack、limits、auto_restart 的寫法，組一封同名 `procs_added`（只換 exec／def），走 `dc.add_letter`。
3. 不在跑＝印「next start uses DEF」；在跑＝沒給 `--restart` 就提醒「takes effect on its next start (ctl stop + start, or --restart)」，給了就 close 畫面→stop→start。

**邊緣狀況**：
- 自己那份覆蓋層：`<stack>/<tools 宣告路徑>` 的 `$override` 指回**舊**定義的 tools 檔（[aos-agent docs/03](../../../cmd/aos-agent/docs/03-tools覆蓋層.md)），換定義後還疊在舊的上面——set-def 要偵測到就提醒（或要求先 `aos-agent tools reset`），不要偷偷改寫。hooks、llm、system 的覆蓋層照名字疊、沒有指回去，照用。
- 新定義宣告的 tools／hooks 相對路徑跟舊的不同：stack 裡舊路徑那份就沒人讀了，提醒一行。
- 換 kind（claude ↔ codex）：小格換一夾（`<stack>/codex`），舊對話接不上，下一輪開新對話並帶 history（現有 reseed），不用另外處理。
- queue 裡的信：不動；`--restart` 時目前這一輪先跑完才停。
- `--envs` 掛的（exec 是一張單子）：表上 exec 不是定義路徑，set-def 拒絕並請它 rm＋add。
- 子 agent：不受影響。

工作量：半天（`cmd/aos-agent/tests/test_set_def.py`：`test_set_def_keeps_stack_and_queue`、`test_set_def_running_needs_restart_flag`、`test_set_def_warns_about_tools_override_of_old_def`）。

## 第 5 項：換完定義後在等的信不提醒（設計題）

**重現**：照原信的路（rm 留 stack、add 換定義、同一個 stack）**多數情況其實會提醒**：stack 裡有 `hooks/mail_notify/notified.json`，掛回來那次 `first` 照紀錄比，拔掉期間到的信提一次（暫存樹實測：拔掉時寄 L2、換定義掛回後 history 多一則 `[aos] new_mail: 1 new letter from tester...`）。會漏的是**這個 stack 沒有 notified.json** 的時候，例如舊定義沒掛 mail_notify、或那時沒有時鐘（`AOS_CLOCK` 沒設＝on_clock hook 根本不跑，stderr 一行 `hook mail_notify (event on_clock) is not checked: AOS_CLOCK is not set`）。實測：舊定義拿掉 mail_notify 掛上、寄 L3、拔掉、換成有 mail_notify 的定義掛回同一個 stack：

```
cat .stack/procs/eca_q/hooks/mail_notify/notified.json
["01794534640998635283.376362.590248"]      ← L3 被記成已知
aos-mailbox -s .stack/procs/eca_q peek
01794534640998635283.376362.590248	tester	REQUEST	L3 waiting      ← 還在等，沒人提過
```

**根因**：`lib/agent/mail_notify/_entry` 的 `main()`：`if event.get("first") and not recorded: new = []`。這是 [backlog-rulings 代定 1](../11/backlog-rulings.md)（「全新起來；使用者 11-11 晚已裁：認可，原話『沒啥好翻的，我覺得都OK』」）：沒有紀錄＝分不出睡前睡後，照「只提醒新到的」。所以照現行裁定它是對的，原信要的是改裁定 → 設計題 Q2。

**修法（照推薦 B）**：`main()` 改成 `if event.get("first") and not recorded and not ran_before(stack)`，`ran_before`＝`<stack>/history.jsonl` 存在且非空。其餘不動。
- 測試：`lib/agent/tests/test_mail_notify.py` 加 `test_first_without_record_but_with_history_tells_waiting`、`test_first_without_record_and_without_history_only_marks`（後者就是現有代定 1 的行為）。
- 跟著改：`--help` 那句、範本兩份 `hooks.json` 的 description、知識庫 `aos/mailbox.json#/check_hook`、templates/docs/02、aos-agent docs/06、lib/docs/03。
- 對跑著的 agent：hook 的路徑是 `{"$env": "AOS_HOME", …}`，aos-home 要重抄 lib 才生效；不用重啟。

## 第 6 項：codex 參數重複 exit 2、信被丟（bug）

**重現**：真 codex（0.167.2，只走到解析參數，沒叫模型）：

```
echo hi | codex exec --skip-git-repo-check --skip-git-repo-check --json -
error: the argument '--skip-git-repo-check' cannot be used multiple times
exit=2
```

`--json` 重複、`-o` 重複同樣退 2；`-c` 可以重複。整條（暫存樹，假 codex 照真 codex 的規矩擋重複）：`print_flags: ["--skip-git-repo-check"]` 的 eca 收一封信 → stderr `aos-eca-turn: error: CliFailed codex exited 2 (its reason is on stderr)`、`cooldown.json` `"dropped": 1`、queue 空了。gpt-price 的 `stderr.txt` 前半段就是這一串（`codex exited 2`），它的 cli.json 現在已經沒有那個旗標。

**根因**：`lib/agent/cli_print.py` 的 `print_codex()` 第 148 行一律接 `["--skip-git-repo-check", "--json", "-o", last, "-"]`；`lib/agent/cli_cfg.py` 的 `load_cfg()` 不看 flags／print_flags 有沒有跟它撞。CLI 退非 0 發生在交出去之後，所以照冷卻規矩那封掉了。

**為什麼算 bug**：同一個檔已經有先例——`sub_registry()` 遇到「tools_sub＋flags 自己寫 --agents」報 CfgBad（「寫什麼就做什麼，不靜靜吞掉」）；[C-56](../../../docs/CONCEPTS/01-設計理念.md)「給的值照字面用」。所以不採「aos-eca-turn 自己去重」（那是靜靜吞掉），改成讀設定時就報錯。

**修法**（patch 的 cli_cfg 段）：`cli_cfg.py` 加常數 `AOS_FLAGS`——codex：`--skip-git-repo-check`、`--json`、`-o`、`--output-last-message`；claude：`-p`、`--print`、`--output-format`、`--session-id`、`--resume`、`-r`、`--continue`、`-c`。`load_cfg()` 驗完型別後，flags／print_flags 有其中任何一個＝`CfgBad <cli.json>: print_flags has --skip-git-repo-check, which aos-eca-turn adds itself; remove it`。`load_cfg()` 在認領信之前就跑，所以**信留在 queue/new、不進冷卻**，agent 停下並帶 reason。暫存樹驗過（抄一份 aos-eca 套 patch）：

```
aos-eca-turn: error: CfgBad ~/code/six-try-1113/agents/eca_codex2/cli.json: print_flags has --skip-git-repo-check, which aos-eca-turn adds itself; remove it
queue/new: 000000000001.01794534880697579730.398264.613514     ← 信還在；沒有 cooldown.json
eca_codex2	stopped	...	failed to start: exited within 3s of wake/start (code 1): ...
```

修好 cli.json 後 `aos-agent ctl start` 就接著答那封。
- 只在有宣告時才加的（`--mcp-config`、`--allowedTools` 追加、`--append-system-prompt-file`、`--system-prompt-snapshot`、`--settings`、`--agents`、codex 的 `-c mcp_servers.*`、`-c developer_instructions`）不擋（claude 收得了重複的，codex 的 `-c` 可重複），寫進文件。
- 跟著改：`cmd/aos-eca/bin/aos-eca-turn` 開頭說明 cli.json 那段、`lib/agent/cli_session.py` 開頭、[templates/docs/01-eca-claude](../../../templates/docs/01-eca-claude.md) 加一節「aos 自己會加的旗標」（上面兩張表）、知識庫講 cli.json 的節點。
- 測試：新檔 `lib/agent/tests/test_cli_reserved_flags.py`：`test_codex_print_flags_skip_git_repo_check_is_cfgbad`、`test_codex_flags_json_is_cfgbad`、`test_claude_flags_resume_is_cfgbad`、`test_other_flags_pass`；`cmd/aos-eca/tests/test_switch.py` 加 `test_cfgbad_flag_keeps_the_letter`（假 codex，信留 new/、沒有 cooldown.json）。repo 現有測試的 cli.json 都沒用到這些旗標（grep 過）。
- 對跑著的 agent：`aos-eca-turn` 走 repo 的 `lib/agent`，下一輪就生效、不用重啟。aos-home 現在七份 cli.json 都沒有這些旗標（唯讀看過），不會有人一改就停。

## 第 7 項：codex 子 agent 的 thread 被當成換對話（bug）

**證據**（gpt-price stack 唯讀）：`stderr.txt` 有 `Error: thread/resume: ... cannot resume an unloaded multi-agent v2 sub-agent through its parent ... (code -32600)` → `CliFailed codex exited 1` → 之後 `history.jsonl was changed since the last turn; starting a new codex conversation`；`cooldown.json` `"dropped": 1`。`codex/transcripts/` 有 6 個對話檔，第一行 `session_meta` 只有一個是主對話（`thread_source: user`），另外 5 個都帶 `parent_thread_id`（指主對話）、`source.subagent.thread_spawn`、`thread_source: subagent`，時間 01:27～01:38。`history_removed.jsonl` 有 5 筆 `op: clear`，時間 01:28、01:41——**子 agent 每跑完一次，aos 的 history 就被清一次**，比原信說的還嚴重。

**重現**（假 rollout，直接叫 `cli_hook.hook_main("codex", …)` 餵一個子 thread 的 `agent-turn-complete`；腳本 `~/code/six-try-1113/repro7_subagent_notify.py`）：

```
session.txt = CHILD        ← 原本是 PARENT
history lines = 0          ← 原本 2 行
history_removed = True
```

**根因**：`lib/agent/cli_hook.py` `hook_main()` codex 分支：codex 的 notify 對子 agent thread 也會叫；子 thread 有存檔（過得了 11-12「旁支 thread 沒存檔就不記」那關），`codex_turns(子)` ≤ 1 → 當成畫面上打了 `/clear`／`/new` → `clear_history(keep_tail=True)`，再 `follow_session` 把 session.txt 換成子 thread。下一輪非互動 `print_codex()` `codex exec resume <子>` → codex 拒絕 → CliFailed、冷卻、那封掉了。

**為什麼算 bug**：11-12 eca-slash 的規矩是「CLI 那邊換了對話，aos 跟上」（使用者 Q1～Q3），子 agent 的 thread 不是換對話；同一段已有「旁支 thread 不記」的先例（`test_codex_side_thread_is_ignored`）。

**修法**（patch 的 cli_cell／cli_hook／cli_print 段）：
- `cli_cell.py` 加 `codex_parent(sid)`：讀那段 rollout 第一行 `session_meta`，有 `parent_thread_id`（或 `source.subagent.thread_spawn.parent_thread_id`）就回父 id，否則 None。對 gpt-price 的真對話檔唯讀試過：子 thread 回主對話 id，主對話回 None。
- `cli_hook.py` codex 分支在「旁支 thread」那關後加：`if sid and codex_parent(sid): return`——不換 session.txt、不清 history、不記 turns。套 patch 重跑重現腳本：`session.txt = PARENT`、`history lines = 2`、沒有 history_removed。
- `cli_print.py` `print_codex()` 開頭：session.txt 指的是子 thread（修好之前已經記錯的）＝提醒一行、改記父 thread、resume 父的。不靠解析 codex 的錯誤字樣。
- 測試：`lib/agent/tests/test_cli_hook_follow.py` 加 `test_codex_subagent_thread_is_ignored`（同重現腳本）；`cmd/aos-eca/tests/test_switch.py` 加 `test_session_on_a_subagent_thread_resumes_its_parent`（手寫一個帶 `parent_thread_id` 的 rollout、session.txt 指它，假 codex 收到的 argv 是 `exec resume <父>`）。
- 跟著改：`lib/agent/cli_session.py` 開頭那段「換到一段剛開的 thread＝/new」補一句子 agent 不算；`templates/docs/01` 的 codex 畫面段。
- 對跑著的 agent：hook 與 `print_codex` 都在 repo 的 `lib/agent`，下一次 notify／下一輪就生效；開著的 codex 畫面不用重開。
- 沒驗：claude 的 `Agent` 子 agent 是不是也會叫畫面 hook、換 session_id（claude 的子 agent 跟主對話同一個 session、目前沒看到出事），留給施工時看。

## patch 草稿

`~/code/six-try-1113/patches/six-fixes.diff`（183 行，`git apply --check` 在 `~/repo/aos` 根過）：第 1、3、6、7 項的程式改動（catalog.py、decl.py、cli_cfg.py、cli_cell.py、cli_hook.py、cli_print.py）。不含測試、文件與第 5 項（等裁）。改完的整份檔在 `~/code/six-try-1113/patches/b/`，底下路徑同 proto8（`b/lib/…`、`b/cmd/…`）。只在暫存樹的抄本上跑過上面那幾段，repo 的現有測試沒跑。

## 建議施工順序與工作量

1. **第 7 項**（約 1 小時）：會清掉 aos 的 history、會丟信，使用者正在用 codex eca 開畫面，最急。
2. **第 6 項**（約 1 小時）：會丟信。
3. **第 3 項**（半小時）。
4. **第 1 項程式部分**（半小時）；條文、知識庫字句等 Q1。
5. 第 5 項等 Q2；第 4 項、第 2 項等 Q4（各半天，set-def 先）。

1～4 是 bug、互不相依，拿到寫入權就可以馬上做；做完跑 `lib/agent/tests`、`cmd/aos-eca/tests`、`cmd/aos-agent/tests`、`lib/aos/defs/tests` 四夾（`python3 -m unittest discover`）、`codemap_gen.py --apply`（檔頭一句話沒變，預期 0 變動）。aos-home 那邊第 1、5 項要照 ⑯ 重抄 lib 才生效，第 3、6、7 項存檔即生效。

## 要使用者裁的題

**Q1 `AOS_HOME` 指什麼？**（第 1 項）條文和知識庫說「這台 proto8 的位置」，這台的 aos-home 是「抄了 lib、templates、knowledge 的樹」。
- A. 照條文：AOS_HOME＝`~/repo/aos/proto8`，aos-home 不再抄四夾、system.txt 改指 `$AOS_HOME/knowledge`。後果：只有一份、不會兩個版本混用；但 repo 一改，工具和知識庫也馬上生效（指令本來就已經這樣）。
- B. 照這台現況改條文：AOS_HOME＝「放 lib、templates、knowledge 的那個資料夾，可以是 proto8 本身或它的抄本」；指令一律從 PATH 找；知識庫「where proto8 is」改成這句，kernel 範例要嘛也抄、要嘛知識庫改說「在 proto8 的 kernel/」。後果：lib／知識庫可以凍住、要更新時才重抄（⑯ 現成），但指令與 lib 版本可能不一致。
- C. 條文不動，只修程式（catalog 走 PATH）。後果：知識庫說的跟這台不一樣這件事繼續存在。
- 推薦 **B**：這台已經這樣搭、手冊也這樣寫，改字句最少；不管選哪個，catalog 走 PATH 都要做。
- **裁定（11-13）＝選 B：照這台現況改條文，`AOS_HOME`＝「放 lib、templates、knowledge 的那個資料夾，可以是 proto8 本身或它的抄本」**（照推薦）。使用者回覆原文：「em-Q1:B」（11-13 第二輪待裁頁 `wu-1113-r2`；回覆整行見[回覆檔](decide_20261113_wu-r2.reply.txt)，裁定後待施工見[裁定落地-1113 § 第二輪](裁定落地-1113.md#第二輪wu-1113-r2裁定後待施工)）。程式那半已做（commit `0b0aaf106`）；條文與知識庫字句還沒改。

**Q2 stack 跑過、但沒有 mail_notify 紀錄時，掛上那次要不要提醒在等的信？**（第 5 項；會改到 11-11 晚認可的代定 1）
- A. 維持：沒紀錄就只記不提；文件寫「換定義後自己 mailbox_peek 一次」。後果：原信那種漏信還會發生（雖然只在舊定義沒掛 mail_notify 或沒時鐘時）。
- B. stack 有 history（跑過）就照睡醒提醒；全新的照舊只記。後果：符合原信「stack 有之前的紀錄時照睡醒」；全新 agent 行為不變。
- C. 沒紀錄一律提醒在等的信。後果：最簡單，但全新 agent 一掛上就會被舊信提醒一次（等於翻掉 11-11「只提醒新到的」）。
- 推薦 **B**。
- **裁定（11-13）＝選 B：跑過的（stack 裡有對話紀錄）就照「睡醒」提醒在等的信；全新的照舊只記**（照推薦）。使用者回覆原文：「em-Q2:B」（出處同 Q1）。還沒施工。

**Q3 eca 交出去之後 CLI 失敗，那封信要不要丟？**（第 6、7 項的共同點；現行是使用者 11-10 裁定 5「掉那一封、但自動重起」）
- A. 維持：修好 6、7 之後，aos 自己的錯在交出去之前就停（信不掉），只剩外面服務的錯照舊丟。
- B. 改成跟 agent-fsm 一樣不丟：冷卻到了拿同一封再試。後果：信不會不見；但一封「本身就會讓 CLI 失敗」的信會每次冷卻到了就再撞一次，間隔拉到 30 分鐘後一直卡在那封。
- 推薦 **A**。
- **裁定（11-13）＝選 A：維持——aos 自己的錯已改成不掉信，外面服務的錯照舊丟那一封**（照推薦）。使用者回覆原文：「em-Q3:A」（出處同 Q1）。不用動。

**Q4 rename、set-def 要不要做？**（第 2、4 項；現在 rm＋add `-s` 已經什麼都保留，實測過）
- A. 兩個都做。
- B. 只做 set-def（daemon 已經支援同名換設定，改動小）；rename 把「rm、再 add -n 新名 -s 舊 stack」寫進 `aos-agent ctl` 的 help 與知識庫。
- C. 都不做，兩個寫法都寫進文件。
- 子題（選 A 時）：改名時 stack 資料夾要不要跟著搬成 `procs/新名`？推薦不搬（KISS，路徑只是名字）。
- 推薦 **B**。
- **裁定（11-13）＝選 B：只做 `set-def`，改名照舊用兩步、寫法寫進說明與知識庫**（照推薦，也就是頂層的代定）。使用者回覆原文：「em-Q4:B」（出處同 Q1）。`set-def` 已做（commit `ab19068d0`）。

## 代定

- 第 6 項不做「aos-eca-turn 自己去重」，改成讀設定時 CfgBad（照 `sub_registry` 的先例）。
- 第 3 項 ws 不在時改用 stack 當 aos-exec 的工作區去關畫面，而不是直接跳過（tmux 開著的畫面才收得掉）。
- 第 7 項用 rollout 第一行的 `parent_thread_id` 認子 agent，不解析 codex 的錯誤字樣；非互動那條另外自己修正記錯的 session。
- set-def 做成獨立子命令，不做 `add --replace`。
