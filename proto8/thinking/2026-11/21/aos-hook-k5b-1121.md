# 「提供 hook 點」的介面：施工第 5 刀的後半（範本接上 before_run／after_run、編譯寫四鍵、旗標維護、procs-kernel 接 loop 層的點）

← [當天索引](README.md)｜設計 [aos-hook-plan-1120](../20/aos-hook-plan-1120/README.md)（loop 層在 [06](../20/aos-hook-plan-1120/06-loop層的點.md)，對不上以 [12 採納表](../20/aos-hook-plan-1120/12-採納表.md) 為準）｜使用者已答 [13](../20/aos-hook-plan-1120/13-使用者已答.md)｜前一半 [k5](../20/aos-hook-k5-1120.md)、[k3](../20/aos-hook-k3-1120.md)

線 top-1121-hook5，11-21 凌晨家機，頂層派。使用者在睡，沒問他。依據（逐字在 13）：方向第 3 題「在 loop 層加通用的點」；待裁第 1 題「能攔」、第 2 題「四個點都跟著停」、第 7 題 kernel「接」、第 11 題「用旗標檔」、第 12 題「before_run / after_run」；11-20 晚 `hook_fire` 換 `aos-hook fire`「明天再說這塊」（所以這刀**沒碰 `hook_fire`**）。

## 結論

- **四樣都做了**：範本的 loop.json 接上 `before_run`／`after_run`；編譯（`agent_spec`）有 hooks 時寫那四個鍵；旗標檔有人對；procs-kernel 範本接上 loop 層的點。
- `loop_points.json` 拿掉兩個 `not_fired_yet`，所以 `hooks.EVENTS` 自動多了 `before_run`、`after_run`：`aos-agent hook add --event before_run`、`self_hook`、編譯都收了。
- 暫存樹實跑（真 daemon、假腦）：沒人掛時 2 秒取樣 40 次看不到一支 `aos-hook`；`hook add --event before_run --condition act`（handler 退 10）＝旗標檔出現、act 被攔 6 次、答案不回來；`hook rm`＝旗標檔消失、答案回來；`after_run` 帶 `next_stage`；權限站 perm 掛了 `loop_hooks.json` 之後每一輪發 `after_run`。
- **有一小塊等使用者**：範本起來時（`on_start`）還是 `hook_fire`，它不對旗標。所以**定義那份 hooks.json 一開始就掛 before_run／after_run 的 agent**，旗標要等有人跑 `aos-agent hook add／rm／reset` 或 `aos-hook check --agent … --stack …` 才出現。等 `hook_fire` 換成 `aos-hook fire`（明天要談的那塊）就自動補上，`aos-hook fire … after_start` 對旗標這段已經寫好、測好。

## 改了哪些檔

