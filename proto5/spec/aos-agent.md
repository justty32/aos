# aos-agent：把一個 agent 資料夾走一格（程式規範，**草稿**）

← [proto5 README](../README.md)｜什麼是 agent 資料夾在 [agent.md](agent.md)；問模型那一步是 [aos-llm-ask.md](aos-llm-ask.md)；跑工具靠 [inst-posix.md](inst-posix.md)

> **最精簡的標準**（使用者定的）：缺的東西之後遇到了再補；不記修訂記錄。
> 這份講「叫一次 aos-agent 到底做什麼」：先看**門**（`waits`），再走**一格**（`state`）。

一句話：**`aos-agent [dir]` 先看 `waits` 這道門——還在等就退出；門開了就把狀態機走一格，然後退出。**
跟 aos-exec 一樣是「一次做一件事」的程式，反覆叫它是 kernel 的事。

## 1. 用法

```
aos-agent [dir]
```

- `dir` 留空＝`.`（跟 aos-exec 一樣）。`dir` 必須是 agent 資料夾（有 `info.json`、`_metainfo._type`
  是 `llm_agent`），不是＝`NotAnAgent`。
- 沒有別的旗標、沒有子命令。

## 2. `state.json` 裡 aos-agent 用的三格

`state.json` 本身（每格解指示詞、程式改寫某格時只動那格）照 [agent.md §4](agent.md)。

