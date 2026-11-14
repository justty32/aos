> 這份是蒐集員交回的原文（kb-1114，11-14）。路徑裡的家目錄已換成 ~，其餘逐字。

# ok-kb 蒐集：知識庫 cli/（含 parts/）與 tools/ 對程式逐檔查核

唯讀查核，2026-11-14。沒跑任何 `aos-*`、沒執行任何工具 `_entry`，全部靠讀原始碼。
路徑縮寫：R＝`~/repo/aos`，P＝`R/proto8`，K＝`P/knowledge/aos`。行號是工作樹當下的行號。
做法：我自己做檔案清單、index、packs 對照、`cli/parts/`；其餘頁分給 5 個唯讀子 agent 逐頁對碼，我抽查了其中最重的幾條（第 8、14、39、56 條親自看過程式行；第 3、4、5、53、54、80、81 條是我自己查的）。「把握：猜」＝沒讀到能證明的那一行。

## 一、檔案清單與大小（bytes）

超過 8000 的只有兩份：`cli/eca.json` 11344、`cli/daemon.json` 8300。

`K/cli/`：_description 824｜_index 3628｜agent 4222｜clock 1905｜**daemon 8300**｜**eca 11344**｜errors 2496｜feedback 1044｜flags 2957｜goal 1783｜grow 1133｜history 1539｜hook 2434｜mailbox 927｜mcp 1844｜mcp_import 5967｜safety 2076｜sandbox 3898｜sweeper 1098｜talk_settings 4219｜tool_env 1451｜tool_flags 733｜tools 3074

`K/cli/parts/`：_description 604｜daemon 1242｜directive 1397｜exec 937｜fsm 947｜json 2300｜llm 1043｜llm_kernel 2093｜lock 761｜loop 842｜post 1068

`K/tools/`：_description 188｜_index 5096｜copy 1317｜edit 1866｜glob 2510｜goal 3109｜grep 3379｜index_view 4435｜json_add 853｜json_del 454｜json_get 2405｜json_len 602｜json_ls 1141｜json_multi_get 1051｜json_multi_set 1591｜json_search 1033｜json_set 1945｜jsonx_add 517｜jsonx_del 715｜jsonx_get 983｜jsonx_ls 620｜jsonx_multi_get 909｜jsonx_multi_set 1172｜jsonx_search 741｜jsonx_set 2066｜ls 2224｜math 1288｜mkdir 869｜move 1396｜peek_clock 1260｜peek_now_time 443｜read 1394｜remove 1073｜run_python 2108｜shell 2286｜stat 1459｜todo 3356｜trash 1393｜view 2419｜write 1443

index 對照：
- `K/cli/_index.json`（23 鍵）：每個鍵都有檔（或夾 `parts`），每個檔都有鍵。沒問題。
- `K/tools/_index.json`（39 鍵）：每個鍵都有檔，每個檔都有鍵。沒問題。
- `K/cli/parts/`：沒有 `_index.json`（見第 3 條）。

## 二、發現（編號連續）

### cli/ 整體

1. **太長**｜`K/cli/eca.json`｜整頁 11344 bytes。各鍵：`_description` 298、`turn` 2951、`screen` 1822、`external_mcp` 2352、`cli_hooks` 2617、`screen_linger` 1203。｜證據：檔案大小。｜確定
2. **太長**｜`K/cli/daemon.json`｜整頁 8300 bytes。各鍵：`_description` 246、`add` 1457、`lifecycle` 728、`letters` 1533、`ls` 696、`shutdown` 595、`prune` 794、`sweep` 597、`cgroup` 1531。｜確定
3. **找不到**｜`K/cli/parts/`｜這夾沒有 `_index.json`，10 份頁（daemon、directive、exec、fsm、json、llm、llm_kernel、lock、loop、post）都沒有 index 鍵；只有上層 `cli/_index.json#/parts` 一句與夾內 `_description.json`。｜證據：`find K/cli/parts`。｜確定
4. **過時**｜`K/cli/_index.json#/parts`「…aos-directive, aos-llm, aos-llm-kernel」｜同夾的 `parts/llm_kernel.json` 寫「Before 2026-11-14 this was a C++ program named `aos-llm-kernel`」，現在是工具夾 `lib/aos/kernel_llm`；index 那句還叫舊名。｜證據：`P/lib/aos/kernel_llm/_entry:30`（`usage: kernel_llm [--enable-counters] KERNEL.json`）、`P/kernel/llm-kernel/daemon.json`（exec 指 `/lib/aos/kernel_llm`）。備註：`P/impls/aos-llm-kernel/` 原始碼夾還在 repo。｜確定
5. **找不到**｜`K/cli/`｜這些指令在 `K/cli/` 沒有自己的頁：`aos-comm`、`aos-json-view`、`aos-share`、`aos-tree-start`（整個 `K/` 都搜不到名字）；`aos-asuser` 只在 `sandbox.json` 被提到；`aos-mcp-launch` 只在 `eca.json` 被提到；C++ 的 `aos-inst` 沒有頁。｜證據：`P/cmd/*/bin/` 清單對 `grep -rl` K。｜確定

### cli/clock.json