| 檔 | 新／改 | 一句話 |
|---|---|---|
| `py/aos/hook_flags.py` | 新 | `sync(stack, points, entries)`：宣告裡有 before_run／after_run 的點，照生效的清單建或刪 `hook_before_run.flag`／`hook_after_run.flag` |
| `py/aos/apps/agent/hook.py` | 改 | `add`／`rm`／`reset` 改完清單就 `keep_flags`；`--help` 的事件表、`--condition`、`--no-intercept` 加兩個點 |
| `py/aos/apps/hook/main.py` | 改 | `fire … after_start` 對旗標（任何來源，有 stack 就對）；`check` 有 stack 時對旗標、多印一行 `flags: …`；寫不成＝`WriteFailed`；`--help` |
| `py/aos/apps/hook/loop_points.json` | 改 | 拿掉兩個 `not_fired_yet`、改 description |
| `py/aos/agent_spec_agent.py`、`agent_spec_parts.py` | 改 | 新 `run_points(fsm 檔名)`；`_Loop.json()` 有 hooks 時多寫四鍵；loop.json 的 description 多一句 |
| `templates/agent-fsm`、`start-api/agents/ann`（抄本）、`agent-python`（重新編譯）的 `loop.json` | 改 | 四鍵：`aos-hook fire -q --agent $AOS_CD`，before 帶 `--field-file stage=$AOS_STACK/stage.txt --field-default stage=<fsm.json 的 start>`，after 帶 `next_stage=` |
| `templates/eca-claude`、`eca-pi`、`start-eca/agents/ann`（抄本）的 `loop.json` | 改 | 四鍵，不帶 stage（設計 12 A8） |
| `templates/kernel/procs-kernel/loop.json`、`start-api/perm/loop.json`（抄本） | 改 | 四個 loop 點都接：`aos-hook fire -q --points $AOS_HOME/lib/aos/apps/hook/loop_points.json --list $AOS_CD/loop_hooks.json`；加 description |
| 五份範本 `hooks.json` | 改 | description 的事件名單加 before_run、after_run（一致性測試要） |
| `py/tools/agent/self_hook/_tooldef.json` | 改 | enum 與說明加兩個點 |
| `knowledge/aos/me/self_hook.json` | 改 | events 加兩行（先寫暫存再改名） |
| `py/tools/aos/defs/refs_check.py` | 改 | 跟著 `on_before_run`／`on_after_run` 查程式在不在；兩個 `_if` 不查（旗標本來就常不在） |
| `py/aos/apps/agent/docs/06-hook.md` | 改 | 事件表兩列、新一節「每一格前後」、eca 表一列；順手改掉「hook 失敗 agent 照起、照停」（k5 之後已不對） |
| `py/aos/apps/hook/README.md`、`templates/kernel/README.md` | 改 | 旗標檔一條；procs-kernel 的 loop 點一段 |
| 測試 | 新 3、改 4 | 新 `py/tests/test_hook_flags.py`（4）、`py/tests/apps/agent/test_hook_flags.py`（2）、`py/tests/apps/hook/test_hook_cli_flags.py`（5）；改 `test_hook_point.py`（不再有 not_fired_yet）、`test_hook_points_match.py`（新 `test_templates_wire_the_loop_points`；hook_fire 只比起停兩點；gdb 那條排除 loop 的點）、`test_agent_spec.py`（四鍵）、`apps/hook/test_hook_cli.py`（not_fired_yet 的警告改用自己宣告的點） |

`apps/agent/hook.py` 347 行、`apps/hook/main.py` 342 行，都超過 300（改前就 326、319），沒拆。

## 怎麼驗的

- 乾淨複本：`git archive d3882e9c5` 疊上本線的檔，複本裡 `python3 install.py`、清掉 `AOS_*` 後逐夾跑。基準（同一個 commit 不疊）與改後的全套數字見「全套測試」。
- 暫存樹實跑：`~/.aos/scratch/top-1121-hook5/bin/live.sh`，輸出 `live-tree1.txt`，樹在 `tree1/`。

```
== no hooks
flags: before_run=off after_run=off
aos-hook seen in 0 of 40 samples (2 s)
== add before_run hold (condition act)
flags: before_run=on after_run=off
held: 6 ; stage now act
{"event": "before_run", "hook": "hold", "stack": ".../procs/ann", "counter_runs": 21, "stage": "act"}
== rm hold
flags: before_run=off after_run=off
FAKE ANSWER to: hello (tool said: 2026-11-20T22:49:32Z)
== add after_run seen
flags: before_run=off after_run=on
{"event": "after_run", "hook": "seen", ..., "counter_runs": 32, "code": 0, "signal": null, "elapsed_ms": 24, "next_stage": "idle"}
seen grew after rm by 0
aos-hook seen in 0 of 40 samples (2 s)
== perm with loop_hooks.json
perm flags: before_run=off after_run=on
round events: 9 after_run, 1 after_start
== shutdown
root exited
```

- `--field-default` 用 `{"$ref": "fsm.json#/start", "$prefix": "stage="}`（12 列為沒核對）：實跑能用（aos-directive 換完 `$ref` 再接 `$prefix`，程式 `cpp/aos-directive/src/resolve.cpp` 也是這樣寫）。
- eca 的接線只驗了形狀（一致性測試），沒實跑：要外部 CLI。

## 全套測試

兩份乾淨複本：`base`＝`git archive d3882e9c5`（開工時 HEAD）、`m2`＝同一份疊本線的檔；各自 `python3 install.py`（含 C++ 全家編譯）、清掉 `AOS_*` 後逐夾 `python3 -m unittest discover`，共 79 夾（腳本 `bin/suite.sh`，結果 `suite-base.txt`、`suite-m2.txt`，log 在 `*.logs/`）。