```json
{
  "state": "idle",
  "input": "input.json",
  "waits": ["tool_result.json"]
}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `state` | `idle`／`think`／`act` | `idle` | 狀態機走到哪（§3）。**沒有 `wait` 這一格**：等不是狀態，是門（§2.2） |
| `input` | 路徑或路徑陣列 | `input.json` | 輸入從哪來：指到的東西接進記憶（§2.1），接完清掉 |
| `waits` | 路徑、路徑陣列、或 `$opt` 物件 | 沒寫＝不用等 | 門：還有沒到的就不走這一格（§2.2） |

路徑相對於 agent 資料夾；資料夾＝裡面所有 `*.json` 照檔名排序。

### 2.1 `input`：輸入怎麼進記憶

指到的每個檔，內容是三種之一，都變成訊息接在記憶尾巴：

| 檔裡是 | 變成 |
|---|---|
| 字串 | 一則 `{"role": "user", "content": …}` |
| 一則訊息物件 | 原樣一則（`role` 照 [aos-llm-ask.md §2.2](aos-llm-ask.md) 驗，不合＝`MessageInvalid`） |
| 訊息陣列 | 原樣一串 |

- 檔不存在、或空陣列＝沒有輸入。
- **清掉**＝讀進去之後把檔 rename 成 `<原名>.done`（舊的蓋掉），不原地清空——別人在 agent 讀完到清掉
  之間又丟一則也不會被吃掉。

### 2.2 `waits`：門

`waits` 是一張**等待表**：一條或多條「等某個檔」。空的或沒寫＝不用等。

**一條長什麼樣**

```json
"waits": [
  "tool_result.json",                                             路徑：檔存在就算到
  {"$opt": "consume", "$val": "tool_result.json"},                到了順便 rename 成 .done
  {"$opt": ["mtime", "consume"], "$val": "log.json", "since": 1758443000},
  {"$opt": "any", "$val": ["a.json", "b.json"]},                  a、b 任一個到就算這條到
  {"$opt": "exists", "$val": "inbox/"}                            資料夾：裡面有任何一個 *.json
]
```

- 一條＝路徑字串，或 `{"$opt": 名字|[名字…], "$val": 路徑|[路徑…]}`（`$opt` 慣例跟 inst 一樣；不認得
  ＝`UnknownOption`、互斥＝`OptionConflict`）。`$val` 陣列＝這一條同時盯好幾個檔。
- `waits` 本身可以是一條（不包陣列）或一條陣列。路徑相對於 agent 資料夾；`.done` 結尾的檔不算。
- aos-agent 會**改寫這格**（劃掉到了的條目），所以 `waits` 在原始 JSON 裡必須是**字面的陣列**（或字面
  的一條），不能整格 `$ref` 出去（[agent.md §2](agent.md)；違反＝`FieldTypeMismatch`）。陣列裡**每一條**
  照樣解指示詞（路徑用 `$fmt` 拼、一條 `$ref` 到別的檔都行），劃掉是按索引劃原始那一條。`since` 這種
  不是 `$` 開頭的 key 指示詞機制會放著不動，agent 自己讀。

| 選項 | 「到了」的意思 | 備註 |
|---|---|---|
| `exists` | 檔存在。資料夾＝裡面有任何一個 `*.json` | **預設** |
| `mtime` | 檔的修改時間 > 這條的 `since`（epoch 秒，整數或小數） | 加這條的人寫 `since`；沒寫＝`FieldTypeMismatch`。跟 `exists` 互斥 |
| `consume` | （不改「到了」的判斷）到了之後把檔 rename 成 `<原名>.done`，資料夾＝裡面當時在的 `*.json` 都 rename | 不然檔一直在，下次沒得等 |
| `any` | `$val` 陣列裡**任一個**到＝這條到 | 跟 `all` 互斥；`$val` 只有一個路徑時無差 |
| `all` | `$val` 陣列裡**全部**到＝這條到 | **預設** |

**每次被叫，門怎麼判**（在讀驗之後、走格之前）：

1. 逐條檢查。**到了的那一條**：先照 `consume` 處理（`any` 的話只 consume 真的到了的那幾個檔），再
   **從表裡劃掉**。沒到的留著。
2. 表劃完還有剩 → 把改過的 `waits` 寫回 `state.json`（只動這格），退出碼 101，這次不走格。
3. 表空了 → 寫回（`waits` 變空陣列），接著照 `state` 走一格（§3）。

所以「一部分到了」的進度會留下來：到了的已經劃掉、consume 過，下次只等剩下的，不會重複判同一個檔。

**誰加、誰劃**：誰要 agent 停下來等，誰就往表尾加一條（外部程式、人、以後的 `act`）；aos-agent 只負責
到了就劃掉，自己不會加。人要它**暫停**就加一條指到不存在的檔（例如 `continue.json`），要它**繼續**就
touch 那個檔——不用另外做 `pause`／`continue`。

**容易踩的**：同一個檔同時列在 `waits` 跟 `input`（例如等 `tool_result.json` 出現、然後把它當輸入收）——
`waits` 那條**不要**開 `consume`，不然門一開檔就被 rename 成 `.done`，`idle` 就收不到了；讓 `input`
那邊去清。

## 3. 走一格到底做什麼

先讀驗（[agent.md](agent.md)：`info.json`／`state.json` 每格解指示詞、指到的檔原樣讀；`state.json`
不存在＝`idle`）；讀驗不過＝這格沒走，退出碼 1、什麼都不寫。門開了（§2.2）就照 `state` 做**一格**：

| 現在是 | 做什麼 | 寫回 `state` | 退出碼 |
|---|---|---|---|
| `idle` | 收 `input`：有東西就接進記憶、清掉 | `think` | 0 |
| `idle` | 沒東西 | 不變 | **101** |
| `think` | 用 [aos-llm-ask](aos-llm-ask.md) 的函式庫問一次，`choices[0].message` 接在記憶尾巴 | 有 `tool_calls` → `act`；沒有（回話）→ `idle` | 0 |
| `think` | 引擎失敗（aos-llm-ask 的「3」那類）→ stderr 一行、記憶不動 | 不變（下一格重試） | 0 |
| `act` | 記憶尾巴那則 `assistant` 的每個 `tool_calls[i]`：照名字找工具、拿 `_meta` 當 inst 跑（`arguments` 字串原樣進 stdin、stdout 整段當結果），**每個 call 接一則 `tool` 訊息**（順序照 `tool_calls`）。找不到的工具＝「沒有這個工具：xxx」；退出碼非 0＝「工具 xxx 失敗（exit n）：」＋stdout；`_meta` 那份 inst 解不開／跑不起來（aos-exec 的 125 那類）＝「工具 xxx 跑不起來：」＋那一行錯誤。三種都只是給模型看的 `tool` 訊息，不算 agent 的錯 | `think` | 0 |

- **為什麼 `act` 不用等**：模型那邊的硬規定是一則 `assistant` 帶了 `tool_calls`，下一次問之前每個 call
  都要有一則 `tool` 訊息緊接在後面。`act` 一格內全部跑完接上，就永遠不會違反。
- 一格只寫：`state.json`（原始 JSON 只動 `state`／`waits`）、記憶檔（整份重寫）、`input`／`waits`
  指到的檔（rename）；都先 `.tmp` 再 rename。**先寫記憶、再寫 `state`**：崩在中間頂多重做一格。
- 跑工具是 import proto5 的 aos_exec／aos_inst，不是開 `aos-exec` 子進程（inst 在記憶體、stdin 要塞
  字串、stdout 要收回來——函式庫層要補一個入口）。
- `$env` 讀的是 aos-agent 自己的環境；`$ref` 相對路徑以 agent 資料夾為中心。
- 同一個 agent **不要同時跑兩份**（沒有鎖）。

## 4. 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 這格做了事（換了格、問了模型、跑了工具、或引擎失敗但會重試） |
| 101 | 在等（`waits` 沒到、`idle` 沒輸入） |
| 1 | 讀驗錯誤（[agent.md §5](agent.md)、[aos-llm-ask.md §2](aos-llm-ask.md)、[directives.md §6](directives.md) 的代號）：stderr 一行 `aos-agent: <代號>: <白話>`，什麼都不寫 |
| 2 | 用法錯（旗標不認得、`dir` 不存在） |

## 5. 之後會有、現在不做的

- **非同步工具**：工具檔多一個 `async` 選項——`act` 啟動它就馬上接一則收據當 `tool` 訊息，工具跑在別的
  cpu／thread，跑完把結果寫進 `input`（當 `user` 訊息回來；順序沒限制，因為不是 `tool` 訊息）。
- **逾時**：工具跑太久要不要砍（現在不砍，跑多久等多久）、引擎連續失敗幾次要停、`waits` 等太久要怎樣——之後再定。
- 誰把輸入丟進 `input`、誰去讀回話（aos-user 之類的外部工具）；反覆叫、放進 kernel；鎖；記憶太長。

## 我自己選的、使用者可以推翻的

1. `input` 沒寫＝`input.json`；檔裡可以是字串／一則／一串；清掉＝rename `.done`。
2. `waits` 是動態表：到了就劃掉；要「永遠等某個檔」的靜態門先不做。
3. `think` 直接看 `tool_calls` 決定去 `act` 還是 `idle`；`act` 一格內跑完所有 call。
4. 先寫記憶再寫 `state`。
