# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-11 收工 公司頂層

1. **授權照舊**：公司機（Windows＋WSL Ubuntu）；頂層只交流與派工（普通 opus、簡單與雜活 sonnet，非雜活先通讀 wf/）；小題用選項框問；真腦在公司只用 eca（claude haiku、codex `gpt-6-luna`；codex 只對 aos 那組 MCP 工具免核准），fsm 真腦回家測。**push 每次都要使用者開口**：今天推了兩次——下午他說「推吧」推到 `23c9544d3`，收工他說「整理完就推」，推到本條所在的 commit。
2. **三份 clone**：WSL `~/repo/aos-tools`（捷徑與 pth 指它、試驗場用它）與 `~/repo/simple_tools/aos` 都在收工推上去的 HEAD，跟 origin/main 一樣。Windows `C:\code\mine\simple_tools\aos` 停在 `23c9544d3`，使用者說明天自己 `git pull`（頂層收工時會把那邊手寫的 `wf/HANDOFF.md` 還原，pull 才不會被擋）。Windows 本地另有舊分支 `wip/hub-step6` 和幾個過期的遠端記錄（GitHub 上實際只有 main），使用者說不動。
3. **今天進 main 的**（原話與裁定都在 [thinking 11-11](../proto8/thinking/2026-11/11/README.md)）：上午 `agents_children`→`subagent`、`aos-agent system`＋`self_system`、人的信箱預設 `~/.aos/stack`、codex 接得上 aos 工具、aos-loop `on_start`／`on_stop`、hook 事件 `after_start`／`after_stop`／`on_clock`＋範本 `timer`；下午工具小格寫入才建、loop／fsm／daemon 自建 stack、`do_task`（start／end／status，只給 fsm）、`fork`（只給 fsm；「eca不給fork。」）、`grep`、`glob`、`todo`、`goal`、新信提醒 `mail_notify`、線 C 六題與積壓代定、旗標前後都收推到全部指令、gitignore-check 改標準。
4. **線 K 工作六已完成**（`2ac75177f`、`d0943e5d8`、`c44dac27c`、`882dc7fe5`、`9457e059f`）：do_task end 預設把期間別人的訊息一起摺掉（`keep_others: true` 才留；使用者「可選。預設清掉。」）；`goal.json`、`tools/todo/todo.json`、`tools/do_task/tasks.json` 進 git 分類表；睡著時新到的信醒來提醒一次；history 空也丟 goal、當開場題目；do_task 算 goal 進展但不耦合（「兩者不要耦合太深，就goal那邊稍微檢查一下history就好。」）；`aos-agent goal set` 文字比照 say 原樣收。全套 66 夾 1092 支，只紅既有 4 支（aos-agent `test_daemon_down` 2、box_check 2）。→ [goal 02](../proto8/thinking/2026-11/11/goal/02-裁定與施工結果.md)、[fork-and-do-task 02](../proto8/thinking/2026-11/11/fork-and-do-task/02-do_task.md)
5. **線 K 留下、明天要處理的三件**（使用者已知，還沒裁）：
   - (a) 五條代定：全新起來時信箱裡既有的信只記成已知、不提醒；`notified.json` 每次跑都寫；do_task 的選項放在 end、名叫 `keep_others`、巢狀時外層沒給就連裡層留下的一起摺；goal 找不到上次提醒、也找不到 summary 時不歸零；history 空時丟的那則也算一次提醒。
   - (b) gitignore 分類兩處漏列：fork 的 `tools/fork/children/<分身>/state` 沒列；分類表只有改名前的 `children.json`、沒有 `subagents.json`。
   - (c) 可能外洩（推的、沒實跑）：do_task end 與 self_history 的結果行會把 `history_removed.jsonl` 的絕對路徑寫進 history，而 history 是進 git 的。先查證，確認了要修。
