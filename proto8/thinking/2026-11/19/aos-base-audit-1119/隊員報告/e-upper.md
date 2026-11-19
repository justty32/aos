# e-upper 報告：11-19 上層默默假設、基底其實沒保證的事

隊員 e-upper｜基準 HEAD 3c4cc4c52（乾淨複本 `~/.aos/scratch/aos-base-audit-1119/src/`）｜暫存樹 `e-upper/tree`（start-api 抄本、假腦 fake）｜重現腳本 `e-upper/repro/`（順序見 `repro/README.txt`）

所有指令都經 `bin/clean` 跑。開工時 `pgrep -af aos-` 只有我自己的查詢指令；我起的行程只有兩台 daemon（第一輪 根 288716、llm 288724；第二輪 404004、404007），收尾都用 `repro/down.sh`（`aos-daemon-ctl -d <我的 stack 絕對路徑> shutdown`）收掉，pid 全部不在；最後掃一遍 `pgrep -f aos-` 各行程的 cwd，沒有一支在 e-upper 底下。機器上其他 aos 行程是別條線的（aos-pylib-cut-1119、b-tests、c-daemon），沒碰。沒改任何程式。

實驗用的定義夾一律由 `repro/agent.py` 生：agent-python 骨架加幾個環境變數開關（`MARK=A/B` 換 system／工具／llm，`FSMV=renamed` 把 idle 改名 rest，`HOOKS=1` 帶 `std.hooks()`，`SYSFILE=` 把 SYSTEM 改成 `by_hand`）。

---

## 先講結論（嚴重的排前面）

| # | 一句話 | 嚴重度 |
|---|---|---|
| F1 | `ctl set-def` 之後 stack 那份工具整份還疊在**舊**定義上（新定義的工具一支都沒有），使用者接著刪掉舊定義夾，那隻 agent 下一次想事情就死、信沒人回 | 會卡死 |
| F2 | `agent.py` 重生把狀態機的格改名，**所有**用這份定義、正停在那格的 agent 下一拍全部死掉；`--auto-restart` 的連死三次後停住；`ctl start` 救不回來 | 會卡死 |
| F3 | 斷點下好之後，`agent.py` 重生拿掉 HOOKS（或換一份沒宣告 hooks 的定義），斷點**悄悄失效**：工具照跑、不停，庫到 `a.bp.ls()` 才報 HooksMissing | 會誤導 |
| F4 | stack 裡「自己那份」是照**定義當下宣告的檔名**去找；重生或 set-def 換了檔名（例 SYSTEM 改 by_hand 成 prompt.txt），先前 `self_system`／`system set` 的那份悄悄不再生效，檔還在 | 會誤導 |
| F5 | 對正在跑長的一輪（或扣在斷點上）的 agent 下 `ctl set-def`：逾時報 WaitFailed、說明書寫「什麼都沒改」，但 stop 已經送出去了；一輪跑完它就停住（auto-restart 也不起）、信沒人回 | 會誤導 |
| F6 | 扣在斷點上時 `aos-daemon-ctl stop` 永遠停在 `stopping`（沒有時間上限、沒提示是斷點）；表、`ctl state` 看不出卡在斷點（照 11-19 裁定是刻意的） | 會誤導 |
| F7 | agent-python 骨架（照 11-19 裁定不帶 hook）生出的定義，`aos.gdb.attach` 一開就 HooksMissing：今天的兩個新東西接不起來 | 只是醜 |
| F8 | 觀察者：目標被 stop 時照判、判中就在目標的 `gdb/log.jsonl` 多一張 `pause_failed`；目標被 rm 後每圈往自己的 `stderr.txt` 寫一行約 350 位元組 warning，不會停 | 只是醜 |
| F9 | aos.gdb 把 stack 裡的檔名寫死（`state.json`、`ctl.json`、`state_flux.json`、`history.jsonl`、`queue/new`），基底允許改名 | 會誤導（推測） |
| F10 | 重生是「逐檔暫存檔＋改名」：每份檔各自完整（沒讀到空檔、壞 JSON），但一組檔之間不是一起換；腦在 think 看舊工具、act 用新工具 → 腦收到 ToolMissing（溫和） | 只是醜 |
| F11 | `system set` 對共用定義的提醒叫人「改定義」，對 agent.py 生的定義下次重生就被蓋回 | 只是醜 |

---

## 發現逐條

### F1　set-def 後工具還疊在舊定義；舊定義一刪，agent 死

