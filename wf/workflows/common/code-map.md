# code map — aos 程式碼結構導航圖

← [common/README](README.md)｜[INDEX](../../INDEX.md)｜維護規則見 [conventions](conventions.md)

**要改程式碼，先讀這張圖**：先找到你要動的領域，只讀那一格列出的檔案，不要順手翻無關的目錄。
這張圖與程式碼衝突時**以程式碼為準**，發現不對就當場修這張圖。

---

## 一分鐘看懂這個專案

`aos` 是一個 **monorepo**：只有一個執行檔 `aos`，靠子命令把陸續長出來的各個「小專案」掛上去（例如 `aos run world`）。現在共有七個核心小專案：`exec`／`wire`／`loop`／`llm`／`tool`／`agent`／`tick`；`core/inst`／`core/llms`／`core/tooljson` 已於 2026-08-30 刪除。

```
repo 根
  aos::common（common/，header-only，目前只有 <aos/export.h>）
       ▲ 每個小專案都連它
  aos::exec（libaos_exec.so） ──┐                 aos::llm（libaos_llm.so）
  aos::wire（libaos_wire.so） ──┴─ 公開相依 → aos::loop（libaos_loop.so）
       │                                             │
       │                exec ＋ loop ── 私有相依 → aos::tool（libaos_tool.so）
       │                                             │
       │                                             └─ agent 的公開相依 → aos::agent（libaos_agent.so）
       │                                                                       ▲
       └────────────── exec ＋ llm ＋ loop ─────────────── agent 的私有相依 ───┘

  aos::loop ── tick 的公開相依 → aos::tick（libaos_tick.so）← tick 的私有相依 ── aos::agent

app/ ── loop 掛 `run／deliver`；llm 掛 `llm`；tool 掛 `tool／contact`；
        agent 掛 `agent／say／listen／talk／state`；tick 掛心跳與登記事務子命令
```

三個一直會用到的概念：

1. **一個執行檔、多個子命令**：不會有第二個 `main`。新的小專案靠自己的 CMakeLists 呼叫 `aos_add_subcommand()` 把子命令掛進 `app/` 的分派表，不用改 `app/` 本身。
2. **每個小專案是一顆獨立的 shared lib**：`aos::llm` → `libaos_llm.so`。傘狀 target 有 `aos::core`（核心）、`aos::modules`（擴充，有擴充存在時才建）、`aos::aos`（全部）；`AOS_BUILD_MERGED_LIB` 開了才會多產出一顆合併的 `libaos.so`（`aos::merged`）。
3. **小專案分兩類，靠所在目錄決定**：`core/` 是 aos 的基本組成（一定會建），`modules/` 是可選的擴充（`-DAOS_BUILD_MODULES=OFF` 整批不建）。建置方式完全一樣，`core/CMakeLists.txt` 與 `modules/CMakeLists.txt` 各自 `set` 了 `AOS_SUBPROJECT_CATEGORY`，`aos_add_subproject()` 讀它來分類。判準：拿掉它 aos 就不再是 aos → core。

---

## 逐檔表格在哪：各小專案分冊

每個檔負責什麼，歷史小專案與建置骨架拆成四冊放在 [`code-map/`](code-map/README.md)；目前核心小專案直接指向各自的 README，`tool`／`llm`／`agent` 的細表另在本檔下半部：