| 夾 | base | m2 |
|---|---|---|
| `py/tests` | 723 OK（skip 1） | **728 OK**（skip 1；＋`test_hook_flags` 4、`test_templates_wire_the_loop_points` 1） |
| `py/tests/apps/agent` | 213 OK | **215 OK**（＋`test_hook_flags` 2） |
| `py/tests/apps/hook` | 15 OK | **20 OK**（＋`test_hook_cli_flags` 5） |
| `py/tests/apps/feedback` | 18，1 failure | 同左（`cwd` 被寫成 `~/…`：TMPDIR 放在家目錄底下的環境題，兩邊一樣，跟本線無關） |
| 其餘 75 夾 | — | 逐夾支數與結果相同（cpp 十夾含 aos-loop 52、aos-daemon 143；gdb 66；templates/tests 29、agent-fsm 215；kernel 126；`templates/tests/image-move-check`、`templates/kernel/tests` 兩邊都是 0 支、退 5，不是 unittest） |

## 沒做的與為什麼

| 沒做的 | 為什麼 |
|---|---|
| `hook_fire` 換 `aos-hook fire`、刪 `hook_fire` | 使用者「明天再說這塊」；範本起停照舊叫它 |
| 起來時對旗標（範本那條路） | 起來那格是 `hook_fire`，任務書要它原樣；`aos-hook fire … after_start` 已會對，換過去就有。**等使用者**：要不要在換之前先給 `hook_fire` 加一行對旗標（見「要使用者定的」） |
| gdb 從宣告讀（第 6 刀）、總文件（第 7 刀） | 建在 `hook_points.json` 的格式上，使用者要先審格式 |
| `hook_points.json` 格式 | 不改（暫定） |
| `stack.gitignore` 擋兩個旗標（09b F14） | 沒擋，見選擇 5 |
| `templates/reviewer` 接線（12 A20） | reviewer 沒有 hooks，沒有點可掛；它的 loop.json 要跟編譯產物逐字相同（k3 同理沒加 hook_points） |
| `templates/kernel/daemon-kernel` | 是 daemon 的身體，aos-daemon 不收這四鍵（k5） |
| 條文（NORMS、CONVENTION、附錄 4） | 不改；要補的字在下面 |

## 替使用者做的選擇（設計沒寫到的）

1. **kernel 的 loop 點用另一份清單 `loop_hooks.json`，不放進 `kernel.json`**：使用者第 7 題選的那格寫「改 procs-kernel 範本的 loop.json；不改 kernel 程式」。放進 `kernel.json` 的話，kernel 每輪驗 hooks 時不認得 before_run（`kernel/hooks.py` 的表只有三個點）＝每輪 HooksBad，就得改 kernel 程式。分開放 kernel 一行沒改；代價是 kernel 有兩份清單。要合成一份＝`kernel/hooks.py` 的 `POINTS` 多讀 `loop_points.json`、loop.json 的 `--list` 改指 `kernel.json`（兩邊的格會在同一個 stack 的 `hooks/<名>/`，名字不能撞）。
2. **procs-kernel 四個 loop 點都接（含 `on_start`／`on_stop` 發 after_start／after_stop）**：旗標要有人在起來時對，`aos-hook fire … after_start` 就是那個時機；順便 kernel 也有起停兩點。代價：站每次起、停各多一支 `aos-hook`（約 36 毫秒）；`loop_hooks.json` 壞了站起不來（四個點都跟著停）。
3. **旗標的對法放在新的小庫 `aos/hook_flags.py`**，`aos-agent hook` 與 `aos-hook` 共用；只管宣告裡有的 loop 點，沒宣告的旗標不碰。
4. **`aos-hook fire … after_start` 對旗標不限 `--agent`**：`--points`／`--list` 的來源（kernel）也對。`aos-hook check` 有 stack（`--stack` 或 `$AOS_STACK`）就對，並多印一行 `flags: 路徑 on|off, …`；沒有 stack 只驗、不對、不多印。
5. **`stack.gitignore` 不擋兩個旗標**（設計 09b F14 說擋）：起來時對旗標今天還沒接上（選擇的前提見上），擋了的話 stack 搬到別台、hooks.json 跟著走、旗標沒跟，before_run／after_run 就靜靜不發。旗標是照 hooks.json 算的、不是這台才有意義的東西。換成 `aos-hook fire` 之後要擋就加兩行。
6. **旗標檔寫一行英文說明**（不是空檔）：人打開看得懂它是什麼。aos-loop 只看在不在。
7. **寫不成旗標＝錯**（`aos-agent: error: WriteFailed`、`aos-hook: error: WriteFailed`），不是 warning：清單已經改了但點不會發，是騙人的成功。`fire after_start` 寫不成＝那隻起不來。
8. **編譯只在有 hooks 時寫四鍵**（跟 `on_start`／`on_stop`、`hook_points` 同進同出）；fsm 的檔名照這隻自己的（`run_points(fsm 檔名)`），`$ref` 從 loop.json 那夾算。
9. **gdb 自動多了 `before_run`／`after_run` 兩種斷點**（它的種類從 `hooks.EVENTS` 算），以「暫停」的方式（不在 `HOLD_EVENTS`）；gdb 下斷點走 `aos-agent hook add`，所以旗標自動對。沒實跑 gdb 的這兩種；一致性測試 `test_gdb` 改成只比身體的點，loop 的留給第 6 刀。
10. `test_hook_cli.py` 那條「掛在 not_fired_yet 的點印警告」改用測試自己宣告的點（aos 自己帶的已經沒有這種點）。

