# contacts — agent 通訊錄（名字 → 資料夾）

← [tools/README](README.md)｜裁決來源 [nested-worlds](../nested-worlds.md)｜原型 [wf inbox README](../../inbox/README.md)

**它不是登記表、不是白名單。** 就是 wf inbox 那種 ROSTER：誰、住哪個資料夾（＝往哪投遞）、負責什麼。
權威永遠是對方資料夾自己（`.aos/agents/<name>/` 存不存在）；通訊錄只是省一趟路的快取，可以過期。

現況：agent 名字靠掃 `<folder>/.aos/agents/`（`core/agent/src/paths.cpp:20–43`），零隻或多隻都報錯；
頂層 `aos say <text>` 只認**目前**世界的唯一 agent（`run_top.cpp:29–34`）；跨資料夾要顯式地址：
`aos agent say <folder> <name> <text>`（`run.cpp:177–180`）或 `aos deliver <folder> -- <argv>`（`core/loop/src/deliver_cli.cpp`）。

## 一、住哪

| 選項 | 誰維護／會不會過期 | 跨世界 | 模型怎麼用 | 版控 |
|---|---|---|---|---|
| **A 世界層 `.aos/contacts.json`** | 人或 `aos contact add`；會過期 | 好，`folder` 指向任何資料夾 | 程式可解析 | 靜態清單，進版控 |
| B 每隻 agent `agents/<name>/contacts.json` | 各自維護，容易分裂 | 好，但重複記 | 可讀 | 個人清單 |
| C 純 Markdown `contacts.md` | 人手；最易漂移 | 好 | `cat` 方便，程式難解析 | 進版控 |
| D 不存檔，掃 `agents/*/` 與子資料夾 `*/.aos/agents/*/` | 不會過期，但只看得到本地存在者 | 差，要遞迴、無邊界 | `ls` | 沒有可審清單 |

**建議 A**，檔案可以不存在。D 不是通訊錄，是本地探索。代價：共用檔可能撞寫（走 `.tmp`＋rename）、可能過期——這正是「快取不是真相」的代價。

## 二、欄位

```json
{"contacts":[
  {"name":"bob","folder":"../bob-world","note":"部署與實機測試"},
  {"name":"reviewer","folder":"../shared","agent":"reviewer","note":"審規格"}
]}
```

| 欄位 | 必填 | 說明 |
|---|---|---|
| `name` | 是 | 寄件時用的名字 |
| `folder` | 是 | 對方**世界**資料夾；相對路徑相對於 `contacts.json` 所在世界，不是 shell cwd。不要把 `.aos/inbox` 或 `say/` 硬編進來 |
| `agent` | 否 | 那個世界裡的 agent 名；省略＝沿用「該世界恰一隻」的規則，找不到唯一就報錯、不猜 |
| `note` | 否 | 負責什麼，一句；只是提示，不是能力宣告 |

**建議**最小 `{name, folder}`；`agent`、`note` 選填。代價：多 agent 世界時省略 `agent` 會歧義。

## 三、誰維護

| 選項 | 代價 |
|---|---|
| A `aos agent init` 自動加到**自己**世界的通訊錄 | 加自己沒意義（自己世界本來掃得到） |
| B `aos agent init` 自動加到**父**世界 | 沒有「父世界」概念（nested-worlds 已裁：子世界不追蹤）；init 默默改另一個資料夾是副作用 |
| C 人手編輯 | 最簡單，會忘 |
| **D `aos contact add <name> <folder> [--agent A] [--note …]`**（原子寫） | 多一個明確步驟 |

**建議 D 為主、C 可用；`agent init` 不碰任何通訊錄。** 版控：靜態清單進版控，優先存相對路徑；絕對路徑的個人條目由使用者自行忽略。

## 四、怎麼用：「寄信給 bob」＝什麼

| 選項 | argv | 代價 |
|---|---|---|
| **A 解析後直接 `aos agent say <folder> <agent> <text>`** | 寫進對方 `say/*.md` | 寄件者直接寫另一個世界的 agent 狀態 |
| B 解析後 `aos deliver <folder> -- aos agent say . <agent> <text>` | 走對方 loop 的 inbox | 多一回合，但「所有動作都投遞」語意一致 |
| C 新增 `aos contact send bob <text>`，內部選 A 或 B | 人用介面 | 多一個子命令 |
| D 只幫 `aos deliver` 找 folder | 不處理 agent 訊息 | 太窄，通訊錄失去主要用途 |

**建議**：MVP 用 A 的語意、之後給 C 當人用介面。對 agent 而言，「寄信」就是登記表裡一條 tool（`aos say`／`aos deliver`，見 [registry](registry.md) 範例），通訊錄只回答「bob 在哪」。
子 agent 的 CPU 與 tools：**A 自己的 `engine.json`、自己的白名單**（不繼承）；B 繼承父 agent；C 每次投遞時父方指定；D 子 agent 沒 CPU 只當 endpoint。建議 A——B／C 會把通訊錄偷偷變成權限與執行設定。

## 五、跟 llm pu（[top-down-cli §三](../top-down-cli.md)）是不是同一件事

傳輸機制相同（名字→資料夾→投遞），語意不同（對方是 agent 還是一顆 CPU）。
A 同一份清單加 `kind: agent|llm-pu`；**B 通訊錄只放 agent，llm pu 放 `engine.json`／endpoint 設定**；C 不加 kind 靠猜。
建議 B；代價是兩份地址設定。等所有 endpoint 都統一成「可收 inst 的地址」那天再升 A。

## 使用者裁決追加（2026-08-30）：使用者自己也是 agent，住 `~`

> 「使用者自己也勉強算是 agent，所在資料夾就是 `~`，其他 agent 可以把信寄到這裡。使用者跟其他 agent say 的時候寄件人就是 `~`。」

- 通訊錄天然有一格 `~`（使用者）：地址＝`~/.aos/`（inbox／say 投遞匣），任何 agent `aos say --to ~ …` 就是「跟使用者講話」；使用者讀信＝在 `~` 下 `aos listen`（或之後的 `aos inbox`）。
- 使用者在任何世界打 `aos say …` 時，訊息的**寄件人是 `~`**（say 訊息要帶 `from` 欄；agent 之間互 say 也帶各自的資料夾當寄件人）。
- 這跟 wf inbox 的「頂層那一格＝`new/`」是同一件事：使用者的信箱是頂層信箱。
- **尚未實作**：say 的 `from`、`~/.aos/` 的初始化、`aos say --to ~`。交給下一棒（修 bug／改進隊）。
