# proto8/impls：aos 的 C／C++ 實作（總入口）

**一句話：這一家小工具做的是同一件事——「在工作區起一個程式、等它、看它的結束碼」——由小到大疊起來：
`inst`（C lib，跑一次）→ `aos-exec`（在工作區執行一個資料夾程式）→ `aos-loop`（一拍拍跑）／`aos-fsm`（一拍跑一格）→ `aos-daemon`（顧一群 loop）；
旁邊三個幫手：`aos-util`（全家共用的函式庫）、`aos-directive`（解 `$ref`／`$env`）、`aos-schema`（用 JSON Schema 驗 JSON）。**

> **現況（2026-10-23）：提供 `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 四支命令列（C++），行為對齊 `proto8/bin` 的 10-22 版。10-23 起整個 `impls/` 進 git；舊快照 `backup/` 10-23 使用者授權刪掉，下面提到的 `backup/…` 都已不在。**
>
> **10-23 命名統合**（使用者「都先幫我統合」，對照表見 [thinking/2026-10-23-naming](../thinking/2026-10-23-naming.md)）：使用者看得到的名字全家照同一張表改——
> loop.json／daemon.json／子項的 `run` → `val`、daemon 的 `children` → `loops`；state 的 `state` 欄 → `phase`、`lap` → `beats`、`started` → `start_ticks`、心跳 `beat` → `at`
> （值改 ISO 8601 UTC 到毫秒，例 `2026-10-23T01:58:45.123+00:00`）；daemon 子項的 `exited` 拆成 `done`（自己結束）／`stopped`（daemon 收掉）；
> fsm trace 的 `ms` → `elapsed_ms`、`at` 也到毫秒；訊息裡的「第 N 圈」→「第 N 拍」；指示詞的 `at` → `$at`；錯誤代號照 C-54 收成 `…Missing`／`…Unknown`／`…Bad`／動作＋`Failed`
> （`Usage` → `ArgumentsBad`／`FlagUnknown`、設定檔 → `CfgMissing`／`CfgBad`、`WsMissing`、`DotenvBad`、`StateBad`、libaos 的 `CommandMissing`／`CommandBad`…，下面代號表是現行的）。
> 換完拿 `proto8/tests`（245 個；`test_tick` 用 bin 的 aos-tick，impls 沒有這支）對照，一樣只剩下面那兩個字面差別；`proto8/demo/run.sh` 換成 impls 四支跑，跟 bin 線逐行一樣（時間、pid 抹掉）。
>
> **10-23（對齊 bin 10-22，ideas 10-22 § 3、§ 6、§ 7）：** aos-exec 的 `.env` 改 dotenv 基礎子集（`export `、`=` 兩邊空白、引號、空白＋`#` 註解、去頭尾空白——值的空白照 python-dotenv 認 Unicode 空白、行首仍只認 ASCII）、
> 預設不蓋已有的、加不帶值的旗標 `--dotenv-override`（只管這一跳；`parse_cli` 收開關表）；aos-daemon 擋子項名字跟自己的 ctl／state 撞名（起來時 `CfgBad` 退 1、ctl 撞＝不採用）；
> aos-fsm 開跑時查整張表（表壞 `CfgBad`）、state 在但讀不了 `StateBad`、USAGE 補 `[旗標]`。aos-util 多一個 `aos/text.hpp`（Unicode 空白、UTF-8 檢查）。
> 拿 `proto8/tests` 對照（243 個）只剩兩個 inst 單子錯誤訊息字面的差別（見 [aos-exec](aos-exec/README.md) 的「拿 proto8/tests 對照」）。
>
> **10-21 晚（ideas 10-21 § 1～§ 9、`git show 08a511dd`）：** aos-exec 改成 `aos-exec [--ws WS] XXX [args...]`（旗標在 XXX 前、舊的位置 WS 拿掉；旗標解析在 aos-util 新的 `aos/cli.hpp`），
> 支援 `.env`（每走進一個資料夾就 cd、讀那裡的 `.env`、旗標蓋回，讀完才照 `$AOS_ENTRY` 挑入口；旗標 ＞ `.env` ＞ 原本環境 ＞ 預設），
> 資料夾與沒 `argv` 的 JSON 物件都一路往下、多一個環境變數 `AOS_CO`（共六個）、字串轉向＝全新的一跳；公開 API 收成 `run_cli`＋`run_inst`＋`argv0`。
> aos-loop、aos-fsm、aos-daemon 的命令列都是「旗標＋唯一一個設定檔（可寫 `檔#/指標`）」，`val` 只收字串或 `[目標, 參數...]`（內嵌單子寫 `loop.json#/body`），
> 每拍都在 fork 出來的子行程裡呼叫 aos-exec 的 `run_cli`；aos-loop 的 `max` 沒寫＝不限；aos-fsm 的 trace 拿掉 `timed_out`；
> aos-daemon 的子 loop 改經 aos-exec 起（exec 成 PATH 上的 aos-loop）。aos-directive 的 `$path` 改成字串拼接。
> `proto8/tests` 拿這四支跑（錯誤一行的代號抹掉；方法見 [aos-exec](aos-exec/README.md) 的「拿 proto8/tests 對照」）：exec、loop、fsm、daemon 都過，只剩要 bin 版 `aos-inst` 命令列的案例（impls 刻意沒有）。
> 動工前的樣子在 `backup/2026-10-21-night/`（10-23 已刪）。
>
> **10-21（對齊 bin 10-20 版）：**
> daemon 照新做法重寫（ideas § 25）、aos-loop 長出 `interval_ms`／`ctl`／`state`、指示詞與 argv 照 10-20 ideas D1～D15（`$ref` 的 `#/` 與 `$at`、argv 陣列放指示詞、
> argv[0] 帶 `/` 又 exec 不了交給 aos-exec、`$path`／`$prefix`、寫法寬容；`$fmt` 未定、沒做）。PATH 只放這四支的 `bin/` 跑 `proto8/demo`（含 demo/daemon），結果跟 bin 線逐檔一樣；
> `proto8/tests` 的 loop／fsm／daemon 測試拿這幾支跑也全過（exec 那幾份只差錯誤一行的寫法）。動工前的樣子在 `backup/aos-impls-2026-10-21-pre-align.tar.gz`（10-23 已刪）。
>
> **10-19 晚（ideas § 20、§ 23）：** aos-exec 在工作區執行一個 aos 程式（找入口、備好環境變數、cd 進去、開跑），
> 入口是 inst 單子時在行程內交給 `inst`（C lib）跑。`inst` 是 C 函式庫、不提供命令列；inst 單子的 JSON 解析不進 C 庫，放在 aos-exec 的 C++ 庫（`src/inst/`）。
> **aos-loop、aos-fsm 已照 10-19 的規則重寫**（§ 23「重寫吧，fsm一起做」）：行為跟 `proto8/bin` 的 Python 版一致（`val`／`max`、看結束碼；`start`／`states`、state 與 trace 在 `$AOS_STACK`），
> 都是「小庫＋薄命令列」、連 aos-exec 的公開 API `aos/exec.hpp`（10-21 晚起：每拍在子行程裡呼叫 `run_cli`）；aos-fsm 借 aos-loop 的 `run_beat` 跑一格。
> demo 的 agent-bob、agent-ann 在 impls 線（三支的 `bin/` 放 PATH）跑得通、結果跟 bin 線一樣（aos-fsm 的 `test_demo`）。
> `aos-util`、`aos-directive`、`aos-schema` 以**函式庫**的形式留著；aos-directive、aos-schema 的 `bin/` 不算對外提供。
> **`aos-inst`：已刪**（10-19，碼已併入 aos-exec 的 src/inst/，舊版在備份 backup/aos-impls-2026-10-19.tar.gz（10-23 已刪））。
> **`aos-daemon` 10-21 已重寫**（繼承 aos-loop 的 `Loop`；10-21 晚子 loop 改經 aos-exec 起，見 [aos-daemon](aos-daemon/README.md)）。舊的 aos-loop／aos-daemon 碼與 aos-fsm 設計稿在備份 backup/aos-impls-loop-fsm-daemon-2026-10-19-pre-rewrite.tar.gz（10-23 已刪）。