| 分冊 | 涵蓋 | 什麼時候會想看 |
|------|------|---------------|
| [code-map/inst.md](code-map/inst.md) | `core/inst/`：公開標頭、五個核心分層、C ABI 包裝層、CLI 層、測試，以及「新增一個 instruction 欄位」的維護鏈（逐檔表格再按層拆在 [`code-map/inst/`](code-map/inst/README.md) 底下的 library／capi／cli／tests 四份） | **`core/inst` 已刪 2026-08-30，本冊為歷史存檔** |
| [code-map/tooljson.md](code-map/tooljson.md) | `core/tooljson/`：公開 API、內部邊界、spec／registry／exec_type／args／text／fingerprint、CLI、測試 | **`core/tooljson` 已刪 2026-08-30，本冊為歷史存檔** |
| [code-map/llms.md](code-map/llms.md) | `core/llms/`：公開 API、內部邊界、content／params／transport／SSE／caps／Reply／Bot／presets、CLI、測試 | **`core/llms` 已刪 2026-08-30，本冊為歷史存檔** |
| [core/exec/README.md](../../../core/exec/README.md) | `core/exec/`：整批 POSIX 行程的啟動、等待、中斷、逾時、輸出與時間 | 要改 `start_all`／`wait_all`／`interrupt_running`、行程群組、PATH／env 準備或暫存檔收拾 |
| [core/wire/README.md](../../../core/wire/README.md) | `core/wire/`：指令、結果與 loop state 三種協定的 C++ struct／JSON 邊界 | 要改協定欄位的解析、序列化、預設值或錯誤回報 |
| [core/loop/README.md](../../../core/loop/README.md) | `core/loop/`：`.aos/` 版面、投遞、匯聚、state 與一回合的推進順序 | 要改資料夾回合機、`aos run`／`aos deliver` 或它對 exec／wire 的接法 |
| [core/tool/README.md](../../../core/tool/README.md) | `core/tool/`：世界層工具登記表、探測與 agent 通訊錄；逐檔表格見下方 `core/tool` 節 | 要改 `.aos/tools/`／`.aos/contacts.json`、`aos tool`／`aos contact` 或工具自述探測 |
| [core/llm/README.md](../../../core/llm/README.md) | `core/llm/`：OpenAI 相容 chat completions client；逐檔表格見下方 `core/llm` 節 | 要改 endpoint／model／request／response、環境變數或 `aos llm` CLI |
| [core/agent/README.md](../../../core/agent/README.md) | `core/agent/`：回合 agent、工具往返與可選 LLM CPU；逐檔表格見下方 `core/agent` 節 | 要改 agent 版面、step、工具呼叫、跨世界 say 或 lmstudio／pi engine |
| [core/tick/README.md](../../../core/tick/README.md) | `core/tick/`：heartbeat 兩張清單的格式、到期規則、`aos tick` 一次心跳與四個登記子命令 | 要改到期判定、`routines.json`／`schedule.json` 的欄位、`log.md` 格式或 `aos routine`／`aos schedule` 的 CLI |
| [code-map/build.md](code-map/build.md) | `common/`、`app/` 的逐檔表格，以及根 CMakeLists／`cmake/`／vcpkg／presets 等建置設定 | 要改建置骨架、子命令登記機制、相依放哪一層，或新增一個小專案 |

**新增或刪除一個原始碼／測試檔（或某個檔的職責變了）時，那一列去哪裡加**：
檔案在 `common/`／`app/`／`cmake/` 底下或是建置設定檔（含新增小專案要加的那行 `add_subdirectory()`）→ `code-map/build.md`。
`core/exec`、`core/wire`、`core/loop`、`core/tick` 的逐檔表格放在小專案自己的 `README.md`，不另立分冊；`core/tool` 的逐檔表格暫收在本檔。
未來多一個小專案，就在 `code-map/` 多一冊，並在上面這張表加一列。**這一步跟程式碼改動同一個 commit**（AGENTS.md 的「改了程式碼就要同步 code map」）。

---

## 文件在哪

`docs/`（repo 根）放**整體**文件：[總覽](../../../docs/overview.md)、[建置](../../../docs/build.md)、[使用](../../../docs/usage.md)、[新增小專案](../../../docs/subprojects.md)。改了建置骨架、子命令機制或相依管理，那邊要跟著更新。

## 常查的東西在哪