6. **過時**｜`clock.json#/register`（全段只講 `--every`，「An entry fires when the new cycle number divides by its EVERY」）與 `#/_description`「sends letters every N cycles」｜程式 add 的排法四選一：`--every N`、`--after N`、`--at WHEN`、`--cron EXPR`；另有 `--by WHO`。牆鐘排法的信是 `[aos] clock: cycle N, due TIME (…). TEXT`；ls 第二欄可以是 `cycle N`、`at TIME`、`cron EXPR next TIME`。｜證據：`P/cmd/aos-clock-register/bin/aos-clock-register:173-199`；`P/py/aos_clock_register.py:29` `KINDS = ("every", "at_cycle", "at_time", "cron")`、`:162-187`。｜確定
7. **找不到**｜`clock.json`｜頁沒寫：aos-clock 的 `WriteFailed`、`FlagUnknown`、`LaunchFailed`、空檔算 0；aos-clock-register 的 `RegisterBad`、`WriteFailed`、`CommandUnknown`、`ClockBad`；`ls -j` 的鍵 `file`、`check_every`、`letters`；長名 `--clock`、`--daemon`；add 時鐘檔不在只是 warning。｜證據：`aos-clock:37,72-73,86`；`aos-clock-register:24,142,149,167-169,222-223,255,275`。｜確定

### cli/daemon.json

8. **跟程式對不上**｜`daemon.json#/prune`「…ctl files that are not JSON objects, stale process identities, and stopped reasons」｜程式不查 stale process identities，只查三樣：stack 不在、ctl 不是 JSON 物件或讀不了、stopped 且有 reason。｜證據：`P/py/daemon_ctl/table.py:162-186`（`inspect_row`）。｜確定
9. **跟程式對不上**｜`daemon.json#/cgroup`「use daemon configuration or proc request limits」＋`#/add`「`--limits` work as for `aos-agent ctl add`」｜`aos-daemon-ctl add --limits` 不收 `mem_total_mb`、`procs_total`（`ArgumentsBad unknown key`），daemon 本身才收。｜證據：`P/py/daemon_ctl/entry.py:151` `LIMIT_INTS = ("mem_mb", "cpu_s", "procs", "file_mb", "files")`、`:168`；`P/impls/aos-daemon/src/child/limits.cpp:33-34,93`。｜確定
10. **跟程式對不上**｜`daemon.json#/lifecycle`「Wrong pairs give `PhaseBad`」｜已在目標狀態不是 PhaseBad：印 `NAME: already X`、退 0、不寄信；sleep 也收 `stopping` 的列。｜證據：`P/py/daemon_ctl/ctl.py:49-53`；`aos-daemon-ctl:757-758`。｜確定
11. **跟程式對不上**｜`daemon.json#/add`「`--auto-restart` restarts it whenever it exits」｜連續 3 次起後 3 秒內退出就不再重起，列留 stopped 並寫 reason。｜證據：`P/impls/aos-daemon/src/daemon/tend.cpp:151-153`。｜確定
12. **找不到**｜`daemon.json`｜頁沒寫：add 的 `--def DEF`；短名 `-n -w -s`；add 撞名 `InstanceExists`、rm 沒那名 `ProcMissing`；prune 的 `--reply-to`、`--timeout-s`（預設 3）；sweep 的 `--min-bytes`、`--stop-grace-s`，`--purge` 不能跟 `--retention-days`／`--min-bytes`／`--stop-grace-s` 同給；pause／resume 只收 running 或 stuck；`CtlMissing`、`PokeFailed`、`StateMissing`、`StateBad`、`CtlRejected`；`ls -j` 的 `running` 鍵。｜證據：`aos-daemon-ctl:467-473,507,515-530,608,677,690-694`；`ctl.py:67-69,135`；`poke.py:19-96`。｜確定
13. **找不到**｜`daemon.json#/shutdown`「A stop already in progress stays stopped…if kill -9 interrupts shutdown…」與 `#/cgroup`「launch.json wrap is not implemented」「Adopted running rows do not read events」「Until subuid isolation is implemented…」｜沒讀到能證明或否定的程式行。｜猜（未查核）

### cli/eca.json

14. **跟程式對不上**｜`eca.json#/screen`「`--eca` goes before the action」｜寫在動作前後都收。｜證據：`P/cmd/aos-eca/bin/aos-eca-screen:311` `aos_flags.parse(sys.argv[1:], {"--eca": "eca"}, sub="root")`、`:75` help「before or after open」。｜確定
15. **跟程式對不上**｜`eca.json#/turn`「DEF_DIR must be an absolute folder with `cli.json` (`AgentBad`)」｜`AgentBad` 只管不是絕對路徑或不是資料夾；沒有 `cli.json` 是 `CfgMissing`。｜證據：`P/cmd/aos-eca/aos_eca/__init__.py:91-92`；`P/lib/agent/cli_cfg.py:36-37`。｜確定
16. **找不到**｜`eca.json#/turn`｜頁沒寫：`--prompt FILE`（`PromptMissing`）；`--one` 不能配 `--on-empty`／`--prompt`；預設 `--on-empty stop`、`--on-busy yield`；cli.json 的 `reseed_bytes`（預設 48000）；代號 `StackMissing`、`HistoryBad`、`PostFailed`、`WriteFailed`、`HookFailed`、`HooksBad`、`ToolsBad`、`CfgMissing`、`CfgBad`、`ToolsMissing`、`CliMissing`。｜證據：`aos_eca/__init__.py:11,59-61,73-98`；`cli_cfg.py:53`。｜確定
17. **找不到**｜`eca.json#/screen`｜頁沒寫：open／watch 的夾沒 `cli.json` 是 `ArgumentsBad`；close 在 cli.json 壞時照關只 warning；沒給 `--eca` 是 `ArgumentsBad`；`CommandUnknown`。｜證據：`aos-eca-screen:156-174,320,329-334`。｜確定
18. **找不到**｜`eca.json#/screen_linger`「tmux 3.2 or newer is required」等、`#/cli_hooks` 裡 Claude Code 自己的行為、`#/external_mcp`「env_file now uses the same dotenv subset」｜aos 程式裡沒有可對的行。｜猜（未查核）