每個專案是一個獨立的 CMake 專案（照 [dcap](../../../dcap/README.md) 的慣例），行為比照 `proto8/lib/` 的 Python 版，
差異記在各自的 README。這一頁講「全家一樣的東西」，各專案的 README 只講自己。

## 地圖與依賴

```
 aos-daemon   一個 loop＋子 loop 的表：$AOS_STACK/<名字>/ 小格、ctl 增減、不自動重起、adopt   src/{daemon,child,common}
     │ 繼承 aos-loop 的 Loop；子 loop＝fork 後子行程呼叫 run_cli(-- 小格/loop.json#/_exec)，exec 成 PATH 上的 aos-loop
 aos-fsm      一拍跑一格：$AOS_STACK/state → 跑那格 → 碼 0 才換 next；trace.jsonl   src/{table,state,common}
     │ 跑一格借 aos-loop 的 run_beat（aos/loop.hpp）
 aos-loop     每拍跑一次 val：0 下一拍、10 停、其他非 0 失敗；轉訊號、收完 128＋N；interval_ms、ctl／state 窗    src/{beat,engine,common}
     │ 每拍：fork 子行程呼叫 aos-exec 的 run_cli({"--", 目標, 參數...})（等同起一支 aos-exec）
 aos-exec     [--ws WS] XXX——定工作區、走進去（cd、讀 .env）、挑入口、備六個 AOS_*、開跑   src/{cli,find,env,inst,launch,common}
     │        可執行檔／argv 陣列＝exec；inst 單子＝行程內交給 libaos、留著當監工
     │ 靜態連 inst（inst-static）、aos-directive、aos-util
     ▼
 inst         純 C 的 libaos：fork＋exec、等、限時收掉。零 malloc、給 FFI     include/aos.h、src/inst_*.c

 aos-util       全家共用：錯誤、三扇門（stdin／stdout／stderr）、旗標（10-21 起的 aos/cli.hpp＋舊的 aos/flags.hpp）、路徑與原子寫入、子程序、訊號
                ← aos-exec、aos-directive、aos-schema 都連它（aos-loop、aos-fsm 經 aos-exec 連到）
 aos-directive  解 JSON 裡的 {"$ref": 檔[#/指標][, "$at"]}、{"$env": 變數}，可帶 $path（字串拼接）、$prefix（lib＋bin） ← aos-exec 連它（單子、argv 陣列、JSON .env key 的指示詞）
 aos-schema     用 JSON Schema（draft-07）驗 JSON（lib＋bin）                  ← 獨立，只連 aos-util
```

