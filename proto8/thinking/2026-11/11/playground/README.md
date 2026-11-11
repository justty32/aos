# 公司試驗場：今天多了什麼、怎麼玩（11-11）

← [2026-11-11](../README.md)｜刷新腳本與驗收紀錄 [01](01-公司刷新與驗收.md)

**結論**：`~/code/playground`（公司 WSL）已照今天的 main 刷新（11-11 13:06 第二次：線 I 的 do_task、新信通知，和工具小格寫入才建都進來了），三隻都掛好、停著、對話是空的。**不用先手動做任何事**（claude 用的工作區 `~/code/playground/ws` 之前就信任過，這次沒換）。開兩個視窗照抄就能玩：

```sh
# 視窗一：起整棵樹（Ctrl-C＝整棵下班；再打同一行＝上班，三隻自己醒）
cd ~/code/playground && source env.sh && aos-exec root

# 視窗二：下指令（都在 ws/ 裡打）
cd ~/code/playground && source env.sh && cd ws
aos-agent ctl ls                       # 三隻都 running 就可以玩
```

不用 Ctrl-C 也能停：`aos-daemon-ctl -d ~/code/playground/.stack shutdown`。

## 三隻

| 名字 | 身體 | 腦 | 花錢 |
|---|---|---|---|
| `fsm_ann` | agent-fsm（aos 自己的 loop） | 假腦 `fake`（先叫 `peek_now_time` 再答 `FAKE ANSWER to: …`） | 不花 |
| `eca_bob` | eca，Claude Code | `haiku`，每題上限 0.3 美金 | 花 claude 額度 |
| `eca_cody` | eca，Codex CLI（沒有畫面） | `gpt-6-luna` | 花 codex 額度 |

三隻都是 36 支工具（十一包；gadgets 包有 `do_task`），hooks 都是 `timer`＋`mail_notify` 兩格（`aos-agent tools --target fsm_ann ls`）。跟一隻說一句話：

```sh
aos-agent say --target eca_bob 'Call the aos tool peek_now_time, then tell me the time in one line.' && aos-agent listen --target eca_bob --timeout-s 300
```

`--target` 換成 `fsm_ann`、`eca_cody` 就是跟另外兩隻說。要一來一回聊：`export AOS_AGENT=eca_bob; aos-agent chat`（Ctrl-C 離開，樹照跑）。

## 讓 agent 改自己的 system（`self_system`）

叫它用工具改自己的 system 文字。**claude 那隻下一句就生效**：

```sh
aos-agent say --target eca_bob 'Use the aos tool self_system to set your system text to: End every answer with [~].' && aos-agent listen --target eca_bob --timeout-s 300
aos-agent say --target eca_bob 'Say hi in one line.' && aos-agent listen --target eca_bob --timeout-s 300     # 句尾有 [~]
```

**codex 那隻要開新對話才生效**（codex 只在對話開頭讀一次；aos 只提醒、不替它開）：同樣叫它改，然後刪掉它的對話 id，再說一句：

```sh
aos-agent say --target eca_cody 'Use the aos tool self_system to set your system text to: End every answer with [~].' && aos-agent listen --target eca_cody --timeout-s 300
rm -f .stack/procs/eca_cody/codex/session.txt .stack/procs/eca_cody/codex/.session_home   # 開新對話
aos-agent say --target eca_cody 'Say hi in one line.' && aos-agent listen --target eca_cody --timeout-s 300    # 句尾有 [~]
```

改回來：叫它 `self_system` 的 `reset`，或人打 `aos-agent system --target eca_bob reset -y`（codex 那隻 reset 後也要刪 session.txt 才回去）。fsm 那隻是**整份取代**、下一格就生效；eca 兩隻是**附加**在 CLI 自己的 system 後面。

## 人自己改 system（`aos-agent system`）

```sh
aos-agent system --target fsm_ann get -l                          # 第一行：從哪來（agent／definition）
echo 'Be brief.' | aos-agent system --target fsm_ann set -          # 換成這段（只改這隻自己那份）
aos-agent system --target fsm_ann reset -y                         # 回到定義那份
```

## 免費看今天的新工具（假腦劇本）

試驗場的總機多一個劇本假腦 `fake-demo-today`：改自己的 system → 讀回來 → 用 `subagent` 生一隻子 `kid`、問它時間、`subagent ls` 列出來、刪掉 → 叫 `do_task` 派一個小幫手問時間（不給 `from`＝用自己的定義） → 把 system 改回去。劇本照對話裡的回合數走，所以掛一隻**新的**來跑：

