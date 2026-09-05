> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# registry — tool 登記表：住哪、欄位、來源、指令、範例

← [tools/README](README.md)｜表述 [description](description.md)｜迴路 [call-loop](call-loop.md)｜合成 [synthesis](../ai-core-field/synthesis.md)

前提（使用者原話）：任何 POSIX 可呼叫的程式都是 tool；要有登記列表＋表述。
原則：**登記表是行為契約、能替程式代答；自述是加分不是門票；不掃 PATH。**
現況：`agents/<name>/tools.json` 每項 `{name, description, argv}`，`agent init` 硬寫 `sh/ls/cat`（`core/agent/src/tools.cpp:29–36`）。

## 一、住哪

| 選項 | `add` 原子寫 | 多 agent 共用 | git 友善 | 跟 inbox 一檔一件一致 | 模型按需 `cat` |
|---|---|---|---|---|---|
| A 單檔 `.aos/tools.json`（F1） | 整表 rename，競寫面大 | 是 | 同檔易衝突 | 否 | 只能整表 |
| B 一資料夾一 tool `.aos/tools/<name>/{tool.json,metainfo.json,help.txt}`（F2） | 三檔一組不原子 | 是 | 一項三檔較吵 | 一資料夾一件 | 最好 |
| **C 一檔一 tool `.aos/tools/<name>.json`**（F3） | 一個 rename | 是 | diff 小 | 完全一致 | 可讀單檔，少 help sidecar |
| D 維持 `agents/<name>/tools.json` | 單 agent 整表 | **否** | agent 間重複 | 否 | 整表 |

**建議 C**；`agents/<name>/tools.json` 退成白名單。代價：help／自述不原樣保存，要時加 `.aos/tool-help/<name>.txt`。
版控：靜態清單→進版控（`.gitignore` 現排除整個 `.aos/`，要加 `!.aos/tools/`，同 heartbeat 規則）。

## 二、一項的欄位

| 欄位 | 出處 | 必填／預設 | 現在誰消費 |
|---|---|---|---|
| `name` | 全部 | **必填**，＝檔名 | prompt、認 tool |
| `exec.argv[]` | 全部 | **必填**，固定前綴 | agent 展開後投遞成 inst |
| `exec.args: list\|string\|none` | F2 | `list` | agent（現只有 string） |
| `exec.stdin: none\|text\|path` | F2／F3 | `none` | inst 投影 |
| `exec.cwd`、`exec.timeout_ms` | inst | 世界根／0 | inst 投影 |
| `exec.stdout: text\|jsonl\|json\|paths` | F3 | `text` | 無人（留位） |
| `exec.exit_codes{code: meaning\|{meaning,retryable}}` | F3 | 0=ok 其餘不可重試 | 無人→ [call-loop 三](call-loop.md) |
| `exec.env_allow[]` | F1 | 缺席＝全繼承 | 無人 |
| `model.description` | 全部 | **必填**一句 | prompt |
| `model.parameters` | F3 | 由 `args` 生薄 schema | 無人→ export |
| `meta.source: manual\|metainfo\|header` | F2 | `manual` | 無人 |
| `meta.lifecycle`、`state`、`guarantee`、`interruptible` | F1／F2 traits | `one_shot`／不宣稱／`none`／不宣稱 | 無人（`guarantee` 決定可否自動重跑） |
| `meta.predictability: high\|medium\|low` | 改名自 nondeterministic | 缺席＝未知 | prompt 一行（[description 一](description.md)） |
| `meta.network`／`stage`／`verified_with`／`extra` | F3 | 選填 | 無人 |

**最少必填幾欄**：A 只填 argv（name 取檔名、description 猜）；**B `name`＋`exec.argv`＋`model.description`**；C 再強制 parameters／traits。建議 B——恰對應 key／OS／模型三個消費面；代價是參數型別只靠預設。

## 三、來源優先序

逐欄合併：**手填 > 程式自述 > aos 預設**；未自述不得推論成「安全」。
自述旗標：A 只探 `--metadata`（ai_core spec，`cli_spec.md` §2.3；但常撞第三方「寫入 metadata」）；**B 只探 `--metainfo`**（handy，碰撞低）；C 兩個都探（可能誤觸第三方 mutation）。建議 B；aos 自家子命令以 `--metainfo` 為準、兼收 `--metadata`；第三方要 `probe --compat-metadata` 才試後者。

| 級 | 探測 | 成功條件 | `meta.source` |
|---|---|---|---|
| 1 | `<argv> --metainfo`，stdin 關、短 timeout | exit 0、stdout 是 JSON object、`description` 非空 | `metainfo` |
| 2 | 讀 `argv[0]` 文字腳本檔頭 | shebang 後第一個非空註解／docstring 行 | `header` |
| 3 | 要求 `--description TEXT` | 非空 | `manual`（優先序最高） |

