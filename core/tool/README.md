# tool：世界層工具登記表與通訊錄

`core/tool` 管理一個世界可用的工具與其他 agent 世界的聯絡方式。工具一項一檔放在
`<world>/.aos/tools/<name>.json`；通訊錄則是 `<world>/.aos/contacts.json`。這一層只
負責登記、讀寫與探測，不負責實際展開參數或執行工具。

## 工具格式

每個工具檔都是扁平 JSON object，`name` 必須和檔名相同。

| 欄位 | 型別 | 必填／預設 | 說明 |
|------|------|-------------|------|
| `name` | string | 必填 | `^[A-Za-z0-9_.-]+$` |
| `argv` | string array | 必填、非空 | 執行時的固定 argv 前綴 |
| `description` | string | 必填、非空 | 一句話表述 |
| `args` | string | `list` | `list`／`string`／`none` |
| `stdin` | string | `none` | `none`／`text` |
| `cwd` | string | 空 | 空字串表示世界根 |
| `timeout_ms` | non-negative integer | `0` | `0` 表示不限時 |
| `source` | string | `manual` | `manual`／`metainfo`／`header` |
| `lifecycle`、`state`、`guarantee`、`interruptible`、`predictability`、`stage` | string | 空 | 九軸選填描述 |
| `network` | bool | 未宣告 | 只有明確宣告時才寫檔 |
| `env_allow` | string array | 空 | 空陣列不寫檔 |

寫檔固定使用兩格縮排並以換行結尾；未知欄位在讀入時會忽略。

## 通訊錄格式

`.aos/contacts.json` 頂層是一個陣列。每項的 `name`、`folder` 是非空必填字串，
`agent`、`note` 是選填字串：

```json
[
  {"name": "bob", "folder": "../bob-world", "note": "部署與實機測試"},
  {"name": "reviewer", "folder": "../shared", "agent": "reviewer"}
]
```

`folder` 原樣保存，不會正規化，也不會檢查目標是否存在。
`~`（使用者）是天然存在的一格，不落進 `contacts.json`，但可被檔案中的同名條目
覆寫；`aos contact ls` 一定會把天然的 `~` 排在第一列。

## CLI

```sh
aos tool add ls --description "列出檔案" -- ls
aos tool add formatter --args list --probe metadata -- formatter
aos tool ls
aos tool ls --json
aos tool rm formatter

aos contact add bob ../bob-world --note "部署與實機測試"
aos contact ls
aos contact ls --json
aos contact status
aos contact status --json
aos contact rm bob
```

`tool add` 的 `--` 之後每個 token 都原樣存進 `argv`。可用 `--folder F` 指定世界；
`contact` 對應的選項叫 `--folder-root F`。兩者未指定時都先看 `AOS_FOLDER`，再從 cwd
往上找世界。`aos tool -h|--help` 與 `aos contact -h|--help` 都會在 stdout 列出完整
子命令與選項並回 0。

`aos contact status` 會把自己的世界與通訊錄各格彙成一張表；agent 狀態讀各世界的
`status.json`，未讀數則直接現場計算 `say/*.md`。單一聯絡人資料夾不存在、沒有 agent
或狀態檔損壞時只在該列顯示原因，不會讓整次查詢失敗。

## 探測降級

| 層級 | 條件 | 結果 |
|------|------|------|
| metainfo | `<argv> --metainfo` 成功，stdout 是含非空 `description` 的 JSON object | 收下表述與合法的已知欄位，`source=metainfo` |
| header | 行程成功，但 stdout 不是可用的 metainfo | 取第一個非空白行，最多 200 bytes，`source=header` |
| failure | 行程失敗、非零退出、signal 或空輸出 | 不登記探測內容，回傳可讀的失敗原因 |

`aos tool add --probe metadata` 會在 `--metainfo` 沒探到時再試 `--metadata`；
`--no-probe` 可完全停用探測。所有探測都關閉 stdin，並在 3000 ms 後逾時。
探測前一定先驗 `argv[0]`：含 `/` 時直接檢查該檔案，否則搜尋 PATH；找不到或不可執行
就回 1 且不登記，`--description` 與 `--no-probe` 也不會略過這道檢查。

## 函式庫

公開 API 入口是 `<aos/tool.hpp>`，包含 `Spec`／`Contact`／`Probe`、registry 與
contacts 的原子讀寫、預設工具安裝，以及 `probe_metainfo()`。`install_say_tool()`
只在 `say.json` 不存在時補上跨世界投遞工具，不會覆寫使用者已調整的登記。