## 要使用者定的（一小塊）

- **換 `hook_fire` 之前，定義那份 hooks.json 掛 before_run／after_run 的 agent 起來時沒有旗標**。三個做法：(a) 等明天談 `hook_fire` 換 `aos-hook fire` 時一起解決（什麼都不用多做）；(b) 先在 `hook_fire` 的 after_start 加一行 `hook_flags.sync`（改 `hook_fire`，任務書說不碰，所以沒做）；(c) 照舊，文件已寫明手改清單要跑 `aos-hook check --agent … --stack …`。我推薦 (a)。出廠範本的 hooks.json 沒有掛這兩個點，眼前沒有人受影響。

## 文件要補的字（條文不改，等使用者看）

- `docs/NORMS/附錄4-持久檔`：stack 多兩個檔 `hook_before_run.flag`、`hook_after_run.flag`（有人掛那個點才在；壞了＝刪掉再 `aos-hook check --agent … --stack …`）；loop.json 一列加 `on_before_run`／`on_after_run`／兩個 `_if`；procs-kernel 夾可以多一份 `loop_hooks.json`。
- `docs/NORMS/04-基礎設施-loop與daemon.md`：k5 列的那句（失敗收工）照舊沒改；另加「範本的 loop.json 經 aos-hook 接 before_run／after_run、旗標檔在才跑」一句。
- C-90 那句「事件清單見…」：第 7 刀的事，沒動。
- `templates/docs/02-agent-fsm.md`、`01-eca-claude.md`、`templates/agent-fsm/README.md`：沒提 loop.json 這四鍵（不算錯，之後總文件一起）。

## 要重建什麼（改持久格式）

- 已經編譯好、正在用、有 hooks 的定義夾（例 `~/aos-home` 的 ann）：loop.json 沒有這四鍵＝before_run／after_run 掛得上但不發（`aos-agent hook add` 照建旗標，aos-loop 不看）。要的話重新編譯，或從範本抄 loop.json。不重建也不會壞。
- 使用者醒來在 repo 跑 `python3 install.py` 才進活樹的 `lib/`：`hook_flags.py`、`aos-hook`／`aos-agent hook` 的旗標、`loop_points.json`（`hooks.EVENTS` 才收這兩個點）、編譯的四鍵、`self_hook` 的說明與 enum、`refs_check`。範本（`templates/`）與知識庫（`knowledge/`）存檔即生效：**install 之前**，從範本新抄的 agent 的 loop.json 已帶四鍵，但舊 `lib/` 的 `aos-hook` 是第 4 刀那份、`aos-agent hook add --event before_run` 會被舊的 EVENTS 擋（HooksBad）——不會出錯，只是掛不上；知識庫已寫了兩個點，腦叫 `self_hook add before_run` 會拿到同一個錯。

## 收尾

- 交件：見 commit；claim 交件時放。沒 push；沒在 `~/repo/aos/proto8` 跑 `install.py`；沒碰 `~/aos-home`；沒叫真模型（假腦）。
- 行程：暫存樹 `tree1` 用 `aos-daemon-ctl -d .stack shutdown` 收，根自己退出；事後 `pgrep -af tree1` 沒有這棵樹的行程。
- 暫存：`~/.aos/scratch/top-1121-hook5/`（複本 `base`、`m1`〔第一輪，hook 測試一支紅已修〕、`m2`；樹 `tree1`；腳本 `bin/clean-env.sh`、`in-copy.sh`、`mine.sh`、`suite.sh`、`live.sh`；結果 `suite-*.txt`、`live-tree1.txt`、`install-*.log`；TMPDIR `tmp/`）。都沒刪。