### cli/mailbox.json、feedback.json

19. **找不到**｜`mailbox.json`｜頁沒寫：read 的 `--drop`、`-j`；user-zone 信不加 `--keep` 也自動歸檔；read 沒信退 10；peek 的 `-j`；send 的 `--outputs`、`--not-done`、`--decide`、`--in-reply-to`、`--from`、WHAT 給 `-` 讀 stdin；代號 `StatusBad`、`MailboxMissing`、`MailboxBad`、`InstanceMissing`、`StackMissing`、`LaunchFailed`、`CommandFailed`、`WriteFailed`、`CommandUnknown`。｜證據：`P/cmd/aos-mailbox/aos_mailbox/__init__.py:141,158-166,209,255,273-278,299-301,322,334-361,373,406`。｜確定
20. **找不到**｜`mailbox.json`「use `aos-user`, not `aos-mailbox read`」｜`P/cmd/` 沒有 `aos-user`；repo 內只找到 `user-advice/2026-09/aos-user.md`，實體在 `~/aos-home/ws/tools/aos-user/aos-user`（`K/user_zone.json` 寫的路徑）。｜證據：`find P -name 'aos-user*'`。｜確定（位置）
21. **找不到**｜`feedback.json`｜頁沒寫：add 的 `--family`、`--tier`；各子命令 `-j`；`--kind` 預設 `other`、`--by` 預設 `$AOS_CD` 夾名、`--model` 預設 `unknown`；`AOS_FEEDBACK` 空字串 `ArgumentsBad`、`PathMissing`、`CommandUnknown`。｜證據：`P/cmd/aos-feedback/aos_feedback/__init__.py:11-14,34,42-48,88-90,124`；`storage.py:20-27,94,104-105`。｜確定
22. **跟程式對不上**｜`feedback.json`「the mean scores per kind times calls/(calls+errors+retries)」｜只算 usage、help、errors、args 四種（`other` 不算）；四種各自平均再取平均；沒有對得上的呼叫時不乘、兩者都沒有是 `null`。｜證據：`storage.py:12`；`comfort.py:33-45`。｜確定

### cli/ 的 aos-agent 各頁（_description、flags、errors、safety、agent、talk_settings、history、hook、goal）

23. **跟程式對不上**｜`errors.json#/timeouts`「`DaemonMissing` means `AOS_DAEMON` is unset or its directory does not exist」｜資料夾在但 daemon 沒在跑也報 DaemonMissing；沒設時先退到 `./.stack`。｜證據：`P/cmd/aos-agent/aos_agent/ctl/shared.py:74-86`；`P/py/daemon_ctl/poke.py:41-66`；`table.py:20-26`。｜確定
24. **跟程式對不上**｜`errors.json#/timeouts`「A timed-out letter stays queued and may still be applied later」｜逾時後先試著撤回；撤回成功就不會被套用。｜證據：`ctl/shared.py:162-167`；`daemon_ctl/post.py:53-59`。｜確定
25. **跟程式對不上**｜`history.json`「`RangeBad` (bad range, or a line of the step in progress)」｜CLI 不擋「正在進行的這一步」，那是工具 self_history 才有。｜證據：`aos_agent/history.py:3`（註解明寫）、`:158,162,164`；`P/lib/agent/self_history/_entry:162`。｜確定
26. **跟程式對不上**｜`agent.json#/where_who` 範例 `{"name", "stack", "ws", "def"}`｜`ctl who --json` 還有 `daemon` 鍵。｜證據：`aos_agent/ctl/who.py:48`。｜確定
27. **跟程式對不上**｜`flags.json#/placement`「Exceptions: `aos-exec`, `aos-sandbox`, `aos-json set/append/merge`」｜`aos-tree-start`（`--force` 要在第一個參數前）與 `aos-mcp-launch`（不用 aos_flags）也不照通則，沒列。｜證據：`P/cmd/aos-tree-start/bin/aos-tree-start:17,46`；`P/cmd/aos-mcp-launch/bin/aos-mcp-launch:25`。｜確定
28. **跟程式對不上**｜`agent.json#/add`「The same name = `InstanceExists`」、`#/phases`「Stop and rm first close the screen」「An already reached state is a successful no-op」、`safety.json#/rm`｜設了 `$AOS_KERNEL` 且沒給 `--daemon` 時都不成立：add 不查重名，start／stop／sleep／wake 不讀表、不關畫面，輸出是 `start accepted for NAME`。頁只在 where_who 講 kernel 路。｜證據：`ctl/add.py:149-150,172-191`；`ctl/phase.py:117-234`；`ctl/rm.py:55-69`。｜確定
29. **跟程式對不上**｜`history.json`「`ls -a   # every message (a first line says how many earlier ones ls left out)`」｜那行只在不帶 `-a`、不帶 RANGE、不帶 `-j` 且超過 20 則時印；註解卻掛在 `-a`。｜證據：`history.py:305-308`。｜確定
30. **找不到**｜`flags.json#/target`｜「只收 -t」那串漏 `goal`、`ctl state`；「不收 -t」那串漏 `ctl set-def`。｜證據：`goal.py:170`；`ctl/state.py:145`；`ctl/__init__.py:13` `NO_TARGET = ("add", "rm", "set-def", "ls", "who")`。｜確定
31. **找不到**｜`agent.json#/add`｜`ctl add --dotenv-override` 沒寫。｜證據：`ctl/add.py:44-46,84`。｜確定
32. **找不到**｜`talk_settings.json#/tools`｜add 的 `--no-cache`、`--path-json`；get／rm 收「名字或路徑」。｜證據：`aos_agent/tools.py:35,46,73,165,170`。｜確定
33. **找不到**｜`hook.json`｜`hook add --timeout-ms N`（預設 60000）與 `--on-error` 預設 stop 沒寫，`ls -l` 卻有 TIMEOUT_MS 欄。｜證據：`aos_agent/hook.py:71-72,238`；`P/lib/agent/hooks.py:13`。｜確定
34. **找不到**｜`talk_settings.json#/say_listen`、`history.json`、`goal.json`｜listen `--timeout-s 0`＝不限；history summarize／set 的 `-` 讀 stdin；goal set 的 `-n`（＝`--limit`，跟通用 `-n --name` 不同義）、goal done 的 `-a`；goal 文字上限 1000、limit 1～1000。｜證據：`listen.py:13,216`；`history.py:68,83,202-203`；`goal.py:42,59,164-165,176,199-200`；`P/lib/agent/goal_state.py:19-20`。｜確定
35. **找不到**｜`errors.json#/codes` 與各頁｜aos-agent 會報、九頁都沒有的代號：`InterfaceBad`、`ScreenBad`、`StateMissing`、`QuestionUnknown`、`KeyMissing`、`LlmBad`、`SystemBad`、`ToolsBad`、`HistoryBad`、`MessageBad`、`WriteFailed`、`PostFailed`。｜證據：`decl.py:20-26,119`；`ctl/shared.py:37`；`listen.py:45`；`llm.py:94,108,173`；`system.py:87,99,158`；`tools.py:186`；`history.py:129,133,228,242,340,342`；`say.py:19`。｜確定
36. **找不到**｜`safety.json#/confirm`｜同一套 `[y/N]` 確認也用在 `goal clear`、`history rm/summarize/set --no-keep`，這頁沒列。｜證據：`goal.py:211`；`history.py:313`。｜確定
37. **找不到**｜`agent.json#/add`「stored in plain text in `procs/<name>/exec.json` (mode 644)」｜明文存有證據；「mode 644」沒找到明寫的權限。｜證據：`ctl/add.py:41`；`P/impls/aos-daemon/src/child/child.cpp:229`。｜猜
38. **重複**｜`_description.json`＋`flags.json#/target`＋`history.json`（`--target` 預設 `$AOS_AGENT` 與例外）；`flags.json#/text`＋`goal.json`（TEXT 起不讀旗標）；`safety.json#/reset`、`#/confirm`＋`talk_settings.json`、`hook.json`（reset 問 y/N、`-y`）；`errors.json#/codes`＋`hook.json`、`talk_settings.json#/system`（定義沒宣告就 XxxMissing）。都是一兩句、不到整段。｜確定

