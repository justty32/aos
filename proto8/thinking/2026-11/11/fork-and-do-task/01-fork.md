# 01 fork：把當下的自己複製一份、給一個 goal、只收回結論（11-11 線 K 施工）

← [fork-and-do-task](README.md)｜程式 [lib/agent/fork](../../../../lib/agent/fork/)、lib/agent/fork_copy.py（`../../../../lib/agent/fork_copy.py`）

使用者原話與五題裁定見 [README](README.md)（「把fork單獨拉出來做為工具」「一律連對話複製」「拿掉這個能力」）。施工後又一句（頂層傳話）：

- 「eca不給fork。」——fork 只給 agent-fsm 的身體；eca 範本 tools.json 寫 `"fork": null`（隊長加）。

## 施工結果（白話）

- **新工具 `lib/agent/fork`**：參數只有 `goal`（必要）、`max_chars`（預設 600）、`timeout_s`／`timeout_cycles`、`keep`。開分身、等結論、抄帳、收掉這套整段照搬舊 do_task（`git show 4a9422604:proto8/lib/agent/do_task/_entry`）：租約紀錄 `<我的 stack>/tools/fork/children/<分身名>/state`、對帳、失敗留三隻、答完先抄公開帳再收。拿掉 `from`／`AOS_DO_TASK_FROM`、`context`、`tools`、`model`（給了＝`ArgumentsBad unknown key …`）。
- **怎麼抄**（`lib/agent/fork_copy.py`）：`ctl who --json` 拿到我的定義與 stack → 讀定義 `interfaces.json` 的 `aos-agent` 宣告 → 把宣告過的 `history`（必要）與 `tools`／`llm`／`hooks`／`system` 這隻自己那份（有才抄）抄進 `<daemon>/procs/<分身名>/` → `aos-agent ctl add --name 分身 --ws 我的工作區 --stack 那份 --envs AOS_FORK_DEPTH=1 我的定義`。先抄好再掛上，分身第一拍就是完整的（after_start hook 也用抄過去的 hooks）。登記檔裡的相對路徑（`$override`、`tools.*.path`、`tools.*.env_file`、`hooks.*.handler`）換算到新位置；指示詞物件照原樣。
- **history 尾巴**：fsm 叫工具時 history 最後一則是帶 `tool_calls` 的 assistant、還沒有 tool 訊息。照抄後補上：第一個沒回的（act 一支一支照順序跑＝正在跑的這次 fork）、其餘沒回的各一則（原文見下）。
- **只給 fsm**：history 裡找不到叫到一半的 tool call＝`BodyUnsupported`（判法同 do_task：eca 的工具來回在 CLI 裡、history 只有 user／assistant 文字），錯誤行 `fork: error: BodyUnsupported fork works only in an agent-fsm body, where each tool call is a line of your history (no unanswered tool call found in it); to hand work to another agent, use subagent`；在建任何東西之前就判（ctl who 之後、對帳與 mkdir 之前）。
- **eca 查過做得到、但使用者裁不給，程式拿掉**：`claude --help` 有 `--fork-session`（配 `--resume X`）、`codex exec --help` 有子命令 `fork`（`codex exec fork X`）。一度接進 cli_session／aos-eca-turn（記號檔 `forked_from.json`＋CLI 分叉、假 CLI 測過），依「eca不給fork。」全部拿掉，cli_session.py、aos-eca-turn、假 CLI 沒留任何 fork 的改動。
- **開場**：`aos-agent say` 一則（原文見下），`listen` 拿第一則回答當結論。預設收掉（`ctl rm --purge`）；`keep: true`＝`ctl stop` 留著、結論後一行 `details: procs/<分身名>/`。
- **深度**：`AOS_FORK_DEPTH`（`ctl add --envs` 帶進分身，經 aos-tools 傳到工具），最多 1 層，分身再叫＝`DepthExceeded`；開場也直接說「不能再 fork」。
- `py/aos_flags.py` 的 `NOTE_KINDS` 加 `fork`。

## 分身看到的最後幾則（原文；goal 換成實際的字，max_chars 預設 600）

補給 fork 那次呼叫的 tool 訊息：

```
[aos] fork: you are the copy made by this call; the original agent is waiting for your conclusion. Your task is in the next message.
```

同一則 assistant 裡排在 fork 後面、還沒跑的呼叫：

```
[aos] fork: not run in the copy (the original runs it after the fork call returns).
```

接著一則 user（`aos-agent say`）：

