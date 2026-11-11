# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-11 晚 家機

1. **授權**：家機（Manjaro）。頂層只跟使用者交流，派 opus 隊長做事。**睡前 push**：頂層 23:10 前推，隊長不推。使用者今晚原話：「繼續跑，有問題就修」「隨便玩吧」。eca_bob 今晚花費上限合計 10 美金，是頂層代定。
2. **今晚做了什麼**（都在 [thinking 11-11 playground](../proto8/thinking/2026-11/11/playground/README.md) 02～04）：
   - 家機試驗場照線 K 版整份重建。
   - 三隻都能一行換模型。
   - 出廠 llm-kernel 補 terra，sol 換成 6.1（`c21947183`）。
   - 11 個模型配工具實測兩輪：[03](../proto8/thinking/2026-11/11/playground/03-模型配工具實測.md)、[04](../proto8/thinking/2026-11/11/playground/04-修與第二輪實測.md)。
   - 修了四件：knowledge_read 能指定 `root`（`55a1bce83`）、eca 範本拿掉 subagent 包（39→37 支，`10539f4ff`）、mailbox_send 寄給自己時錯誤訊息補自己的名字（`bb24ebba6`）、json_write 鍵包引號就剝掉照用（`6799c55ea` 先只給提示，`eb772bbdf` 改成照用）。
3. **使用者今晚的裁定**（原話在 04 開頭）：
   - 知識庫不給預設。
   - read 跟 write 一樣能指定 root。
   - do_task 摺掉後模型重做＝「自己承擔。本來就是這樣。」
   - eca 不給 subagent 相關工具。
   - codex 不念系統文字＝「喔」，不處理。
   - 線 K 五條代定認可（「沒啥好翻的，我覺得都OK」）。
   - knowledge 改回 memory：「目標是整套改回。」
4. **代定**：eca 留 def 包（agent_def、tools_def），見 04 § 修了什麼。
5. **要使用者裁的**（04 § 第二點裡沒做的、§ 第二輪發現、§ 第三輪）：
   - root 要不要也收檔案和 json 物件（`a.json#/x`）。
   - eca_cody 的唯讀沙盒讓 codex luna／terra 不敢用 aos 寫入工具：要改 `workspace-write`，還是在 system 裡加一句？
   - codex 自帶 goal 工具，跟 aos goal 撞名。
   - mailbox_send 的 `box` 能指到 agent 的 queue 資料夾。
   - fsm 沒有「同一個錯連發」的煞車：gemma 連撞二十幾次。
6. **試驗場**（`~/code/playground`）：
   - 樹在背景跑；fsm_ann 用 gemma、eca_bob 用 haiku、eca_cody 用 gpt-6-luna，對話都是空的；fsm 41 支、eca 37 支。
   - 怎麼起：`cd ~/code/playground && source env.sh && cd ws`，`aos-agent chat -t fsm_ann`。停：`aos-daemon-ctl -d ~/code/playground/.stack shutdown`。
   - proxy 已重起，4000 有 6.1 的 sol 和 terra。
7. **明天要做**：
   - knowledge 整套改回 memory。
   - 接外部 MCP 第一階段。
   - 線 K 剩兩件：gitignore 漏列（fork 的 children state、`subagents.json`）、`history_removed.jsonl` 絕對路徑可能外洩。
   - 公司 proxy 要加 6.1 條目。

## 2026-11-11 收工 公司頂層

