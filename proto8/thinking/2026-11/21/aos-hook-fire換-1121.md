# hook_fire 換成 aos-hook fire、刪掉 hook_fire（範本起停兩點、編譯、文件、測試；行為差別逐項）

← [當天索引](README.md)｜設計 [aos-hook-plan-1120 的 05](../20/aos-hook-plan-1120/05-發事件指令.md)（對不上以 [12 採納表](../20/aos-hook-plan-1120/12-採納表.md) 為準）｜前一刀 [k5b](aos-hook-k5b-1121.md)

線 top-1121-hookfire，11-21 家機，頂層派。

## 使用者原話

11-20 晚：「那個hook_fire的程式，是一個命令行程式碼？」「喔太好了，那明天再說這塊。」

11-21 當面。頂層問：「1. 這樣換可以嗎？`hook_fire` 可以刪嗎？ 2. 順序：……我傾向現在就派、要它避開對方的檔」
使用者：「1.可以。2.可以。對了，旗標檔是啥」

## 使用者對 k5b 的回應（11-21）

頂層轉來，使用者看了 k5b 的回報：

「剛剛那個hook我覺得OK，畢竟hook體系的唯一約定，就是要在interfaces.json中宣告，有宣告就能用，至於怎麽實作的，就是各家自己的事情。」

（以下是頂層的理解，不是使用者的話：k5b 的做法與那十條代定他接受；hook 體系唯一的約定＝在 `interfaces.json` 宣告，宣告了就能用，旗標檔、另放 `loop_hooks.json` 這類實作細節是各提供者自己的事。）

## 結論

- 範本的 `on_start`／`on_stop` 全部改成 `aos-hook fire -q --agent $AOS_CD after_start|after_stop`，跟 k5b 接的 `on_before_run`／`on_after_run` 同一種寫法。編譯（`agent_spec`）寫出來的也一樣。
- `py/tools/agent/hook_fire` 整夾刪掉（只有 `_entry` 一個檔）。程式、測試、說明裡提到它的地方都換掉了；`proto8/docs/` 的條文沒改（下面「文件要補的字」）。
- 換過去之後，**定義那份 hooks.json 一開始就掛 before_run 的 agent，起來就有旗標檔**（k5b 留的那一小塊自動解決）：暫存樹實跑，沒有人跑 `aos-agent hook` 或 `aos-hook check`，旗標就在、handler 攔得住。
- **舊的 loop.json（還指著 hook_fire）裝新版之後起不來**：on_start 找不到程式＝退 1＝aos-loop 收工（k5「四個點都跟著停」）。`~/aos-home` 的 ann 就是這種，見「~/aos-home 的 ann 怎麼辦」。

## 換了哪些地方

| 地方 | 改了什麼 |
|---|---|
| 範本 loop.json：`agent-fsm`、`eca-claude`、`eca-pi`、`start-api/agents/ann`、`start-eca/agents/ann` | `on_start`／`on_stop` 換成 `aos-hook fire`；description 改寫 |
| `templates/agent-python/loop.json` | 在乾淨複本重新編譯（`python3 agent.py --compile`）後抄回；同夾其餘檔編譯出來一字不差 |
| `py/aos/agent_spec_agent.py`、`agent_spec_parts.py` | 新的小函式 `fire(event, fields=())`，起停兩點與 before_run／after_run 共用；拿掉 `HOOK_FIRE`；description 同範本 |
| `py/aos/apps/hook/main.py`、`README.md`、`loop_points.json` | 檔頭、說明的歷史段落、宣告的 description 不再提舊程式 |
| `py/aos/agentlib/agent_hooks.py`、`hook_clock.py`、`hooks.py`、`py/aos/apps/eca/main_turn.py` | 檔頭與註解裡的呼叫者 |
| 測試 | `templates/tests/agent-fsm/test_clock_hook.py`（改叫 `bin/aos-hook`；新 `test_fire_flags_on_start`；錯誤碼改測 `EventUnknown`、`ArgumentsBad`、`StackMissing`、`HookFailed`）、`test_clock_hook_daemon.py`（檔頭）、`cpp/aos-daemon/tests/test_stop_cause.py`（`on_stop` 改叫 `aos-hook fire`）、`py/tests/test_hook_points_match.py`（`test_hook_fire` 換成 `test_templates_wire_start_stop`：八份 loop.json 的起停都是 `aos-hook fire -q … after_start|after_stop`，agent 的帶 `--agent $AOS_CD`）、`test_agent_spec.py`、`test_hooks_engine.py` |
| 說明 | `py/aos/apps/agent/docs/06-hook.md`、`py/docs/03`（拿掉 hook_fire 那列）、`py/docs/04`、四份範本 README、`templates/docs/01`、`02`、`cpp/aos-loop/README.md`、`docs/01-用法.md` |
| 刪 | `py/tools/agent/hook_fire/_entry`（夾跟著空掉） |

