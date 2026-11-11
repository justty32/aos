# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

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
   | `agents_children`（11-11 早，[subagent-rename](../proto8/thinking/2026-11/11/subagent-rename.md)） | `subagent`（記帳檔 `tools/subagent/children.json`；包名 `children` 照舊） |
   | `llm.json` 的 `endpoint` | `model` |
   | hook `on`／`exec`／`match`／`change`／`wait`；事件 `tool_after` 這類 | `event`／`handler`／`condition`／`intercept`（預設開）／`async`；`before_queue`、`after_queue`、`before_tool`、`after_tool` |
   | `aos-tools ls -b` | 拿掉（`ls` 預設就是短版，`-l` 長版） |

5. **試驗場狀態**：`~/code/playground` 是 22:15 刷的（備份 `.bak-1110-2215`），停在改名與列表短版之前——`self_tools ls` 會 FlagUnknown、litellm 要 `export LITELLM_KEY=sk-none`、定義指舊名 `memory_*`。刷新腳本 [tonight/03](../proto8/thinking/2026-11/10/tonight/03-試驗場刷新.md) 已對上最終狀態、22:51 在新複本上跑過（兩隻 34 支、gemma 叫 knowledge_read 對）；**補刷原件等使用者**（WAIT_USER 第一條）。
6. **還待裁**：
   - 小模型寫不出 `$` 開頭的鍵：`self_tools`、`self_hook` 的 `path_json` 要不要給一條不用 `$` 鍵的路。
   - act 附給腦的 stderr 尾巴仍帶下層 CLI 句（C-52 例外的結構）。
   - hook：`after_queue` 停下後那封信晾著要不要補；要不要寫進 CONVENTION；要加哪些事件。
   - mailbox：人的預設 stack 是不是就 `~/.stack`。
   - clock：agent 被刪時它登記的項不會跟著清（每 100 cycle 自檢只清箱子已不在的）。
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

## 2026-11-09 深夜 23:2x 家機頂層（使用者要接 aos mcp 後重開／resume）

1. **授權與狀態**：同下一條（隨意 push、opus／sonnet 分工、/goal 到 11-10 06:20 當 arcagi 支援、安全邊界見下一條第 5 點）。使用者經 arcagi 轉達：「順便寄信給aos agent，跟他說我要給他接mcp。」→ 重開後 **先重掛 `wf/inbox/` Monitor**（腳本見 SESSION-LOG 續行點那條的寫法：每 5 秒比對頂層 *.md、另查 ~/arcagi-STOP），再讀 SESSION-LOG「今晚當 arcagi 支援」續行點。
2. **在辦**：arcagi 第四封（23:21 接 aos mcp／wf 轉知識庫）由 opus 回 DONE 中，信裡含 arcagi 與 aos 兩邊各自的 mcp 接法；回完原信與 23:23 PROGRESS 都歸 done。若重開時還沒看到 DONE（`ls ~/repo/arcagi/wf/inbox/ | grep aos-DONE`），就重派。
3. 無新條號。`proto8/thinking/2026-11/09/local-model-bench/` 是停掉評比的殘留未追蹤夾，等使用者說刪不刪。
4. **push 規矩改了（使用者 23:3x）**：「今晚都不要push，就在我睡醒前十分鐘準備好要push的東西(注意檔案大小)，我醒來後再push。」→ 今晚只 commit 到本地 main、不 push；06:10 前整理待 push 清單（`git log origin/main..main`、各 commit 新增檔大小、有無大檔／二進位），寫進 SESSION-LOG 續行點，等使用者醒來 push。

## 2026-11-09 深夜 23:xx 家機頂層（使用者開新 session）

1. **授權與狀態**：同下一條（隨意 push、opus／sonnet 分工、只用 e4b、不 load/unload、顯卡跑到 07:30）。使用者要開新 session。
2. **舊 session 留下的背景工作（新 session 先查還活著沒）**：
   - soak 長跑：腳本 `/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/74d55541-5004-44aa-b8d6-5fec53a393a2/scratchpad/soak/soak.py`（23:0x 剛啟動）；派它的 opus 隊長跟舊 session 一起結束，**沒人收報告**。查 `pgrep -af soak.py`；活著就由新 session 等到早上收、寫 `proto8/thinking/2026-11/09/soak-1109/`；死了就看使用者要不要重派。試驗場備份 `~/code/playground.bak-1109soak`。
   - 本地模型評比：隊長在修 report.py 重跑，同樣隨舊 session 結束，產物看 `proto8/thinking/2026-11/09/local-model-bench/`（可能未 commit）。
   - arcagi：22:30 回 PROGRESS（`wf/inbox/20261109T2230-arcagi-PROGRESS.md`，未處理），N1 蠟模、N2 CUDA 跑到 06:45，07:30 前回 DONE；看板 `~/repo/arcagi/notes/rounds/gpu-night-1109/`。它是使用者自己的 session，不受影響。
   - 23:0x 實測：LM Studio 只載 e4b、閒置，GPU 7%／6 W——整夜負載還沒起來。