| 專案 | 是什麼 | 產物 | 現況 | README |
|---|---|---|---|---|
| aos-exec | 命令列：`aos-exec [--ws WS] XXX [args...]`，在工作區執行一個 aos 程式（`.env`、含行程內跑 inst 單子）；庫有公開 API（`run_cli`、`run_inst`、`argv0`） | `lib/libaos-exec.a`、`bin/aos-exec` | **提供**（10-21 晚加旗標、`.env`、`AOS_CO`） | [aos-exec](aos-exec/README.md) |
| aos-loop | 命令列：`aos-loop [旗標] loop.json`，每拍跑一次 val；庫有公開 API（跑一拍、骨架 `Loop`、`loop_cli`） | `lib/libaos-loop.a`、`bin/aos-loop` | **提供**（10-19 晚重寫、10-21 加窗、10-21 晚收旗標） | [aos-loop](aos-loop/README.md) |
| aos-fsm | 命令列：`aos-fsm [旗標] fsm.json`，一拍跑一格 | `lib/libaos-fsm.a`、`bin/aos-fsm` | **提供**（10-19 晚新做） | [aos-fsm](aos-fsm/README.md) |
| inst | C 函式庫 libaos：起一個程式、等它結束、告訴你結果 | `lib/libinst.so`（FFI）、`lib/libinst.a` | 庫（不讀 JSON、沒有命令列） | [inst](inst/README.md) |
| aos-util | 全家共用的 C++ 函式庫 | `lib/libaos-util.a` | 庫 | [aos-util](aos-util/README.md) |
| aos-directive | 指示詞 `$ref`／`$env`（可帶 `$path`、`$prefix`；10-21 改版、10-21 傍晚 `$path` 改字串拼接） | `lib/libaos-directive.a`、`bin/aos-directive` | 庫（bin 不對外提供） | [aos-directive](aos-directive/README.md) |
| aos-schema | JSON Schema 驗證 | `lib/libaos-schema.a`、`bin/aos-schema` | 庫（bin 不對外提供；aos-exec 這次不連） | [aos-schema](aos-schema/README.md) |
| aos-inst | 命令列：一張 inst 跑一次 | `lib/libaos-inst.a`、`bin/aos-inst` | 已刪（10-19，碼已併入 aos-exec 的 src/inst/，舊版在備份 backup/aos-impls-2026-10-19.tar.gz（10-23 已刪）） | （已刪） |
| aos-daemon | 命令列：`aos-daemon [旗標] daemon.json`，顧一群子 loop（經 aos-exec 起） | `lib/libaos-daemon.a`、`bin/aos-daemon` | **提供**（10-21 重寫、10-21 晚子 loop 經 aos-exec） | [aos-daemon](aos-daemon/README.md) |

