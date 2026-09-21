# aos-agent：把一個 agent 資料夾走一格（程式規範，**草稿**）

← [proto5 README](../README.md)｜資料夾長什麼樣在 [agent.md](agent.md)；跑工具靠 [inst-posix.md](inst-posix.md)／[exec.md](exec.md)

> **最精簡的標準**（使用者定的）：缺的東西之後遇到了再補。這份只講「叫一次 aos-agent 到底做什麼」。
> 不記修訂記錄。

一句話：**`aos-agent [dir]` 把 `dir` 這個 agent 資料夾的狀態機走一格，然後退出**——跟 aos-exec 一樣是
「一次做一件事」的程式，反覆叫它是 kernel 的事。

## 1. 用法

```
aos-agent [dir]
```

- `dir` 留空＝`.`（跟 aos-exec 一樣）。`dir` 必須是 agent 資料夾（有 `info.json`、`_metainfo._type`
  是 `llm_agent`），不是＝`NotAnAgent`。
- 沒有別的旗標、沒有子命令。`init`／`start`／`stop`／`tools …` 那些（[thinking/aos-agent.md](../../thinking/aos-agent.md)）
  之後再說。

## 2. 輸入從哪來、回話回到哪：**記憶就是信箱**

沒有 inbox／outbox。要跟 agent 說話，就**往它的記憶（`history` 指到的檔）尾巴加一則 `user` 訊息**；
它的回話就是記憶尾巴那則 `assistant` 訊息，誰問的誰自己去讀。所以：

- `idle` 看記憶最後一則：是 `user` → 有事，進 `think`。
- `act` 的回話＝那則 `assistant` 留在記憶裡，不另外寫到哪。

（這是目前最省的做法：不用新檔、不用新格式。之後要信箱再加。）

## 3. 走一格到底做什麼

先讀驗（照 [agent.md](agent.md)：`info.json` 每格解指示詞、`state.json` 與指到的檔原樣讀、工具檔
合併；`state.json` 不存在＝`idle`）；讀驗不過＝這格沒走，退出碼 1、什麼都不寫。過了就照 `state`
做**一格**：

| 現在是 | 做什麼 | 寫回 `state` | 退出碼 |
|---|---|---|---|
| `idle` | 記憶最後一則是 `user` → 什麼都不做，只換格 | `think` | 0 |
| `idle` | 不是（空的、或最後是 `assistant`）→ 沒事 | 不變 | **101** |
| `think` | 組請求（`system` 有內容就補一則 `system` 在最前面 ＋ 整份記憶 ＋ 去掉 `_` key 的工具表）打 `engine`；拿到 `choices[0].message` 就接在記憶尾巴（＝aos-llm-ask 做的事，見 [aos-llm-ask.md](aos-llm-ask.md)；aos-agent import 它的函式庫） | `act` | 0 |
| `think` | 引擎失敗（HTTP 錯、逾時、回來沒有 `choices[0].message`）→ stderr 一行、記憶不動 | 不變（下一格重試） | 0 |
| `act` | 記憶最後一則 `assistant` 有 `tool_calls` → 照順序每個跑一次（§4），每個結果接一則 `tool` 訊息 | `think` | 0 |
| `act` | 沒有 `tool_calls`（回話，`content` 空也算） | `idle` | 0 |
| `wait` | 這一版進不去這格；`state.json` 裡寫著 `wait` 就當 `StateInvalid` | — | 1 |

- 一格只寫兩個檔：`state.json`（`{"state": …}` 整份重寫）、記憶檔（整份重寫）；都是先 `.tmp` 再
  rename。`info.json` 永遠不寫。
- `$env` 讀的是 aos-agent 自己的環境；`$ref` 相對路徑以 agent 資料夾為中心。
- 同一個 agent **不要同時跑兩份**（沒有鎖）。

## 4. 跑一個工具

模型的一則 `tool_calls[i]`：

1. `function.name` 在合併表裡找；找不到 → 不跑，`tool` 訊息 `content`＝`沒有這個工具：<名字>`。
2. 找到了就拿它的 `_meta` 當一份 posix inst 跑（base＝agent 資料夾，`stdin`＝`function.arguments`
   那個字串原樣，`stdout` 由 aos-agent 收；`_meta` 寫了 `stdin`／`stdout` 讀驗階段就已經是 `ToolInvalid`）。
3. 退出碼 0 → `content`＝stdout 整段；非 0 → `content`＝`工具 <名字> 失敗（exit <碼>）：`＋stdout。
   inst 自己解不開／跑不起來（aos-exec 那套的 125）也算這種，`content` 是那一行錯誤。
4. `tool` 訊息一定帶 `tool_call_id`＝`tool_calls[i].id`。

跑工具是 import proto5 的 aos_exec／aos_inst 做的，不是開一個 `aos-exec` 子進程（`_meta` 在記憶體裡、
不是檔案；stdin 要塞字串、stdout 要收回來——這兩件 aos-exec 命令列沒有，函式庫層要補一個入口）。

## 5. 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 這格做了事（換了格、問了模型、跑了工具、或引擎失敗但會重試） |
| 101 | 沒事做（`idle` 而且記憶尾巴不是 `user`） |
| 1 | 讀驗錯誤（[agent.md §4](agent.md) 與 [directives.md §6](directives.md) 的代號）：stderr 一行 `aos-agent: <代號>: <白話>`，什麼都不寫 |
| 2 | 用法錯（旗標不認得、`dir` 不存在） |

引擎失敗、工具失敗都**不是**錯誤碼：前者 stderr 一行 `aos-agent: engine: <白話>` 然後退 0，
後者變成 `tool` 訊息給模型看。

## 6. 沒管的事

- 誰把 `user` 訊息塞進記憶、誰去讀回話（aos-user 之類）。
- 反覆叫、放進 kernel（`.aos/inst.json` 寫 `{"argv": ["aos-agent", "."]}` 就行，那是使用者的事）。
- 上限、計數、鎖、記憶太長。
