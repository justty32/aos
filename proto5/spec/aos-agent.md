# aos-agent：把一個 agent 資料夾走一格（程式規範，**草稿**）

← [proto5 README](../README.md)｜什麼是 agent 資料夾在 [agent.md](agent.md)；問模型那一步是 [aos-llm-ask.md](aos-llm-ask.md)；跑工具靠 [inst-posix.md](inst-posix.md)

> **最精簡的標準**（使用者定的）：缺的東西之後遇到了再補。這份只講「叫一次 aos-agent 到底做什麼」。
> 不記修訂記錄。**跑工具那塊還沒想好**（使用者：看起來還需要一支 aos-tool-exec），§3 的 `act` 先佔位。

一句話：**`aos-agent [dir]` 把 `dir` 這個 agent 資料夾的狀態機走一格，然後退出**——跟 aos-exec 一樣是
「一次做一件事」的程式，反覆叫它是 kernel 的事。它主要處理三件事：**收輸入**（`input`）、**等檔案**
（`waits`）、**逾時**（等太久怎麼辦）。

## 1. 用法

```
aos-agent [dir]
```

- `dir` 留空＝`.`（跟 aos-exec 一樣）。`dir` 必須是 agent 資料夾（有 `info.json`、`_metainfo._type`
  是 `llm_agent`），不是＝`NotAnAgent`。
- 沒有別的旗標、沒有子命令（`init`／`start`／`stop`／`tools …` 那些之後再說）。

## 2. `state.json` 裡 aos-agent 用的欄位：`input`、`waits`

`state.json` 本身（`state` 那一格、每格解指示詞、改寫時只動 `state`）照 [agent.md §4](agent.md)。
aos-agent 另外看兩格，都是「指到外面的檔」：