## 從哪開始讀

1. **aos-util**（最小）：全家的共同語彙——`aos::Error`、`aos::Json`、三扇門、旗標（`aos/cli.hpp`）、路徑、子程序、訊號。讀完它，別的專案裡沒解釋的名字都在這。
2. **inst**（C）：一個 `.h` 三個 `.c`，從 `src/inst_exec.c` 的 `aos_inst_start` 由上往下讀。
3. **aos-exec**：先看 `src/cli/cli.cpp` 的 `run_cli`（解旗標 → 一跳跳走 → 開跑），再看 `src/find/find.cpp` 的 `hop`（定工作區 → 走進去讀 `.env` → 挑入口 → 判種類），
   其餘照 README 的元素表進資料夾；inst 單子怎麼交給 libaos 在 `src/inst/`。
4. **aos-loop** → **aos-fsm** → **aos-daemon**：同樣先 `main.cpp`（各二三十行），再看 aos-loop 的 `src/beat/`（跑一拍：fork 子行程呼叫 aos-exec 的 `run_cli`）
   與 `src/engine/`（骨架 `Loop`：讀設定、每拍讀 ctl、睡、跑一拍、寫 state）；aos-daemon 是 `Loop` 的子類別，子 loop 在 `src/child/`。
5. aos-directive、aos-schema 各自獨立，用到再看。

每個專案的 README 章節順序都一樣：一句話＋比喻＋例子 → 用法 → 元素（資料夾地圖）→ 流程（從 main 往下）→ 為什麼這樣做 →
公開介面 → 跟 Python 版的差異 → 建置與測試 → 已知限制（沒有的章節就省）。每個原始檔開頭都有一段白話：它是哪個元素的哪一塊、對應 Python 版哪個函數。

## 慣例（全家一樣；新專案照這張做）

### 命名

| 東西 | 規則 | 例 |
|---|---|---|
| 專案＝資料夾＝CMake 函式庫 target＝vcpkg manifest 的 name | `aos-<短名>` | `aos-loop` |
| 函式庫產物 | `lib/lib<專案名>.a`（STATIC） | `lib/libaos-loop.a` |
| 執行檔 target／產物 | `<專案名>_main` → `bin/<專案名>` | `aos-loop_main` → `bin/aos-loop` |
| namespace | `aos::<短名>`，整個專案一層、不分子 namespace（看檔案在哪個資料夾就知道是哪個元素）；aos-util、aos-directive 直接 `aos` | `aos::loop::Engine` |
| 公開標頭 | 只有一個：`include/aos/<短名>.hpp`；好幾個：`include/aos/<短名>/*.hpp`；沒有要給別人用的就沒有 `include/` | `aos/inst.hpp`、`aos/loop/engine.hpp` |
| 元素 | `src/<元素>/`，元素的標頭跟資料夾同名 `src/<元素>/<元素>.hpp`，裡面列「幾塊 → 哪個檔」 | `src/table/table.hpp` |
| 跨元素共用 | `src/common/common.hpp`（型別別名、自己的錯誤代號） | |
| 入口 | `src/main.cpp`：只把元素串起來，不做事 | |
| 錯誤代號 | 常數 `code::Xxx`，字串＝跟 Python 版同名的 CamelCase（照 C-54：`…Missing`／`…Unknown`／`…Bad`／動作＋`Failed`） | `code::CfgBad` |
| 測試 | `tests/compare.py`（跟 Python 版逐案比）、`tests/test_cli.py`（命令列黑箱）、`tests/test_lib.*`（函式庫）、`tests/test_ffi.py`；ctest 名＝檔名去掉副檔名 | |

