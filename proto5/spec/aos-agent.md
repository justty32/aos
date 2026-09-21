# aos-agent：把一個 agent 資料夾走一格（程式規範，**草稿**）

← [proto5 README](../README.md)｜什麼是 agent 資料夾在 [agent.md](agent.md)；問模型那一步是 [aos-llm-ask.md](aos-llm-ask.md)；跑工具靠 [inst-posix.md](inst-posix.md)

> **最精簡的標準**（使用者定的）：缺的東西之後遇到了再補；不記修訂記錄。
> 這份講「叫一次 aos-agent 到底做什麼」：先看**門**（`waits`），再走**一格**（`state`）。
> 三個入口（`state`、`input`、`waits`）都留了擴充空間，之後加選項就好。

一句話：**`aos-agent [dir]` 先看 `waits` 這道門——還在等就退出；門開了就把狀態機走一格，然後退出。**
跟 aos-exec 一樣是「一次做一件事」的程式，反覆叫它是 kernel 的事。

## 1. 用法

```
aos-agent [dir]
```

- `dir` 留空＝`.`（跟 aos-exec 一樣）。`dir` 必須是 agent 資料夾（有 `info.json`、`_metainfo._type`
  是 `llm_agent`），不是＝`NotAnAgent`。
- 沒有別的旗標、沒有子命令（`init`／`start`／`stop`／`tools …` 那些之後再說；`pause`／`continue`
  已經不用另外做，見 §2.3）。

## 2. `state.json` 裡 aos-agent 用的三格

`state.json` 本身（每格解指示詞、程式改寫某格時只動那格）照 [agent.md §4](agent.md)。

```json
{
  "state": "idle",
  "input": "input.json",
  "returns": "returns/",
  "waits": [{"$opt": "consume", "$val": "tool_result.json", "since": "2026-09-21T16:20:00", "timeout_ms": 60000}]
}
```

| 鍵 | 型別 | 沒寫時 | 誰動它 | 意思 |
|---|---|---|---|---|
| `state` | `idle`／`think`／`act` | `idle` | aos-agent | 狀態機走到哪（§3）。**沒有 `wait` 這一格**：等不是狀態，是門（§2.3） |
| `input` | 路徑、路徑陣列、或 `$opt` 物件 | `input.json` | 誰都能往裡塞；aos-agent 消化 | 輸入從哪來：指到的東西接進記憶（§2.1），接完清掉 |
| `returns` | 同上 | `returns/` | 非同步工具寫；aos-agent 消化 | 非同步工具跑完的結果從這回來（§2.1）。現在的精簡標準沒有非同步工具，這格先佔位 |
| `waits` | 同上 | 沒寫＝不用等 | 誰都能加一條；aos-agent 到了就劃掉 | 門：還有沒到的就不走這一格（§2.3） |

三格的值長法一樣：**路徑字串**（一個檔；資料夾＝裡面所有 `*.json` 照檔名排序）、**陣列**（依序）、
**`$opt` 物件**（`$val` 是前兩種之一，`$opt` 是選項名或名字陣列，跟 inst 一樣的慣例；不認得＝
`UnknownOption`）。路徑相對於 agent 資料夾。

### 2.1 `input`／`returns`：輸入怎麼進記憶

指到的每個檔，內容是三種之一，都變成訊息接在記憶尾巴：

| 檔裡是 | 變成 |
|---|---|
| 字串 | 一則 `{"role": "user", "content": …}` |
| 一則訊息物件 | 原樣一則（`role` 照 [aos-llm-ask.md §2.3](aos-llm-ask.md) 驗，不合＝`MessageInvalid`） |
| 訊息陣列 | 原樣一串 |

- 檔不存在、或空陣列＝沒有輸入。
- **收的順序**：先 `returns`、再 `input`。
- **清掉**：讀進去之後把檔 rename 成 `<原名>.done`（舊的蓋掉），不原地清空——別人在 agent 讀完到清掉
  之間又丟一則也不會被吃掉。選項 `keep`（讀了不清）、`delete`（直接刪），互斥。
- `returns` 回來的東西在記憶裡是 **`user` 訊息**（那個 call 的 `tool` 訊息位置已經被「已啟動」的收據
  占掉了，OpenAI 只有四種 role），內容由工具自己寫清楚是哪個 call 的結果。

### 2.2 記憶的順序規則

模型那邊的硬規定：一則 `assistant` 帶了 `tool_calls`，**下一次問之前每個 call 都要有一則 `tool`
訊息**，而且要緊接在後面。aos-agent 靠兩件事保證：`act` 一格內把每個 call 的 `tool` 訊息全部接完
（§3）；`idle` 收輸入時先 `returns` 再 `input`（§2.1）。

### 2.3 `waits`：門

`waits` 是一張**等待表**，空的或沒寫＝不用等。aos-agent 每次被叫，**第一件事**先看它：

- 表裡還有沒到的 → 這次什麼都不做（`state` 也不碰），退出碼 101。
- 全部到了 → 到了的每一條照選項處理、**從表裡劃掉**，然後才照 `state` 走一格。

誰要 agent 停下來等，誰就往表裡加一條：`act` 派了工具就加結果檔、外部程式要它等就加、人要它
**暫停**就加一條指到不存在的檔（例如 `continue.json`），要它**繼續**就 touch 那個檔——所以不用另外
做 `pause`／`continue`。