### cli/tools.json、tool_env.json、tool_flags.json、grow.json、mcp.json、mcp_import.json、sandbox.json

39. **跟程式對不上**｜`tool_flags.json`「Extra stdin keys are ignored.」｜不認得的鍵是 `ArgumentsBad`，不是忽略。｜證據：`P/lib/tool_io.py:459-480`（`raise Error("ArgumentsBad", "unknown key%s …")`）、`:526`。｜確定
40. **跟程式對不上**｜`grow.json`「`--dry-run` goes before up/down」｜寫在子命令或 CALLER 之後也收。｜證據：`P/cmd/aos-grow/bin/aos-grow:446`、`:48-49`。（程式自己的子命令 help `:68,85` 仍寫 before up。）｜確定
41. **跟程式對不上**｜`mcp_import.json#/routes`「http … needs `env_file` (`PackBad` without it)」｜只有寫了 `bearer_token_env` 卻沒 `env_file` 才 `PackBad`；沒寫 bearer 就不需要 env_file。｜證據：`P/lib/mcp_client.py:448-449`；`P/lib/mcp_server_file.py:114-116`。｜確定
42. **跟程式對不上**｜`mcp_import.json#/errors`「`PackBad`, `PackMissing`, `DotenvBad`: the server file or its env file is broken or missing」｜env_file（與 ca_file）不在是 `PathMissing`，頁的代號表沒有 `PathMissing`。｜證據：`mcp_server_file.py:53,74-75,87`。｜確定
43. **跟程式對不上**｜`mcp_import.json#/import`「None of them = all tools」｜兩旗標都沒給時先用檔裡已有的 `only`／`except`；旗標跟檔裡不同、或兩旗標同給是 `ArgumentsBad`。｜證據：`P/cmd/aos-mcp-import/bin/aos-mcp-import:245-246,254,260-263,270`。｜確定
44. **跟程式對不上**｜`tools.json#/ls_rm_get`「prints `removed NAME` for each」｜實際印 `removed NAME (FILE: key deleted)` 或 `(FILE: set to null over BASEFILE)`；底檔也有同名時是寫 `"NAME": null`。｜證據：`P/cmd/aos-tools/bin/aos-tools:932-940`。｜確定
45. **跟程式對不上**｜`tools.json#/add`「`PathMissing` naming the file and field it came from」｜add 當下的錯句不帶檔與欄位；帶來源的是 get／call 與 `$override` 底檔。｜證據：`aos-tools:455,634-635,790-792,890-892,1098-1100`。｜確定
46. **找不到**｜`tools.json`｜頁沒寫：`call NAME [ARGS_JSON]` 第二個位置參數、`AOS_STACK_IN_CALLER`；`ls --long`、`ls -j`、`add -n`；`ls -l` 配 `--json` 是 `ArgumentsBad`；工具名規則（`[A-Za-z0-9_-]`、64 字，`NameBad`）；代號 `CommandUnknown`、`RegistryBad`、`ToolDefMissing`、`ToolDefBad`、`ToolMissing`、`DotenvBad`、`DirectiveBad`、`CommandMissing`、`WriteFailed`；override 的 `--path-json`。｜證據：`aos-tools:70-71,300-307,847-849,898-899,962-981,1038-1054,1088-1125`。｜確定
47. **找不到**｜`tool_flags.json`｜頁沒寫：`--no-KEY`、旗標 `-` 對鍵名 `_`、陣列鍵重複旗標、`positional`、`--tooldef`／`--metainfo`／`--write-defs`。｜證據：`tool_io.py:359,365-374,377-420`；`P/lib/tool_spec.py:263-272`。｜確定
48. **找不到**｜`grow.json`｜頁沒寫：`-n`、`--name` 預設、up 的第二種情形（那格已是 `NAME` 時 `NAME.json`→`NAME/_entry`）、`--take` 的檔要在設定檔的夾裡、代號 `CfgMissing`、`CfgBad`、`WriteFailed`、`CommandUnknown`。｜證據：`aos-grow:23,221,345-398,459`。｜確定
49. **找不到**｜`mcp.json`｜頁沒寫：短名 `-w`、`-s`；逾時與空 stdout 的 `CommandFailed` 字樣、先 TERM 2 秒後 KILL；`--own` 那份在時只用它；`--hooks` 不是夾、`--own` 空是 `ArgumentsBad`。｜證據：`P/cmd/aos-mcp/bin/aos-mcp:105,119-126,163-164,207-214,262-272`。｜確定
50. **找不到**｜`mcp_import.json`｜頁沒寫：sync 的兩行輸出（`run again with --yes to write`、`synced N of M tools…`）；sync 也收 `--timeout-s`；登記名併連續 `_`、上限 64；server 名 `[a-z][a-z0-9_]{0,31}` 且不可為 `aos`；`timeout_ms` 預設 60000；代號 `WriteFailed`、`FlagUnknown`、`StackMissing`。｜證據：`aos-mcp-import:101-110,184-185,233-238`；`P/lib/mcp_freeze.py:17,23-31`；`mcp_server_file.py:22,59-60`。｜確定
51. **找不到**｜`sandbox.json#/run`｜頁沒寫：「壞設定＝不套沙箱照跑」還含設定裡有 `$ref`、`$env` 變數沒設、檔讀不了；`CommandMissing` 還含 `commands` 列的指令、`s6-setuidgid`、`aos-asuser`、`sudo`、`true`；CONFIG 不在但 `CONFIG.json` 在時自動補 `.json`；`/proc`、`/dev` 一定有。｜證據：`P/cmd/aos-sandbox/bin/aos-sandbox:107-108,122-130,149-154,173-188,231-234,292-297,323-355`。｜確定
52. **找不到**｜`tool_env.json`「the tool's own `.env` (fills gaps only)」、`sandbox.json#/run`「signal N = 128+N」、`#/config`「…take the same keys」、`mcp.json#/_description`「An eca agent gets it automatically」｜不在指定來源內，沒對到程式行。｜猜（未查核）