3. **已裁（新 session）**：使用者「amber_sword不用跑。差異也不用補。」新 session 曾派兩個 opus 接手 soak 與本地模型評比，22:4x 使用者改口「arcagi 那個 agent 才是主要的暖爐提供者，你這邊配合他，這兩件可以不用做了」→ 兩個 agent 停掉、soak driver 與試驗場 stack 收掉（Ctrl-C 根），已寄 PROGRESS 給 arcagi 說 e4b／GPU 全讓出；soak、評比都沒產報告、沒 commit
4. **新 session 的角色（使用者 22:5x）**：「你的用途主要是在arcagi agent那邊，如果他對aos體系有問題，或是想要參考過去thinking或一些東西，你就負責解答。除此之外，如果他有相關需求，你這邊也可以對aos相關資產進行修改與改進。」→ 頂層掛 Monitor 盯 `wf/inbox/` 新信（30 分到期要重掛），已寄 PROGRESS 告知 arcagi 怎麼找我；impl_cpp 核心仍是使用者親手寫、不代寫。使用者 22:5x：「你這邊，今晚就先仍用proto8的東西，大修這塊不急。」——今晚支援 arcagi 一律以 proto8 為準，impl_cpp 不動。
5. **使用者 22:58 下 /goal（到 06:20）安全邊界**：寫入只限 aos repo（impl_cpp 除外）與自己 scratchpad；不寫 ~/repo/arcagi（只寄信到它 wf/inbox/）、不寫 ~/code/playground-arc1；不 sudo、不裝套件、不改系統與 LM Studio／litellm 設定；不讀 ~/.ssh、keyring、瀏覽器資料、別專案金鑰；codex 明帶 -m 與 -s、不用 astra；~/arcagi-STOP 存在就停止派新工作；子 agent 交接書帶安全邊界段並原樣傳給孫 agent；一線一里程碑；同一分鐘同 STATUS 只寄一封；每次 commit 更新 SESSION-LOG 續行點並 push。無新條號。

## 2026-11-09 深夜 22:3x 家機頂層（compact 前）

1. **授權與狀態**：使用者在家、本 session 隨意 push；子 agent 普通 opus、雜活 sonnet，派前讀 wf 規矩（雜活除外）。使用者要睡了，要**顯卡跑整夜到明早 07:30**（天冷當暖爐，「不用降低負載」）。**LM Studio 一次只載一個模型照舊**（使用者 22:2x 選「照規矩，大家共用 e4b」）：只用 `google/gemma-4-e4b`；使用者自己開了 LM Studio 與 litellm proxy；他說要下載 qwen3.8 27B，今晚不評（16GB 塞不下、也違反一次一個）。
2. **今晚在跑的（背景子 agent，完成會通知頂層）**：
   - **soak 長跑**（opus 隊長）：家機試驗場 `~/code/playground` 真腦 e4b 三層整夜，注入 kill／sleep／poke／pause／SIGINT，取樣 RSS／fd／檔案大小；開跑前備份 `~/code/playground.bak-1109soak`；報告 `proto8/thinking/2026-11/09/soak-1109/`。
   - **本地模型評比**（opus 隊長）：今晚只評 e4b，題庫＋判準＋一鍵重跑腳本做紮實，其他模型待白天單獨測；報告 `proto8/thinking/2026-11/09/local-model-bench/`。
   - **arcagi**：已寄信 `~/repo/arcagi/wf/inbox/20261109T2228-aos-REQUEST.md`（使用者「兩個都試試看。cuda神經網路也是可以拿來符號邏輯，暴力搜索。」）：(1) 本地 e4b 大量鑄蠟模、比提示法擬合率；(2) CUDA 暴力搜尋雛形；S1 forbid 相依就一起。arcagi 的 agent 是使用者自己開的 session（可能要使用者叫它看信）。
   - **amber_sword**（`~/repo/narratives/amber_sword`，非 git repo、只能讀）：使用者提議「用 aos 知識庫去搞」，頂層誤當決定派了隊長、隨即停掉（沒寫任何檔）；**使用者還沒決定要不要今晚跑**。教訓：使用者說「不如…？」「幫我想想」是要討論，不是派工。
3. **白天的設計線**：使用者手寫大修，起點 repo 根 `impl_cpp/`（C++23、骨架取自 archive/aos-v1、`core/inst` 原封搬 v1，差異在 `impl_cpp/core/inst/差異.md` 待他決定補不補）。無新條號。使用者 22:3x 問「蠟模」是什麼（頂層已白話解釋）。

## 2026-11-09 晚 收工（家機 Manjaro）

1. **授權與狀態**：使用者在家、本 session 隨意 push；子 agent 普通派 opus、雜活派 sonnet，派前讀 wf 規矩。使用者累了、已收工。家機已跟上 11-09（impls 重建、install、試驗場改成只有根帶鐘，假腦自動驗過，`3670feaaa`）。
2. **設計**：使用者開始**親手大修**，起點 repo 根 [`impl_cpp/`](../impl_cpp/README.md)：骨架取自 `archive/aos-v1`、C++23（使用者先說 20、看到 v1 後改 23）、vcpkg（nlohmann-json、catch2）、Ninja preset debug／release／asan、`.vscode`；第一個零件 `core/inst` 照使用者「aos-inst 也從 aos-v1 拿」原封搬 v1 的 exec＋wire Inst 解析，跟現行 proto8 aos-inst 的差異攤在 `impl_cpp/core/inst/差異.md`，**補不補等使用者**。主角是使用者：agent 只搭環境、照吩咐搬，不替他寫核心。大修材料在家機桌面 `~/Desktop/aos-大修材料/`，第四批後 `proto8/` 沒改、免同步。
3. **新定條號與在跑的 agent**：無新條號；子 agent 都收了。