- **現象**：e5 有自己那份 tools（`tools add math2`，檔裡 `$override` 指 `../../../defs/old5/tools.json`）。`ctl set-def e5 defs/new5` 之後：system 是新的（SYSTEM-VERSION-B）、llm 是新的（temperature 0.9），**工具是舊定義那整組**（do_task、mailbox_*、math、math2、peek_clock、peek_now_time），新定義的 look 包一支都沒有；set-def 只印一行 warning。接著 `rm -rf defs/old5`（換了定義、清掉舊的，很自然），下一封信：`aos-tools: error: PathMissing …/defs/old5/tools.json does not exist` → `agent-fsm: error: ToolsBad` → `aos-loop RunFailed`，表上 stopped，信 AnswerMissing。
- **怎麼重現**：`../bin/clean bash repro/up.sh; ../bin/clean bash repro/mkdefs.sh; ../bin/clean bash repro/e5_setdef_old_tools.sh`
- **嚴重度**：會卡死（那隻停住、信等著；history 與信不丟）
- **影響到**：ctl set-def、agent.py 重生（換定義＝ctl set-def 指新夾的人最容易踩）、self_tools、agent_def
- **建議處理方向**：(a) set-def 時把 stack 那份的 `$override` 改指新定義（Argon B4 提過，要改執行期）；(b) set-def 預設拒絕、要 `--keep-own-tools` 或先 `tools reset`；(c) 不改程式，把 warning 升級成「它現在用的是舊定義的整組工具、舊定義不能刪」並寫進 set-def 的 help；(d) aos-tools 在 `$override` 指不到時退成「沒有底」而不是整份報錯（會靜悄悄少工具，是另一種壞）。
- **依據**：實測（輸出摘要如上）；`py/aos/apps/agent/ctl/set_def.py` 的 warn_own_tools（只 note、不改寫）；`templates/agent-fsm/cell_common.py:38-48`（自己那份在就只用它）；`py/aos/apps/agent/docs/03-tools覆蓋層.md`「自己那份壞掉＝整隻停下」寫了一般情況，set-def 的 help 沒把兩件事接起來。aos-inherit 02 的 G1 已測到「疊舊定義」，**刪舊定義就死**是這次補的。

### F2　重生改了狀態機格名，用這份定義的 agent 全部死掉

- **現象**：兩隻 agent（e2a 無 auto-restart、e2b 有）共用 defs/d2，都停在 idle。`FSMV=renamed` 重生（idle→rest）後幾拍內：e2a stopped，`aos-fsm: error: StateUnknown unknown state idle (the state in …/stage.txt is not in the table)`；e2b 連起三次、每次 3 秒內死，`restarted 3 times in a row … not restarting again`。`aos-agent ctl start e2a` 回 started，3 秒後又 stopped（stage.txt 還寫 idle）。要救只能手改 stack 的 stage.txt（違反「不碰 stack」）、把格名改回去，或 `rm --purge`（丟 history）。
- **怎麼重現**：`../bin/clean bash repro/e2_fsm_rename.sh`
- **嚴重度**：會卡死
- **影響到**：agent.py 重生、std.fsm／ag.fsm、ag.load（衍生改格名同理）、共用定義的多隻 agent
- **建議處理方向**：(a) aos-fsm 遇到 stage 不在表上時退回 start（印 warning）而不是死；(b) agent.py 重生前查 daemon 表上用這份定義的 agent 的 stage.txt，有人停在要消失的格就 SpecBad／要 `--force`；(c) 維持現狀，只靠骨架 README 第 3 條（已寫，但沒提「ctl start 救不回」與「共用的全倒」）。
- **依據**：實測；`cpp/aos-fsm/docs/01-用法.md`「裡面的狀態不在表上＝StateUnknown」；aos-compile-庚/07 第二節自己標「照說明推的，沒有實測」——這次實測坐實，並多看到 auto-restart 三連死與 ctl start 無效。

### F3　重生拿掉 HOOKS，斷點悄悄失效

