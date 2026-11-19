# `agent.py` 長什麼樣：SYSTEM／TOOLS／LLM／FSM 各怎麼宣告、各自生出定義夾裡哪份檔、哪些檔它不管

← [README](README.md)｜上一份：[02-現況-定義夾與agent_def](02-現況-定義夾與agent_def.md)｜下一份：[04-agent-py-兩個例子](04-agent-py-兩個例子.md)

## 先講結論

1. `agent.py` 放在定義夾裡，跟 `tool.py` 同一個寫法：固定開頭、大寫常數、最後一行 `ag.main(...)`。lib 叫 `aos/agent_spec.py`，慣用縮寫 `ag`（對照 `tool_spec`／`ts`）。
2. 它生的是**骨架與內容**那幾份 json 與 `system.txt`；**格的 Python、`.env`、stack 裡的一切、daemon 表上的設定，它都不管**。
3. 生出來的東西是普通的 aos 定義夾，**產出之後就跟 `agent.py` 沒關係**（使用者 11-19：「好比C語言和.o之間的關係」，[10](10-使用者裁定.md)）：夾裡不留任何「我是生成的」記號或帳，沒有 lib 專用的格式，把 `agent.py` 刪掉照樣能跑、能改。
4. 路徑一律原樣吐指示詞（`{"$env": "AOS_HOME", …}`），不在生成時展開成這台機器的絕對路徑。

## 宣告與生成檔的對照

| 宣告 | 寫法 | 生出什麼 |
|---|---|---|
| `DESCRIPTION` | 一句英文 | `_metainfo.json` 的 `summary`（只動自己的鍵，見下）；各份 json 的 `description`；`README.md` 不在時種一份 |
| `SYSTEM` | 字串；或 `ag.by_hand("system.txt")` | `system.txt` |
| `TOOLS` | 串列：`ag.pack("look")`（疊一個工具包）、`ag.tool("名", 路徑)`（單一個工具）、`ag.no("名")`（從包裡拿掉） | `tools.json`（`$override` 與 `tools` 兩格） |
| `LLM` | dict，如 `{"model": "luna"}` | `llm.json` |
| `FSM` | `ag.fsm("起點", [ag.state("名", argv, {結束碼: "下一格"}), …])`；或 `ag.stock_fsm()`＝借 agent-fsm 範本那四格（使用者第 6 題選借） | `fsm.json`，**外加整副骨架**：`_entry`、`body.json`、`loop.json`、`interfaces.json` |
| `META`（選） | dict，如 `{"cost": {"time_ms": 60000}, "resource": ["llm"]}` | `_metainfo.json` 的那幾個鍵 |
| `INTERFACES`（選） | dict，蓋在預設上 | `interfaces.json` 多出或換掉的鍵（如 `aos-observed`） |
| `HOOKS`（選，第三刀） | dict 原樣；或「用範本那組」 | `hooks.json`，`loop.json` 多 `on_start`／`on_stop` |
| `FILES`（選，第三刀） | `{"ladder.json": {…}}` | 那個檔名，dict 原樣寫出 |

路徑的小工具：`ag.home("/lib/tools/base/read")` 吐 `{"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}`；`ag.env("AOS_WS", "/tools/x")` 同理換變數名。定義夾內的相對路徑（`"tools/math"`、`"idle.py"`）照寫。

## 三個設計決定

**一、有沒有宣告 `FSM`，決定骨架歸誰。** 宣告了＝整副骨架都由 `agent.py` 生（使用者要的「不必在那邊mkdir半天」）。沒宣告＝骨架照舊手寫或用 `agent_def new` 抄來，`agent.py` 只寫它宣告的那幾份內容檔，檔名照既有的 `interfaces.json` 找（跟 `agent_def tools` 找檔的方法一樣）。後者讓沒有狀態機的 eca 版接得上，排在第三刀（使用者第 3 題）。

