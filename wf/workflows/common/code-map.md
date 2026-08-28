# code map — aos 程式碼結構導航圖

← [common/README](README.md)｜[INDEX](../../INDEX.md)｜維護規則見 [conventions](conventions.md)

**要改程式碼，先讀這張圖**：先找到你要動的領域，只讀那一格列出的檔案，不要順手翻無關的目錄。
這張圖與程式碼衝突時**以程式碼為準**，發現不對就當場修這張圖。

---

## 一分鐘看懂這個專案

`aos` 是一個 **monorepo**：只有一個執行檔 `aos`，靠子命令把陸續長出來的各個「小專案」掛上去（例如 `aos exec world`）。第一個小專案是 `core/inst/`——一支讀 JSON instruction、`fork`/`exec` 跑起來的 POSIX 指令執行器。

```
repo 根
  aos::common（common/，header-only，目前只有 <aos/export.h>）
       ▲ 每個小專案都連它
  aos::inst（core/inst/，核心小專案 → libaos_inst.so）
       │  C++ 分層，相依單向：inst ← format ← handoff；inst ← format ← resolve；inst ← exec
       │    inst    inst_t 資料結構、狀態列舉             （src/inst.cpp）
       │    format  唯一懂 JSON schema 的層                （src/format.cpp）
       │    resolve 以明示 context 解析 `$env`／`$ref`        （src/resolve.cpp）
       │    handoff instruction 檔案投遞／聚合／取件／釋放  （src/handoff.cpp + handoff_deliver.cpp + handoff_header.cpp）
       │    exec    唯一碰 fork/exec/waitpid 的層          （src/exec.cpp + spawn_prep.cpp + wait.cpp）
       │  外加兩層，各自只往下看：
       │    C ABI 包裝（src/capi*.cpp，對外標頭 <aos/inst.h>）
       │    CLI 世界／回合層（src/run*.cpp，進入點 aos_init_cli_main／aos_exec_cli_main／aos_deliver_cli_main）
       ▼
app/（唯一執行檔 aos，子命令分派）── `aos init`／`aos exec`／`aos deliver` 掛的就是上面這條

  aos::tooljson（core/tooljson/，核心小專案 → libaos_tooljson.so）
       │  spec／registry：驗證 tool spec 與開放的 _type 登記
       │  exec_type／args：只解析 exec 配方並展開 argv，不啟動行程
       ▼
app/ ── `aos tooljson list|check spec.json` 掛的就是這條

  aos::llms（core/llms/，核心小專案 → libaos_llms.so）
       │  LLM：端點、模型、Params、能力三態與可抽換 HTTP transport
       │  Bot／Reply：system、history、tools 與非串流 ask 的交易式收尾
       ▼
app/ ── `aos llms ask|models` 掛的就是這條（成功路徑會連網）
```

三個一直會用到的概念：

1. **單向相依是鐵律**：`inst ← format ← handoff`、`inst ← format ← resolve` 與 `inst ← exec`——handoff 與 resolve 使用 format，exec 只使用 inst，三者互相不知道對方存在。五組宣告目前併在同一個標頭 `include/aos/inst.hpp` 裡，**併在一起不代表可以互相引用**，標頭開頭那段註解就是講這件事。
2. **一個執行檔、多個子命令**：不會有第二個 `main`。新的小專案（未來的 `llm/`、`tooljson/`……）靠自己的 CMakeLists 呼叫 `aos_add_subcommand()` 把子命令掛進 `app/` 的分派表，不用改 `app/` 本身。
3. **每個小專案是一顆獨立的 shared lib**：`aos::inst` → `libaos_inst.so`。傘狀 target 有 `aos::core`（核心）、`aos::modules`（擴充，有擴充存在時才建）、`aos::aos`（全部）；`AOS_BUILD_MERGED_LIB` 開了才會多產出一顆合併的 `libaos.so`（`aos::merged`）。
4. **小專案分兩類，靠所在目錄決定**：`core/` 是 aos 的基本組成（一定會建），`modules/` 是可選的擴充（`-DAOS_BUILD_MODULES=OFF` 整批不建）。建置方式完全一樣，`core/CMakeLists.txt` 與 `modules/CMakeLists.txt` 各自 `set` 了 `AOS_SUBPROJECT_CATEGORY`，`aos_add_subproject()` 讀它來分類。判準：拿掉它 aos 就不再是 aos → core。

> **2026-08-24：`core/inst` 的凍結已由使用者解除。** `inst.cpp`／`format.cpp`／`exec.cpp`／`spawn_prep.*`／`wait.*`／`capi*.cpp` 現在可以改。解凍是為了兩件已拍板的事：每筆 instruction 的 non-blocking 欄位，以及 JSON 的 `$ref`／`$env`／`$opt` 指示詞（設計見 [`docs/inst-directives.md`](../../../docs/inst-directives.md)、順序見 [`docs/roadmap.md`](../../../docs/roadmap.md) 的 T0）。解凍**不等於可以隨手改**——上述單向相依仍然是鐵律。

---

## 逐檔表格在哪：各小專案分冊

每個檔負責什麼，按小專案拆成四冊放在 [`code-map/`](code-map/README.md)：