6. **kernel 討論**（`97a06eb5a`，記錄在 [kernel/](../proto8/thinking/2026-11/11/kernel/README.md)）：只釐清概念，**沒有排任何施工**、沒改程式與條文。kernel 是寄件人眼中的身分（請求寄到哪、哪裡就是 kernel），定義回到「資源管理＋排程」；一般 proc 與人都寄 `AOS_KERNEL`（沒設走 `AOS_DAEMON`，都沒設報錯），問腦走 `AOS_LLM_KERNEL`；鏈自然形成，信封共通、body 不設限。使用者最後說：「判官這東西...我覺得應該將其吸納進我們之後的kernel框架中。不過沒關係，今天釐清了概念，後續架構規劃上就很輕鬆了。」會過時的條文清單與日後清單在該夾 [03](../proto8/thinking/2026-11/11/kernel/03-過時清單與日後清單.md)。記錄核對時發現：`fork`、`subagent` 在 `AOS_DAEMON` 沒設時會報 `DaemonMissing`，即使設了 `AOS_KERNEL`。
7. **只到設計、沒施工**：接外部 MCP（設計與裁定在 [new-tools](../proto8/thinking/2026-11/11/new-tools/) 03，使用者說「明天」做第一階段）；i18n（遠期構想，[i18n](../proto8/thinking/2026-11/11/i18n.md)）；two-machines 剩 8 項（「之後吧」）；大修材料不用同步；kernel 框架。
8. **試驗場** `~/code/playground`：停著，還是 13:06 那版（36 支，沒有 grep／glob／todo／goal／fork／新 do_task），備份 `~/code/playground.bak-1111-1306`；今天沒重刷。下次重刷時劇本假腦的 do_task 那步要改成 start → 做事 → end。
9. **回家要測／要做**（都在 [WAIT_USER](WAIT_USER.md)）：fsm 真腦跑 goal／fork／do_task／mail_notify／self_system／timer 跑一晚；家機 pull 前先移走沒進 git 的 `proto8/cmd/aos-mailbox/bin/aos-mailbox`；家機試驗場重刷；`/tmp/lineI`、`/tmp/lineJ`、`/tmp/lineK-*`、`/tmp/aos-*` 殘留要使用者自己刪；WSL `~/repo/aos-tools` 兩個未追蹤的舊建置產物 `proto8/impls/aos-kernel-llm/`、`proto8/impls/aos-gate/` 可刪、待使用者點頭。已知問題：do_task 在摺疊中途被砍，留下的訊息會重複一次。

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

## 2026-11-10 下午 公司頂層（compact 前）

1. **授權與狀態**：公司電腦（Windows 桌面 app；施工一律在 WSL `~/repo/aos-tools`，這台 Windows 沒 python）。**今天不 push，下班前統一 push**（使用者早上先說隨便 push、隨即改口）；子 agent 也不准 push。普通工作 opus、雜活 sonnet、規劃可開 fable（使用者 11-10「好，可以開fable agent」）；頂層只交流。使用者：「不要因為太敢就省略東西，時間沒有緊急到那樣。」（不砍範圍、不跳驗收，做不完跨天）；今天的裁定多是選項框快裁（「主要靠直覺…大修的時候再來處理」）。arcagi 停線、等大修完再續。
   - **兩份 clone 的同步**：所有施工 commit 都在 WSL 那份本地 main（領先 origin 20 個以上，含早上 Windows 這份的 `67a0d67d1`、`7963f5d74`）；Windows 這份只多**本檔這段未 commit 的改動**。下班前：整理 WSL 那份 `git log origin/main..main`（各 commit 新檔有無 >1 MB／二進位；prefix-fixes 隊長回報過到 `233514b4a` 為止都沒有）給使用者看→他點頭後從 WSL push→Windows 這份 `git checkout wf/HANDOFF.md` 之前先把這段搬進 WSL 那份 commit，再 pull。
2. **今天做完的（都在 WSL 本地 main）**：
   - **prefix-fixes**（桌面問題清單 207 列分桶；直接修 61 列做了 60）：線 1～5、線 6 `procs_ctl_mailbox`→`procs_requests`、坑-52 PDEATHSIG 全套＋eca 的 CLI、坑-74 等腦 10 分鐘提醒、新子命令 `aos-daemon-ctl shutdown`、`copy-out`（坑-73）與 `.aos-proto8` 錨點（坑-92；11-10 下午已拔）、收尾修 `caf9a32f7`。試驗場 `~/code/playground` 已刷新（備份 `.bak-1110`），桌面大修材料同步到 `6efb876fe`（220 列）。→ `proto8/thinking/2026-11/10/prefix-fixes/`（04 施工結果）。**沒修、等使用者說要不要**：adopt 接回的列失敗後直接下表看不到原因；stop→sleep→start 後新 loop 照做舊 stop 馬上退出；「ctl 信箱」說法要不要照新命名原則改。
   - **sweeper 清道夫**：`_sweeper` 列（每台 daemon 自己掛、只管自己）、`aos-daemon-ctl sweep [--purge] [--dry-run]`、保留期預設 7 天、判官範本 `max_running` 5。→ `thinking/2026-11/10/sweeper/`。沙箱帳號沒實跑。
   - **two-machines 圖紙**（fable，`2d5d61905`）：之後被使用者大幅改向，見下。