```
[aos] fork: you are a fork: a copy of the agent whose conversation is above, made when it called the fork tool. You have its definition, its settings and its conversation, so you know what it knew. The original is waiting for you and will see only your final reply, not your steps.
Your task: <goal>
Do only this task (use your tools if you need them). When it is done, reply with the conclusion only: what the task asks you to bring back, not the steps you took. At most 600 characters. You cannot fork again (fork fails with DepthExceeded in a fork); do the work yourself.
```

## 帶與不帶

| 東西 | 帶？ | 為什麼 |
|---|---|---|
| 定義 | 同一份（表上我那列的 `def`） | 「複製自己」 |
| history（定義宣告的那份） | 帶，整份照行抄＋補 tool 訊息 | 裁定「一律連對話複製」 |
| tools／llm／hooks／system 這隻自己那份（self_tools、self_llm、self_hook、self_system 改的） | 帶（相對路徑換算） | 「用 self_* 改過的東西」 |
| `goal.json` | 不帶，也不替分身寫 | 見代定 5 |
| todo（`tools/todo/todo.json`） | 不帶 | 工具小格是各工具自己的帳；history 裡叫過 todo 的結果分身看得到 |
| 其他工具小格（subagent 的帳、do_task／fork 的紀錄、observed 抄本） | 不帶 | 分身不該以為原本那隻的子 agent 是它的（subagent rm 會殺錯人） |
| hook 狀態（`hooks/<名>/on_clock.json`、mail_notify 的 `notified.json`、`hook_tools_seen.json`） | 不帶 | 分身是新起的：on_clock 本來就從頭算；信箱是空的、沒東西可通知；tool_added 第一次只記不發 |
| queue、信箱、`think/`、`stage.txt`、`cooldown.json`、`observed.jsonl`、`history_removed.jsonl`、stack 根的 `subagents.json`（配額覆蓋層） | 不帶 | 身體的執行狀態與帳；`stage.txt` 帶了會讓分身從 act 重跑那次 fork |

## 代定（每條可翻案）

1. **包**：跟 subagent 同包（`lib/packs/subagent.json`，包檔隊長加）；不算 subagent 的配額。
2. **參數**：只留 goal、max_chars、timeout_s／timeout_cycles、keep。`context` 拿掉（整段對話都在）、`tools`／`model` 拿掉（分身就是自己；要別的腦或工具組用 subagent）。
3. **keep 保留**：除錯、追問用；分身答完 ctl stop，不佔 loop。
4. **深度 1 層**，變數 `AOS_FORK_DEPTH`（不沿用 `AOS_DO_TASK_*`）：分身的分身只是同一段對話再抄一次，而且每層都抄整份 history。
5. **不寫分身的 goal.json、也不帶原本那隻的**：listen 拿到第一則回答就收，goal 提醒只會在結論「之後」才來（idle 看到沒 tool_calls 的 assistant＋active goal 就丟），只會白催、多燒一輪；帶原本的 goal 則會被催去做原本那隻的事。
6. **分身名** `f-<父名前 32 字>-<UTC 毫秒>-<4 hex>`；**stack 位置** `<daemon>/procs/<分身名>/`（同 `ctl add` 不給 `--stack` 時的預設位置；用相對路徑傳 `--stack`，表上存相對 daemon）。ctl add 被拒＝刪掉抄好的 stack 與紀錄；daemon 沒回（DaemonMissing／DaemonFailed）＝留著記 failed，下一次對帳收。
7. **補 tool 訊息**：最後一則 assistant 裡第一個沒回的＝這次 fork（認順序不認名字：工具不知道自己登記成什麼名）。
8. **eca 怎麼擋**：判 history 形狀（同 do_task、同一個代號 `BodyUnsupported`），不判定義（定義長什麼樣不是 fork 該知道的；不是從 act 叫的〔人手動 aos-tools call〕也一起擋下）。
9. **aos 註記種類** `fork` 登記進 `NOTE_KINDS`；fork_copy 在 lib、不 import py，自己拼同一格式（同 goal_state、mail_notify）。
10. **錯誤代號**：新增用到 `HistoryMissing`（定義沒宣告 history）、`InterfaceMissing`／`InterfaceBad`（宣告讀不懂）、`BodyUnsupported`，其餘同 do_task；`FromMissing`、`ToolMissing` 不再有。

## 待裁（可直接貼進選項框）

1. 分身要不要寫一份 goal.json？ — A 不寫，拿第一則回答就收（現狀，推薦）／B 寫，等分身自己 goal done 才收結論（較穩但要分身會叫 goal）／C 寫，收到結論後由 fork 從外面標 done。
2. todo 清單帶不帶？ — A 不帶（現狀，推薦）／B 抄一份 `tools/todo/todo.json` 給分身。
3. 深度上限？ — A 1 層，分身不能再分身（現狀，推薦）／B 2 層（同舊 do_task）。