### cli/parts/

53. **找不到**｜`parts/json.json`｜aos-json 的子命令 `add`、`ls`、`search` 頁沒寫（頁有 get、peek、where、set、append、merge、del、batch、env、ref、check）；旗標 `--key`、`--value`、`--contains`、`--up`、`--long`、`--offset`、`--limit`、`--prefix` 沒寫。｜證據：`P/impls/aos-json/src/main.cpp:61-63`；`cmd/list.cpp:180,207`；`cmd/write.cpp:155`。｜確定
54. **找不到**｜`parts/exec.json`、`loop.json`、`daemon.json`、`directive.json`、`post.json`、`llm.json`、`fsm.json`｜頁沒寫的旗標與代號：aos-exec `--stack-lazy`（`aos-exec/src/env/env.cpp:47`）；aos-loop `--enable-counters`、`AOS_LOOP_SIGNAL`、`on_timeout_ms`（`aos-loop/src/main.cpp:3,28,38`）；aos-daemon `--interval-ms`、`--ctl`、`--state`、`--state-flux`、`--enable-counters`（`aos-daemon/src/main.cpp:3`）；aos-directive `--at`（`aos-directive/src/main.cpp:53`）；aos-post send `--in-reply-to`（`aos-post/src/main.cpp:100`）；aos-llm `ls --json`、`recv --quiet`、send／ask `--priority`、`EndpointsMissing`（`aos-llm/src/main.cpp:49-53`、`ls/ls.cpp:19`）；aos-fsm `StateUnknown`、`CfgBad`（`aos-fsm/src/table/table.cpp:112,147`）。｜確定
55. **找不到**｜`parts/_description.json`「`aos-json set`, `append` and `merge` want them before FILE」｜沒讀到能證明的那一行（沒追 aos-json 的 parse_args 本體）。｜猜（未查核）

### tools/ 第一批（look、change、delete、shell、gadgets）