- **現象**：e10（定義帶 std.hooks()）下 before_tool 斷點（tool＝peek_now_time），觸發器寫在 stack 自己那份 hooks.json。之後 agent.py 重生不帶 HOOKS：定義夾的 hooks.json 還在，但 interfaces.json 沒有 hooks 鍵了。說一句話：**沒停**、peek_now_time 照跑、答「FAKE ANSWER … (tool said: …)」。`a.bp.ls()` 這時才報 `HooksMissing e10 does not declare hooks`。用 before_tool 擋危險工具的人，會以為還擋著。
- **怎麼重現**：`../bin/clean python3 repro/e10_regen_drops_hooks.py`
- **嚴重度**：會誤導
- **影響到**：aos.gdb（a.bp）、agent.py 重生、ctl set-def（換到沒宣告 hooks 的定義同理，推測）
- **建議處理方向**：(a) brain／act 讀 hooks 時，定義沒宣告但 stack 有 hooks.json 就印 warning；(b) agent.py 重生後印一行「這份定義不再宣告 hooks，掛在它上面的 agent 自己那份 hooks 失效」；(c) aos.gdb 下斷點時在 stack 留記號、aos-gdb 開時比對；(d) 只寫文件。
- **依據**：實測；`py/aos/declared_files.py`、`templates/agent-fsm/cell_common.py` 同一套「照宣告找自己那份」的規則（見 F4）。

### F4　自己那份照宣告的檔名找：檔名一換就悄悄失效

- **現象**：e7 先 `system set` 自己那份（MY-OWN-SYSTEM，寫到 stack/system.txt）。重生把 SYSTEM 改成 by_hand 的 prompt.txt，interfaces.json 的 system 變 prompt.txt。之後 `system get` 與腦真正收到的都是 HAND-WRITTEN PROMPT；stack 裡的 MY-OWN-SYSTEM 還在、沒人讀、沒有任何提示。tools、llm、hooks 是同一條規則（讀程式）。
- **怎麼重現**：`../bin/clean bash repro/e7_own_copy_orphaned.sh`
- **嚴重度**：會誤導（agent 用 self_* 學到的東西靜悄悄沒了；檔還在，改回檔名就回來，不算丟）
- **影響到**：agent.py 重生（by_hand、INTERFACES）、ctl set-def、self_system／self_tools／llm set
- **建議處理方向**：(a) brain 發現 stack 裡有「上一份宣告名」的檔但不是現在的名字時 warning（要記上一份名字）；(b) agent.py 重生時改了宣告檔名就印一行；(c) 只寫文件（docs/03、07-system 補一句）。
- **依據**：實測；`templates/agent-fsm/brain.py:110-115`、`cell_common.py:41-47`；`docs/03-tools覆蓋層.md`「自己那份寫 stack/同一 tools 路徑」寫了規則，沒寫改名的後果。

### F5　set-def 逾時說沒改，其實 stop 已經送出

- **現象**：e8 扣在 before_tool。`ctl set-def --timeout-s 5 e8 defs/d8` → `WaitFailed waited 5 s, the daemon has not finished stopping e8`，退 1；help 寫「If the stop fails or times out nothing else is changed」。表上卻已是 stopping、定義仍是舊的。放行後工具跑完、它就 stopped（auto-restart 不起，因為是人下的 stop），那封信沒人回。不只斷點：任何一輪超過逾時（預設 30 秒；eca 一輪二三十分鐘）都一樣。
- **怎麼重現**：`../bin/clean python3 repro/e8_setdef_while_held.py`
- **嚴重度**：會誤導（結果是 agent 停住，要人 ctl start）
- **影響到**：ctl set-def、aos.gdb、eca
- **建議處理方向**：(a) 逾時時把 stop 收回；(b) 逾時訊息改成「stop 已送出、這一輪跑完它會停，之後 ctl start 或重下 set-def」；(c) set-def 預設等更久或等到底。
- **依據**：實測；`py/aos/apps/agent/ctl/set_def.py` 的 cmd（phase.cmd_stop 逾時直接丟、沒收回）與 HELP 原文。

### F6　扣在斷點上：daemon stop 等到天荒地老，表上看不出原因

