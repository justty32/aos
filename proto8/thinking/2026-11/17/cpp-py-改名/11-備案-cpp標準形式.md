← [入口](../cpp-py-改名.md)｜涵蓋：【備案，定案前攤的】C++ 照「標準 CMake 專案形式」整理的三個方案（只改名／一個專案產物進 build／libs＋apps 重排）；使用者 11-17 下午說「C++這塊也先不考慮vcpkg, cmake啥的」，沒走，留作紀錄｜主案看 [04](04-主案-安裝包形狀.md)

> 本檔寫在方向定案之前。裡面的「推薦」「題 C-3」等字樣是當時的，現在以 [04](04-主案-安裝包形狀.md)、[08](08-要裁的題.md) 為準。

# C++ 方案：`impls/` → `cpp/`

## 「標準 C++ 專案」指的是哪幾件事

| 件 | 白話 | 現在 |
|---|---|---|
| 一個頂層 CMake、子專案掛在下面 | 一個入口、一種建法 | 有頂層，但每專案也能單獨建，兩種並存 |
| 公開標頭在 `include/`、實作在 `src/`、測試在 `tests/` | 看夾名就知道哪些是給別人用的 | 8 個已是；3 個沒對外 API、沒有 `include/` |
| 產物全進 `build/` | 原始碼樹保持乾淨，刪 `build/` 就回到原樣 | 產物散在 10 個 `<專案>/bin`、`<專案>/lib` |
| `CMakePresets.json` | 「怎麼建」寫成檔，`cmake --preset default` 一行 | 沒有 |
| 測試進 `ctest` | `ctest` 一行跑全部 | 沒有；35 支 Python 測試各自 `unittest discover` |
| `install()` 目標 | `cmake --install` 把成品抄到指定位置 | 沒有 |
| 函式庫與執行檔分開（`libs/`＋`apps/`） | 大專案常見，小專案不一定 | 同一夾 |
| 相依一份清單 | 一份 `vcpkg.json` | 12 份，內容一樣 |

## 三個方案對照

| | C-小：只改名 | C-中：一個專案、產物進 `build/`（推薦） | C-大：`libs/`＋`apps/` 重排 |
|---|---|---|---|
| 夾名 | `cpp/` | `cpp/` | `cpp/` |
| 子專案夾 | 原樣 | 原樣（`cpp/aos-exec/…`） | 拆成 `cpp/libs/exec`、`cpp/apps/aos-exec` |
| 產物 | 各專案 `bin/` `lib/` | `cpp/build/bin/`、`cpp/build/lib/` | 同中，另有 `install` 到 `cpp/dist/` |
| `PATH` | 10 段 | **1 段** | 1 段 |
| 建法 | 兩種並存 | 只留頂層；`cmake --preset default && cmake --build --preset default` | 同中 |
| 測試 | 各自跑 | `ctest` 包住 35 支 Python 測試 | 同中，另可加 C++ 單元測試 |
| vcpkg | 12 份 | 1 份 | 1 份 |
| 動的檔（不含純文字） | 約 73 | 約 73＋約 45 | 約 73＋約 45＋約 60 |
| 風險 | 低 | 低～中（19 支測試吃自己專案的 `bin/`） | 中（README 連結約 150 處、每個專案的 CMake 重寫） |

三個方案都另有「只是文字」的約 440 處／170 檔（條文、wf、README）要不要跟（題 X-2）。

## C-小：只改名

```
cpp/
  CMakeLists.txt  vcpkg.json  cmake/  docs/  README.md
  aos-util/  aos-inst/  aos-directive/  aos-exec/  aos-json/
  aos-lock/  aos-post/  aos-loop/  aos-fsm/  aos-daemon/  aos-llm/
    └ 每個：CMakeLists.txt  include/  src/  tests/  bin/（產物）  lib/（產物）
```

