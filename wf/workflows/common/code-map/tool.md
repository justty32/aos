← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## core/tool

`core/tool` 是世界層的工具與聯絡方式登記庫（公開 target `aos::tool`，產物 `libaos_tool.so`），提供 `aos tool` 與 `aos contact` 兩條子命令。它以私有相依使用 `aos::exec` 做工具自述探測、使用 `aos::loop` 解析目前世界；`aos::agent` 的公開 API 直接暴露 `aos::tool::Spec`，因此把 `aos::tool` 列成公開相依。完整使用入口見 [core/tool/README.md](../../../../core/tool/README.md)。

### 世界層檔案格式

每個工具是一個扁平 JSON object，放在 `<world>/.aos/tools/<name>.json`；檔內 `name` 必須等於檔名，讀 registry 時遇到壞檔會整次報錯，不會靜默略過。欄位名沿用目前實作所選的 ai_core 軸向詞彙；程式碼實際保存的完整欄位如下。

| 欄位 | 型別與規則 |
|------|------------|
| `name` | 必填非空 string，只接受英數、`_`、`.`、`-`。 |
| `argv` | 必填、非空的 string array；是執行工具時的固定 argv 前綴。 |
| `description` | 必填非空 string；給模型的一句話表述。 |
| `args` | 選填 `list`／`string`／`none`，預設 `list`。 |
| `stdin` | 選填 `none`／`text`，預設 `none`。 |
| `cwd` | 選填 string，預設空字串（agent 執行時視為世界根 `.`）。 |
| `timeout_ms` | 選填非負整數，預設 `0`；tool registry 的 `0` 代表不限時，agent 投遞時目前會換成 30000 ms。 |
| `source` | 選填 `manual`／`metainfo`／`header`，預設 `manual`。 |
| `lifecycle`／`state`／`guarantee`／`interruptible`／`predictability`／`stage` | 選填 string；未填時留空且不寫回 JSON。 |
| `network` | 選填 bool；程式另記錄是否曾明確宣告，未宣告就不寫回 JSON。 |
| `env_allow` | 選填 string array；空陣列不寫回 JSON。 |

repo 根的 `.aos/tools/` 目前放了五個進版控的範例登記：`sh`／`ls`／`cat`／`git`／`aos`。

通訊錄 `<world>/.aos/contacts.json` 的頂層是 JSON array；每項必須有非空 string `name`／`folder`，可選 `agent`／`note` string。`folder` 原樣保存；`aos say --to` 使用時才以目前世界為基準組出目標路徑（絕對路徑仍保持絕對），若 `agent` 缺席則解析目標世界裡唯一的 agent。

### `aos tool add` 探測與合併順序

`aos tool add` 先驗 argv[0]：含 `/` 就查該檔案，否則搜尋 PATH；找不到或不可執行就回 1 且不登記，`--description`／`--no-probe` 也不能略過。通過後預設執行 `<argv> --metainfo`，關閉 stdin 並設 3000 ms 逾時。退出成功後依序降級：stdout 若是含非空 `description` 的 JSON object，就收下表述與合法的已知選填欄、記 `source=metainfo`；否則取同一份 stdout 的第一個非空行（最多 200 bytes）、記 `source=header`。若加 `--probe metadata`，只有前一次完全沒探到可用內容時才再以 `--metadata` 重試；`--no-probe` 則全部略過探測。

合併優先序是**命令列旗標 > 探測結果 > `Spec` 預設值**。若最後仍沒有 description，CLI 不會自行再跑第三個探測，而是失敗並要求以 `--description` 手填；已手填 description 時會採用它並把 `source` 改成 `manual`。

### 檔案表與分層

相依只往下看：`spec` 是純 JSON 邊界；`registry` 在它上面加世界路徑、原子檔案 I/O 與預設工具；`probe` 只經公開 `aos::exec` API 跑探測；`contacts` 重用 registry 內部的文字／原子寫入 helper；兩支 CLI 最上層組合公開 API，`cli_common.hpp` 只放輸出 helper。

| 檔案 | 負責什麼 |
|------|----------|
| `core/tool/include/aos/tool.hpp` | 公開 `Spec`／`Contact`／`Probe` 型別，以及世界解析、spec JSON、registry、預設工具、探測與 contacts API。 |
| `core/tool/src/internal.hpp` | 小專案內部文字讀取與 tmp＋rename 原子寫入宣告；不安裝。 |
| `core/tool/src/cli_common.hpp` | 兩支 CLI 共用的表格輸出、JSON escape、UTF-8 截短、join 與縮排 helper。 |
| `core/tool/src/spec.cpp` | 純工具 spec 邊界：驗名稱與必填／列舉型欄位、解析扁平 JSON、按固定格式序列化並省略未宣告的選填欄。 |
| `core/tool/src/registry.cpp` | 世界解析與 `.aos/tools/` 路徑、單項／整張 registry 的原子讀寫刪除、依名稱排序，以及 `sh`／`ls`／`cat` 預設登記。 |
| `core/tool/src/probe.cpp` | 用 `aos::exec` 執行 `--metainfo`／指定旗標，判斷退出、signal、逾時與輸出，再解析 JSON 或退回第一個非空行。 |
| `core/tool/src/contacts.cpp` | 驗證、讀寫 `.aos/contacts.json`，合成 `$HOME` 的天然 `~` 聯絡人，並依名稱新增／取代、查找與移除。 |
| `core/tool/src/tool_cli.cpp` | `aos tool add／ls／rm` 的完整 help、參數解析、argv[0] 檔案／PATH 預檢、探測重試、旗標覆寫、人工 description 閘門與人類／JSON 列表輸出。 |
| `core/tool/src/contact_cli.cpp` | `aos contact add／ls／rm` 的完整 help、參數解析、`--folder-root`、可選 agent／note，以及天然 `~` 置頂的人類／JSON 列表輸出。 |
| `core/tool/tests/test_tool_cli.cpp` | CLI 回歸：登記／列表／移除、metainfo 合併、缺少 executable 不登記、既有 executable 可登記，以及 tool／contact help。 |
| `core/tool/CMakeLists.txt` | 建 `aos::tool`／`libaos_tool.so`、連私有 `aos::exec`＋`aos::loop`，登記 `tool`／`contact` 子命令與測試。 |
| `core/tool/README.md` | 工具與通訊錄格式、CLI、探測降級與公開函式庫入口。 |