```json
{
  "state": "idle",
  "input": "input.json",
  "waits": {"$opt": ["consume", "any"], "$val": ["tool_result.json", "inbox/"]}
}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `input` | 路徑、路徑陣列、或 `$opt` 選項物件 | `input.json` | 輸入從哪來：指到的東西會被接進記憶（§2.1），接完清掉 |
| `waits` | 路徑、路徑陣列、或 `$opt` 選項物件 | 沒寫＝沒東西可等，`wait` 格進不去 | 在 `wait` 格時盯哪些檔：條件到了就切回 `think`（§2.2） |

兩格的值長法一樣：

- **路徑字串**：一個檔；**資料夾**（結尾 `/`、或本來就是資料夾）＝裡面所有 `*.json` 照檔名排序當一串。
- **陣列**：依序處理，順序＝陣列順序。
- **`$opt` 選項物件**：`$val` 是上面兩種之一，`$opt` 是選項名或名字陣列（跟 inst 一樣的慣例）；各格
  認得的選項在下面。不認得＝`UnknownOption`。
- 路徑相對於 agent 資料夾。

### 2.1 `input`：輸入怎麼進記憶

指到的每個檔，內容可以是三種之一，都變成訊息接在記憶尾巴：

| 檔裡是 | 變成 |
|---|---|
| 字串 `"看看資料夾裡有什麼"` | 一則 `{"role": "user", "content": …}` |
| 一則訊息物件 `{"role": …}` | 原樣一則（`role` 照 [aos-llm-ask.md §2.3](aos-llm-ask.md) 驗，不合＝`MessageInvalid`） |
| 訊息陣列 | 原樣一串 |

- 檔不存在、或內容是空陣列＝沒有輸入。
- **清掉**：讀進去之後把檔 rename 成 `<原名>.done`（有舊的就蓋掉），不原地清空——這樣別人在 agent
  讀完到清掉之間又丟一則也不會被吃掉。
- 選項：

| 選項 | `$val` | 意思 |
|---|---|---|
| `keep` | 必帶 | 讀了不清掉（測試用；小心 `idle` 會一直有事） |
| `delete` | 必帶 | 讀了直接刪，不 rename |

（沒選＝rename 成 `.done`。`keep`／`delete` 互斥。）

### 2.2 `waits`：什麼叫「到了」

`wait` 格每次被叫到就檢查一遍 `waits` 指到的檔；「到了」就把 `state` 切回 `think`。

| 選項 | `$val` | 意思 |
|---|---|---|
| `exists` | 必帶 | 檔在就算到（**預設**）。資料夾＝裡面有任何一個 `*.json` |
| `mtime` | 必帶 | 檔的修改時間比「開始等的時間」新才算到；開始等的時間記在 `state.json` 的 `wait_since`（aos-agent 進 `wait` 格時寫、離開時清） |
| `consume` | 必帶 | 到了之後把那個檔 rename 成 `<原名>.done`（資料夾＝裡面的檔都 rename）；不然檔一直在，下次沒得等 |
| `any` | 必帶 | 陣列裡**任一個**到了就算到 |
| `all` | 必帶 | 陣列裡**全部**都到才算到（**預設**） |
| `timeout_ms` | — | （還沒想好怎麼寫；逾時之後去哪一格、要不要記錯，見 §5） |

`exists`／`mtime` 互斥、`any`／`all` 互斥。等到的檔**內容怎麼進記憶**（例如 `tool_result.json` 變成
`tool` 訊息）跟 aos-tool-exec 一起定，這一版只切格。

## 3. 走一格到底做什麼

先讀驗（[agent.md](agent.md)：`info.json`／`state.json` 每格解指示詞、指到的檔原樣讀；`state.json`
不存在＝`idle`）；讀驗不過＝這格沒走，退出碼 1、什麼都不寫。過了就照 `state` 做**一格**：

| 現在是 | 做什麼 | 寫回 `state` | 退出碼 |
|---|---|---|---|
| `idle` | 看 `input`：有東西 → 接進記憶、清掉 | `think` | 0 |
| `idle` | 沒東西 | 不變 | **101** |
| `think` | 用 [aos-llm-ask](aos-llm-ask.md) 的函式庫問一次，`choices[0].message` 接在記憶尾巴 | 有 `tool_calls` → `act`；沒有（回話）→ `idle` | 0 |
| `think` | 引擎失敗（aos-llm-ask 的「3」那類）→ stderr 一行、記憶不動 | 不變（下一格重試） | 0 |
| `act` | **還沒想好**：把 `tool_calls` 交給 aos-tool-exec（還沒設計）跑，結果之後會落在 `waits` 指的檔 | `wait` | 0 |
| `wait` | 照 §2.2 檢查 `waits`：到了 | `think` | 0 |
| `wait` | 沒到 | 不變 | **101** |
| `wait` | `waits` 沒寫卻進了這格 | — | 1（`StateInvalid`） |

- 一格只寫：`state.json`（原始 JSON 只動 `state`、`wait_since`）、記憶檔（整份重寫）、`input`／`waits`
  指到的檔（rename／刪）；都是先 `.tmp` 再 rename。
- `$env` 讀的是 aos-agent 自己的環境；`$ref` 相對路徑以 agent 資料夾為中心。
- 同一個 agent **不要同時跑兩份**（沒有鎖）。

## 4. 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 這格做了事（換了格、問了模型、或引擎失敗但會重試） |
| 101 | 在等（`idle` 沒輸入、`wait` 沒到） |
| 1 | 讀驗錯誤（[agent.md §5](agent.md)、[aos-llm-ask.md §2](aos-llm-ask.md)、[directives.md §6](directives.md) 的代號）：stderr 一行 `aos-agent: <代號>: <白話>`，什麼都不寫 |
| 2 | 用法錯（旗標不認得、`dir` 不存在） |

## 5. 沒管的、還沒想好的

- **跑工具**：aos-tool-exec 還沒設計（使用者的話）。它至少要定：`tool_calls` 怎麼交給它、結果落在哪個檔、
  那個檔怎麼變成 `tool` 訊息接回記憶。
- **逾時**：`waits` 等太久去哪一格（回 `think` 讓模型知道？回 `idle`？）、要不要記錯幾次——使用者說
  這是 aos-agent 的核心之一，但還沒拍。
- 誰把輸入丟進 `input`、誰去讀回話（aos-user 之類）；反覆叫、放進 kernel；鎖；記憶太長。

## 我自己選的、使用者可以推翻的

1. `input` 沒寫＝`input.json`；檔裡可以是字串／一則／一串。
2. 清掉＝rename 成 `.done`；`keep`／`delete` 兩個選項。
3. `waits` 的選項名：`exists`（預設）／`mtime`／`consume`／`any`／`all`（預設）；`mtime` 靠 `state.json` 的 `wait_since`。
4. `think` 直接看 `tool_calls` 決定去 `act` 還是 `idle`（少走一格）。
5. 逾時、`act`、等到的檔怎麼進記憶：全部留空。