handy 08-06 已把 metainfo 降級成「LLM 自己讀腳本」——自述是便利來源，不是門票。

## 四、指令與白名單

`aos tool add <name> [--description T] [--args …] [--stdin …] [--replace] -- <argv...>`：驗 name／argv → 探 `--metainfo` → 逐欄合併 → 已存在且無 `--replace` 就拒 → tmp＋rename。argv token 原樣存、不拆詞（同 PROTOCOL §2）。
子命令：A 只 `add/ls/rm`；**B 加 `probe`（唯讀印候選 JSON）**；C 加 `export --format openai|mcp`。建議 B，`export` 延後到 `aos llm --tools` 之後。
白名單：`agents/<name>/tools.json` 退成 `["sh","ls"]`；缺檔＝全部可用、`[]`＝全禁；未知 name 於 step 報錯。**是菜單不是沙盒。**
LLM 類工具：A 不強制；**B 只強制 `meta.predictability: low`**；C 強制 F3 整組 meta。建議 B（零成本，符合新定義）；代價是粗粒度，`verified_with` 有實測才補。

## 五、範例（9 個真實程式，一行一項）

```json
[
{"name":"ls","exec":{"argv":["ls"],"args":"list","stdin":"none"},"model":{"description":"列出檔案或資料夾資訊；args 是選項與路徑 token。"},"meta":{"source":"manual","guarantee":"idempotent","predictability":"high"}},
{"name":"grep","exec":{"argv":["grep"],"args":"list","stdin":"text","exit_codes":{"0":"matched","1":"no_match","2":{"meaning":"error","retryable":false}}},"model":{"description":"以 PATTERN 搜尋檔案或 stdin；args 至少給 pattern。"},"meta":{"source":"manual","guarantee":"idempotent","predictability":"high"}},
{"name":"jq","exec":{"argv":["jq"],"args":"list","stdin":"text"},"model":{"description":"用 filter 處理 stdin 或檔案裡的 JSON；args 第一個非選項是 filter。"},"meta":{"source":"manual","guarantee":"idempotent","predictability":"high"}},
{"name":"git","exec":{"argv":["git"],"args":"list","stdin":"text"},"model":{"description":"執行 git 子命令，可讀可改 repo；args 第一個 token 是 subcommand。"},"meta":{"source":"manual","state":"stateful_external","guarantee":"none","predictability":"high"}},
{"name":"aos-deliver","exec":{"argv":["aos","deliver"],"args":"list","stdin":"none","exit_codes":{"0":"ok","1":"io_or_parse","2":"usage"}},"model":{"description":"把 inst JSON 或 `--` 後的 argv 原子投遞到某世界的 inbox；args 開頭可給 folder。"},"meta":{"source":"manual","state":"stateful_external","predictability":"high"}},
{"name":"aos-say","exec":{"argv":["aos","say"],"args":"list","stdin":"none"},"model":{"description":"把所有 args 接成一則訊息送給目前世界唯一的 agent。"},"meta":{"source":"manual","state":"stateful_external","predictability":"high"}},
{"name":"aos-llm","exec":{"argv":["aos","llm"],"args":"list","stdin":"text","timeout_ms":120000,"env_allow":["PATH","AOS_LLM_URL","AOS_LLM_MODEL","AOS_LLM_KEY"]},"model":{"description":"把 stdin prompt 送到 OpenAI 相容端點，stdout 回文字。慢、不確定，能查表就別用。"},"meta":{"source":"manual","predictability":"low","network":true,"stage":"runtime"}},
{"name":"aos-run-sub","exec":{"argv":["aos","run"],"args":"list","stdin":"none"},"model":{"description":"推子世界一步；args 必須是 [sub,\"--step\",\"1\"]，sub 是子世界資料夾。"},"meta":{"source":"manual","state":"stateful_external","predictability":"medium"}},
{"name":"llme","exec":{"argv":["llme"],"args":"list","stdin":"text","env_allow":["PATH","LLME_CONFIG_DIR","LLME_LLM"]},"model":{"description":"依 args 第一個 endpoint 選設定，其餘參數與非 TTY stdin 轉交 llm。"},"meta":{"source":"manual","predictability":"low","network":true,"stage":"runtime"}}
]
```

填法依據：`ls`／`grep`／`jq` 本機 `--help`（grep exit 1＝沒中）；`git` 是 dispatcher，保守標 stateful，精準契約應一個 subcommand 一項；`aos deliver` 見 `core/loop/src/deliver_cli.cpp:14–18`；`aos say` 見 `run_top.cpp:20–34`；`aos llm` 見 `core/llm/src/run.cpp:13–24`；`aos run <sub> --step 1` 見 [nested-worlds](../nested-worlds.md)；`llme` 依 `cllm/apps/HANDY-PORT-SPEC.md` §1。
`aos-run-sub` 標 `medium`：機制可預期，子世界裡 agent 做什麼不可預期。