- **現象**（扣住 60 秒觀察，HOLD 可調）：表上 running，下 `aos-daemon-ctl stop` 後一直 stopping（19、34、49、64 秒都是，pid 不變）；`ctl pause` 收下但不生效；說三封信 → queue 3 封一直累積；根的時鐘照走（239→290）；auto-restart 沒誤判（pid 沒換）；`aos-agent ctl ls`／`ctl state` 只寫 stopping、3 queued，看不出卡在斷點。`ctl rm` 1.2 秒收掉（SIGTERM），hold 行程沒了、字條 hold_ended、工具沒跑、3 封信留在 stack 的 queue/new。
- **10 分鐘會不會不一樣**：讀程式看沒有任何計時器會到期——hook 是 timeout_ms 0、act 格 timeout_ms 0、daemon 的 stop「沒有時間上限」（`cpp/aos-daemon/docs/03-起-停-暫停.md`）、預設 stuck_after_*＝0 不判卡住——所以 10 分鐘、一天都是同樣樣子（推測，只實測 60 秒）。
- **怎麼重現**：`HOLD=60 ../bin/clean python3 repro/e4_long_hold.py`
- **嚴重度**：會誤導（「表上看不出」是 11-19 使用者裁定的「解耦合」，不是漏；但 daemon stop 停在 stopping 沒有任何地方說為什麼）
- **影響到**：aos.gdb、aos-daemon stop、aos-agent ctl ls／state
- **建議處理方向**：(a) 不動，在 gdb README 寫「扣住時 daemon stop 會一直 stopping，要 rm／sleep 或先放行」；(b) aos-gdb 啟動時列出「stopping 中又扣著的」；(c) 若有人給 agent 列加 restart_on_stuck＋stuck_after_*（今天只有 daemon.json／procs_ctl 寫得到，ctl add 沒旗標），扣住時任何一道 ctl 就會讓它被判 stuck、TERM 掉（推測），要寫進說明。
- **依據**：實測（輸出摘要如上）＋讀文件推 10 分鐘與 stuck。

### F7　骨架生的定義不能直接拿來 gdb

- **現象**：repro/agent.py（骨架原樣、不帶 HOOKS）生的 d1 掛上後，aos.gdb 的 attach 直接丟 `HooksMissing e4 does not declare hooks`。
- **怎麼重現**：把 repro/e4_long_hold.py 第 15 行的 defs/d4 改成 defs/d1 跑
- **嚴重度**：只是醜（錯誤訊息清楚）
- **影響到**：aos.gdb、agent-python 骨架（11-19 裁「骨架不帶 hook」）
- **建議處理方向**：(a) 錯誤行加一句「agent.py 加 HOOKS = std.hooks()」；(b) 骨架 README 提一句要 gdb 就加 HOOKS；(c) 骨架預設帶 hooks 宣告。
- **依據**：實測；`py/aos/gdb/__init__.py:74`。

### F8　觀察者跟目標的生命週期

- **現象**（every_ms=300、sh 條件看一個旗標檔）：
  1. 目標 `ctl stop` 後旗標成立：觀察者照判（stopped() 只看 paused／hold／未套用的 ctl，不看「已停」），pause 送不出去，在**目標**的 gdb/log.jsonl 留 pause_failed（4 秒兩張）；條件一直成立就一直累積。
  2. 旗標拿掉後 `ctl start`：目標正常跑、沒被誤停。
  3. 目標 `ctl rm`（stack 留著）：觀察者每圈寫一行 `cannot find e6: … InstanceMissing …`（約 350 位元組）到自己的 stderr.txt，幾秒就 2.8 KB；不會自己停，算一天約二三十 MB（推測）。表上觀察者照寫 running。
  4. 同名換一個 stack 加回來：觀察者重找到新 stack、判中、新目標 paused（Argon A8 的修正有效）。
- **怎麼重現**：`../bin/clean python3 repro/e6_watcher_target_life.py`
- **嚴重度**：只是醜
- **影響到**：aos.gdb 觀察者（丙）
- **建議處理方向**：(a) stopped() 也把表上 stopped／不在表上當「不判」；(b) 找不到目標的 warning 只在第一次或改變時印；(c) 目標不在表上 N 圈後觀察者自己退出、表上 stopped 帶原因。
- **依據**：實測；`py/aos/gdb/watcher.py:106-110`（stopped）、`:131-138`（找不到就 warn、continue）。

### F9　aos.gdb 寫死 stack 檔名

- **現象**：基底允許改名：loop.json 的 ctl／state／state_flux、daemon 的 procs_loop 等、interfaces.json 的 history。aos.gdb 直接開 state.json（`py/aos/gdb/__init__.py:292`、`:310`）、ctl.json（`trigger.py:252`）、state_flux.json（`trigger.py:273`）、history.jsonl（`look.py:146`）、queue/new（`look.py:160`）。手寫定義把 ctl 改名的話，stopped()／ctl_unapplied() 永遠讀不到，觀察者與 resume 判斷會錯、不報錯。agent.py 生的定義名字固定，所以今天不會中。
- **怎麼重現**：沒實測（讀程式）
- **嚴重度**：會誤導（推測；目前碰不到）
- **影響到**：aos.gdb
- **建議處理方向**：(a) 從 `aos-agent ctl state --json` 或定義的 loop.json／interfaces.json 取名字；(b) 寫進 gdb README「只支援預設檔名」。
- **依據**：讀程式推的（推測），行號如上。