- 動：`env.sh`、`install.sh`、約 60 支測試裡的 `"impls"`、`index_gen.json` 與描述檔的 98 個鍵、`scope.py` 禁區表、兩處錯誤訊息。C++ 原始碼與 CMake 邏輯零改（只有註解與選項名 `AOS_IMPLS_ALL`）。
- 好處：最快、最不會壞。
- 代價：名字換了，形狀沒變；「標準形式」一件都沒做。

## C-中：一個專案、產物進 `build/`（推薦）

```
cpp/
  CMakeLists.txt        唯一入口：加 11 個子專案、enable_testing、35 支測試的 add_test
  CMakePresets.json     新：default（Release）、asan
  vcpkg.json            唯一一份
  cmake/settings.cmake  不動
  docs/  README.md
  aos-util/ … aos-llm/  每個：CMakeLists.txt  include/  src/  tests/
  build/                產物（不進 git）：bin/ 放 10 支執行檔、lib/ 放 .a 與 .so
```

- 動：C-小那些，再加——11 份 CMakeLists（輸出位置改一行、拿掉單獨建的守衛）、刪 10 份 `vcpkg.json` 與 11 份專案 `.gitignore`、19＋6 支吃 `<專案>/bin` 的測試改從 `PATH` 找、`env.sh` 的 `PATH` 段。
- 好處：`PATH` 從 10 段變 1 段；原始碼樹乾淨；重建樹步驟單裡「編 C++」變成兩行固定指令；「兩種建法會互蓋」的雷沒了；`ctest` 一行跑完 C++ 區全部測試。
- 代價：不能再 `cd aos-exec && cmake -B build` 單獨建一個（要單獨編一個改用 `cmake --build build --target aos-exec_main`）。
- 風險：有測試偷吃自己專案 `bin/` 的；全掃一次就清得掉。
- **實測**：暫存複本上把 10 份 CMakeLists 的輸出位置用一行 `sed` 改到 `build/`，夾名同時改成 `cpp/`，結果見 [09](09-實測紀錄.md)。
- 小發現：`env.sh` 現在掃的是 `impls/*/bin`；產物進 `cpp/build/bin` 後，`cpp/*/bin` 這個掃法**剛好還吃得到**（`build` 也是一個夾）。好事是過渡期不會斷，壞事是它是碰巧，施工時要改成明寫。

## C-大：`libs/`＋`apps/` 重排

```
cpp/
  CMakeLists.txt  CMakePresets.json  vcpkg.json  cmake/  docs/
  libs/   util/ inst/ directive/ exec/ json/ lock/ post/ loop/ fsm/ daemon/ llm/
            └ 每個：include/aos/…  src/  tests/
  apps/   aos-exec/ aos-json/ aos-lock/ …（每個只有 main.cpp 與 CMakeLists）
  build/  dist/（install 出來的 bin/ lib/ include/）
```

- 多動：9 個 `main.cpp` 搬家、每專案 CMake 拆成兩份、11 份 README 與約 150 處相對連結、`install()`＋匯出設定讓外面 `find_package(aos)`。
- 好處：最像教科書；`impl_cpp/` 或別的專案想連 aos 的函式庫有正式入口。
- 代價：現在沒有人在外面連這些 `.a`；每個專案 3 個夾變成散在兩棵樹，讀一個專案要跳兩處。
- 風險：搬動多，歷史（`git blame`）要跟著 `--follow`。

## 推薦：C-中

理由三個：

1. 你要的「標準形式」裡最有感的四件（一個入口、產物進 `build/`、presets、ctest）它都給了，而且每一件都能用一行指令驗。
2. 它直接幫到你要自己重建樹這件事：編 C++ 變成固定兩行，`PATH` 少九段。
3. C-大多出來的 `libs/`＋`apps/` 與 `install()`，現在沒有使用者（沒有外部專案連這些函式庫）；等有了再做，不會白做。

`install()` 要不要現在就加，單獨列一題（C-3）：加了可以把成品抄到 `cpp/dist/`，讓「跑的版本」與「正在編的版本」分開；不加就是 `PATH` 直接指 `build/bin`，編到一半樹會用到半成品。