知識庫（`knowledge/`）沒有一條提到 hook_fire，沒改。生成的 `_index.json`／code map 由排隊重生。

## 行為差別逐項

| 項目 | 以前（hook_fire） | 現在（aos-hook fire --agent） | 依據 |
|---|---|---|---|
| 叫法 | `$AOS_HOME/lib/tools/agent/hook_fire/_entry EVENT DEF` | `aos-hook fire -q --agent DEF EVENT`，從 PATH 找 | 設計 05「loop.json 裡的寫法」；跟 k5b 的 before_run 一樣 |
| 事件資料 | after_start＝`{}`；after_stop＝code、signal、cause 三欄 | 同。三欄照宣告（`loop_points.json`）從 `AOS_LOOP_CODE`、`AOS_LOOP_SIGNAL`、`AOS_LOOP_CAUSE` 取 | 設計 05 |
| cause | 去頭尾空白；空的、沒設＝null；值照抄 | 同（測試照舊八種值） | — |
| code／signal 不是整數 | 當 null | `ArgumentsBad`、退 1（前後空白先去掉） | 設計 05、12 A14：int 欄不是整數＝ArgumentsBad。aos-loop 一律給整數或空字串，實際碰不到 |
| 定義沒寫 `hook_points` | 點照內建表認，沒人能掛，退 0 | `EventUnknown`、退 1 → loop 起不來 | 設計 13 第 10 題「沒寫 hook_points 的定義一個 hook 都不能掛」、aos-hook README「沒有＝沒有點」。範本與編譯都是有 hooks 才寫起停兩鍵、同時寫 hook_points，所以只有手抄 loop.json 又沒抄 hook_points 的會碰到 |
| stdin | 不讀 | 讀一個 JSON 物件（空的、terminal＝`{}`） | 設計 05。daemon 給 aos-loop 的 stdin 是 /dev/null，所以一樣。**邊緣**：前景直接跑 aos-loop、stdin 又是一條一直不關的管子，aos-hook 會等到 `on_timeout_ms`（預設 5 秒）被砍＝起不來。實測：`sleep 4 \| aos-hook fire …` 等了 4.0 秒才回 |
| after_start 清 on_clock 狀態 | 有 | 有（`--agent` 時） | 設計 05 對照表 |
| after_start 對旗標 | 沒有 | 有：照生效的清單建或刪 `hook_before_run.flag`／`hook_after_run.flag`；寫不成＝`WriteFailed`、退 1 | 12 B1、k5b |
| stdout | 什麼都不印 | `-q`：什麼都不印 | — |
| stderr | `hook_fire: error: 代號 原因`；warning `hook_fire: warning: …` | `aos-hook: error: …`；`aos-hook: warning: …` | 設計 05 對照表 |
| 錯誤代號 | HookFailed、HooksBad、PointsBad、ArgumentsBad、StackMissing | 多 EventUnknown、WriteFailed | — |
| 退出碼 | 0／1 | 0／1（10 只給能攔的點；起停兩點不能攔） | — |
| 失敗時 loop 停不停 | aos-loop 決定：k5 起四個點失敗都收工（on_start 失敗＝身體不跑；on_stop 失敗＝本來退 0 的改退那個碼） | 同，沒變 | k5、使用者「四個點都跟著停」 |
| 花的時間 | 一次約 30 毫秒 | 約 36 毫秒（k4 量的） | — |

