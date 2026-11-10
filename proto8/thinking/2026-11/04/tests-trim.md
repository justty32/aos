# 2026-11-04 測試大刪：proto8/tests、impls 與 core 的 ctest 全刪

← [thinking README](../../README.md)｜月份表 [2026-11](../README.md)｜相關：[testing 工作流](../../../../wf/workflows/testing.md)、code map 02-tests、[AGENTS.md 鐵律](../../../../AGENTS.md)

本檔只記使用者原文（逐字）、決定、盤點結論與執行清單、要使用者裁的題（[user/03](../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。三題 11-04 已裁（見「使用者裁定」）。**11-04 先盤點；同天 aos-agent 實作與 four-elements 07 收完後照清單執行完（見「執行結果」）。**

> 11-10 改讀（prefix-fixes 坑-55）：本頁記的是 11-04 當時的刪除決定與結果，不代表現在沒有測試。11-10 依現行檔名 `test_*.py` 盤點（排除封存、建置與隱藏副本）：repo 現役 56 支，含 proto8 48 支（`impls/` 10、`lib/` 30、`cmd/` 3、`templates/` 5）及 `wf/tools/` 8 支；另 `proto8/archive/` 有 7 支封存測試，不計入現役。

## 使用者原文（11-04，逐字）

> 話說，感覺proto8/test已經成為我們的負擔了，能夠精簡嗎？我希望能大刪特刪

> 據說有研究，說AI寫的test，百分之八十都沒啥用。

看到「激進版／溫和版」兩案的題目時：

> 激進版，不用說，甚至我希望整個刪掉也OK。

頂層再問 C++ 的 ctest：

> ctest也可以刪掉吧

頂層提醒這會動到鐵律 1：

> 這個鐵律刪掉，不用ctest

（鐵律 1 已由頂層在 AGENTS.md 刪掉、編號保留。）

## 決定

1. **`proto8/tests/` 整個刪**（35 支 test_*.py、4 支共用小程式 aos_bins／dead_brain／own_error／stack_talk、`spy_bin/`、`fixtures/` 四份）。不出溫和版。
2. **C++ 的 ctest 也全刪**：repo 根 `core/*/tests`、`aos_add_test`／`enable_testing`／Catch2；`proto8/impls/*/tests` 與各 CMakeLists 的測試段；`CMakePresets.json` 的 test preset。
3. 刪完之後的驗證只剩「**build 得過**」（repo 根 `cmake --build --preset default`、proto8 照順序建 impls）。
4. 執行排在 aos-agent 實作（它會新增／改 test_agent_cmd、test_aos_llm、test_eca_*、test_agent_fsm，刪 extras/human、eca 與其測試）與 four-elements 07（aos-exec、aos-loop、fsm `stage.txt`、ai_tools 解析，改 test_exec*、test_loop、test_fsm、test_cli_tools、test_aos_mcp、test_grow、test_sandbox、test_janet 與 impls 的 test_cli）**之後**——現在刪，它們的 commit 會把檔帶回來或撞衝突。
5. **已執行（11-04，983701a0 之後）**：見檔末「執行結果」。

## 盤點結論（11-04，HEAD 129a1a52）

### 規模

| 範圍 | 進 git 的檔 | 行數 | 跑多久（WSL） |
|---|---|---|---|
| `proto8/tests/`（含 fixtures、spy_bin） | 71 | 10,653（test_*.py 10,153） | 約 300 秒（510 案）|
| `proto8/impls/*/tests`（13 專案的 test_cli.py 等） | 約 30 | 8,433 | 各專案 ctest 合計數十秒 |
| `core/*/tests`（7 個小專案，Catch2＋1 支 Python） | 約 44 | 5,686 | repo 根 ctest 8 項 |
| **合計** | **約 145** | **約 24,800** | |

外加要改的設定：根 `CMakeLists.txt`、`cmake/AosSubproject.cmake`、`CMakePresets.json`、`vcpkg.json`、7 份 `core/*/CMakeLists.txt`、13 份 `proto8/impls/*/CMakeLists.txt`。

### proto8/tests 逐檔（若只留冒煙時會留哪支）

「冒煙候選」＝刪光後若要留一兩案證明起得來，從這支挑；其餘照使用者決定直接刪。

| 檔 | 行／案 | 測什麼 | 碰哪支活程式 | 備註 |
|---|---|---|---|---|
| test_exec.py | 425／39 | 經 aos-exec 跑 agent 資料夾（WS、STACK、巢狀、args、loop→fsm） | aos-exec、aos-loop、aos-fsm | 冒煙候選（端到端）；用 fixtures/agent-ann、agent-bob；four-elements 在改 |
| test_exec_rules.py | 426／34 | aos-exec 入口規則、錯誤代號 | aos-exec | 與 impls/aos-exec test_cli 重複移植 |
| test_exec_env.py | 438／37 | AOS_CD 的 .env、優先順序 | aos-exec | 同上 |
| test_exec_dotenv.py | 199／11 | .env 格式子集、對 python-dotenv | aos-exec | |
| test_directive_argv.py | 222／17 | `$ref`、argv 指示詞、插 aos-exec | aos-exec、aos-directive | |
| test_directive_lenient.py | 38／1 | 指示詞寬容 | 同上 | |
| test_inst.py | 191／15 | inst 單子經 aos-exec | aos-exec、libinst | |
| test_loop.py | 390／29 | aos-loop 直接叫、訊號、命令列、ctl／state | aos-loop | four-elements 步 4 改過 |
| test_fsm.py | 369／28 | aos-fsm 一格、stage.txt、next | aos-fsm | four-elements 步 3 改過 |
| test_daemon.py | 559／30 | daemon procs 表、ctl、收工、接回 | aos-daemon | 與 impls/aos-daemon test_cli（1,788 行）大量重疊 |
| test_aos_daemon_ctl.py | 450／14 | add／rm／ls／where／stop／start | bin/aos-daemon-ctl（Python） | 別處沒測；aos-agent 步 6、7 會改 |
| test_tick.py | 107／10 | aos-tick | bin/aos-tick | 別處沒測；用 fixtures/tick |
| test_aos_tools.py | 242／13 | 工具註冊檔 add／rm／ls／call | bin/aos-tools | 冒煙候選（agent 叫工具的唯一路） |
| test_aos_llm.py | 122／4 | aos-llm show／set、agent-fsm 的 llm 子介面 | bin/aos-llm、demo/agent-fsm | aos-agent 步 2、3 剛加 |
| test_agent_fsm.py | 470／12 | demo/agent-fsm 範本：收信→問腦→跑工具 | demo/agent-fsm、aos-loop、aos-fsm、daemon | 冒煙候選（aos 自己的 agent 範本）；aos-agent 在改 |
| test_agent_cmd.py | 546／16 | aos-agent 子命令 | extras/agent/bin/aos-agent | 冒煙候選；aos-agent 在加 |
| test_eca.py | 173／4 | eca-claude 範本端到端（假 claude） | demo/eca-claude、bin/aos-eca-turn | aos-agent 在改 |
| test_eca_cmd.py | 475／13 | aos-eca 掛 daemon | extras/eca | aos-agent 實作後 extras/eca 刪，本檔跟著刪 |
| test_eca_turn.py | 522／23 | aos-eca-turn 一輪、--on-empty／--on-busy | bin/aos-eca-turn | |
| test_eca_llm.py | 117／4 | eca 的 llm 子介面 | bin/aos-eca-llm | aos-agent 步 1 |
| test_eca_screen.py | 115／4 | eca 的 screen 子介面（tmux） | bin/aos-eca-screen | aos-agent 步 1 |
| test_cli_tools.py | 422／13 | 假 claude／codex、cli_session、tmux attach | lib/agent | 假 CLI 劇本；ai_tools 解析在改 |
| test_aos_mcp.py | 202／12 | aos-mcp 當 MCP server | extras/ai_tools | four-elements 步 2 改過 |
| test_human.py | 445／20 | aos-say／aos-listen | extras/human | aos-agent 實作後 extras/human 刪，本檔跟著刪 |
| test_llm_kernel.py | 245／9 | llm-send＋kernel 跟 loop／daemon 接起來 | aos-llm-kernel、aos-llm-send | 單元在 impls |
| test_sandbox.py | 393／20 | bwrap／s6 沙箱 | extras/sandbox | 缺 s6 時 4 案 skip |
| test_grow.py | 173／6 | aos-grow 長一級／縮回、行為不變 | extras/grow | 用 fixtures/agent-eve |
| test_janet.py | 117／4 | Janet 編成 aos | extras/langs/janet | 沒 janet 整檔 skip |
| test_lua_aos.py | 175／9 | Lua 編成 aos、跟 agent-ann 比 | extras/langs/lua | 用 fixtures/agent-ann |
| test_lib.py | 251／12 | lib 工具契約形狀、base 七支 | proto8/lib/base | 契約文字比對多 |
| test_file_tools.py | 187／10 | ls／stat／view／json_edit… | proto8/lib/base、aos-json | 用 fixtures/agent-eve |
| test_pi_tools.py | 229／15 | read／write／edit／bash | proto8/lib/base | |
| test_pyfix.py | 232／5 | agent 當工具（假腦劇本兩份） | lib/agent/pyfix | 假腦劇本；用 fixtures/agent-eve |
| test_memory.py | 114／6 | 記憶庫 save／search／forget | lib/aos/memory | |
| test_send_message.py | 138／7 | 寄信工具名冊、群組 | lib/aos/send_message | |

各檔跑多久見檔末「計時」（WSL 暫存 clone `/tmp/aos-trim-*`，沒碰 `~/repo/simple_tools/aos`）。

### fixtures 跟誰走

| fixture | 誰用 | 刪光後 |
|---|---|---|
| agent-ann | test_exec、test_lua_aos，**還有 `extras/langs/lua/examples/agent_ann.lua` 執行時讀 `../../../../tests/fixtures/agent-ann/` 的三支 .py** | 刪了 lua 範例就跑不起來 → 題 2 |
| agent-bob | test_exec | 一起刪 |
| agent-eve | test_file_tools、test_grow、test_human、test_lib、test_llm_kernel、test_pyfix | 一起刪；`demo/agent-fsm/act.py`、`brain.py` 只在註解提到「照它改」，改註解 |
| tick | test_tick | 一起刪；`bin/aos-tick` 檔頭註解拿它當例子，改註解 |

### 刪光後會失去什麼（什麼壞了就沒人發現）

- **跨程式接起來的路**：aos-exec 前插、loop 每次叫 fsm、fsm 寫 `stage.txt`、daemon 起子項並寫 procs 表——impls 的 test_cli 只各測一支，proto8/tests 是唯一把它們串起來跑的。壞了要等手動跑 agent 才知道。
- **Python 那一半沒有任何別的測試**：aos-tick、aos-tools、aos-daemon-ctl、aos-llm、aos-eca-turn／llm／screen、aos-agent、aos-mcp、aos-grow、aos-sandbox、janet／lua 編譯器、lib/base 十幾支工具、memory、send_message、pyfix、cli_session。這些連「起不起得來」都只剩手跑。
- **錯誤一行的代號規矩**（`程式名: 代號 原因`，own_error 對每一則錯誤檢查代號已登記、原因開頭對得上）：沒人自動檢查，改名或打錯代號不會被抓到。
- **C++ 的細節路徑**：inst 的 pidfd 退路（`test_lib_nopidfd` 強制走 1 毫秒輪詢）、aos-post 認領的競爭、aos-lock、aos-llm-kernel 的排序與 slots、aos-schema／aos-util 的函式庫——這些平常跑 agent 碰不到，壞了最難發現。
- **core/ 舊 C++ 主線**（core/agent、exec、loop、llm、tick、tool、wire）：Catch2 單元測試一起沒了。
- 重構「行為不變」的依據沒了：之後的 refactor 只能靠讀碼與手跑。

### 刪了 build 會不會壞（已查）

- **proto8/impls**：測試段都在 `if(PROJECT_IS_TOP_LEVEL)` 裡、跟主程式 `add_executable(... src/main.cpp)` 同一段。只刪 `tests/` 不改 CMakeLists 會壞的是 `add_executable(test_lib tests/…)`（aos-schema、aos-util、inst）與 `util_cli tests/util_cli.cpp`（aos-util）——configure 找不到原始碼。`add_test(... tests/test_cli.py)` 只在跑 ctest 才壞。所以每份 CMakeLists 要刪：`enable_testing()`、測試用的 `find_package(Python3 …)`（13 份都只給測試用，沒有別的目標要 Python3）、`add_test`、測試用的 `add_executable`／`target_*`／`foreach`（inst 那段 C 旗標）。
- **repo 根**：`aos_add_test` 在 `AOS_BUILD_TESTS`（頂層預設 ON）時才建，但 `core/agent/CMakeLists.txt` 末行 `include(${CMAKE_CURRENT_SOURCE_DIR}/tests/fake_loop.cmake)` **沒有條件**——刪了 tests/ 不刪這行 configure 就壞。
- 沒有活程式 import `proto8/tests` 的東西（只有註解提到）；唯一執行時依賴是上面的 lua 範例。
- `wf/tools`、`.claude/` 的 hook 沒跑 ctest／unittest。

## 執行清單（頂層叫了才做；一個 commit 或分三個：proto8/tests、impls、core＋文件）

### 一、刪目錄

- `proto8/tests/`（整個，含 `fixtures/`、`spy_bin/`、`__pycache__`）
- `proto8/impls/<名>/tests/`：inst、aos-util、aos-directive、aos-schema（含 `tests/data`）、aos-exec、aos-json、aos-loop、aos-fsm、aos-lock、aos-post、aos-daemon、aos-llm-kernel、aos-llm-send（執行時再 `ls proto8/impls` 對一次，aos-agent 若加了新專案一起處理）
- `core/{agent,exec,llm,loop,tick,tool,wire}/tests/`

### 二、改建置設定

- `proto8/impls/*/CMakeLists.txt`（13 份）：拿掉測試段（見上），`if(PROJECT_IS_TOP_LEVEL)` 留主程式；註解「執行檔與測試只在…」改「執行檔只在…」；aos-daemon 那行「對照 proto8/tests/test_daemon.py」註解刪。
- `core/*/CMakeLists.txt`（7 份）：刪 `aos_add_test(...)` 整段；core/agent 再刪 `include(.../tests/fake_loop.cmake)`；core/tick/README.md:162 的範例跟著刪。
- `cmake/AosSubproject.cmake`：刪 `aos_add_test` 函式與說明（約 189～213 行）。
- 根 `CMakeLists.txt`：刪 `option(AOS_BUILD_TESTS …)`（34 行）與 `if(AOS_BUILD_TESTS) find_package(Catch2 …) enable_testing() endif()`（67～70 行）。
- `vcpkg.json`：刪 `features.tests`（catch2）。
- `CMakePresets.json`：刪 `base` 的 `"VCPKG_MANIFEST_FEATURES": "tests"` 與整個 `testPresets`。
- 驗證：WSL 暫存 clone，`cmake --preset default && cmake --build --preset default`（舊 build 目錄的快取裡有 `VCPKG_MANIFEST_FEATURES`，用乾淨目錄）＋ proto8 impls 照順序 `cmake -B build && cmake --build build`，都過＝完成。

### 三、改程式裡指向測試的註解／路徑

- `proto8/bin/aos-tick`（第 8 行例子）、`proto8/bin/aos-tools`（第 5 行例子）、`proto8/demo/agent-fsm/act.py`、`brain.py`（「照 tests/fixtures/agent-eve 改」）：改說法或刪。
- `proto8/extras/langs/lua/examples/agent_ann.lua`：整檔刪（題 2 使用者裁「範例一起刪」），lua README 與 code map 06 跟著改。
- `proto8/tests/aos_bins.py` 的 PATH 拼法（spy_bin、各 impls bin、extras/ai_tools/bin）沒有別人用，隨目錄刪。

### 四、改文件

wf：

- `wf/workflows/testing.md`：整份縮成「驗證＝build 得過」一張小表（repo 根 build、proto8 impls 照順序 build、要真模型／外部 CLI 的照實驗檔交使用者），第 7 行「（鐵律 1）」拿掉；分檔 `testing/01-proto8.md`、`testing/02-測試分類與綠燈.md` 刪（01 裡 WSL mirrored 埠、bwrap／s6 的環境紀錄若還要，搬進 dev-env 或 gotchas）。
- 引鐵律 1 的：`wf/WORKFLOWS.md:7`（「能測就測（鐵律 1）」→「改完 build 得過」）、`wf/workflows/tidy/content-trim.md:9`（改成「不改原意」本身，不引鐵律 1）、`wf/workflows/testing.md:7`。
- 寫「ctest 全綠／綠燈」當 Done when 的：`feature-dev/README.md:12、21`、`refactor/README.md:12`、`refactor/moving-things.md:79`、`add-subproject.md:102（aos_add_test 範本）、138`、`dev-env.md:19、29（錨點 #proto8不在-ctest-裡 會斷）`、`common/user.md:11（「加測試」）`、`team-model.md`、`hackathon/staff/{judge,researcher,scribe}.md`、`workshop/{briefs,staff}.md`、`common/gotchas/04-…`——一律改「build 得過」；`dispatch/README.md`、`experiments/t5-agent-loop/record/*`、`tidy/reports/*`、`salvage/README.md`、`HANDOFF.md` 是當時紀錄，不改。
- code map：`common/code-map/proto8/02-tests.md` 整份刪、`proto8.md` 與 `code-map/README.md` 拿掉那列；`proto8/01-impls*.md` 各專案的 `tests/` 列刪；`code-map/build.md:41～45`（AOS_BUILD_TESTS、aos_add_test、vcpkg 測試相依）、`agent.md`、`agent-lookup.md`、`llm.md`、`tool.md`、`code-map.md` 裡 core 的 `tests/` 列刪；`proto8/13-demo.md` 提到 test_agent_fsm 的改。

repo 根與 core：

- `README.md:14`（`&& ctest --preset default` 拿掉）、`docs/build.md`（25、51、56：Catch2、AOS_BUILD_TESTS）、`docs/subprojects.md`（59、187～195：aos_add_test）、`docs/aos-core-guide.md`（55、58：`VCPKG_MANIFEST_FEATURES=tests`、`-DAOS_BUILD_TESTS=OFF`）、`docs/usage.md`；各 `core/*/README.md` 的測試段。`brief/2026-09-25.md` 是當時紀錄，不改。

proto8：

- `proto8/README.md:18、40`（tests/ 那列）、`proto8/impls/README.md` 與 `impls/docs/01～04`（建置迴圈裡的 `ctest --test-dir build`、「新專案照這張清單」裡的寫測試一項）、各 impls 的 `README.md`／`docs/*建置與測試*`（aos-daemon 07、aos-loop 04、aos-lock、aos-schema、aos-util、inst 01／02、aos-exec 05、aos-fsm 02、aos-json 02、aos-llm-kernel 03、aos-llm-send 01、aos-post 02、aos-directive 01）。
- `proto8/bin/README.md`、`bin/docs/01、04`；`proto8/demo/README.md`；`proto8/lib/README.md`、`lib/docs/01、03`；`proto8/extras/README.md` 與各 extras README（agent、ai_tools、eca、grow、human、langs、janet、lua、sandbox）的「測試」那行。
- 條文：`docs/CONCEPTS/01/02-C-51.md`、`CONCEPTS/02`、`CONCEPTS/05-agent.md`、`CONVENTION.md`、`CONVENTION/02/05-P-23～P-26.md`、`06-P-41.md`、`NORMS.md`、`NORMS/02`、`NORMS/主題.md` 裡提到 `proto8/tests`／`test_*.py` 的：多半是「由 test_x 驗」的出處註，刪那半句，條文本身不動。
- thinking、session_logs、archive 裡的舊紀錄不改（照 thinking 規矩只留原文與結論，舊檔名是當時事實）。

執行時用 `grep -rnE "ctest|unittest|proto8/tests|test_[a-z_]+\.py|aos_add_test|AOS_BUILD_TESTS|Catch2" --include=*.md` 排除 archive／thinking／session_logs／build 再掃一次，以掃到的為準（兩個 agent 收完後行號會動）。

## 要使用者裁的題

1. **刪光後要不要留一支冒煙腳本**（不是測試框架、不進 ctest）：例如 `proto8/smoke.sh` 三十行左右——建好 impls 後用假腦經 aos-exec 跑 `demo/agent-fsm` 一題、`aos-tools ls`、`aos-agent ls`，任何一步非 0 就停，幾秒跑完。好處：「改完根本起不來」這種最大的壞還抓得到；代價：又是一份要跟著改的東西。不留＝驗證只有 build。
2. **`extras/langs/lua/examples/agent_ann.lua` 執行時讀 `tests/fixtures/agent-ann/`**：(a) 把 agent-ann 那 7 個檔搬進 `extras/langs/lua/examples/agent-ann/`、改路徑；(b) lua 範例（與 test_lua_aos 一起）刪掉；(c) 不管，範例壞著。
3. **core/ 的 Catch2 刪了之後 vcpkg 的 `tests` feature 與 presets 一起拿掉**（清單已列）；若還想留著「以後要寫測試時的掛點」（`aos_add_test` 函式空殼），說一聲就只刪測試檔、不刪函式。

### 使用者裁定（11-04，選項原文）

1. 冒煙腳本：「不留」——不寫 `smoke.sh`，刪完後驗證只剩 build 得過。
2. lua 範例：「範例一起刪 (Recommended)」——`extras/langs/lua/examples/agent_ann.lua` 跟 fixtures 一起刪（`clocks.lua` 不讀 fixtures，留著）；`extras/langs/lua/README.md` 第 13、20、21 行那列與兩行指令改成只講 clocks.lua，code map `proto8/06-周邊工具.md:49` 拿掉 agent_ann.lua。
3. `aos_add_test`：「整個刪 (Recommended)」——函式連說明一起刪、不留空殼（清單二已照這樣列）。

## 計時

WSL 暫存 clone（HEAD 129a1a52，impls 用 Release 建）逐檔 `python3 -m unittest <檔>`：35 支全過，**510 案、9 skip（janet 沒裝 4、s6 沒裝 4、python-dotenv 1），合計約 300 秒**。最慢五支 test_agent_cmd 43 秒、test_daemon 38、test_agent_fsm 37、test_human 33、test_eca_cmd 31，佔六成；其餘多在 1～8 秒，test_cli_tools 24、test_eca_turn 18。impls 各自的 ctest 與 core 的 ctest 這次沒計時。

## 執行結果（11-04）

- 刪掉 148 個進 git 的檔、約 24,700 行：`proto8/tests/` 70 檔（含 aos-agent 新加的 test_agent_cmd、test_eca_llm、test_eca_screen、test_aos_llm、stack_talk.py 與 fixtures）、13 個 `proto8/impls/*/tests/` 28 檔、7 個 `core/*/tests/` 46 檔、`extras/langs/lua/examples/agent_ann.lua`、`wf/workflows/testing/` 兩份分檔、code map `proto8/02-tests.md`。
- 建置設定：13 份 impls CMakeLists 的測試段、7 份 core CMakeLists 的 `aos_add_test`（core/agent 連 `include(tests/fake_loop.cmake)`）、`cmake/AosSubproject.cmake` 的 `aos_add_test`、根 `CMakeLists.txt` 的 `AOS_BUILD_TESTS`／Catch2／`enable_testing`、`vcpkg.json` 的 `tests` feature、`CMakePresets.json` 的 `VCPKG_MANIFEST_FEATURES` 與 `testPresets`。
- 驗證：WSL 暫存目錄（乾淨 build 目錄）repo 根 `cmake --preset default && cmake --build --preset default` 過；proto8 impls 13 個各自 `cmake -B build && cmake --build build` 過；wf-lint broken 0（順手把 thinking／舊日誌裡 31 處指向已刪 extras/eca、extras/human、testing/01、02-tests 的連結改純文字，修一個錨點）。
- 文件：testing.md 重寫成「build 得過」；WORKFLOWS、tidy/content-trim 不再引鐵律 1；feature-dev、refactor、add-subproject、dev-env、user.md、team-model、hackathon／workshop 職務單、gotchas、code map（build、agent、agent-lookup、llm、tool、proto8 01-impls*、06、13、README、proto8.md）、repo 根 docs（build、subprojects、aos-core-guide、README）、core READMEs（exec、loop、tick、agent）、proto8 README、bin、demo、lib、extras、impls 各 README／docs、條文裡指向測試或 fixtures 的出處（改「11-04 隨 proto8/tests 刪了」）。
- 程式註解：bin/aos-tick、aos-tools、demo/agent-fsm act.py／brain.py、lib/agent claude／codex `_entry`、cli_session.py、pyfix `_entry`、lib/aos/aos_ws.py、CONCEPTS abbr.json 的例子。