**二、逃生門兩個。** 11-18 調查第 23 條說 lib 認得的東西一定比 aos 少。所以：`ag.by_hand("檔名")`＝「這份檔我自己手寫，`interfaces.json` 指到它就好，別生、別蓋」；`FILES`＝「這份 dict 原樣吐成這個檔」。lib 不認得的 key 寫在 dict 裡一律照吐。

**三、生成前先驗，錯誤指回 `agent.py`。** `ag.state()`、`ag.tool()` 寫錯時照 `ts.param()` 的做法先記著，`main` 再報一行 `SpecBad`，訊息寫怎麼改。驗的內容不自己發明，照讀的那一方的規矩：

| 驗什麼 | 規矩出處 |
|---|---|
| FSM：起點在表上、每個「下一格」在表上、結束碼是 0～255 或 `*`、有 0 或 `*` | aos-fsm 開跑時查表的規則（今天要跑起來才報 `CfgBad`） |
| TOOLS：每個工具有路徑、名字不重複 | `defs check` 的「each tool must declare a path」 |
| LLM：`model` 是字串、key 在 `llm_keys` 裡 | `defs check`、`interfaces.json` 的 `llm_keys` |
| DESCRIPTION 非空 | `defs check` 的 summary |

原則：**lib 先查的 ⊇ `defs check` 對那幾份檔查的**。生出來的東西如果還被 `defs check` 嫌，那是 lib 的錯，照實報、不替它圓。狀態機那一塊是今天 `agent_def check` 完全沒查的（見 [02](02-現況-定義夾與agent_def.md)），所以這裡是淨賺。

## 重生時每份檔怎麼寫

| 檔 | 規則 |
|---|---|
| `agent.py` 有宣告的那幾份（上表） | **直接蓋**。不比對、不問、不留舊的 |
| `_metainfo.json` | **不整份重寫**：只設自己的鍵（`summary`、`META` 給的），其他鍵原樣留著。理由：`agent_def new` 會在裡面寫 `lineage`（從哪抄來），人也可能加自己的鍵 |
| `README.md` | **種子檔**：不在的時候用 `DESCRIPTION` 寫一行（`defs check` 要求第一行非空），在了就不碰 |
| 其他所有檔 | 不碰。`agent.py` 拿掉某個宣告後，那份舊檔留在原地，不替人刪 |

## 它不管的東西

| 東西 | 為什麼不管 |
|---|---|
| `.env` | 這台機器的私事（金鑰、PATH），不該寫進會進 git 的原始碼 |
| 格的程式（`idle.py`、`brain.py`…）、`screen/`、`compact_hook` | 是肉不是骨架；借範本的（指過去），或抄一份手改 |
| stack 裡的全部：kit 寫的那兩份、`self_*` 的差異、歷史、佇列、`stage.txt` | 那是記憶體，不是原始碼（11-18 調查第 7 條） |
| daemon 表上的 `--limits`、`--envs`、`--kit`、掛在誰底下 | 那是部署，不是程式（第 11 條）；庚只生定義 |
| `subagents.json`、`cli.json`、`tools_sub.json` | 第一刀不管（照舊手寫）；第三刀可用 `FILES` 原樣吐 |

## 命令列與函式兩種用法

| 旗標 | 做什麼 |
|---|---|
| `--write-defs [資料夾]` | 重生（直接蓋）；資料夾沒給＝`agent.py` 所在的夾 |
| `--defs` | 把會生成的全部內容印成一個 JSON（`{"檔名": 內容}`），不寫檔。想先看會蓋成什麼、或拿去跟夾裡的比，用這個；己（總覽）之後也可以直接吃 |
| 都沒有 | 印用法。**不會把 agent 跑起來**——「描述本身就是入口」是丁案，不在庚的範圍 |

lib 內部分成兩個可以單獨叫的函式：「算出全部內容」（回 `{"檔名": 內容}`）與「寫進某個夾」；`ag.main` 只是薄薄一層旗標。這樣在 Python 互動環境裡也能直接叫，是替除錯那條線留的（[11](11-跟除錯那條線的接點.md)）。

`_entry` 仍然是生成的那張掛上 daemon 的單子，不是 `agent.py`。