1. **授權照舊**：公司機（Windows＋WSL Ubuntu）；頂層只交流與派工（普通 opus、簡單與雜活 sonnet，非雜活先通讀 wf/）；小題用選項框問；真腦在公司只用 eca（claude haiku、codex `gpt-6-luna`；codex 只對 aos 那組 MCP 工具免核准），fsm 真腦回家測。**push 每次都要使用者開口**：今天推了兩次——下午他說「推吧」推到 `23c9544d3`，收工他說「整理完就推」，推到本條所在的 commit。
2. **三份 clone**：WSL `~/repo/aos-tools`（捷徑與 pth 指它、試驗場用它）與 `~/repo/simple_tools/aos` 都在收工推上去的 HEAD，跟 origin/main 一樣。Windows `C:\code\mine\simple_tools\aos` 停在 `23c9544d3`，使用者說明天自己 `git pull`（頂層收工時會把那邊手寫的 `wf/HANDOFF.md` 還原，pull 才不會被擋）。Windows 本地另有舊分支 `wip/hub-step6` 和幾個過期的遠端記錄（GitHub 上實際只有 main），使用者說不動。
3. **今天進 main 的**（原話與裁定都在 [thinking 11-11](../proto8/thinking/2026-11/11/README.md)）：上午 `agents_children`→`subagent`、`aos-agent system`＋`self_system`、人的信箱預設 `~/.aos/stack`、codex 接得上 aos 工具、aos-loop `on_start`／`on_stop`、hook 事件 `after_start`／`after_stop`／`on_clock`＋範本 `timer`；下午工具小格寫入才建、loop／fsm／daemon 自建 stack、`do_task`（start／end／status，只給 fsm）、`fork`（只給 fsm；「eca不給fork。」）、`grep`、`glob`、`todo`、`goal`、新信提醒 `mail_notify`、線 C 六題與積壓代定、旗標前後都收推到全部指令、gitignore-check 改標準。
4. **線 K 工作六已完成**（`2ac75177f`、`d0943e5d8`、`c44dac27c`、`882dc7fe5`、`9457e059f`）：do_task end 預設把期間別人的訊息一起摺掉（`keep_others: true` 才留；使用者「可選。預設清掉。」）；`goal.json`、`tools/todo/todo.json`、`tools/do_task/tasks.json` 進 git 分類表；睡著時新到的信醒來提醒一次；history 空也丟 goal、當開場題目；do_task 算 goal 進展但不耦合（「兩者不要耦合太深，就goal那邊稍微檢查一下history就好。」）；`aos-agent goal set` 文字比照 say 原樣收。全套 66 夾 1092 支，只紅既有 4 支（aos-agent `test_daemon_down` 2、box_check 2）。→ [goal 02](../proto8/thinking/2026-11/11/goal/02-裁定與施工結果.md)、[fork-and-do-task 02](../proto8/thinking/2026-11/11/fork-and-do-task/02-do_task.md)
5. **線 K 留下、明天要處理的三件**（使用者已知，還沒裁）：
   - (a) ~~五條代定~~：11-11 晚使用者已認可（「沒啥好翻的，我覺得都OK」）。
   - (b) gitignore 分類兩處漏列：fork 的 `tools/fork/children/<分身>/state` 沒列；分類表只有改名前的 `children.json`、沒有 `subagents.json`。
   - (c) 可能外洩（推的、沒實跑）：do_task end 與 self_history 的結果行會把 `history_removed.jsonl` 的絕對路徑寫進 history，而 history 是進 git 的。先查證，確認了要修。
6. **kernel 討論**（`97a06eb5a`，記錄在 [kernel/](../proto8/thinking/2026-11/11/kernel/README.md)）：只釐清概念，**沒有排任何施工**、沒改程式與條文。kernel 是寄件人眼中的身分（請求寄到哪、哪裡就是 kernel），定義回到「資源管理＋排程」；一般 proc 與人都寄 `AOS_KERNEL`（沒設走 `AOS_DAEMON`，都沒設報錯），問腦走 `AOS_LLM_KERNEL`；鏈自然形成，信封共通、body 不設限。使用者最後說：「判官這東西...我覺得應該將其吸納進我們之後的kernel框架中。不過沒關係，今天釐清了概念，後續架構規劃上就很輕鬆了。」會過時的條文清單與日後清單在該夾 [03](../proto8/thinking/2026-11/11/kernel/03-過時清單與日後清單.md)。記錄核對時發現：`fork`、`subagent` 在 `AOS_DAEMON` 沒設時會報 `DaemonMissing`，即使設了 `AOS_KERNEL`。
7. **只到設計、沒施工**：接外部 MCP（設計與裁定在 [new-tools](../proto8/thinking/2026-11/11/new-tools/) 03，使用者說「明天」做第一階段）；i18n（遠期構想，[i18n](../proto8/thinking/2026-11/11/i18n.md)）；two-machines 剩 8 項（「之後吧」）；大修材料不用同步；kernel 框架。
8. **試驗場**（家機那台 11-11 晚已照線 K 版重建、樹在跑，見 [playground 02](../proto8/thinking/2026-11/11/playground/02-家機刷新與驗收.md)；以下是公司那台）`~/code/playground`：停著，還是 13:06 那版（36 支，沒有 grep／glob／todo／goal／fork／新 do_task），備份 `~/code/playground.bak-1111-1306`；今天沒重刷。下次重刷時劇本假腦的 do_task 那步要改成 start → 做事 → end。
9. **回家要測／要做**（都在 [WAIT_USER](WAIT_USER.md)）：fsm 真腦跑 goal／fork／do_task／mail_notify／self_system／timer 跑一晚；（家機 aos-mailbox 原件、試驗場重刷 11-11 晚都已處理）；`/tmp/lineI`、`/tmp/lineJ`、`/tmp/lineK-*`、`/tmp/aos-*` 殘留要使用者自己刪；WSL `~/repo/aos-tools` 兩個未追蹤的舊建置產物 `proto8/impls/aos-kernel-llm/`、`proto8/impls/aos-gate/` 可刪、待使用者點頭。已知問題：do_task 在摺疊中途被砍，留下的訊息會重複一次。