```sh
aos-agent ctl add --name fsm_demo ../agents/fsm_ann && aos-agent llm --target fsm_demo set model=fake-demo-today
aos-agent say --target fsm_demo 'show me' && aos-agent listen --target fsm_demo --timeout-s 120
aos-agent history --target fsm_demo ls                              # 看它叫了 self_system、subagent、do_task 哪幾次、結果是什麼
aos-agent ctl rm --purge -y fsm_demo                                # 玩完拿掉
```

## 派一件小事（`do_task`）——下次重刷後改了

> **11-11 稍後（線 K）**：下面這段是 13:06 刷新時的舊 do_task。之後 do_task 改成 save／load、另做 `fork`，並新增 grep、glob、todo、goal（[fork-and-do-task](../fork-and-do-task/README.md)、[new-tools 04](../new-tools/04-施工結果.md)、[goal 02](../goal/02-裁定與施工結果.md)）；試驗場要重刷才有（fsm 41 支、eca 39 支），劇本 `fake-demo-today` 的 do_task 那步要改成 `{"op": "start", "task": "Check the time"}` → peek_now_time → `{"op": "end", "summary": "Checked the time."}`（摺完 assistant 則數會倒退，後面幾步用 llm_fake 的 `when` 接，或把 do_task 放最後）。重刷後：`do_task` 在自己的對話裡做一段任務，`end` 時那段換成一則 `[aos] summary: …`、原文在 `<stack>/history_removed.jsonl`；`fork` 把自己連對話複製一份去做一個 goal、只拿回結論；兩支都只給 fsm，eca 叫到＝`BodyUnsupported`。

舊版（13:06 刷新時）：`do_task`（原名 thought）派一件事給用完即刪的小幫手、只拿回短結論，過程不進自己的對話。**不給 `from`＝用自己的定義**生小幫手（工具、hooks 一起帶）；小幫手可以再派一層，再深＝`DepthExceeded`。上面假腦劇本裡就有一步是它，免費。要真腦做：

```sh
aos-agent say --target eca_cody 'Use the aos tool do_task with goal "What time is it? Answer in one line." and tell me what it brought back.' && aos-agent listen --target eca_cody --timeout-s 600
```

小幫手的帳留在 `<叫它那隻的 stack>/tools/do_task/observed/<小幫手名>/`（這行這次沒用真腦跑；luna 在線 I 跑過 do_task）。

## 新信通知與免打擾（`mail_notify`）

三隻預設都掛著 `mail_notify`（每 1 分鐘看一次自己的信箱；11-11 使用者翻案前是 10 秒，試驗場那幾份 `hooks.json` 要重抄才會變 1 分鐘，見 [backlog-rulings](../backlog-rulings.md)）：起來、睡醒時信箱裡已經在等的不提醒；之後有**沒通知過**的新信，就往自己的對話放一則 `[aos] new_mail: N new letters from A, B. Look with mailbox_peek, read with mailbox_read.`，連來幾封只合成一則、不帶內文。試（假腦、不花錢；在 ws/ 裡打）：

```sh
aos-mailbox send --to fsm_ann --status REQUEST --title hello 'first letter'
sleep 65; aos-agent history --target fsm_ann ls | grep new_mail       # 多一則 [aos] new_mail（後面跟假腦的回答）
```

免打擾：叫它自己用 `self_hook` 的 `rm`（name `mail_notify`），或人打 `aos-agent hook --target fsm_ann rm mail_notify`；改回預設開：`aos-agent hook --target fsm_ann reset -y`（刪掉這隻自己的 hooks 清單、回到定義那份）。改間隔：同名再 `add`、加 replace。**eca 兩隻每則通知都算一題、會花錢**（codex 那隻收到後會自己 `mailbox_peek`／`mailbox_read`）。

## 工具小格寫入才建

以前每支被叫過的工具都在 `<stack>/tools/<名>/` 留一個資料夾（很多是空的）；現在**只有真的寫東西的工具**才有（`subagent`、`do_task`、`shell`、`run_python`…）。叫完 `peek_now_time` 看 `ls .stack/procs/fsm_ann/` 沒有 `tools/`；跑過上面假腦劇本的 fsm_demo 只有 `tools/do_task`、`tools/subagent`。

## 叫子 agent（`subagent`）

上面那段假腦就是 `subagent` 的完整一輪（add → ask → rm）。要真腦自己做，對 eca 說「用 aos 工具 subagent 從 `~/code/playground/templates/agent-fsm` 生一隻叫 kid 的、問它時間、再刪掉」——子預設是假腦、不花錢，但 eca 那隻本身會花（這條沒實跑過）。看自己生了誰：`aos-agent say --target eca_bob 'Use the aos tool subagent with op ls.'`。