設計稿沒寫、要我決定的：沒有。有差別的都在設計裡。

## 怎麼驗

乾淨複本：第一輪 `base`＝`git archive a71fd65b0`（開工時 HEAD）、`m3`＝同一份只疊本線的檔（別線未交的不抄；`hook_fire` 不解出來）。中途 effort 線交件（`110294e33`），全套改在 `base2`＝`git archive 110294e33`、`m4`＝它疊本線的檔上跑；第一輪的全套沒跑完就停了，只用它的針對性測試與暫存樹實跑。各自 `python3 install.py`、清掉 `AOS_*` 後逐夾跑。腳本在 `~/.aos/scratch/top-1121-hookfire/bin/`（`mine.sh`、`suite.sh`、`live.sh`、`sleepcause.sh`）。`m1`、`m2` 是抄壞的兩份（`m1` 留了空的 hook_fire 夾、`m2` 抄到一半被 `head` 截斷），沒用、沒刪。

### 全套

`base2`（`110294e33`）與 `m5`（它疊本線最後的檔，含 reasoning_effort）各 80 夾，`bin/suite.sh`，結果 `suite-base2.txt`、`suite-m5.txt`（log 在 `*.logs/`）。交件前 HEAD 又前進到 `2c3225a07`（effort 第二輪、工具說明瘦身，都沒碰本線的檔），在 `base3`／`m6` 重跑一次全套，結果跟下表逐夾相同（`suite-base3.txt`、`suite-m6.txt`），agent-python 在 m6 重新編譯也跟 repo 那份一字不差。

| 夾 | base2／base3 | m5／m6 |
|---|---|---|
| `py/tests` | 728 OK（skip 1） | **729 OK**（＋`test_llm_keys_take_reasoning_effort`；`test_hook_fire` 換成 `test_templates_wire_start_stop`，支數不變） |
| `templates/tests/agent-fsm` | 219 OK | **220 OK**（＋`test_fire_flags_on_start`） |
| `cpp/aos-daemon/tests`（含 `test_stop_cause`） | 143 OK（skip 4） | 同 |
| `templates/tests`、`py/tests/apps/hook`、`apps/agent` | 29、20、215 OK | 同 |
| 兩邊都紅、一樣的 | `apps/eca` 3 failures 1 error（`test_switch.TtySocket`，暫存路徑太長）、`apps/feedback` 1（`cwd` 寫成 `~/…`）、`apps/gdb` 1 failure 1 error（`test_gdb_live` 的 ctrl-c 兩支）、`cpp/aos-loop` 1 error（`test_cause_sigint_ignores_file`） | 同左 |
| 其餘夾 | — | 逐夾支數與結果相同 |

中間一輪 `m4`（鍵名還是 `effort`）的全套多抓到一處：`templates/reviewer/interfaces.json` 也是編譯產物的樣子（`test_agent_spec_load.Reviewer` 用 agent.py 編出來比），`llm_keys` 要跟著多一個鍵，已補。

### 暫存樹實跑（真 daemon、不叫腦）

`live.sh`，輸出 `live-tree1.txt`，樹在 `tree1/`。ann 的定義 hooks.json 一開始就加三格：`up`（after_start，記事件）、`down`（after_stop，記事件）、`hold`（before_run、condition think、退 10）。