56. **過時**｜`tools/peek_now_time.json`「No arguments.」「If someone wants a local time, convert it yourself」「`ArgumentsBad` (give `{}`, no keys…)」｜程式與 tooldef 都有參數 `local`（boolean）：`{"local": true}` 印本機時間加 UTC 偏移加星期。11-13 加的，頁沒跟上；`tools/_index.json#/peek_now_time.json`「in UTC」同樣。｜證據：`P/lib/base/peek_now_time/_entry:4,42-45`；`_tooldef.json` 的 `properties.local`。｜確定
57. **跟程式對不上**｜`read.json#/errors`、`ls.json#/errors`、`view.json#/errors`、`stat.json#/errors` 的「`ReadFailed`, `WriteFailed`, `WsMissing`」｜這四支不寫檔，發不出 `WriteFailed`（各 tooldef 的 errors 也沒有）。｜證據：四支 `_entry` 與 `tool_io.py`、`file_summary.py` 搜不到 `WriteFailed`；只有 `read/_entry:56`、`ls/_entry:77`、`stat/_entry:80`、`view/_entry:77` 的 `ReadFailed`。｜確定
58. **跟程式對不上**｜`write.json#/errors` 末行「`ReadFailed`, `WriteFailed`, `WsMissing`」｜write 發不出 `ReadFailed`；`WriteFailed` 在同節上面已有專條，又列一次（重複）。｜證據：`P/lib/base/write/_entry:42-63`。｜確定
59. **跟程式對不上**｜`view.json#/_description`「A small value comes whole in `value`. A big one comes as `children`」｜超過 80 字的字串兩者都沒有，只有 `type`、`counter_chars`、`head`（前 60 字）。｜證據：`P/lib/file_summary.py:31-32`；`view/_entry:105`。｜確定
60. **跟程式對不上**｜`edit.json#/errors`「`FileMissing`: no such file… `FileBad`: not a UTF-8 text file」｜路徑是資料夾（非一般檔）回 `FileMissing`，不是 `FileBad`。｜證據：`P/lib/base/edit/_entry:53-54`。｜確定
61. **跟程式對不上**｜`view.json#/_description`「other files: the first 40 lines as `head`」｜Python／Markdown 大綱是空的也給 `head`；語法錯另有 `syntax_error` 鍵。｜證據：`view/_entry:158-159,169-172`。｜確定
62. **跟程式對不上**｜`ls.json#/_description`「An empty folder prints `... empty`」、`#/long`「`counter_items` (all items)」｜`... empty` 的條件是「這頁沒項目且沒 hidden 行」（offset 超過總數也印）；`hidden` 為 false 時 `counter_items` 不含 `.` 開頭的。｜證據：`P/lib/base/ls/_entry:79-80,132,169-170`。｜確定
63. **跟程式對不上**｜`read.json#/errors`「or one line is over 50KB」｜只有要印的第一行超過 50KB 才 `FileBad`，後面的行超長只是截斷。｜證據：`read/_entry:75,80`。｜確定
64. **跟程式對不上**｜`stat.json#/_description`、`#/errors`「`ReadFailed`: the file is there but could not be read」｜stat 只讀前 4MB（`text`、`counter_lines`、`format` 都只依這 4MB）；`os.stat`、`os.listdir` 沒包 try，讀不了的資料夾是 traceback 不是 `ReadFailed`。｜證據：`P/lib/base/stat/_entry:66,70,78`。｜確定（依程式推論、沒實跑）
65. **跟程式對不上**｜`run_python.json#/rules`「saved as `main.py` in your stack」｜寫的是工具自己的 `$AOS_STACK`（agent stack 裡的 `tools/run_python/` 小格）。｜證據：`run_python/_entry:69`；`P/lib/observed.py:71-75`。｜猜
66. **找不到**｜`grep.json`、`glob.json`｜頁沒寫：尾行 `... no matches from offset N`（grep 也沒列 `... no matches`）；grep 的 `path` 是單一檔時 `glob` 被忽略；glob 壞連結不列、fifo／socket 是 `other` 只有 `type: any` 才列。｜證據：`grep/_entry:121-122,163-166`；`glob/_entry:84,104-105`；`P/lib/file_walk.py:145-154`。｜確定
67. **找不到**｜`ls.json`、`read.json`、`view.json`｜頁沒寫：ls 的 TYPE `missing`、INFO `json array`／`json value`、頂層 key 最多 12 個、超過 1MB 的 .json 不看；read 的空檔印 `(empty file)`、`offset`／`max_lines` 小於 1 是 `ArgumentsBad`；view 的 `children` 最多 200（`counter_children_more`）、小值門檻 1000 字、給了 `start`／`end` 時 `pointer` 被忽略。｜證據：`ls/_entry:42,92-109,124,152`；`read/_entry:43-45,57-59,65-67`；`view/_entry:57-68,83,106-112,130-138`。｜確定
68. **找不到**｜`trash.json`、`edit.json`、`math.json`、`shell.json`、`run_python.json`、`peek_clock.json`｜頁沒寫：trash 同秒再丟夾名加 `-1`；edit 改連結指的檔、有一處 CRLF 就全寫 CRLF；math 的 `cannot evaluate`、`unsupported syntax: Constant`；shell／run_python 的 `timeout_s` 是 `0 < t <= 300`（0 被拒，頁寫「not between 0 and 300」）與截斷提示行原文；peek_clock 鐘檔空的算 0。｜證據：`trash/_entry:62-67`；`edit/_entry:52,64,92-93`；`math/_entry:43,64-65`；`shell/_entry:54,73`；`run_python/_entry:53,62`；`P/lib/tool_io.py:69-71`。｜確定
69. **跟程式對不上**（tooldef 那邊，頁是對的）｜`P/lib/base/remove/_tooldef.json`「Returns JSON {path, type, counter_files}」（`counter_files` 只有資料夾才有）；`stat/_tooldef.json` 沒提 `broken`；`ls/_tooldef.json` 類型漏 `missing`；`P/lib/agent/todo/_tooldef.json` 的 errors 沒有 `StackMissing`（頁有、程式會吐）。｜證據：`remove/_entry:53`；`stat/_entry:62-65`；`ls/_entry:105`；`todo/_entry:152-154`。｜確定