| 我想找… | 去哪 |
|---------|------|
| 子命令怎麼被登記、怎麼被分派 | `cmake/AosSubproject.cmake` 的 `aos_add_subcommand()` → `app/CMakeLists.txt` 產表 → `app/src/main.cpp` |
| 某個相依該放在哪一層 | [common/ 那節](code-map/build.md)的判準；完整說明在 [`docs/subprojects.md`](../../../docs/subprojects.md) |
| 新增一個小專案（像 llm 那樣）要照什麼模子 | [`docs/subprojects.md`](../../../docs/subprojects.md)；函式定義在 `cmake/AosSubproject.cmake` |
| 一批指令怎麼並行 fork、逾時或 runner 中斷怎麼殺整個 process group | `core/exec/src/start.cpp` 的 `start_all`／`run_child`；統一輪詢與逾時 `kill(-pid, SIGKILL)` 在 `core/exec/src/wait_all.cpp`，signal handler 可呼叫的群組註冊表與 `interrupt_running()` 在 `core/exec/src/interrupt.cpp` |
| 協定的三種 JSON 長什麼樣、欄位怎麼對應 | struct 與公開轉換 API 在 `core/wire/include/aos/wire.hpp`；實作分在 `core/wire/src/inst.cpp`／`outcome.cpp`／`state.cpp`，共用取值在 `json_io.hpp` |
| `.aos/` 動態版面（inbox／turn／batch／state.json） | 路徑推導在 `core/loop/src/layout.cpp`；協定版面在 [`PROTOCOL.md`](../dispatch/proto/PROTOCOL.md) §1 |
| 世界層工具登記表與 agent 通訊錄放哪、是否進版控 | `.aos/tools/<name>.json` 與 `.aos/contacts.json` 由 `core/tool` 管；`.gitignore:8-13` 只放行這兩種靜態設定（另有 heartbeat 清單），其餘 `.aos/` 動態狀態不進版控 |
| 一回合的順序：匯聚 → 並行執行 → 落檔 → 更新 state | `core/loop/src/turn.cpp` 的 `run_turn`；running／done state 的組裝在 `core/loop/src/state.cpp` |
| `aos run`／`aos deliver` 的 CLI 怎麼解參數 | `core/loop/src/run.cpp` 的 `aos_run_cli_main`／`core/loop/src/deliver_cli.cpp` 的 `aos_deliver_cli_main` |
| 投遞與 state／turn 落檔怎麼保持原子 | `core/loop/src/fs.cpp` 的 `write_atomic`：先寫 `path + ".tmp"`，再以 `rename` 發佈 |

---

## 真相層優先序

三份真相（程式碼／規格文件／code map）衝突時的優先序，**必須明確**：

```text
code/tests > docs/aos-folder.md 這類 normative 規格 > schema/examples/fixtures > code map > 其他 docs > generated
```

- 上層與下層衝突時，**以上層為準並修正下層**；但規格與程式碼衝突時**先確認哪一邊是刻意的**（roadmap M0 之後 normative 在 SPEC，程式碼要跟規格走）——分不清就記 [WAIT_USER](../../WAIT_USER.md)。
- generated（產生出來的檔、build 產物）永遠不是唯一真相。
- code map 是**導航不是規格**；行為以 code/tests 為準，發現不對當場修 code map（維護鏈見 [conventions](conventions.md)）。

---

## core/tool

`core/tool` 是世界層的工具與聯絡方式登記庫（公開 target `aos::tool`，產物 `libaos_tool.so`），提供 `aos tool` 與 `aos contact` 兩條子命令。它以私有相依使用 `aos::exec` 做工具自述探測、使用 `aos::loop` 解析目前世界；`aos::agent` 的公開 API 直接暴露 `aos::tool::Spec`，因此把 `aos::tool` 列成公開相依。完整使用入口見 [core/tool/README.md](../../../core/tool/README.md)。

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

## core/llm 與 core/agent