```
== add ann (definition hooks.json already has up, down, hold; nobody ran aos-agent hook or aos-hook check)
flags: before_run=on after_run=off
up:
  {'event': 'after_start', 'hook': 'up'}
held: 8; stage now think; history lines 1
{"event": "before_run", "hook": "hold", "stack": ".../procs/ann", "counter_runs": 9, "stage": "think"}
== stop ann
down:
  {'event': 'after_stop', 'hook': 'down', 'code': 0, 'signal': None, 'cause': 'stop'}
== start ann
up: （第二筆 after_start）
flags: before_run=on after_run=off
== sleep ann
down: （第二筆）{'event': 'after_stop', 'hook': 'down', 'code': 143, 'signal': 15, 'cause': 'signal'}
== add old (loop.json from before: on_start points at lib/tools/agent/hook_fire/_entry, now gone)
old	stopped	-	1	...	failed to start: exited within 3s of wake/start (code 1): aos-loop: warning: on_stop loop.json#/on_stop exited 1
old stderr.txt:
aos-exec: error: EntryMissing entry not found: .../m3/proto8/lib/tools/agent/hook_fire/_entry
aos-loop: error: PointFailed on_start loop.json#/on_start exited 1
aos-exec: error: EntryMissing entry not found: .../m3/proto8/lib/tools/agent/hook_fire/_entry
aos-loop: warning: on_stop loop.json#/on_stop exited 1
old history lines: 0; old stage.txt: none
== shutdown
root exited
```

- 起、停各發一次：`after_start` 兩次（add、start）、`after_stop` 兩次（stop、sleep），欄位對。
- 旗標：沒人跑 `aos-agent hook`／`aos-hook check`，起來就是 on；handler 擋住 think 8 次，停在 think、history 只有使用者那一則（腦沒被叫）。
- sleep 的 cause 是 `signal` 不是 `sleep`：**舊版也一樣**。`sleepcause.sh` 在 `base`（hook_fire）與 `m3` 各跑有攔、沒攔兩種，四次都是 `"code": 143, "signal": 15, "cause": "signal"`。跟這次換沒關係，沒查、沒修，列在「沒做的」。
- 舊 loop.json＋新 lib＝那隻起不來，表上 `stopped`、`failed to start`，身體一次都沒跑。

## ~/aos-home 的 ann 怎麼辦

沒碰 `~/aos-home`。它的 `agents/ann/loop.json` 是舊編譯產物，`on_start`／`on_stop` 還指 `$AOS_HOME/lib/tools/agent/hook_fire/_entry`。

**不處理會怎樣**：使用者在 repo 跑 `install.py` 之後，`lib/tools/agent/hook_fire/` 就沒了（install 會清掉 `py/` 已經沒有的檔）。ann 下次起來（start、wake、auto_restart、daemon 重起）時 on_start 找不到程式、退 1，aos-loop 收工：ann 起不來，表上 `stopped`、原因 `failed to start`（上面 `old` 那隻就是重現）。已經在跑的那隻，停下時 on_stop 找不到＝一行 warning、after_stop 不發。

**怎麼處理**（擇一，都在 install.py 之前或之後都可以，但要在 ann 下次起來之前）：

- 照範本抄 loop.json（ann 是從 start-api 抄的就用這份；它的 hooks.json 沒動過就只抄這一個檔）：
  ```
  cp $AOS_HOME/templates/start-api/agents/ann/loop.json ~/aos-home/agents/ann/loop.json
  ```
- 或 ann 有 `agent.py` 的話重新編譯：`cd ~/aos-home/agents/ann && python3 agent.py --compile`（要 install.py 之後，用新 lib 編）。

抄完先驗一次（唯讀，不跑 handler）：`aos-hook check --agent ~/aos-home/agents/ann`。印 `ok: N points …` 就好；印 `0 points` 或 `EventUnknown`／`HooksBad`＝ann 的 `interfaces.json` 還沒有 `hook_points`（第 3 刀以前編譯的），起停兩點會 `EventUnknown`、一樣起不來，這時要整隻照範本重抄或重新編譯，不能只抄 loop.json。

照設計 12 A19 的順序：**先停樹（或至少把 ann sleep）→ install.py 並改 loop.json → 再起樹**。先 install 再停，正在跑的 aos-loop 記著舊的 on_stop，停下那一下 after_stop 發不出來（只一行 warning，不壞事）。

找還有沒有別的舊 loop.json：`grep -rl --include=loop.json -F hook_fire ~/aos-home`。repo 裡 `wf/temp/ok-onboard/defs/gather-p0/loop.json`、`wf/temp/ok-limits/defs/sol/loop.json` 也還指 hook_fire（暫存的隊員定義，不在本線範圍，沒改）：哪天再用要同樣處理。