### tools/ 第二批（json、jsonx、index_view、todo、goal）

70. **跟程式對不上**｜`json_get.json#/path`「`FILE#` with nothing after it is an error」＋`#/errors`「`PointerBad`: … the pointer after `#` does not start with `/`」｜`FILE#` 實際吐 `SpecBad`。整個 `K/tools/` 沒有一頁出現 `SpecBad`；7 支的 tooldef 有列（json_multi_get、json_multi_set、jsonx_ls、jsonx_search、jsonx_del、jsonx_multi_get、jsonx_multi_set），其餘 json_*／jsonx_* 走同一段也會吐但 tooldef 沒列。｜證據：`P/lib/aos_json.py:55-58,103-105,289`；`P/impls/aos-json/src/doc/pointer.cpp:66-67`。｜確定
71. **跟程式對不上**｜`json_multi_set.json#/errors`「Inside an item (not a `{"path", "value"}` object…): that item's `[error]` line」｜item 不是物件時整次呼叫被 schema 擋下，只有一行 `ArgumentsBad`、一格都不做。｜證據：`json_multi_set/_tooldef.json`（items 型別 object）；`P/lib/tool_io.py:466-491`；`P/lib/aos_json_multi.py:15,47-48`。｜確定（讀碼、沒實跑）
72. **跟程式對不上**｜`jsonx_set.json#/errors`「`FollowMissing`: a `$ref`/`$env` object on the way…」（標題涵蓋讀取那幾支）｜`FollowMissing` 只有寫入（jsonx_set／add／del）會出；讀取不帶 follow 是照字面走，沒那鍵才 `PointerMissing`。｜證據：`P/impls/aos-json/src/follow/locate.cpp:111-124`；`cmd/edit.cpp:48`；`cmd/read.cpp:26-29`。｜確定
73. **跟程式對不上**｜`goal.json#/rules`「Only talking, or calling `goal` with op get, does not count」｜叫 goal 的任何 op 都不算進展，不只 get。｜證據：`P/lib/agent/goal_state.py:123-127,165-166`。｜確定
74. **過時**｜`index_view.json#/_description` 範例「`[index] knowledge/aos/tools/_index.json, 36 entries`」｜該 index 現在 39 鍵。｜證據：`len(json.load(K/tools/_index.json)) == 39`。｜確定
75. **找不到**｜`index_view.json`｜頁沒提 tooldef 列的 `LaunchFailed`、`CommandFailed`、`WsMissing`，也沒連到別的錯誤頁；`IndexBad` 另一種（字串但不是合法路徑）沒寫；壞 `_metainfo` 的 note 只在有別的 index 層時才出現；第三欄 `index: bad (…)`、`(natural index: … does not exist)` 沒寫。｜證據：`index_view/_tooldef.json`；`P/lib/aos_index.py:71,174-178,199-201,214-219`。｜確定
76. **找不到**｜`goal.json#/errors`｜tooldef 列的 `CommandMissing`、`WsMissing`、`LaunchFailed`、`CommandFailed`、`DaemonFailed` 頁沒提；`limit` 上限 1000、goal 文字上限 1000 字頁與 tooldef 都沒寫。｜證據：`goal/_tooldef.json`；`P/lib/agent/cmd_call.py:48-65`；`goal_state.py:19-20`；`P/cmd/aos-agent/aos_agent/goal.py:164-165,199-200`。｜確定
77. **找不到**｜`jsonx_set.json#/_description`｜`follow` 不套用在 `from` 的來源路徑（來源只帶 `--resolve`），頁沒寫。｜證據：`P/lib/aos_json.py:220-221`。｜確定
78. **找不到**｜`json_get.json#/errors`、`json_set.json#/errors`、`json_multi_set.json#/errors`、`todo.json#/errors`｜小的漏列：`depth` 不是正整數、`key` 不是字串（`aos_json.py:173-174,186-187`）；`TargetBad`「父層是純值」（`impls/aos-json/src/cmd/edit.cpp:102`）；`max_bytes` 不合法整批擋（`aos_json_multi.py:19-20`）；路徑結尾 `/-` 時 `parents` 不起作用（`aos_json.py:240-254`）；todo 的 `json` 非布林、mark 缺 `n`／`status`、item 有多餘鍵、add 時已滿 50 項（`todo/_entry:158-159,174-176,185-186,190-193`）。｜確定
79. **找不到**｜`tools/` 各短頁｜json_add、json_del、json_len、json_ls、json_search、json_multi_get、jsonx_add、jsonx_del、jsonx_get、jsonx_ls、jsonx_multi_get、jsonx_multi_set、jsonx_search 這 13 頁本身不列任何錯誤代號（靠連到 `json_get.json#/errors`、`json_set.json#/errors`、`jsonx_set.json#/errors`）；連過去後除 `SpecBad`（第 70 條）外都找得到。｜證據：各 `_tooldef.json` 的 errors 對頁文字。｜確定

### tools/ 的涵蓋範圍