| 選項 | 意思 |
|---|---|
| `exists` | 檔在就算到（**預設**）。資料夾＝裡面有任何一個 `*.json` |
| `mtime` | 檔的修改時間比這條的 `since` 新才算到 |
| `consume` | 到了之後把檔 rename 成 `<原名>.done`（資料夾＝裡面的檔都 rename）；不然檔一直在，下次沒得等 |
| `any` | 陣列裡任一條到了就算整張到 |
| `all` | 全部到才算（**預設**） |

`exists`／`mtime` 互斥、`any`／`all` 互斥。每一條可以多帶兩個一般 key（指示詞機制忽略非 `$` 的
key）：`since`（aos-agent 加這條時寫的時間）、`timeout_ms`（逾時，§4）。

## 3. 走一格到底做什麼

先讀驗（[agent.md](agent.md)：`info.json`／`state.json` 每格解指示詞、指到的檔原樣讀；`state.json`
不存在＝`idle`）；讀驗不過＝這格沒走，退出碼 1、什麼都不寫。門開了（§2.3）就照 `state` 做**一格**：

| 現在是 | 做什麼 | 寫回 `state` | 退出碼 |
|---|---|---|---|
| `idle` | 收 `returns`、`input`（§2.1）：有東西就接進記憶、清掉 | `think` | 0 |
| `idle` | 沒東西 | 不變 | **101** |
| `think` | 用 [aos-llm-ask](aos-llm-ask.md) 的函式庫問一次，`choices[0].message` 接在記憶尾巴 | 有 `tool_calls` → `act`；沒有（回話）→ `idle` | 0 |
| `think` | 引擎失敗（aos-llm-ask 的「3」那類）→ stderr 一行、記憶不動 | 不變（下一格重試；上限見 §4） | 0 |
| `act` | 記憶尾巴那則 `assistant` 的每個 `tool_calls[i]`：照名字找工具、拿 `_meta` 當 inst 跑（`arguments` 字串原樣進 stdin、stdout 整段當結果），**每個 call 接一則 `tool` 訊息**（順序照 `tool_calls`）。找不到的工具＝`tool` 訊息「沒有這個工具：xxx」；退出碼非 0＝「工具 xxx 失敗（exit n）：」＋stdout；工具逾時＝「逾時」 | `think` | 0 |

- 一格只寫：`state.json`（原始 JSON 只動 `state`／`waits`）、記憶檔（整份重寫）、`input`／`returns`／
  `waits` 指到的檔（rename／刪）；都先 `.tmp` 再 rename。**先寫記憶、再寫 `state`**：崩在中間頂多
  重做一格。
- 跑工具是 import proto5 的 aos_exec／aos_inst，不是開 `aos-exec` 子進程（inst 在記憶體、stdin 要塞
  字串、stdout 要收回來——函式庫層要補一個入口）。
- `$env` 讀的是 aos-agent 自己的環境；`$ref` 相對路徑以 agent 資料夾為中心。
- 同一個 agent **不要同時跑兩份**（沒有鎖）。

## 4. 逾時：三處

| 哪裡 | 誰定 | 到了怎樣 |
|---|---|---|
| 跑一個工具 | 工具檔那個工具的 `timeout_ms`（沒寫＝60000） | 砍掉（照 inst 逾時規則），`tool` 訊息寫「逾時」，`act` 照走 |
| 問引擎 | `engine.timeout_ms`（HTTP 一次等多久）＋ `think` 連續失敗上限（`info.json` 的 `engine.retries`，沒寫＝5） | 到上限：往記憶接一則 `user`「引擎連續失敗 N 次」、回 `idle`，讓下一句話能重新觸發 |
| `waits` 的一條 | 那條的 `timeout_ms`（沒寫＝不逾時） | 劃掉這條、往 `input` 補一則 `user`「等 X 逾時」；門照常判 |

## 5. 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 這格做了事（換了格、問了模型、跑了工具、或引擎失敗但會重試） |
| 101 | 在等（`waits` 沒到、`idle` 沒輸入） |
| 1 | 讀驗錯誤（[agent.md §5](agent.md)、[aos-llm-ask.md §2](aos-llm-ask.md)、[directives.md §6](directives.md) 的代號）：stderr 一行 `aos-agent: <代號>: <白話>`，什麼都不寫 |
| 2 | 用法錯（旗標不認得、`dir` 不存在） |

## 6. 之後會有、現在不做的

- **非同步工具**：工具檔多一個 `async` 選項——`act` 啟動它就馬上接一則收據當 `tool` 訊息，工具跑在別的
  cpu／thread，跑完把結果寫到 `returns`（位置由 aos-agent 啟動它時用環境變數告訴它），下次 `idle`
  當 `user` 收進來。`returns` 那格就是為這個留的。
- 誰把輸入丟進 `input`、誰去讀回話（aos-user 之類的外部工具）；反覆叫、放進 kernel；鎖；記憶太長。

## 我自己選的、使用者可以推翻的

1. `input` 沒寫＝`input.json`、`returns` 沒寫＝`returns/`；檔裡可以是字串／一則／一串；清掉＝rename `.done`。
2. `waits` 是動態表：到了就劃掉；要「永遠等某個檔」的靜態門先不做（需要時加個 `keep` 選項）。
3. `think` 直接看 `tool_calls` 決定去 `act` 還是 `idle`；`act` 一格內把所有 call 跑完、`tool` 訊息全接上，所以不需要等。
4. 逾時的三個預設數字（工具 60 秒、引擎重試 5 次、`waits` 不逾時）跟「逾時＝補一則 `user`」這個做法。
5. 先寫記憶再寫 `state`。