| 分冊 | 涵蓋 | 什麼時候會想看 |
|------|------|---------------|
| [code-map/inst.md](code-map/inst.md) | `core/inst/`：公開標頭、五個核心分層、C ABI 包裝層、CLI 層、測試，以及「新增一個 instruction 欄位」的維護鏈（逐檔表格再按層拆在 [`code-map/inst/`](code-map/inst/README.md) 底下的 library／capi／cli／tests 四份） | 要改 instruction 結構、format／resolve／handoff／exec、C ABI 或 `aos init`／`aos exec`／`aos deliver` |
| [code-map/tooljson.md](code-map/tooljson.md) | `core/tooljson/`：公開 API、內部邊界、spec／registry／exec_type／args／text／fingerprint、CLI、測試 | 要改 tool spec 驗證、`_type` registry、argv 展開或 `aos tooljson` |
| [code-map/llms.md](code-map/llms.md) | `core/llms/`：公開 API、內部邊界、content／params／transport／SSE／caps／Reply／Bot／presets、CLI、測試 | 要改 LLM client、串流、toolset、presets 或 `aos llms` |
| [code-map/build.md](code-map/build.md) | `common/`、`app/` 的逐檔表格，以及根 CMakeLists／`cmake/`／vcpkg／presets 等建置設定 | 要改建置骨架、子命令登記機制、相依放哪一層，或新增一個小專案 |

**新增或刪除一個原始碼／測試檔（或某個檔的職責變了）時，那一列去哪裡加**：
檔案在 `core/inst/` 底下 → `code-map/inst.md`，再照它的表選 `code-map/inst/` 的 library（標頭與五個核心分層）／capi／cli／tests 一份；在 `core/tooljson/` 底下 → `code-map/tooljson.md`；在 `core/llms/` 底下 → `code-map/llms.md`；在 `common/`／`app/`／`cmake/` 底下或是建置設定檔（含新增小專案要加的那行 `add_subdirectory()`）→ `code-map/build.md`。
未來多一個小專案，就在 `code-map/` 多一冊，並在上面這張表加一列。**這一步跟程式碼改動同一個 commit**（AGENTS.md 的「改了程式碼就要同步 code map」）。

---

## 文件在哪

`docs/`（repo 根）放**整體**文件：[總覽](../../../docs/overview.md)、[建置](../../../docs/build.md)、[使用](../../../docs/usage.md)、[新增小專案](../../../docs/subprojects.md)。改了建置骨架、子命令機制或相依管理，那邊要跟著更新。

`core/inst/docs/` 放 inst 專屬的細節，不是 code map 的一部分，但改東西之前有時值得先看：

| 檔案 | 內容 |
|------|------|
| `architecture.md` | 分層為什麼這樣切、為什麼先把整份輸入讀完再執行、`fork` 兩側各自要做的工作（async-signal-safe 的界線在哪）|
| `handoff.md` | 投遞、彙整、取件、釋放的原因、路徑、錯誤資料與完整公開 API 範例（含 `deliver`、批 header sidecar、fsync 發布順序與去重）|
| `resolve.md` | resolve 分層的原因、未解析表示、`$env` context、`$ref` 路徑／pointer／巢狀與循環、驗證順序、錯誤位置與完整公開 API 範例 |
| `format.md` | JSON schema 細節 |
| `exec.md` | 執行語意細節 |
| `capi.md`／`cxxapi.md` | C ABI／C++ API 的使用說明 |

---

## 常查的東西在哪

| 我想找… | 去哪 |
|---------|------|
| instruction 有哪些欄位、JSON 長什麼樣 | `core/inst/include/aos/inst.hpp` 的 `inst_t`；schema 細節在 `core/inst/src/format_decode.cpp` 的 `known_key`／`decode` 與 `format_encode.cpp` 的 `encode` |
| exit code、逾時、行程群組怎麼處理 | `core/inst/src/exec.cpp` |
| PATH 怎麼解析、環境變數怎麼合併 | `core/inst/src/spawn_prep.cpp` |
| C ABI 怎麼對應到 C++ API | `core/inst/src/capi.cpp` 開頭的 `static_assert` 一串 |
| instruction inbox 怎麼投遞／聚合／取件／釋放 | 投遞在 `core/inst/src/handoff_deliver.cpp`，其餘三個動作在 `core/inst/src/handoff.cpp`；批 header sidecar 與批 id 在 `handoff_header.cpp`，路徑推導與檔案存取（含 fsync／排他發布／投遞唯一名）在 `handoff_fs.cpp` |
| CLI 怎麼映射交接結果、怎麼跑一批 instruction | `core/inst/src/run_exec.cpp`／`run_batch.cpp`；argv 在 `run.cpp`，loop 在 `run_loop.cpp`，`aos deliver` 的 argv 與進入點自帶於 `run_deliver.cpp` |
| 子命令怎麼被登記、怎麼被分派 | `cmake/AosSubproject.cmake` 的 `aos_add_subcommand()` → `app/CMakeLists.txt` 產表 → `app/src/main.cpp` |
| 某個相依該放在哪一層 | [common/ 那節](code-map/build.md)的判準；完整說明在 [`docs/subprojects.md`](../../../docs/subprojects.md) |
| 為什麼要先把整份輸入讀完才開始執行 | `core/inst/docs/architecture.md`「為什麼要先把整份輸入讀完」|
| `fork` 前後各自能做什麼 | `core/inst/docs/architecture.md`「`fork` 兩側各自要做的工作」；程式碼在 `core/inst/src/exec.cpp` 的 `run_child` |
| 新增一個小專案（像 inst 那樣）要照什麼模子 | [`docs/subprojects.md`](../../../docs/subprojects.md)；函式定義在 `cmake/AosSubproject.cmake` |