這兩個核心小專案合起來，讓 agent 活在 loop 推進的回合世界裡：`aos agent` 保存人格、對話、狀態與工具往返，loop 每回合從 `.aos/every/agent-<name>.json` 複製一條 `step`；`aos llm` 則是它直接連結的思考引擎，向 OpenAI 相容端點做一次非串流補全。工具的真登記表由 `core/tool` 放在世界層 `.aos/tools/<name>.json`；agent 層 `agents/<name>/tools.json` 若存在只是一張白名單，不存在就使用世界裡全部工具。工具往返的關鍵節奏是：**回合 N 投遞 → N+1 執行 → N+2 讀得到結果**。
agent 本身不 fork／exec 工具，只把 instruction 交給 world inbox；loop 負責匯聚、執行與落結果。
因此 agent 與 loop 透過公開 API 解析目前世界，再靠 `.aos/` 版面協作；思考、執行與結果回收各自落在不同回合。
送給模型的工具清單每項固定一行；模型呼叫的 `args` 必須符合登記的 `list`（字串陣列）／`string`（單一字串）／`none`（省略或空值）。工具執行結果與未知工具／args 形狀錯誤都以同一個 JSON envelope 當 `tool` message 回給模型：共同欄位是 `call_id`／`tool`／`args`／`ok`／`result`，失敗再加 `error.type`／`message`／`retryable`。
`aos agent` 不另開 `aos llm` 子行程，而是直接呼叫它的公開函式庫 API。

### `core/llm` 檔案表

| 檔案 | 負責什麼 |
|------|----------|
| `core/llm/include/aos/llm.hpp` | 公開 API：message／options／CLI options，以及環境設定、參數解析、request／response JSON、`parse_response_model()` 與帶可選 `served_model` 出參的 `complete()` 介面。 |
| `core/llm/include/aos/slot.hpp` | 公開槽 API：兩層 CPU 上限、取槽／自動放槽、`waiting-llm` 與槽狀態查詢。 |
| `core/llm/src/llm.cpp` | 函式庫實作：讀 `AOS_LLM_*`、組 OpenAI messages request、用 libcurl POST `<base>/chat/completions`，驗 HTTP 並抽出 `choices[0].message.content` 與實際 `model`。 |
| `core/llm/src/slot.cpp` | 使用者層與世界層上限合併，以 `flock` 槽與數字優先度等待票限制各 CPU 並行數，並統計佔用與等待。 |
| `core/llm/src/run.cpp` | `aos llm` CLI 層：完整 help、stdin prompt 或 `--messages` 檔案進站，處理 `--system`／endpoint／model／timeout／`--engine`／`--priority`，呼叫前取槽；`--slots` 顯示並行上限現況；端點實際模型不同時仍印回覆、另報兩個模型並回 1。 |
| `core/llm/tests/test_llm.cpp` | 離線驗環境／CLI 參數、messages 與 response JSON、實際模型抽取，以及 help 不連端點。 |
| `core/llm/tests/smoke_slots.sh` | 手動端到端 smoke：離線假端點驗槽串行、逾時退回、世界層限縮，以及 pi step 持有 provider 槽。 |
| `core/llm/README.md` | 使用入口、預設 LM Studio endpoint／model、`--engine`／`--priority`／`--slots`、兩層並行上限設定與錯誤語意。 |

### `core/agent` 檔案表與分層

相依只往下看：`paths ← store`；`paths + store ← deliver／tools`；`init／step` 再組合這些下層；最上面的 `run` 只呼叫 `aos::agent` 公開 API。跨小專案方面，`core/agent` 公開相依 `aos::tool`（公開標頭直接使用 `aos::tool::Spec`），私有相依 `aos::exec`／`aos::llm`／`aos::loop`。箭頭右邊知道左邊，**下層不知道上層存在**。