## 沒做的

| 沒做的 | 為什麼 |
|---|---|
| `proto8/docs/` 條文三份 CONVENTION、附錄 4 | 不改條文，要補的字在下面 |
| 第 6 刀（gdb 讀宣告）、第 7 刀（總文件）、`hook_points.json` 格式 | 任務書不做 |
| `stack.gitignore` 擋兩個旗標（09b F14，k5b 選擇 5 沒擋） | 起來時對旗標現在接上了，k5b 說「換成 aos-hook fire 之後要擋就加兩行」；但要不要擋是使用者的事，這次沒加 |
| sleep 的 cause 是 `signal` 不是 `sleep` | 舊版一樣，不是這次的事；沒查原因 |
| 前景跑 aos-loop、stdin 是不關的管子時 on_start 會等到逾時 | 設計 05 定了 stdin 的讀法；daemon 底下沒事。要擋的話可以讓 aos-hook 在 stdin 是管子以外的東西時才讀，或 loop.json 給 stdin 接 /dev/null，等使用者 |
| `wf/temp` 兩份舊 loop.json | 不在範圍 |

## 文件要補的字（條文不改，等使用者看）

- `docs/CONVENTION/03-shell版與inst版.md:22`：例子寫 `on_start` 是 `{"$env": "AOS_HOME", "$path": "/lib/tools/agent/hook_fire/_entry"}`，那支已經沒了。要換一個還在的例子（例如 `templates/agent-fsm/hooks.json` 裡 `timer` 的 handler `{"$env": "AOS_HOME", "$path": "/lib/tools/agent/hook_noop"}`）。
- `docs/CONVENTION/02-題目stack停錯腦/03-P-43-本文.md:4`：「`on_start`／`on_stop` 掛 `py/tools/agent/hook_fire`」→「`on_start`／`on_stop` 經 `aos-hook fire --agent` 發 after_start／after_stop」。
- `docs/CONVENTION/06-巢狀/03-P-37～P-40.md:5`：提到 hook_fire 的那句跟著換（同上）。
- `docs/NORMS/附錄4-持久檔.json`：loop.json 那列的 note「agent 範本兩格指到 py/tools/agent/hook_fire」→「agent 範本兩格經 aos-hook fire --agent」；on_clock.json 那列的 writer「py/tools/agent/hook_fire after_start 叫」→「aos-hook fire --agent … after_start 叫」。k5b 列的旗標兩列、loop.json 四鍵照舊等補。

## 順手：編譯認 reasoning_effort（頂層加派）

線 top-1121-effort 留的一行（[llm-effort-1121「沒做的」](llm-effort-1121.md)）：`py/aos/agent_spec_parts.py` 的 `LLM_KEYS` 加思考程度那個鍵，順序照 `templates/agent-fsm/llm_settings.KEYS`（model、程度、再來調參那幾個）。鍵名是 **`reasoning_effort`**：頂層轉來使用者剛裁的「effort...改叫reasoning_effort吧，說清楚」。effort 線第二輪（`4a2ede307`）已把 agent-fsm 那邊改名交件，兩邊名字一致。以前用 `agent.py` 編譯、`llm` 寫程度會被擋（`llm key ... is not one of llm_keys`），現在 `reasoning_effort` 照寫進 llm.json；編譯出的 interfaces.json 的 `llm_keys` 也多這一個，所以 `templates/agent-python/interfaces.json` 重新編譯後多一行。新測試 `test_agent_spec.py` 的 `test_llm_keys_take_reasoning_effort`：`llm_keys` 前兩個是 model、reasoning_effort，值照寫進 llm.json，舊名 `effort` 擋下。因為同一個檔，跟上面一起交一筆。進度 `llm-effort` 的第 1 件劃掉。

## 交件

- 見 commit；claim 交件時放。沒 push；沒在 repo 跑 `install.py`；沒碰 `~/aos-home`；沒叫真模型。
- 進度 `aos-hook-iface` 的 what 加一句、next 改寫。