### F10　重生不是一次換整組；think／act 之間換了會怎樣

- **現象**：一邊 80 次交替重生（A/B，system 放大到 2000 行），一邊另一支執行緒連讀 system.txt、llm.json、tools.json、interfaces.json、fsm.json：38520 次讀取 **0 次錯誤**（沒有空檔、壞 JSON、找不到檔）；133 次讀到新舊混搭（例 system B、llm B、tools A）。混搭一部分是讀的人自己一份份讀造成的，但 brain.py 本來就是先讀 tools（叫一支 aos-tools 子行程）、再讀 system、再讀 llm，跨度比改名的空窗長得多。實際的 agent：扣在 before_tool（腦照 A 版選了 peek_now_time），重生成 B 版（沒有這支）再放行 → act 回 `ToolMissing peek_now_time is not registered`，腦收到錯誤當工具結果，agent 沒死。也就是 gdb 說的「續了照原樣跑」是「同一個呼叫、同樣參數」，工具本身照**放行當下**的定義找。
- **怎麼重現**：`../bin/clean python3 repro/e1_regen_race.py 80`；`../bin/clean python3 repro/e9_regen_between_think_and_act.py`
- **嚴重度**：只是醜
- **影響到**：agent.py 重生、aos.gdb（放行語意）
- **建議處理方向**：(a) 維持（設計稿 07 已決定不做整夾換）；(b) gdb README 補一句「放行時工具照當下的定義找」。
- **依據**：實測；`py/aos/agent_spec.py` 的 write_defs（逐檔 tmp＋os.replace，照 RENAME_LAST 排序）。

### F11　共用定義的提醒叫人去改定義

- **現象**：a1、a3 共用 d1，a1 `system set` 印「this definition … is also used by a3 … (to change them all, edit the definition: aos-tools / aos-json)」。d1 是 agent.py 生的，照這句去改，下次重生就被蓋回。
- **怎麼重現**：`../bin/clean bash repro/e3_shared_def.sh`
- **嚴重度**：只是醜
- **影響到**：agent.py 重生
- **建議處理方向**：(a) 定義夾有 agent.py（原始碼含 agent_spec）時改說「改 agent.py 再重生」；(b) 不動。
- **依據**：實測。

---

## 測試表

| 項目 | 預期（依據） | 實際 | 差在哪 |
|---|---|---|---|
| 重生途中讀定義：空檔／壞檔 | 不會（agent_spec.py write_defs：暫存檔＋改名） | 38520 次 0 錯 | 無 |
| 重生途中讀定義：整組一致 | 文件沒保證（庚/07「新舊交錯極短」） | 133 次混搭；think 舊 act 新 → ToolMissing | 符合文件；但腦讀一組檔的跨度比空窗長，撞得到 |
| fsm.json 何時生效 | 下一拍（agent.py 結尾那句、庚/07） | 改格名後第 8 拍就 StateUnknown | 無 |
| loop.json 何時生效 | 下次起來（aos-loop 起跑讀一次） | 沒實測（讀文件） | — |
| system／tools／llm 何時生效 | 每次想事情重讀（brain.py 註解） | e3、e7 都是下一題就變 | 無 |
| 格改名、agent 停在舊格 | StateUnknown、身體停（庚/07 推測） | 全部共用者都停；auto-restart 三連死；ctl start 無效 | 多了後兩點 |
| 共用定義，一隻 self_* 改自己 | 只改自己的 stack（docs/03、07-system） | 另一隻不受影響、有 warning | 無 |
| 共用定義，重生 | 全部都變（rules.json 第 1 條） | 兩隻都變 | 無 |
| set-def 後工具疊哪份 | 舊定義、warning（set-def help） | 舊定義整組；system／llm 是新的 | 跟 help 一致，但刪舊定義就死（help 沒說） |
| set-def 逾時 | 「nothing else is changed」（set-def help） | stop 已生效，放行後停住 | 不一致 |
| 扣住時 daemon stop | 等它自己退、沒上限（daemon docs/03） | 一直 stopping | 一致 |
| 扣住時 rm | 改送 SIGTERM（daemon docs/03） | 1.2 秒收掉、工具沒跑、信留著 | 一致 |
| 扣住時時鐘 | 照走（時鐘是另一支 proc） | 照走 | 無 |
| 扣住時信 | 收進 queue（gdb 第二版） | 累積 3 封 | 無 |
| 扣住時 auto-restart | 只管退出（daemon docs/03） | 沒誤判 | 無 |
| 觀察者：目標停了 | 第二版沒寫 | 照判、留 pause_failed | 文件沒寫 |
| 觀察者：目標 rm | 第二版 A8 | 每圈 warning、不停 | 文件沒寫 |
| 觀察者：同名換 stack 加回 | 重核後換（A8） | 換了、停得到 | 無 |
| 重生拿掉 HOOKS 後斷點 | 文件沒寫 | 悄悄失效 | 文件沒寫 |
| 自己那份、宣告名改了 | docs/03 只寫規則 | 悄悄失效 | 文件沒寫後果 |