| 檔案 | 負責什麼 |
|------|----------|
| `core/agent/include/aos/agent.hpp` | 公開資料型別與 API：世界／唯一 agent 解析、初始化、say／log／status／history／pending／tools、argv 展開、工具呼叫抽取及單步 `step()`；completion callback 讓測試可離線注入。 |
| `core/agent/src/internal.hpp` | 小專案內部契約：集中 `Paths`（含正典 `log.jsonl`）、journal／儲存、prompt、投遞等下層宣告；不安裝、不是跨小專案 API。 |
| `core/agent/src/paths.cpp` | 最底層路徑規則：`resolve_folder()` 從 cwd／`AOS_FOLDER` 找世界，`resolve_name()` 找唯一 agent；並正規化 world folder、驗 agent 名稱，推導 `.aos/inbox`、`.aos/every` 與 `agents/<name>/` 全部檔位。 |
| `core/agent/src/store.cpp` | 儲存層：文字讀取、tmp＋rename 原子寫入、正典 `log.jsonl` 追加與 `log.md` 重畫／竄改還原，以及 history／status／pending 的 JSON 讀寫與驗證；沒有 journal 的舊世界仍直接讀 `log.md`。 |
| `core/agent/src/deliver.cpp` | 投遞層：把已按登記展開的工具 argv、cwd、timeout 包成 instruction，原子寫入 world inbox。 |
| `core/agent/src/tools.cpp` | 工具層：讀世界 registry 並套用可選 agent 白名單、每工具一行的 system prompt、依 `list`／`string`／`none` 展開 argv，以及抽取、驗證 LLM 工具呼叫並回報未知工具／args 錯誤。 |
| `core/agent/src/step.cpp` | 回合編排層：收 say 與工具結果、把執行結果或呼叫錯誤包成固定 JSON `tool` message、更新 history／log／status、lmstudio 呼叫前取 provider 槽且等不到回 75、用 `engine.model` 覆蓋環境模型；LLM 成功後才刪 say，失敗寫 `error` 與 log 指引；無新事件時不耗 LLM token，也不自我投遞。 |
| `core/agent/src/init.cpp` | 初始化層：限制一個 world 只住一隻 agent，建立 agent 版面（含 `log.jsonl`）與必要的 world turn／state；世界 registry 為空才安裝 `sh`／`ls`／`cat`，不建立 agent 白名單；依 `AOS_BIN` → `/proc/self/exe` → PATH → `aos` 解析 every instruction 的 argv[0]。`say()` 也在這裡原子投遞訊息。 |
| `core/agent/src/user.cpp` | 使用者世界層：解析 `$HOME` 與 say 寄件世界，維護扁平的 `~/.aos/say/`／`log.md`，並投遞、彙整使用者信件。 |
| `core/agent/src/run.cpp` | `aos agent init／step／say／listen／talk／state` 完整 help 與 CLI 分派；init 省略 folder 時固定用 cwd，其他命令維持世界解析；共用 state 增加 unread／engine／model，listen 顯示未讀，talk 讀 stdin 前驗 runner 鎖。 |
| `core/agent/src/run.hpp` | agent CLI 內部介面：共用 `state_text()` 與 listen／talk 實作；pending 顯示規則、未讀區塊宣告都在這裡，不安裝。 |
| `core/agent/src/run_top.cpp` | 頂層 `aos say／listen／talk／state` 進入點與逐命令完整 help：解析 cwd 世界與唯一 agent；`say --to` 驗目標世界並印真正收件匣，`listen` 顯示未讀，`talk` 回報 pi 尚未內建並共用 runner 鎖檢查。 |
| `core/agent/tests/test_agent_cli.cpp` | CLI 回歸：全組 help、say 真實目的地與錯誤、state 未讀／engine／model、listen 未讀、talk runner 鎖與 pi 指引。 |
| `core/agent/tests/test_agent_lifecycle.cpp` | 生命周期回歸：lmstudio model、LLM／pi 失敗保留訊息、error／log 指引、journal 渲染／防竄改／舊世界相容，以及 every 的絕對 aos 路徑。 |
| `core/agent/tests/fake_loop.py` | 測試用 loop 替身：依協定搬入 inbox、複製 every、並行跑 instruction、寫 out／state、鏡射 agent status 並推進 turn。 |
| `core/agent/tests/smoke.sh` | 端到端 smoke：在 bob cwd 無參數初始化、驗 every 的 argv[0] 是可執行的 aos 路徑，再用替身推三回合，驗 every 每回合執行與 `state.json` 的 status 鏡射。 |
| `core/agent/tests/smoke_user.sh` | 手動端到端 smoke：離線驗 lmstudio step 搶槽、使用者 `~` 的 say／listen 與天然通訊錄列。 |
| `core/agent/README.md` | 回合 agent 的快速使用、工具往返節奏與函式庫入口。 |
| `core/agent/docs/pi-interface.md` | pi 0.84.2 實測、三種接法與尚未內建的 extension adapter 規劃；不是目前已完成的 CLI transport。 |

