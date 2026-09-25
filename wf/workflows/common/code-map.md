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

每個檔負責什麼，歷史小專案與建置骨架拆成四冊放在 [`code-map/`](code-map/README.md)；目前核心小專案直接指向各自的 README，`tool`／`llm`／`agent` 的細表與 proto5/lib 逐模組一句也在 `code-map/`（見 code-map/README.md 對照表末五列）：

各分冊與核心小專案 README 的**完整對照表**（哪一冊涵蓋什麼、什麼時候看）在 [code-map/README.md「全部分冊與各核心小專案的逐檔表格入口」](code-map/README.md#全部分冊與各核心小專案的逐檔表格入口)；那一列該加在哪看下面這段。

**新增或刪除一個原始碼／測試檔（或某個檔的職責變了）時，那一列去哪裡加**：
檔案在 `common/`／`app/`／`cmake/` 底下或是建置設定檔（含新增小專案要加的那行 `add_subdirectory()`）→ `code-map/build.md`。
`core/exec`、`core/wire`、`core/loop`、`core/tick` 的逐檔表格放在小專案自己的 `README.md`，不另立分冊；`core/tool`、`core/llm`、`core/agent` 的逐檔表格在 `code-map/tool.md`、`code-map/llm.md`、`code-map/agent.md`，proto5/lib 逐模組一句在 `code-map/proto5-lib.md`。
未來多一個小專案，就在 `code-map/` 多一冊，並在 [code-map/README.md](code-map/README.md) 的完整對照表加一列。**這一步跟程式碼改動同一個 commit**（AGENTS.md 的「改了程式碼就要同步 code map」）。

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