3. **還在跑：two-machines 施工隊長（opus，ListAgents 找「two-machines 施工隊長」）**。圖紙原是「專用 image repo＋`aos-image freeze/thaw`」，使用者下午連續改向，**以這些原話為準**（都已轉給它）：
   - 「換台還要特別跑東西...，我原本預期他就是cp過去，起daemon她就自動繼續了。頂多就是各種路徑(ws,知識庫)和環境變數準備好就好。」→ 不可有換台必跑的步驟，零件自己認出殘留並自癒。
   - 指到外面的路徑：「使用者自己準備。要用相對位置、絕對位置、環境變數指定都可」「兩台各自設一次...不要限制只設一次」→ 三種寫法都收、每次用到才解、不固化；`.aos-proto8` 錨點 11-10 下午使用者裁定整個拔掉（「怎麼還是有.aos-proto8 ?」「那就拔掉，可以動程式」）：`copy-out --proto8` 只剩 env（預設）／relative／absolute，`--relink`、`aos-tools add --anchor` 已拔；換台不跑任何指令，env 寫法每台設 `AOS_HOME（11-10 傍晚由 AOS_PROTO8 改名）`。
   - 目標用法：「我在C:/code/mine/something，建立defs/, stacks/，剩下就是something自身的東西。git clone下來之後直接aos-exec --stack stacks/daemon defs」；下班前對根下 **`shutdown`**（他先說 sleep、更正「喔不是，就shutdown」）再 `git push`。stacks 跟著專案自己的 repo（正常歷史，aos 不可 force push／代 commit）——「stacks 進專案 repo 正常歷史」我先這樣假設，未正式裁。
   - 「gitignore要弄好」（獨立交付項：實跑分類、兩方向都對、自動檢查釘住）。
   - 「要自動繼續的話，有需要的話可以加上boot指令」（只有零件自癒做不到時才加，與 shutdown 成對）。
   - 「aos image...拿掉吧。」；跨專案：`another/` 放可被引用的 def、`llms/` 是最終的 llm kernel（獨立起停）；「llms我可能會用環境變數指定。然後如果llms那邊我沒開aos daemon，那就是我自己的問題，但我也希望他不要搞壞」。
   - 位置：「喔喔，其實是/mnt/c」「或者說，WSL能訪問到的都可能是目標」→ /mnt/c 實測最優先（結果要先短訊回頂層、有硬傷立刻告訴使用者），寫成「依賴哪些檔案系統特性」的通則，能不依賴就改、做不到就啟動時探測並清楚拒絕。
   - 早上選項框已裁、仍有效的：eca 換台用 aos 紀錄重開對話；失敗的信掉那封＋自動重起；加 `--auto-restart`；eca 失敗後冷卻只拿一封試；金鑰只給問腦那支行程；知識庫編輯不加版本檢查；不做金鑰掃描；知識庫＝「就是一個資料夾…不要與其耦合」，工具層可假設 git 與鎖。
   - **等它回的**：圖紙對照表（照舊／要改／作廢）、/mnt/c 實測短訊、要不要 `boot`（清單＋指令長相）、gitignore 分類結果、T7 給使用者親手做的真機驗證步驟（真 claude，約 15 分鐘）。
