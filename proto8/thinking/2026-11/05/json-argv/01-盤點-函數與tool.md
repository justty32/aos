盤點 aos 函數定義 ↔ LLM tool 呼叫現在怎麼轉（schema 怎麼生、呼叫 JSON 怎麼變回執行、結果怎麼回），逐處標「不是無痛」的地方（附檔:行；路徑以 main 現況為準，S5 後位置另註）。
← [json-argv README](README.md)｜下一份 [02-盤點-指令與旗標](02-盤點-指令與旗標.md)

## 現況鏈（一張圖）

```
_tooldef.json ──aos-tools ls --json──▶ [{name,kind,path,tooldef,metainfo}]
   {description,parameters}              │                    │
                                 brain.py:94-104         aos-mcp:149-172
                                 → OpenAI function       → MCP {name,description,inputSchema}
LLM tool_use.arguments ──act.py:101-129──▶ aos-tools call 名 ──execve aos-exec path──▶ _entry
                        (原字串 stdin)     (dir/json: stdin 原樣)                  tool_io.arguments()
                     ──aos-mcp:177-187──▶ aos-tools call 名   (exe: 寫 $AOS_STACK/tool_call.json、--tool-call FILE)
                        (json.dumps(dict))
結果 ◀── stdout 整段；退碼＝工具的（訊號 128+N）；錯誤行 stderr＋stdout 各一行（tool_io.die echo=True）
```

## 逐處：定義 → schema

| 處 | 做法 | 檔:行 |
|---|---|---|
| 工具資料夾 | `_tooldef.json`＝`{description, parameters}`（OpenAI function 去 name，P-41）；`check_tooldef` 只驗 description 是字串、parameters 是物件 | `bin/aos-tools:117,179`（S5 後 `cmd/aos-tools/`） |
| JSON 檔工具 | 頂層 `_tooldef` key | `bin/aos-tools:187` |
| 可執行檔工具 | 跑 `XXX --tooldef`（cwd＝檔所在夾、10 s 逾時）、按 mtime＋大小快取進註冊檔 | `bin/aos-tools:132-153,200-206` |
| 給 fsm 腦 | `ls --json` → `{"type":"function","function":{name,description,parameters}}` 寫 `think/request.json` | `demo/agent-fsm/brain.py:94-104,169-175`（S5 後 `templates/agent-fsm/`） |
| 給 MCP | 同一份 → `{name, description, inputSchema: parameters or {type:object,properties:{}}}`；`_metainfo` 轉 annotations（side_effect→readOnlyHint…） | `extras/ai_tools/bin/aos-mcp:131-142,165-166`（S5 後 `cmd/aos-mcp/`） |
| pyfix 子 agent | 另一份 tools→function 轉換與 call 迴圈 | `lib/agent/pyfix/agent/{brain,act}.py`（S10 依裁定封存） |

結論：**定義→schema 這半邊已經是「同一份、原樣包」**，沒有手寫第二份 schema。兩個消費者都只取 `description`、`parameters`，所以 `_tooldef.json` 加工具側才讀的 key（no-pid 的 `env`、03 的 `positional`／`errors`）不會漏給模型。

## 逐處：tool 呼叫 JSON → 執行

| 處 | 做法 | 檔:行 |
|---|---|---|
| act 格 | 取最後一則 assistant 的 `tool_calls[].function.arguments`（字串），`json.loads` 驗過但**原字串**當 stdin；env `AOS_STACK=<stack>/tools/<名>/`；沒逾時（只受 act 格 1 800 000 ms） | `demo/agent-fsm/act.py:101-129,119` |
| aos-mcp | `json.dumps(arguments)` 當 stdin；env 加 `AOS_WS`、`AOS_STACK=…/tools/<名>/`；逾時取 `_metainfo.time_ms.max`，TERM 再 KILL 整群 | `aos-mcp:177-187,170-172` |
| aos-tools call（dir/json） | 先把登記格 `env` 蓋進 environ，`execve("aos-exec",[path])`，stdin 原樣 | `bin/aos-tools:420,426` |
| aos-tools call（exe） | stdin 先寫 `$AOS_STACK/tool_call.json`，再 `aos-exec path --tool-call FILE`、stdin=DEVNULL | `bin/aos-tools:429-444` |
| 工具端 | `tool_io.arguments(*required)`：讀整段 stdin 當 JSON，空＝`{}`，非物件＝`ArgumentsBad`；required 只驗「非空字串」 | `lib/tool_io.py:61-70` |
| brain 的 `--memory` | `aos-tools call memory` stdin `{"op":"read"}`，寫死 30 s | `brain.py:33,117-122` |
| eca（claude／codex） | 寫 `mcp.json` 把 aos-mcp 掛成 MCP server；`cli.json` 的 `tools_flags` 原樣插進 aos-mcp argv | `lib/agent/cli_session.py:145-163` |

## 不是無痛的地方（編號供 06 引用）