### `agents/<name>/` 版面

| 路徑 | 存什麼、誰寫 |
|------|--------------|
| `persona.md` | agent 人格；`aos agent init` 寫初值，使用者可直接編輯。 |
| `history.json` | 送給 LLM 的 user／assistant／tool messages；init 建空檔，`step` 讀寫。 |
| `status.json` | `status`／`detail`／`updated_at`／`turn`；init／step 原子寫，loop 唯讀鏡射進 world `state.json`。 |
| `say/*.md` | 等 agent 收取的使用者訊息；`say` 每則寫一個排序檔，`step` 讀入 history 後刪除。 |
| `log.jsonl` | 正典稽核紀錄；一行一則 `turn`／`role`／`content`，role 為 user／assistant／tool／note；init 建空檔，所有追加先寫這裡。 |
| `log.md` | 從 `log.jsonl` 完整重畫的可讀 transcript；listen／talk 讀取時若與 journal 不符會警告並還原。舊世界沒有 journal 時仍直接讀本檔。 |
| `tools.json` | 工具**白名單**，可有可無；不存在＝世界 `.aos/tools/` 登記的工具全部可用，空陣列＝全部停用。接受字串陣列，並相容含 `tools` 陣列的物件及帶 `name` 的舊物件項；init 不建立它。 |
| `pending.json` | 已投遞但尚未回收的工具 call ID、工具名、args 與投遞回合；init／step 寫，step 依它找結果。 |

### 常查的東西在哪