4. **新條號**：無新編號；條文加註在各線結果檔（N-17 例外二、N-28、N-67、C-54 R14 的 11-10 註等）。使用者今天的命名原則：「mailbox，他是底層的aos post機制…應該是用承載的機制作命名」；隨想「有序無序感覺也沒差」未處理（agent 的 `queue/` 不動）。
5. **還沒問／沒回的小事**：未追蹤殘留夾（Windows 這份 `proto8/impls/aos-schema/`、`inst/`；WSL 另有 `aos-gate/`、`aos-kernel-llm/`）刪不刪；上面第 2 點三件沒修的要不要修。
6. **之後的裁定（午後到傍晚，逐字見 [two-machines README 午後方向改變](../proto8/thinking/2026-11/10/two-machines/README.md#午後方向改變逐字)）**：
   - 隊長兩題：「1.可以。2.可以，這個就隨意，不要去假設或限制，然後defs/, stacks/都只是舉例，搞不好他會是其他名字，乃至於分散於defs_1, defs_2, stacks/root，或其中一些放在其他外部資料夾。」（1＝准動 C++；2＝stacks 進不進專案 repo 隨使用者——上面第 3 點「先這樣假設」已由這句定掉）
   - 「他有需要的話可以派fable」；六項快修照勾（stop→sleep→start、設計-56、設計-52、open-14、坑-76、坑-102，已做），留大修：設計-44、adopt 接回失敗看不到原因。
   - 「總之我五點下班，下班前全部弄好。剩下的明天再做」
   - kernel 不在＝印 warning、原地等，不論有沒有 auto-restart，kernel 回錯照舊停；kernel 排隊信樣板與指南不擋、照帶：「都按照推薦」。
   - boot 不做（起根本身就會叫醒睡下的列）。施工九個 commit 到 `875aff2b2`、文件未 commit；續行點與明天清單見 [13](../proto8/thinking/2026-11/10/two-machines/13-施工結果/03-不同之處與留給明天.md#留給明天大修)。

7. **下午後段（16:00 前後，two-machines 隊長補）**：11-10 下午後段：aos-tools 改版已完成並 push（`$override` 覆蓋檔、`--replace`、env_file、快取搬 stack、C-85、C-86）；cli-sweep 掃描（[報告](../proto8/thinking/2026-11/10/cli-sweep/README.md)，未施工）使用者已答：Q2＝A 分工照舊、差別收到最少；Q3＝「兩支都留 stack，要刪另外說」即 `aos-agent ctl rm` 預設留 stack、刪加 `--purge`；Q4＝A 已停再停兩支都算成功；Q5＝A 根範本自己清掉繼承來的 `AOS_DAEMON`；Q6＝A 不動、對照表放 help 第一屏；Q1 自填兩次，重擬版原話「旗標也可以寫在子命令前面，但這樣就等同於aos-yyy zzz [flags] XXX [flags] QQQ。因為zzz有個意義：aos-yyy-zzz和aos-yyy zzz相等。所以其實都可以。」（頂層轉述：每層「節點 [旗標] 下一個位置參數」遞迴、兩種寫法都收＝09 選項 A；明天施工前再確認）；09 三個讀法「No preference」＝照推薦、補進 P-44（含第 6 行過時句）；Q7＝`copy-out --template 名 目的地`、沒給報錯、加 `--list`（help 第一句白話講它是「把範本抄出去開新 agent／新根」）；Q8＝`aos-agent tools add [--name 名] 路徑`、補 `--envs`／`--env-file`、跟 aos-tools add 一致（[README](../proto8/thinking/2026-11/10/cli-sweep/README.md)）。two-machines B01 做了一半（`7c1791e6e`：`--ws-json`／`--stack-json`／`--path-json` 的 `$env` 寫法進表、每次起重解）。**明天順序**：B01 剩下（絕對路徑原樣存、`--*-json` 純字串原樣存，要動 aos-daemon 存表）→ cli-sweep 第一批 → aos-tools 的 lv6 連帶 → two-machines 其餘 15 條（[next_todo](../proto8/thinking/2026-11/10/two-machines/next_todo.json)）。以上都只記裁定、還沒施工。

8. **11-10 最後一小時（16:00～16:55）**：two-machines 隊長——B01 一半已 push（`7c1791e6e`），它把 `aos-daemon-ctl add` 打壞、`c2a6aa976` 修好已 push；cli-sweep Q4＝A（已停再停兩支都算成功，印 `名字: already 狀態`、退 0）`1d3ece5e5`；甲4、甲5 也做了（`624355ee5`：add 撞名＝InstanceExists、rm 不在表上＝ProcMissing、shutdown 印一句話），甲3 也做了（`afab03ad5`：ls 說 daemon 活著沒）；甲6、Q3、Q1、Q6 沒做；Q5 已裁不修（使用者「喔沒關係，root這東西本來使用者就要多注意一點。」，只在文件提醒起根前 `unset AOS_DAEMON`）（[10b](../proto8/thinking/2026-11/10/cli-sweep/10b-施工結果-兩支ctl.md)）。另一隊——cli-sweep Q7 `copy-out --template`（`7558433b7`）、`AOS_PROTO8` 改名 `AOS_HOME`（`3fe4c3e18`，使用者「AOS_PROTO8改成AOS_HOME，這樣之後大修改版，還可以直接換」）。調查 [templates-cp](../proto8/thinking/2026-11/10/templates-cp/README.md) 已寫完：範本改 AOS_HOME 寫法＋自帶 .env 後 `cp -r` 就能用、只 export `AOS_HOME`、lv1～4 不用改；使用者「copy-out能刪就刪」＝選項 A（範本全改、copy-out 整支刪、文件教 `cp -r`），三題快選都選推薦（範本拿掉 symlink 的 `tools/` 夾、`.env` 帶預設＋`AOS_HOME` 必填檢查、`copy_def.py` 一起拿掉、`agents new` 改單純整夾複製）——只記裁定、明天施工。**明天順序**：B01 剩下（絕對路徑原樣存、`--*-json` 純字串原樣存）→ templates-cp（刪 copy-out、範本改寫）→ cli-sweep 甲6、Q3、Q6、Q1 → aos-tools lv6 連帶 → two-machines 其餘 15 條。