例外：`inst` 是純 C 專案，沿用 dcap 的 C 模板：資料夾 `inst`、target `inst`／`inst-static`、標頭 `aos.h`、函數 `aos_inst_*`。

### 寫法（不要太難）

- 好懂 > 巧妙 > 效能。普通函數、普通 struct、if／for；一個函數做一件事、短；名字直白。
- 不用：模板技巧、巨集魔法、多層繼承（daemon 繼承 loop 的拍引擎這一層是設計，到此為止）、`std::function`／`std::variant` 包閉包、
  ranges 管線、縮寫函式模板（`const auto&` 參數）、`std::exception_ptr`。要「一定收尾再丟例外」就寫 `try { } catch (...) { 收尾; throw; } 收尾;`。
- 每個 `if` 都加 `{}`；少用三元運算子（寫成 if）；少用 `auto`（型別寫出來）。
- C++：4 格縮排、120 欄；C（inst）：`clang-format --style=LLVM`、一行一件事（不在 if 條件裡賦值、不串長的 `&&`）。
- `Json`（nlohmann `ordered_json`）常拿來當「可能是 null」的值用（Python 遺風）：`Json last_code_`＝null 或數字。

### 錯誤

每支工具出錯都丟 `aos::Error{code, msg}`（aos-util 的 `aos/error.hpp`）；`main` 接到就 `aos::emit_error`：stderr 一行
`{"error": {"code", "msg"}}`、退出 1。**例外：aos-exec** 印的是一行 **`aos-exec: 代號 原因`**（例 `aos-exec: EntryMissing 入口不存在：nope`）、退出 1——
照 proto8 N-60／P-21「程式名: 原因」，代號放原因開頭給測試認（計畫 v2 衝突 4）。**aos-loop、aos-fsm 同格式**（`aos-loop: 代號 原因`、`aos-fsm: 代號 原因`）。`code` 看是哪種錯（跟 Python 版同名），`msg` 給人看（字面不保證）。
**一個代號只定義一次**：兩支以上會吐的放 aos-util 的 `aos::code`；只有一支會吐的放那支自己的 `code`；每支在自己的 `code` 裡
`using namespace aos::code;`，程式裡一律寫 `code::Xxx`。全家的代號：