| # | 哪裡痛 | 檔:行 | 03／04 怎麼解 |
|---|---|---|---|
| A1 | **schema 寫三份**：`_tooldef.json` 的 parameters、`_entry` 的 HELP「Arguments:」段、`_entry` 裡手寫型別驗證；沒人拿 schema 驗 input（aos-schema 沒接上） | `lib/base/read/_entry:7-15,49-54`；`lib/agent/self_tools/_entry:16-26,105-115` | `tool_io.start` 讀 `_tooldef.json` 生 help＋最小檢查（03） |
| A2 | **型別丟失**：`arguments()` 只驗 required 是字串；int／bool／enum 各工具手驗、`enum` 沒人照驗 | `lib/tool_io.py:70`；`read/_entry:52` | 同上 |
| A3 | **同一份 input 兩種讀法**：dir/json 吃 stdin，exe 吃 `--tool-call $AOS_STACK/tool_call.json`；同 stack 並發互相覆寫；repo 沒有任何 exe 實作 `--tooldef`／`--tool-call`，aos-exec 也只當 ARGS 傳下去 | `bin/aos-tools:429-444` | **刪 `--tool-call` 路**：exe 工具也吃 stdin（proto8 不留舊路）；`--tooldef` 保留（exe 自己印定義） |
| A4 | **arguments 形態兩種**：act 傳 LLM 原字串，aos-mcp 傳 `json.dumps(dict)` | `act.py:115`；`aos-mcp:187` | 統一傳原字串（P-41「原樣」）；aos-mcp 收到的已是 dict，`json.dumps` 是唯一辦法——寫進 README 當已知差異 |
| A5 | **結果回傳不一致**：act 尾巴加 `(tool X exit code N)`、不附 stderr、不逾時；aos-mcp `isError`＋stderr 尾 2 048 B、逾時看 `_metainfo`；memory 30 s、self_tools 60 s 寫死 | `act.py:128`；`aos-mcp:227-233`；`brain.py:33`；`self_tools/_entry` | 06 J5：act 也讀 `_metainfo.time_ms.max` 當逾時、退非 0 時附 stderr 尾（C-52 例外表已准 aos-mcp，act 比照） |
| A6 | **argv 拼接**：self_tools／agents 把 JSON 鍵拼成 `aos-agent tools --target ME add …`；`aos-json/tools/json` 把 `cmd` 拼成 `aos-json CMD … TARGET` | `self_tools/_entry:121-128`；`impls/aos-json/tools/json/_entry:53-61` | 轉接工具本來就該拼（給人用程式沒有 stdin 介面，Q1 不做反向）；拼法照 02 表 |
| A7 | **env 夾帶**：`AOS_STACK` 三處各自改寫 `tools/<名>/`；`AOS_MEMORY` 由登記格 `env` 注入；`AOS_DAEMON`／`AOS_KERNEL` 隱式繼承 | `act.py:119`、`brain.py:115`、`aos-mcp:179`；`aos-tools:420` | 04：小格路徑收進 `aos-tools call`（一處算）；hub 變數照 N-63、登記格 `env`＝no-pid 的補法 |
| A8 | **錯誤行四份實作**：`tool_io.die`、`aos_flags.die`、`aos-json/tools/json/_entry:35` 自寫、`cli_session` 自己的；act 前綴同時有 `act:`／`agent-fsm:`；`aos-mcp:227` 的 `CommandFailed` 沒 `error:` | 各該行 | 06 J2：全部走 `tool_io`／`aos_flags`（stdio-unify 已裁「收成共用模組」），aos-mcp 那行補 `error:` |
| A9 | **`--help` 三種認法**：tool_io 任何位置看到就算、其他 argv 默默忽略；aos_flags 只在旗標位置、未知旗標報錯；demo 格手寫 `flags()` 不支援 `--x=V`／`--` | `tool_io.py:24-28`；`aos_flags.py:98-109`；`brain.py:40-47` | 03：工具改走 schema 映射（未知旗標＝`FlagUnknown`）；demo 格改用 `aos_flags.parse` |
| A10 | **語言**：lib tooldef 英文、`impls/aos-json/tools` 中文；`_metainfo.summary` 中英混 | `impls/aos-json/tools/json/_tooldef.json` | S10 併 lib 時改英文（程式輸出一律英文） |
| A11 | **WS 取法**：check_inbox、pyfix、json/_entry 用 `AOS_WS` 預設 `.`；其他 `tool_io.workspace()` 沒設＝`WsMissing` | `check_inbox/_entry:29`、`json/_entry:63` | 全走 `workspace()`（aos-exec 一定給 `AOS_WS`） |
| A12 | **bootstrap 複製**：每支 `_entry` 貼 10 行找 tool_io 的碼，judge 那份已分岔 | `read/_entry:17-27`；`judge/_entry:43-47` | 保留（lib 規則 9 定的找法），但做成一行 `exec(open(...))`？不——維持 10 行，sonnet 掃一次對齊即可（S8 拆大檔時一併） |
| A13 | **同名不同物**：`impls/aos-json/tools/json_edit`（`{file,want}`、叫 LLM）vs `lib/base/json_edit`（`{path,set,del}`） | 兩夾 | S10 併 lib 時前者改名 `json_rewrite` 或封存 |

## 無痛互轉的判準（給 06 驗收）

1. 任一工具只有一份參數定義（`_tooldef.json`）；`--help`、型別檢查、tool schema 都從它來。
2. 腦叫、MCP 叫、人在殼裡叫（`aos-exec 工具 --k v`）三條路進同一個 dict。
3. 錯誤行只有兩份實作（`tool_io`、`aos_flags`，後者包前者的 tokenizer）。
4. `aos-tools call` 對 dir／json／exe 三種工具只有一條入參路（stdin）。