80. **找不到**｜`K/tools/`｜`P/lib/packs/*.json` 共 61 支工具，`K/tools/` 有頁的 38 支。沒頁的 23 支：comm 包 `board_set`、`board_clear`、`board_wait`、`board_read`、`board_ls`；def 包 `agent_def`、`tools_def`；events 包 `clock_register`、`self_hook`；gadgets 包 `do_task`；kernel_gate 包 `kernel_gate`；mailbox 包 `mailbox_peek`、`mailbox_read`、`mailbox_send`；self 包 `self_tools`、`self_llm`、`self_system`、`self_state`、`self_ctl`、`self_history`；subagent 包 `subagent`、`agents_ctl`、`fork`。其中 5 支 `board_*` 在整個 `K/` 都搜不到名字（comm 包是工作樹未入庫的新東西）；其餘 18 支在 `K/` 上層頁（`me/`、`agents.json`、`mailbox.json`、`packs.json` 等）有提到。`tools/_description.json` 寫「One node per stock tool」。｜證據：packs 清單對 `K/tools/` 檔名；`grep -rlw` K。｜確定
81. **找不到**｜`K/tools/`｜有 `_tooldef.json`、不在任何 pack、`K/tools/` 也沒頁的：`lib/agent/` 的 `user_send`、`user_verify`（`K/user_zone.json` 有提）、`claude`、`codex`；`lib/aos/` 的 `box_check`、`defs`、`feedback`（`K/cli/feedback.json` 有提）、`kernel_llm`（`K/cli/parts/llm_kernel.json`）、`kernel`、`llm_forward`、`measure`、`metainfo_check`、`promote`、`review_round`、`rollback`、`shell_report`、`watch`；`lib/base/` 的 `llm_fake`、`llm_http`、`mcp_tool`（`K/cli/mcp_import.json` 有提）。整個 `K/` 搜不到名字的：`box_check`、`llm_forward`、`measure`、`metainfo_check`、`promote`、`review_round`、`rollback`、`shell_report`、`llm_fake`、`llm_http`。｜證據：`find P/lib -name _tooldef.json`（80 個）對 packs 與 K。｜確定（清單）；`claude`、`codex`、`kernel`、`watch`、`defs` 是常用字，K 裡是否有講這幾支工具本身：猜
82. （不算問題，備查）頁對應的工具已不存在的：**沒有**。`K/tools/` 38 頁每頁都有對應的 `_tooldef.json`。

### 壞連結

83. （不算問題，備查）**壞連結 0 個**。兩夾各頁裡的 `aos/…json#/key` 交叉參照（tools 約 59＋20 頁的全部、cli 九頁 17 個、其餘 cli 頁全部）都解得到檔與鍵。

## 三、查過、頁上寫的都對得上的

完全對得上（沒有任何一條發現）：
- `cli/sweeper.json` 整頁（預設 1 MiB、7 天、300 秒、封存路徑、四步驟、鎖被佔退 0、範本每 10 分鐘）。
- `cli/parts/lock.json`（acquire／release／show、`--note`、`--wait-ms`、`--lease-cycles`、`--force`、退 10、holder 身分；`aos-lock/src/main.cpp:38-40,70,153,168`）。
- `cli/parts/llm_kernel.json`（工具夾 `lib/aos/kernel_llm`、`--enable-counters`、範本 `interval_ms: 300`、`StackMissing`）。
- `tools/copy.json`、`move.json`、`mkdir.json`、`remove.json`。
- `tools/json_ls.json`、`json_search.json`、`json_len.json`、`json_add.json`、`json_del.json`、`json_multi_get.json`、`jsonx_get.json`、`jsonx_ls.json`、`jsonx_search.json`、`jsonx_add.json`、`jsonx_del.json`、`jsonx_multi_get.json`、`jsonx_multi_set.json`（除共用的第 70、72、79 條外，頁上的參數、預設、輸出格式都對）。
- `tools/todo.json`（ops、50 項／300 字、存檔位置、`StackMissing`；只有第 78 條的小漏列）。

頁上寫到的部分對得上、只有漏寫（列在上面「找不到」）：
- `cli/parts/`：daemon、directive（`InputBad` 在 `aos-util/src/io.cpp:59`）、exec、fsm（`stage.txt`、`next` 規則）、json（列出的子命令都在）、llm（五個子命令、ls 七欄、`LlmKernelMissing`、`RegretFailed`）、loop、post（七個子命令、`--reply-to`、`--ordered`、`--keep`、`--reply`）。
- `cli/`：`flags.json#/text`、`#/help`、`#/short`；`errors.json#/_description`、`#/codes`；`safety.json#/rm`、`#/reset`；`agent.json#/_description`、`#/ls_state`、`#/phases`（非 kernel 路）；`talk_settings.json#/say_listen`、`#/chat_screen`、`#/llm`、`#/system`；`goal.json`；`hook.json`；`mcp.json`；`tool_env.json`；`sandbox.json#/config`；`daemon.json#/_description`、`#/ls`、`#/sweep`、`#/letters`；`eca.json#/external_mcp`、`#/cli_hooks`（aos 這邊）、`#/screen_linger`；`clock.json#/clock`。
- `tools/`：grep、glob（所有數字與格式都對）、shell、run_python、math、peek_clock、trash、write、json_get、json_set、json_multi_set、jsonx_set、index_view（路徑規則全對）、goal `_description`。

預設值查過沒有錯的：ctl `--timeout-s` 30（ls／who／where／state 是 3）、history ls 最後 20 則每則 200 字、goal limit 10、`screen_close_after_s` 600、`--on-queued` fail、grep／glob 預設 100 上限 500、shell 30／run_python 60 上限 300、`max_bytes` 8000、`AOS_JSON_MAX_ITEMS` 200。兩夾沒有發現任何寫錯的預設值。

## 四、各種類條數

跟程式對不上 35｜找不到 39｜過時 4｜太長 2｜重複 1｜壞連結 0（另 2 條備查不計：第 82、83 條）