## 掛一個時鐘 hook（`on_clock`）

`ws/hooks/ping_me` 已放好：每次觸發往這隻自己的 queue 寄一句 `tick: what time is it?`。掛在 fsm_ann（假腦、不花錢）每 30 秒一次：

```sh
aos-agent hook --target fsm_ann add --event on_clock --every-ms 30000 --on-error continue hooks/ping_me
aos-agent listen --target fsm_ann --last 3            # 過一會兒看：多了幾則 tick 的回答
aos-agent hook --target fsm_ann rm ping_me            # 拿掉
```

一掛上（以及每次起來、睡醒）會**先觸發一次**，之後照間隔。handler 本身不進對話，是它寄的那封信讓腦回答。**別掛在 eca 兩隻上**：每次 tick 都是一題、都花錢。範本預設掛著一格 `timer`（每 5 分鐘、什麼都不做），`aos-agent hook --target fsm_ann ls` 看得到。

## 起來／停下時跑東西（`after_start`／`after_stop`）

`ws/hooks/up_down` 已放好：把事件 JSON 記進 `ws/up_down.log`。

```sh
aos-agent hook --target fsm_ann add --event after_start --on-error continue -n up hooks/up_down
aos-agent hook --target fsm_ann add --event after_stop --on-error continue -n down hooks/up_down
aos-agent ctl stop --target fsm_ann; aos-agent ctl start --target fsm_ann; cat up_down.log    # 一行 after_stop（code 0）、一行 after_start
aos-agent hook --target fsm_ann rm up; aos-agent hook --target fsm_ann rm down
```

整棵下班（Ctrl-C／shutdown）也算停下（`code` 143）；`kill -9` 不會跑 after_stop。

## 人的信箱換位置

`aos-mailbox` 的預設信箱改成 `~/.aos/stack/mailbox`（`aos-mailbox where` 印出來）。寄給一隻（在 ws/ 裡）：`aos-mailbox send --to fsm_ann --status REQUEST --title 'hello' 'Say hi back with mailbox_send.'`；看回信：`aos-mailbox peek`（這兩行這次沒實跑）。

## 已知限制

- **fsm 真腦回家測**：公司 LM Studio 只有小模型，fsm_ann 這次只接假腦；`stupid-fast`（LM Studio 的 `qwen/qwen3-1.7b`）沒驗。
- **eca_bob（haiku）沒驗新信通知**：這次只驗到它叫 `peek_now_time`（額度已回）；收 `[aos] new_mail` 只在 fsm_ann、eca_cody 驗過。
- **codex 的畫面沒驗**：eca_cody 拿掉了畫面，`aos-agent open --target eca_cody` 不能用；eca_bob 照舊有畫面。
- **claude 全新工作區第一次要手動按信任**：這次沒碰到。哪天把 eca 掛到別的工作區、`ctl ls` 出現 `TrustMissing`，就在那個資料夾開一次 claude 按信任再退出（`cd <那個資料夾> && claude`），aos 不替你按。
- **刷新會清東西**：下次刷新會清掉三隻的對話、信箱、`llm set`／`hook add`／`system set` 改過的設定，和試驗場 `knowledge/` 裡 agent 寫的東西（整份會先備份）。
- 三隻已掛好，不用再 `ctl add`（再 add 一次＝`InstanceExists`）。

<details><summary>刷新做了什麼、備份在哪、怎麼退回</summary>

- 備份：`~/code/playground.bak-1111-1306`（第二次刷新前整份；上午那次刷新前的是 `.bak-1111-1024`）。退回：停樹 → `rm -rf ~/code/playground && mv ~/code/playground.bak-1111-1306 ~/code/playground`。
- 換掉的：`lib/ py/ templates/ knowledge/` 換成 repo 版（`py/`、`templates/` 是新加的）；總機定義 `llm_kernel/def` 換 repo 的 `kernel/llm-kernel`，`stupid-fast` 改回這台的 `qwen/qwen3-1.7b`，多 `fake-demo-today`；三隻從範本重抄。
- `env.sh`：加 `export AOS_HOME=$PG`；舊的 `AOS_MEMORY` 那行改成 `AOS_KNOWLEDGE=$PG/knowledge`。其他行沒動。
- 根、總機、領班的定義（`root/`、`daemon/`，表上的名字 `switchboard`、`foreman`）沒動。
- 腳本全文與每步驗收在 [01](01-公司刷新與驗收.md)。

</details>