| 我想找… | 去哪 |
|---------|------|
| agent 每回合怎麼被執行、預設工具何時安裝 | `core/agent/src/init.cpp` 的 `aos_program_path()`／`initialize()`：建版面、世界 registry 為空時安裝預設工具，並把目前 aos 的絕對路徑寫進 `.aos/every/agent-<name>.json`；loop 每回合複製它，`step` 不自我投遞。 |
| agent 訊息何時才會從 say 刪除、失敗怎麼記 | `core/agent/src/step.cpp` 與 `engine_pi.cpp`：成功取得回覆後才記 history／log 並刪 say；失敗寫 `status=error`、journal note 與連線／API key 指引，pi 回 1。 |
| `state`／`listen`／`talk` 的未讀與 runner 判斷在哪 | 共用 `state_text()`、未讀列印、`run.lock` 檢查與輪詢在 `core/agent/src/run.cpp`；頂層入口在 `run_top.cpp`。 |
| 世界工具登記表與 agent 白名單怎麼合併 | spec JSON 在 `core/tool/src/spec.cpp:116-180`，registry 掃檔在 `core/tool/src/registry.cpp:85-108`；`core/agent/src/tools.cpp:119-142` 讀整張世界表，`tools.json` 存在時再取白名單交集。 |
| 工具怎麼表述、`list`／`string`／`none` 怎麼展開 argv | `core/agent/src/tools.cpp:85-117` 每工具組一行 prompt；`core/agent/src/tools.cpp:144-168` 對 list 追加 token、對 string 替換所有 `{args}`（沒有占位符就追加一個 argv）、對 none 保留固定 argv。 |
| 怎麼從 LLM 回覆裡抽出工具呼叫 | `core/agent/src/tools.cpp:170-241`：由回覆末行往上找完整 JSON object 行，先查工具是否在可用表，再依其 `args` 登記驗字串陣列／字串／省略或空值；未知工具與形狀錯誤都回傳具名錯誤，不再靜默忽略。 |
| 工具結果與呼叫錯誤怎麼回給模型 | `core/agent/src/step.cpp` 的 `execution_tool_result()`／`step()`：等 `pending.turn + 1` 的 out 全到齊後加入 execution 結果，或在抽取當回合立即加入未知工具／args 錯誤。 |
| `aos say --to` 怎麼找對方世界 | `core/agent/src/run_top.cpp` 的 `say_dispatch()`／`validate_world()`：查目前世界 `.aos/contacts.json`，以目前世界為基準組出 contact folder，驗世界與 agent；contact 沒寫 agent 時解析目標世界唯一 agent，再呼叫 `say()` 並印實際 inbox。 |
| LM Studio 端點與模型怎麼設 | 全域預設從 `core/llm/src/llm.cpp` 的 `options_from_env()` 讀 `AOS_LLM_URL`／`AOS_LLM_MODEL`／`AOS_LLM_KEY`；agent 的 `engine.json` 若有 model，`core/agent/src/step.cpp` 的 `complete_locally()` 會覆蓋環境模型。 |
| LLM 並行上限住哪、怎麼排隊 | `<AOS_HOME>/cpus.json`（權威）與 `<world>/.aos/llm.json`（只能往下限）；實作在 `core/llm/src/slot.cpp`；用 `aos llm --slots` 看現況。 |
| 取槽等太久會怎樣 | stderr 一行 `waiting-llm`、exit 75（`EX_TEMPFAIL`）；agent 走 lmstudio 或 pi 時 status 都寫 `waiting-llm`，訊息還沒被吃掉，下回合重試。 |
| loop 替身在哪、怎麼跑 | `core/agent/tests/fake_loop.py`；repo 根執行 `python3 core/agent/tests/fake_loop.py <folder> --step N --interval 100`。完整 smoke 是 `bash core/agent/tests/smoke.sh`（使用 `build/bin/aos`）。 |

已採用的 every 常駐投遞裁決見 [`wf/workflows/ideas/self-delivery-in-loop.md`](../ideas/self-delivery-in-loop.md)；pi 終端介面調查與建議接法見 [`core/agent/docs/pi-interface.md`](../../../core/agent/docs/pi-interface.md)。

## `core/agent` 的可選 LLM CPU

`agents/<name>/engine.json` 選擇既有的 lmstudio 引擎或 pi coding agent；pi 分支在同一次
`step` 裡完成模型思考與內建工具操作，不進 `tools.json`／pending 的三回合往返。

| 檔案 | 負責什麼 |
|------|----------|
| `core/agent/src/engine.cpp` | `engine.json` 的讀寫與驗證（含 lmstudio model）、lmstudio／pi 預設值、共用 LLM priority 解析，以及 pi session 使用的 v4 UUID 產生。 |
| `core/agent/src/engine_pi.cpp` | pi 引擎的 step 分支：組 argv 與 stdin、執行 pi、解析 JSONL 最終回覆；成功後才刪 say，失敗寫 error／note、`No API key` 指向 provider 環境變數並回 1；step 期間佔 provider 槽，等不到回 75。 |
| `core/agent/tests/test_agent_engine.cpp` | engine 選擇、設定相容性、假 pi 插銷、JSONL 解析與 pi step 行為測試。 |
| `core/agent/docs/pi-cpu.md` | pi 0.84.2 的 provider／JSONL／session 實測、aos 接法，以及相對於 `aos llm` 的取捨。 |