| 代號 | 誰吐 | 什麼時候 |
|---|---|---|
| `ArgumentsBad` | 每支命令列（含 aos-exec、aos-loop、aos-fsm、aos-daemon） | 參數用錯（位置參數、旗標少了值、aos-schema 參數不是剛好一個）；10-21 起的四支：旗標缺值、沒給 XXX／設定檔、設定檔多給、不帶值的旗標寫成 `--x=V`（10-22）（10-23 統合前叫 Usage） |
| `FlagUnknown` | 10-21 起的四支（`aos/cli.hpp`）、10-16～17 那代（`aos/flags.hpp`；目前沒有程式叫它） | 不認得的旗標（10-23 統合前 `aos/cli.hpp` 這條也叫 Usage） |
| `InputBad` | aos-schema、aos-directive（aos-util 讀 stdin）；libaos（`aos_inst_strerror`） | stdin 一份 JSON 都解不出來（10-23 統合前叫 JsonSyntax）；libaos 的輸入 `in`／`out` 是 NULL、`argv` 空（10-23 統合前叫 FieldType） |
| `InputExtra` | aos-schema、aos-directive（aos-util 讀 stdin） | stdin 有好幾份 JSON |
| `CfgMissing` | aos-loop、aos-fsm、aos-daemon（`load_cfg`） | 設定檔（loop.json、fsm.json、daemon.json）不在；`#/` 指不到 |
| `CfgBad` | aos-loop、aos-fsm、aos-daemon | 設定檔讀不了、不是 JSON、`#` 後不是 `/`；不是物件、某個 key 型別不對、必填沒寫；`val` 寫成物件；aos-fsm 開跑時查整張表不合（10-22：`start`／`next` 不在表上、`next` 空字串或頭尾有空白、格的形狀不對）；aos-daemon 10-22 起：子項名字跟自己的 ctl／state 撞名（10-23 統合前分成 ReadFailed、JsonSyntax、FieldType、Conflict） |
| `StateBad` | aos-fsm | 10-22 起：`$AOS_STACK/state` 在但讀不了（沒權限、是資料夾、不是 UTF-8）（10-23 統合前叫 ReadFailed） |
| `SchemaMissing` | aos-schema | SCHEMA檔 不在（10-23 統合前叫 ReadFailed） |
| `WriteFailed` | aos-loop、aos-fsm、aos-daemon | state 窗寫不了；aos-fsm：`trace.jsonl`、`.state` 寫不了；aos-daemon：子項的 loop.json 寫不了 |
| `MkdirFailed` | aos-daemon、aos-exec | 資料夾建不了（aos-exec：`AOS_STACK`；aos-daemon：子項的小格） |
| `LaunchFailed` | inst、aos-loop、aos-daemon、aos-exec | 子程序起不來（執行檔不在、fork 失敗；aos-exec 還有 exec 失敗、libaos 起不來；aos-daemon：小格的 stderr 開不了） |
| `Internal` | 每支 | 照理不會發生的例外 |
| `DirectiveBad` | aos-directive（aos-exec 原樣透傳） | 指示詞解不開：`$env` 沒設、`$ref` 讀不到（含指到資料夾）／不是 JSON、指不到、繞圈（寫法不合不算錯，10-20 D13～D15） |
| `WsMissing`、`EntryMissing`、`EntryBad` | aos-exec | 見 [aos-exec](aos-exec/README.md)（`WsMissing` 10-23 統合前叫 WorkspaceMissing） |
| `DotenvBad` | aos-exec | `.env` 在但讀不到（權限、是資料夾、壞掉的捷徑）；`.env` 壞（格式不合〔10-22 起含引號沒收尾、引號裡有 `\`、單引號裡有 `${`、引號後有雜字、`=` 後空白再接 `#`〕、`${名字}` 沒設、不是 UTF-8）；JSON 的 `.env` key 指示詞解不開、名字不合。只印位置、不印值（10-23 統合前分成 EnvReadFailed、EnvBad） |
| `CwdMissing`、`OpenFailed`、`CommandMissing`、`CommandBad`、`WaitFailed`、`KillFailed`、`PathConflict`、`PathNotAbsolute` | libaos（`aos_inst_strerror`；aos-exec 跑 inst 單子起不來時放在 `LaunchFailed` 的原因開頭） | 見 [inst](inst/README.md)（`CommandMissing`／`CommandBad` 10-23 統合前叫 CommandNotFound／CommandNotExecutable） |
| `StackMissing` | aos-loop（定義在 `aos/loop.hpp`）、aos-fsm、aos-daemon | 要 `AOS_STACK` 卻沒設（loop 開了窗、fsm、daemon） |
| `StateUnknown` | aos-fsm | state 檔裡的狀態不在表上。見 [aos-fsm](aos-fsm/README.md) |
| （舊 aos-loop 的 `WindowMissing`、`StateWriteFailed`、`Signaled`、`CtlBad`、`CtlMissing`、`CtlReadFailed`；舊 aos-daemon 的 `CommandBad`、`OpUnknown`、`NotFound`、`Exists`、`ScanFailed`、`ReplyFailed`、`PolicyFailed`、`RestartFailed`、`TableWriteFailed`） | 已隨舊版換掉 | ctl 壞不是錯（不採用、記在 state 的 `last_warning`） |
| `SchemaBad` | aos-schema | schema 不合 draft-07、`$ref` 指不到 |

### 命令列：設定、旗標、三扇門、指示詞

> **10-19 起的命令列（aos-exec、aos-loop、aos-fsm、aos-daemon）不照這一節**：不讀 stdin 設定，設定只認設定檔（loop.json、fsm.json、daemon.json 是唯一的位置參數，可寫 `檔#/指標`；ideas § 22「捨棄舊的」、10-21 傍晚 § 9），
> 不寫結果 JSON（結果＝結束碼），錯誤一行「程式名: 代號 原因」。**10-21 起收旗標**（ideas 10-21 § 1～§ 3）：旗標寫在位置參數前面，`--x V` 或 `--x=V`、重複給最後一個算、`--` 結束旗標、
> 第一個不是旗標的參數起原樣；不認得＝`FlagUnknown`、缺值＝`ArgumentsBad`。規則在 aos-util 的 `aos/cli.hpp`（`parse_cli`、`load_cfg`；對應 bin 的 `aos_flags.py`）：
> aos-exec 有 `--ws` 與不帶值的 `--dotenv-override`（10-22）；aos-loop、aos-daemon 有 `--max`、`--interval-ms`、`--ctl`、`--state`（旗標 ＞ 設定檔 ＞ 預設）；aos-fsm 目前沒有旗標。
> 下面是 10-16～17 那代（aos-schema、aos-directive 的 bin）的規矩。

- **設定只從 stdin 讀一份 JSON**（`aos::read_stdin`）：空的＝`{}`、多份＝`InputExtra`、解不出來＝`InputBad`、壞掉的尾巴丟掉。
  沒有 TARGET、沒有 `-`：任何位置參數＝`ArgumentsBad`（跟 Python 版刻意不同）。
- **旗標＝純量 key 原名**（`aos::parse_flags`）：`--timeout_ms 100`、`--stop_on_end true`（底線；不收減號寫法）。每個旗標都要帶值；
  值先當 JSON 解、解不了當字串；蓋過 stdin 的同名欄位。清單由各專案的欄位表自動產生；陣列、物件（`argv`、`envs`、`inst`、舊 daemon 的子項表）不鏡射。
  `--` 後面整段：aos-inst 拿去蓋 `argv`；loop、daemon 不收（`ArgumentsBad`）。
- **指示詞**（aos-directive）：stdin 與每個旗標值裡的 `{"$ref": 檔}`、`{"$env": 變數}` 先解開再驗欄位。
- **結果 stdout 一行 JSON、退出 0**（`aos::emit`，排版同 Python `json.dumps`，key 照原順序）；**出錯 stderr 一行、退出 1**。
  子程式回非 0 不算錯（那是結果）。
- **找兄弟執行檔**（`aos::sibling_tool`）：自己是 `impls/X/bin/X`，要叫 Y 就叫 `impls/Y/bin/Y`，不看 PATH。

### 目錄（照 dcap，三處偏離）

```
<專案>/
  CMakeLists.txt    include(../cmake/settings.cmake) → project() → 兄弟專案 → 函式庫 → if(PROJECT_IS_TOP_LEVEL) 執行檔＋測試
  vcpkg.json        nlohmann-json（aos-schema 再加 json-schema-validator）
  include/aos/...   公開標頭（有要給別人用的才有）
  src/              除 main.cpp 全進函式庫；一個元素一個資料夾
  tests/            compare.py／test_cli.py／test_lib.*（＋資料）
  bin/ lib/ build/  產物與建置目錄（不進 git）
```

跟 dcap 不同的三點（使用者拍板）：函式庫 **STATIC**（不是 SHARED）、執行檔 **`-static-pie` 全靜態**（啟動不必動態載入 libstdc++，
aos-inst 實測啟動 0.78ms→0.37ms、記憶體 5→2.3MB；代價是執行檔較大、glibc 有安全更新要重建）、**兄弟專案用 `add_subdirectory` 一起編**
（它們的 `lib/*.a` 會輸出到各自的資料夾，所以建 aos-fsm 也會更新 `../aos-loop/lib/`、`../aos-exec/lib/`——可接受）。

### 建置

每個專案都一樣：

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- 共通的 CMake 設定在 [`cmake/settings.cmake`](cmake/settings.cmake)（vcpkg toolchain 的找法、Release、`compile_commands.json`、PIC、
  `-static-pie` 與 sanitizer 例外），各專案 `project()` 之前 `include` 它。只有 `set()`，沒有函數、沒有巨集。
- nlohmann-json 走 vcpkg（toolchain 自動找 `~/dev/vcpkg`，或設 `VCPKG_ROOT`）；每個專案一份 `vcpkg.json`（可接受的重複）。
- 要用兄弟專案就 `add_subdirectory`，包在 `if(NOT TARGET ...)` 裡（同一個 build 裡好幾個專案都要它，只 add 一次）：
  ```cmake
  if(NOT TARGET aos-util)
    add_subdirectory(../aos-util aos-util-build)
  endif()
  target_link_libraries(你的target PRIVATE aos-util)
  ```
- 依賴順序：inst → aos-util → aos-directive → aos-exec → aos-loop → aos-fsm、aos-daemon；aos-schema 獨立（庫留著，沒人連）。
  一次全建（aos-fsm、aos-daemon 的 `test_demo` 要前面幾支的 `bin/` 先建好，所以照這個順序）：
  ```sh
  for p in inst aos-util aos-directive aos-schema aos-exec aos-loop aos-fsm aos-daemon; do (cd $p && cmake -B build && cmake --build build && ctest --test-dir build) || break; done
  ```
- Sanitizer：`cmake -B build-asan -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined"`（`settings.cmake` 看到 `-fsanitize` 就不加 `-static-pie`）。
  帶 sanitizer 的 `.a` 會蓋掉共用的 `lib/`，建完記得重建正常版。
- clangd 看 `build/compile_commands.json`（會自己去 `build/` 找）。

### 測試

| 檔 | 做什麼 | ctest 名 | 誰有 |
|---|---|---|---|
| `tests/test_cli.py` | 命令列黑箱：餵 stdin 或設定檔、看退出碼與輸出 | `test_cli` | aos-util、aos-directive（57 組）、aos-schema（12 案）、aos-exec（56 組）、aos-loop（40 組）、aos-fsm（29 組）、aos-daemon（20 案，unittest） |
| `tests/test_demo.py` | 整合：proto8/demo 在 impls 線跑，跟 proto8/bin 線逐檔比 | `test_demo` | aos-fsm（agent-bob、agent-ann）、aos-daemon（demo/daemon） |
| `tests/test_lib.*` | 函式庫 | `test_lib`、`test_lib_*` | inst（C；另一份 `test_lib_nopidfd` 走輪詢退路）、aos-schema、aos-util（7 條，含 10-23 的代號 `cli`） |
| `tests/test_ffi.py` | Python ctypes 載 `.so` | `test_ffi` | inst |

## 新專案照這張清單

1. 資料夾 `aos-<短名>`；`CMakeLists.txt` 照 [aos-directive 的](aos-directive/CMakeLists.txt)（最短的一份）改名字；`vcpkg.json` 抄一份改 name／description。
2. namespace `aos::<短名>`；`src/common/common.hpp` 放 `using aos::Error; using aos::Json;` 與自己的 `code`（`using namespace aos::code;` ＋獨有的）。
3. 先用一句話說清楚這支程式是什麼，從那句話裡的元素拆 `src/<元素>/`，每個元素一個同名 `.hpp` 列「幾塊 → 哪個檔」；跨元素共用的進 `common/`；
   全家都要的進 aos-util。`main.cpp` 只串。
4. 命令列：`aos::parse_flags` ＋ `aos::read_stdin` ＋ `aos::resolve` ＋ 欄位表；結果 `aos::emit`、錯誤 `aos::emit_error`。
5. README 照上面的章節順序；只講自己，共通的連回這一頁。
6. 測試：有 Python 版就 `tests/compare.py`；命令列黑箱 `tests/test_cli.py`；ctest 名＝檔名。
7. 每個檔開頭一段白話（哪個元素的哪一塊、對應 Python 哪個函數）；寫法照「寫法（不要太難）」。
