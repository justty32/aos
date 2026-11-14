> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# description — 表述：給模型看的一行、給機器看的 JSON、呼叫格式

← [tools/README](README.md)｜登記表 [registry](registry.md)｜迴路 [call-loop](call-loop.md)

現況：`system_prompt` 只渲染 `- <name>: <description>`（`core/agent/src/tools.cpp:38–53`），模型末行手寫 `{"tool":"…","args":"…"}`。
術語：**可預期性**（`predictability`）＝結果是否符合人類預期，**不是**同輸入同輸出；值域 `high|medium|low`，缺席＝未知（不是 high）。

## 一、給模型看的一行

| 選項 | 樣子 | 代價 |
|---|---|---|
| **A 精簡文字行**（F2） | `- ls (args: list, stdin: none, 可預期性: high): 列出資料夾內容；args 例如 ["-la","."]` | 最相容、prompt 最短；模型可能漏欄位或寫錯字串 |
| B 一工具一行 JSON（F3 三欄） | `{"name":"ls","description":"…","parameters":{…}}` | 結構明確；token 多，笨模型會把「定義 JSON」誤當「呼叫 JSON」 |
| C 原生 tool calling：`aos llm --tools` 把 `name/description/parameters` 送後端 | 模型回 tool_call，不手寫末行 | 最標準；要先做 `aos llm --tools`，各後端能力不等 |

cllm 的結論（`backend-structured-output.md` §37–48）：OpenAI 相容只保證 wire format 不保證能力；tool calling 是三種結構化輸出裡最通用，但仍要「client 端驗證＋retry/guard」。對 qwen 9B：**MVP 用 A＋client 嚴格解析＋結構化退回**（[call-loop 三](call-loop.md)）；`aos llm --tools` 對 LM Studio 真打過一次後再升 C。
可預期性要不要進那一行：A 不放；**B 每行都放**；C 只標 low。建議 B，並在 prompt 寫一句定義；代價是 token，且模型可能誤讀成成功率。

## 二、給機器看的完整 JSON

A 登記項本身就是 OpenAI／MCP 格式；**B 登記項是 aos 自己的形狀，`aos tool export --format openai|mcp` 匯出投影**；C 只存文字、呼叫時臨時生 schema。
建議 B——登記項是唯一真相，外部格式是投影（照 F3 的 `exec`／`model` 兩層）。映射表（改自 ai_core `kb-ext/ext_04` §2）：

| aos 欄位 | OpenAI function | MCP tool | 備註 |
|---|---|---|---|
| `name` | `function.name` | `name` | 受外部命名限制 |
| `description` | `function.description` | `description` | |
| `args` 型別（list／string／none）→ 生成 `parameters` | `function.parameters` | `inputSchema` | 只描述 `args` 是 array／string，**不**升格成 CLI binding |
| `predictability` | 無標準欄位；sidecar 或摘要進 description | `_meta` | **不是** `nondeterministic` |
| `guarantee`／`exit_codes` | 無；sidecar | `_meta` | 可否安全重試 |

OpenAI function 物件別塞非標準欄位，會被後端拒收。

## 三、呼叫格式改 argv list

現況 `expand_argv` 逐字代入不拆詞（`tools.cpp:92–105`），`"-la ."` 變一個參數。

| 選項 | 呼叫行 | 代價 |
|---|---|---|
| A 維持字串 | `{"tool":"ls","args":"-la ."}` | 只有 `sh` 吃得下；其餘工具實際上壞的 |
| B 一律 list | `{"tool":"ls","args":["-la","."]}` | `sh` 要整串，得特例 |
| **C 依登記 `args: list\|string\|none`** | list：逐項接在固定前綴後；string：整串當一個元素（現行語意，只給 `sh`）；none：不收 | parser 與舊 `tools.json` 要相容遷移 |

建議 C。list 模式保留空白、引號、萬用字元，**不經 shell**。

**具名槽 `{param}` 是不是回頭走 tooljson 失敗路？** 界線：
- 可接受（F3 的最小版）：`["git","-C","{folder}","status"]`——每個槽只替換**一個已驗證的 argv token**，不重排、不加旗標、不拆字串。
- 不接受（＝使用者判失敗的 tooljson）：由任意 JSON object 推導 positional／`--flag value`／repeat／預設值／互斥／shell quoting 的**綁定編譯層**。
- `parameters` 只用來驗 `args` 是 array／string 與元素型別，不當 CLI binding compiler。
選項：**A MVP 只做固定前綴＋list/string/none**；B 之後加有限 token 替換；C 不做。

## 四、表述從哪來

| 來源 | 優點 | 代價 |
|---|---|---|
| 手填（`aos tool add --description`） | 任何 POSIX 程式都能登記、最貼使用目的 | 會過期 |
| `--metainfo`／`--metadata` 自述抄入 | 機讀、可生 `parameters` 與行為欄 | 多數程式不支援；probe 要關 stdin、限時、只信 exit 0 的 JSON |
| 模型自己 `cat .aos/tools/<name>/help.txt` | 長說明、例子不佔 prompt（handy 08-06「LLM 自己讀」） | 只能在已知工具存在後用；內容視為不可信資料 |

建議三者並存、優先序**已審核的手填 → 自述快照 → help.txt**，登記項記 `source`。模型可以摘要、不可成為登記表真相。細節與降級表見 [registry 三](registry.md)。