## 測試（WSL、這份 clone、`lineK_env.sh`）

- `lib/agent/fork/tests/test_fork.py`：12 支綠——參數錯 7 種、`from`／`tools`／`model`／`context` 都是 `ArgumentsBad`、深度（`AOS_FORK_DEPTH` 1、7＝`DepthExceeded`，-1、two＝`ArgumentsBad`，`AOS_DO_TASK_DEPTH` 不算）、DaemonMissing／StackMissing／WsMissing、`--help`、收尾次序（say→listen→抄帳→stop 或 rm）、開場文；fork_copy：補 tool 訊息（第一個是 OWN、其餘 OTHER、已回的跳過）、只抄宣告的檔且相對路徑換算對、指示詞與絕對路徑不動、goal.json／stage.txt／工具小格不抄、HistoryMissing／InterfaceMissing／InterfaceBad、eca 形狀的 history（空、只有文字、工具都回了）＝BodyUnsupported 且錯誤指到 subagent、什麼都沒寫。
- `templates/tests/agent-fsm/test_fork.py`：1 支綠（真 daemon＋真 llm kernel＋`llm_fake` 劇本，劇本用另一位施工員加的 `when`）——兩隻（pat 不 keep、kim keep）各先聽到暗號 `plum-42`、self 改過 system，再叫 fork：分身的 history 頭一則就是暗號、第 5 則是補的 tool 訊息、第 6 則是開場；分身再叫 fork＝`DepthExceeded`（帳上 code 1）；分身答「The password is plum-42.」＝父那則 tool 的內容；父 history 只有 6 則（user、assistant、user、assistant〔叫 fork〕、tool〔結論〕、assistant），沒有開場、DepthExceeded；分身的 `think/request.json` 裡有暗號（腦看得到）；system.txt 跟過去；沒有 goal.json；pat 的分身收掉、kim 的留著且 `stopped`、結論尾 `details: procs/f-kim-…/`；父的 observed 有分身的帳。
- `cmd/aos-eca/tests` 整夾 68 綠（eca 的 fork 改動拿掉後回到原樣）、`lib/agent/tests` 21 綠。
- knowledge_check：新節點 `aos/agents/fork.json`；暫時補上 index 三格（agents/_index.json、agents.json 的 `_index` 與 `$ref`、subagent 包登記）跑＝fork 相關 0 錯誤 0 提醒，跑完還原。

## 沒驗到的

- 真腦沒跑（回家測，fsm 接真腦）。
- ctl add 被拒時刪 stack、daemon 沒回時記 failed 的那兩條沒測；對帳、租約、失敗 gc 是 do_task 原樣搬來的，沒另外測。
- eca 被擋的那條只在單元測試（假 history）驗過，沒有真的掛一隻 eca 去叫（範本會寫 `"fork": null`，正常看不到這支）。
- 沙箱（aos-sandbox）裡叫 fork：要 rw `<daemon>/procs/`（抄 stack 寫在那裡）與 ro 原本那隻的 stack，沒試。同一隻同時開兩個 fork 也沒試。

## 真腦驗證（回家測：fsm 接真腦；`. lineK_env.sh` 之後，在有 llm kernel 的那台 daemon 的工作區）

```sh
aos-agent ctl add --name fk1 --ws . "$AOS_HOME/templates/agent-fsm"
aos-agent tools -t fk1 add --name fork "$AOS_HOME/lib/agent/fork"     # 包還沒掛就先單加
aos-agent llm -t fk1 set model=luna
aos-agent say -t fk1 "The password is plum-42. Remember it."
aos-agent listen -t fk1 --timeout-s 300
aos-agent say -t fk1 "Call the fork tool once with goal 'Tell me the password I gave you earlier' and keep true. Then tell me exactly what it returned."
aos-agent listen -t fk1 --timeout-s 900
aos-agent history -t fk1 ls            # 該只看到 -> fork(...) 一則和一則 tool（結論＋details 行），沒有分身的過程
aos-agent ctl ls                       # f-fk1-… 在、stopped
aos-agent history -t f-fk1-<…> ls -a   # 分身：前面是 fk1 的整段、補的 tool 訊息、開場、它的回答
aos-agent ctl rm --purge f-fk1-<…>; aos-agent ctl rm fk1
```

## 要重建什麼

- 不用重建。新檔：叫 fork 那隻的工具小格 `tools/fork/children/`、`tools/fork/observed/`（工具小格，同 do_task 舊版）。
- 範本與試驗場的定義要看到 fork＝包裡加那格（隊長加）；`~/.cache/aos-mcp-aos/tools.json` 這類 tooldef 快取要重刷。