## 2026-11-10 深夜 家機總整合（收工）

1. **授權**：家機（Manjaro）、今晚隨意 push（只有 main）；子 agent 普通 opus、雜活 sonnet；eca 一律 haiku。不動 `~/code/playground`（使用者的樹可能開著）、`~/code/playground-ak5`、repo 外的檔、`impl_cpp/`。使用者最後一句：「弄一弄，按照wf/規矩整理收拾，push上去後，我就要關機睡覺了」。
2. **各線狀態**：今晚七條線＋使用者回來後的四批裁定（[tonight-rulings](../proto8/thinking/2026-11/10/tonight-rulings/README.md)）、tool-packs、tools-def 全部施工完進 main；兩範本都十一包 34 支；C++ build 過、全套 Python 測試 51 夾 808 支綠；最後一輪整棵實跑見 [tonight/04](../proto8/thinking/2026-11/10/tonight/04-最後一輪整合驗收.md)（假腦 34 支全過、修 `ctl state` hooks 舊鍵 `d4ae3fc37`；gemma 只補驗一半、eca haiku 沒跑，續行點在 04）；怎麼玩 [tonight](../proto8/thinking/2026-11/10/tonight/README.md)。
3. **代定清單位置**：[self-tools README § 代定](../proto8/thinking/2026-11/10/self-tools/README.md#代定)、[self-tools 05](../proto8/thinking/2026-11/10/self-tools/05-llm設定改名與ls.md)；[json-memory 05](../proto8/thinking/2026-11/10/json-memory/05-步驟與代定.md#代定清單可翻案)；[self-family 01](../proto8/thinking/2026-11/10/self-family/01-施工結果.md)、[03](../proto8/thinking/2026-11/10/self-family/03-self_state與self_ctl施工結果.md)；[hook 01 圖紙](../proto8/thinking/2026-11/10/self-family/hook/01-圖紙.md)、[hook 02](../proto8/thinking/2026-11/10/self-family/hook/02-施工結果.md)；[agents-split README](../proto8/thinking/2026-11/10/agents-split/README.md)（15 條）；[mailbox 01](../proto8/thinking/2026-11/10/mailbox/01-設計.md)；[clock-letters README](../proto8/thinking/2026-11/10/clock-letters/README.md)；[templates-cp 05](../proto8/thinking/2026-11/10/templates-cp/05-施工結果.md)；[tool-packs 01](../proto8/thinking/2026-11/10/tool-packs/01-施工結果.md)、[02](../proto8/thinking/2026-11/10/tool-packs/02-memory-read施工結果.md)；[tools-def](../proto8/thinking/2026-11/10/tools-def/README.md)（01／02）；[tonight-rulings 05](../proto8/thinking/2026-11/10/tonight-rulings/05-knowledge改名.md)、[06](../proto8/thinking/2026-11/10/tonight-rulings/06-列表長短四項.md)；總整合自己的：eca-claude `_metainfo` 的 `cost.time_ms: 60000`、知識庫新開 `mailbox.json`／`clock.json`／`cli/hook.json`／`cli/mailbox.json`、2 KB 一段的上限這次沒拆（self_hook、me 簡介、cli/agent 略超）。
4. **今晚所有改名對照**（proto8 不留舊名、不做相容；舊定義重抄範本）：

   | 舊 | 新 |
   |---|---|
   | `memory`／`memory_read`、`memory_write`、`memory_export`、`memory_sync` | `knowledge_read`、`knowledge_write`、`knowledge_export`、`knowledge_sync` |
   | `memory_fs.py`、包 `lib/packs/memory.json`、`_memory.json` | `knowledge_fs.py`、`lib/packs/knowledge.json`、`_knowledge.json` |
   | `AOS_MEMORY`、`--memory`（brain.py／aos-mcp）、`MemoryMissing`／`MemoryBad` | `AOS_KNOWLEDGE`、`--knowledge`、`KnowledgeMissing`／`KnowledgeBad` |
   | `AOS_MY_STACK` | `AOS_LINUX_USER_STACK` |
   | `wall_clock`、`bash`、`json_edit` | `peek_now_time`、`shell`、`json_write` |
   | 舊 `agents` 工具、`agents.json` | `agents_children`／`agents_ctl`／`agent_def`、`children.json` |
   | `agents_children`（11-11 早，[subagent-rename](../proto8/thinking/2026-11/11/subagent-rename.md)） | `subagent`（記帳檔 `tools/subagent/children.json`；包名 `children` 照舊〔11-11 稍後也改，見下一列〕） |
   | `subagent` 周邊的 children 系（11-11 稍後，使用者「隊長那串...一起改吧」，[subagent-rename](../proto8/thinking/2026-11/11/subagent-rename.md#11-11-稍後周邊一起改成-subagent-系)）：包 `lib/packs/children.json`、配額檔 `children.json`、`max_children`、記帳檔 `tools/subagent/children.json`、`ChildSlotMissing`／`ChildUnknown`／`ChildMissing`／`ChildQueued`、輸出 `children N/MAX`、ctl state 類別 `children` | `lib/packs/subagent.json`（包名 subagent）、`subagents.json`、`max_subagents`、`tools/subagent/subagents.json`、`SubagentSlotMissing`／`SubagentUnknown`／`SubagentMissing`／`SubagentQueued`、`subagents N/MAX`、類別 `subagents`（`agents_ctl`、`agent_def` 不動） |
   | 知識庫節點 `aos/cli/grow_screen.json`；knowledge_write 範本預設指出廠庫（11-11 線 C，[knowledge-fix](../proto8/thinking/2026-11/11/knowledge-fix/README.md)） | `aos/cli/grow.json`（ECA 畫面併進 `cli/eca.json`）；knowledge_write 不給預設、呼叫給 `root` 或 `AOS_KNOWLEDGE`，都沒有＝`KnowledgeMissing`；thought 進 gadgets，兩範本 36 支 |
   | 工具 `thought`（`lib/agent/thought`、`AOS_THOUGHT_FROM`／`AOS_THOUGHT_DEPTH`、`aos/agents/thought.json`、沙箱例子 `thought-boxed`）；知識庫 `aos/tools.json`（11-11 線 I，[do-task-rename](../proto8/thinking/2026-11/11/do-task-rename.md)、[knowledge-fix 03](../proto8/thinking/2026-11/11/knowledge-fix/03-六題裁定與施工.md)） | `do_task`（`lib/agent/do_task`、`AOS_DO_TASK_FROM`／`AOS_DO_TASK_DEPTH`、`aos/agents/do_task.json`、`do-task-boxed`；沒給 from＝呼叫者自己的定義）；`aos/tools_def.json` |
   | `llm.json` 的 `endpoint` | `model` |
   | hook `on`／`exec`／`match`／`change`／`wait`；事件 `tool_after` 這類 | `event`／`handler`／`condition`／`intercept`（預設開）／`async`；`before_queue`、`after_queue`、`before_tool`、`after_tool` |
   | `aos-tools ls -b` | 拿掉（`ls` 預設就是短版，`-l` 長版） |

5. **試驗場狀態**：`~/code/playground` 是 22:15 刷的（備份 `.bak-1110-2215`），停在改名與列表短版之前——`self_tools ls` 會 FlagUnknown、litellm 要 `export LITELLM_KEY=sk-none`、定義指舊名 `memory_*`。刷新腳本 [tonight/03](../proto8/thinking/2026-11/10/tonight/03-試驗場刷新.md) 已對上最終狀態、22:51 在新複本上跑過（兩隻 34 支、gemma 叫 knowledge_read 對）；**補刷原件等使用者**（WAIT_USER 第一條）。
6. **還待裁**：
   - ~~小模型寫不出 `$` 開頭的鍵~~（11-11 已裁：`$` 鍵不動）。
   - ~~act 附給腦的 stderr 尾巴~~（11-11 已裁：維持）。
   - ~~hook 三題~~（11-11 已裁）：after_queue 晾著的信「不補」；CONVENTION「先不寫」；事件選「起來與停下」，之後又加了照時鐘觸發的 `on_clock`（「hook就可以添加一個類型，就是loop每次exec前和exec後……」），施工見 [clock-hook](../proto8/thinking/2026-11/11/clock-hook/README.md)。
   - ~~mailbox：人的預設 stack 是不是就 `~/.stack`。~~ **11-11 已裁**：`~/.aos/stack`（使用者「改成帶 aos 字樣的位置」→「~/.aos/stack」，`09709c6ac`）。
   - ~~clock 殘留~~（11-11 已裁：「交給自檢吧。如果要順手清的話，就是aos-agent ctl rm與另一個功能有耦合了。」；之後改向成 hook 的 `on_clock`，時鐘寄信那組「啊，不要拿掉好了，先留著」原樣不動）。
   - `agents_ctl` 能 rm 別人帳上的子。
   - tools_def「之後可加」的幾項（[tools-def](../proto8/thinking/2026-11/10/tools-def/README.md)）。
7. **WAIT_USER 新加／改**：試驗場補刷、`~/.cache/aos-mcp-aos/tools.json` 跟上改名（照抄 sed 一行）、eca 信任選單要手動信任一次、hook 線 eca haiku 真對話（agent 不代跑）。
