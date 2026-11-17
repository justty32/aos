# 03 CMake 還是 Makefile

← [入口](../外部依賴.md)｜上一份 [02-nlohmann-json](02-nlohmann-json.md)｜下一份 [04-cgroup-s6-系統工具](04-cgroup-s6-系統工具.md)

**結論**：C++ 這塊確實不大（11 個專案、82 個原始檔），而且每個專案長得一樣（`src/` 全編成一個 `.a`、`src/main.cpp` 連成一個執行檔），Makefile 寫得出來，實測手寫 26 行就編好兩個專案，增量編譯與平行都正常。**推薦換一份頂層 Makefile、安裝腳本叫 `make -j`**；代價是 clangd 要的 `compile_commands.json` 得自己產、改旗標不會自動全部重編。想零風險的話，留 CMake 只拿掉 vcpkg 也完全可以（[02](02-nlohmann-json.md) 已實測）。

## CMake 現在做了哪些事

| 事 | 怎麼做的 |
|---|---|
| 共通設定 | `impls/cmake/settings.cmake`：找 vcpkg toolchain、預設 Release、輸出 `compile_commands.json`、全開 PIC、執行檔 `-static-pie`（`-fsanitize` 時改動態）、C++20 不開 GNU 擴充 |
| 專案間依賴順序 | 每個專案用 `add_subdirectory(../兄弟)` 拉進依賴，外包 `if(NOT TARGET …)` 防重複；頂層 `impls/CMakeLists.txt` 照順序 add：inst、util、directive、exec、json、loop、lock、post、fsm、daemon、llm |
| 依賴圖 | util ← directive ← exec（另連 inst 的 `.a`、pthread）← loop ← fsm；daemon ← loop＋post；lock ← util；post ← util＋lock；json ← util＋directive；llm ← util＋post |
| 收原始碼 | `file(GLOB_RECURSE … CONFIGURE_DEPENDS src/*.cpp)` 去掉 `src/main.cpp`；例外 `aos-daemon` 手列 16 檔 |
| 產物位置 | 寫回各專案自己的 `bin/`、`lib/`（`RUNTIME/ARCHIVE_OUTPUT_DIRECTORY = 專案原始碼夾`）；`aos-util` 只有 `.a`、`aos-inst` 出 `.so`＋`.a`（C11、`-Werror`、預設 hidden，只匯出標了 `AOS_API` 的函式） |
| 兩種建法 | 頂層一次建，或 `cd 專案 && cmake -B build` 單獨建（兩種同時跑會互蓋） |
| 測試怎麼找執行檔 | **不用 ctest**。測試是 Python unittest，把 `impls/*/bin` 加進 PATH（例：`aos-daemon/tests/support.py`）；`env.sh` 也一樣加 |
| 要多久（公司 WSL、8 核、`-j8`） | 全新編 159.8 秒；沒改東西 0.34 秒；動 `aos-lock` 3 個 `.cpp` 4.9 秒 |

## 三個選項

| 選項 | 要重寫多少 | 得到 | 失去 |
|---|---|---|---|
| **A 留 CMake，只拿掉 vcpkg** | `settings.cmake` 刪 toolchain 段、`aos-util` 改兩行、刪 11 份 `vcpkg.json`；成品位置照 `cpp-py-改名` 的 S2 改 | 零風險（已實測編過）；IDE（CLion、VS Code CMake Tools）與 clangd 照舊；改旗標會自動重編 | 使用者還是要裝 CMake ≥ 3.21；12 份 CMake 檔（共 512 行，扣掉註解與空行 322 行）照舊要維護 |
| **B 換一份頂層 Makefile（推薦）** | 新寫一份約 100 行（**估的**，見下）取代 11 份 CMakeLists 與 `settings.cmake` | 少一個要裝的東西（make 跟 g++ 幾乎總是一起裝）；一份檔看得完；增量、平行（`-j`）、標頭依賴追蹤（`-MMD -MP`）都有 | clangd 要的 `compile_commands.json` 得另外產（安裝腳本順手寫，約 20 行 Python，或用 `bear`）；改 `CXXFLAGS` 不會自動全部重編（要 `make clean`）；IDE 的 CMake 整合沒了；單獨建一個專案變成 `make aos-exec` |
| C 安裝腳本直接叫 g++ | Python 裡自己寫：收檔、照依賴順序編、`ar`、連結；要增量就得自己比時間、讀 `.d` 檔；要平行就自己開執行緒池。估 150～200 行 | 只剩 g++ 一個工具；全在 Python 裡，跟安裝腳本同一份 | 等於重寫一個小 make：增量與依賴追蹤自己做、容易出錯；開發時每次都要叫安裝腳本才能編；compile_commands 一樣要自己產 |

B 和 A 的差別主要在「使用者要多裝一個 CMake」以及「我們要維護幾份建置檔」；功能上兩者都夠。你說「反正我們C++這塊也沒多少東西」，實況支持這句，所以推薦 B。

## 實測：手寫 Makefile 編 `aos-util`＋`aos-lock`

在 `~/.aos/scratch/deps-1117/mk/Makefile`（26 行，含註解與 `clean`），用 [02](02-nlohmann-json.md) 收進來的單檔 `json.hpp`：

| 檢查 | 結果 |
|---|---|
| 產物 | `libaos-util.a`、`libaos-lock.a`、`bin/aos-lock`（`-static-pie`） |
| `make -j8` 全新編 | 20.2 秒，退 0；`aos-lock --help` 正常 |
| 再跑一次（沒改東西） | `make -q` 退 0（已是最新） |
| 改一個 `aos-util` 公開標頭（`clock.hpp`） | 只重編 3 個用到它的 `.o`，依賴追蹤有效 |

寫法重點：每個專案一組「`find src -name '*.cpp' ! -path '*/src/main.cpp'` → `.o` → `ar rcs` 成 `.a`」，執行檔＝`main.o`＋自己的 `.a`＋依賴的 `.a`（照依賴圖由上往下排）；旗標 `-std=c++20 -fPIC -Wall -Wextra -MMD -MP -O2 -DNDEBUG`，nlohmann 用 `-isystem`。全家版要多處理的：`aos-inst` 是 C（另一組旗標、多出一個 `.so`、`-fvisibility=hidden -Werror`）、`aos-exec` 連 `-pthread`、sanitizer 建置時把 `-static-pie` 換掉（`make STATIC=`）。所以估 100 行上下，**全家版沒寫、沒測**。

## 沒細看

- 家機 Manjaro 的 make／g++ 版本與 `libc.a`。
- CMake 的 `CONFIGURE_DEPENDS` 與 Makefile 的 `find` 在「新增檔案」時都會自動收進來；「刪檔」後 Makefile 會留下舊的 `.d`，`-MP` 讓它不報錯，**沒實測刪檔情境**。