## 可以放心的

- 重生每份檔各自完整，讀的人不會讀到空檔或半份 JSON（F10 的實測）。
- 共用一個定義夾時，`tools add`、`system set` 只改自己的 stack，另一隻完全不受影響，而且會印「別人也用這份」的提醒。
- 扣在斷點上很久，時鐘、別的 proc 照常；auto-restart 不會因為一輪很長而誤判重起；rm／sleep 收得掉，扣著的那次工具不會跑掉、信留在 stack。
- 觀察者在目標被 rm 又同名換 stack 加回來時找得到新的；目標停了又起來，條件不成立就不會誤停。
- think 和 act 之間定義變了，act 找不到工具＝腦收到一則錯誤、agent 不死。

## 沒測到的＋原因

- **ag.load（agent_spec_load.py）與 aos.py 入口（py/aos/py/）**：不在基準 HEAD 3c4cc4c52 的乾淨複本裡（後來的 012b2b191、ee96fd190 才交），只用 git show 讀、沒跑。讀到的假設：ag.load 用 runpy 跑底那支 agent.py，底那支在 import 時做的事（讀檔、讀環境變數、std.pack 讀 $AOS_HOME/lib/packs）衍生那支重生時都會做一次；生出的 json 照舊整份，所以 F2、F3、F4 對衍生出來的定義一樣成立（改了底的格名或拿掉 HOOKS，衍生的重生後同樣中，推測）。aos.py 的 _shell.call 用 subprocess.run 沒給 timeout，靠各支 CLI 自己的逾時（ctl stop 30 秒、listen --timeout-s）；哪支 CLI 沒有自己的上限就會讓 REPL 卡住（推測，沒找到實例）。
- **扣住 10 分鐘**：只扣了 60 秒；理由見 F6（沒有任何計時器，行為不隨時間變），推測一樣。
- **restart_on_stuck＋扣住**：ctl add 沒有這個旗標，要改根的 daemon.json／procs_ctl 才給得上，沒做；推測扣住時任何 ctl 指令都會讓它被判 stuck、收掉、hold_ended。
- **eca 身（claude／codex 當腦）上的扣住**：要真 CLI，沒做（gdb 第二版也沒測）。
- **扣住時 daemon 重起**：gdb 第二版用 bash hook 測過；這次沒重做。
- **sub:N 子帳號**：不在我這題的實驗範圍，沒碰。
- **loop.json 改了何時生效**：照 aos-loop 文件「起跑讀一次」，沒實測。

## 重現腳本一覽（~/.aos/scratch/aos-base-audit-1119/e-upper/repro/）

up.sh（起樹）、mkdefs.sh（建 d1、d4）、down.sh（收樹）、agent.py（實驗用定義原始碼）、e1_regen_race.py、e2_fsm_rename.sh、e3_shared_def.sh、e4_long_hold.py、e5_setdef_old_tools.sh、e6_watcher_target_life.py、e7_own_copy_orphaned.sh、e8_setdef_while_held.py、e9_regen_between_think_and_act.py、e10_regen_drops_hooks.py；順序寫在 README.txt。都在 e-upper 夾裡用 `../bin/clean …` 跑，先 up.sh、mkdefs.sh，最後 down.sh。第二輪從頭（up → mkdefs → e3、e5、e10、e8 → down）重跑過，結果相同。
