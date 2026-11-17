← [入口](../cpp-py-改名.md)｜涵蓋：`impls/` 11 個專案現在的形狀、誰依賴誰、產物與測試、跟標準形式差在哪｜下一份 [02-現況-py與cmd](02-現況-py與cmd.md)

# 現況：`impls/`（C／C++）

數字是 `wc`、`grep` 實數的（子 agent 盤、我抽核）；標「估」的才是估的。

## 一張圖：誰依賴誰

```
util ◄── directive ◄── exec ──► inst（純 C）
  ▲          ▲          ▲
  │          └── json   └── loop ◄── fsm
  ├── lock ◄── post ◄─┬─ daemon ──► loop
  └───────────────────┴─ llm
```

箭頭＝「依賴」。最底是 `util`、`inst`；最上是 `daemon`、`fsm`、`llm`、`json`。

## 每個專案一列

| 專案 | 標頭放哪 | 產物 | 程式／標頭行 | 測試（py 支） | 碰 Linux 機制嗎 |
|---|---|---|---|---|---|
| aos-util | `include/aos/util/` | 只有 `.a` | 1128／341 | 1 | 半（訊號、`/proc`） |
| aos-inst（純 C） | `include/aos/inst.h` | `.so`＋`.a` | 697／306 | 0 | 是（fork、exec、setsid） |
| aos-directive | `include/aos/` | `.a`＋執行檔 | 596／144 | 2 | 否（純解 `$ref`／`$env`） |
| aos-exec | `include/aos/` | `.a`＋執行檔 | 1528／310 | 4 | 是（exec、訊號、epoll） |
| aos-json | 沒有 `include/` | `.a`＋執行檔 | 2277／302 | 3 | 否（純 JSON） |
| aos-lock | `include/aos/` | `.a`＋執行檔 | 674／69 | 2 | 是（flock、fork） |
| aos-post | `include/aos/` | `.a`＋執行檔 | 859／164 | 0 | 輕（檔案信箱） |
| aos-loop | `include/aos/` | `.a`＋執行檔 | 1340／418 | 3 | 是（fork、訊號） |
| aos-fsm | 沒有 `include/` | `.a`＋執行檔 | 306／97 | 2 | 本身是邏輯，借 loop |
| aos-daemon | 沒有 `include/` | `.a`＋執行檔 | 3554／504 | 12 | 最重（cgroup、fork、setsid） |
| aos-llm | `include/aos/` | `.a`＋執行檔 | 886／172 | 6 | 輕；**沒有 HTTP**，只是往信箱寄收信 |

合計約 13,800 行程式＋2,800 行標頭，35 支測試。

對你說的「C++ 放會與 linux 機制牽扯的東西」：`directive`、`json`、`fsm`、`llm` 四個不算 Linux 機制。其中 `directive` 被 `exec`、`loop`、`json` 連進去，拿不走；`fsm` 靠 `loop`；`json`、`llm` 是獨立的葉子。這次改名不動它們的語言（[08](08-要裁的題.md) 題 X-4 只問你要不要記一筆）。

## 現在怎麼建、產物在哪

| 項目 | 現況 |
|---|---|
| CMake | 頂層一份（`foreach` 照依賴序加 11 個）＋每專案一份；每專案也能單獨建，靠 `include(../cmake/settings.cmake)` 與 `if(NOT TARGET x) add_subdirectory(../x …)` 找兄弟 |
| 兩種建法 | 頂層註解自己寫「擇一，不要同時跑（寫同一個 `bin/`、`lib/` 會互蓋）」 |
| 產物 | **寫回原始碼樹**：每專案自己的 `<專案>/bin/`、`<專案>/lib/`（`set_target_properties` 逐個指定），不進 `build/` |
| `PATH` | `env.sh` 掃 `impls/*/bin`，加 9 段（`util`、`inst` 沒有執行檔） |
| vcpkg | 12 份 `vcpkg.json`（頂層 1＋專案 10，`inst` 沒有），內容都只有 `nlohmann-json` |
| 共通設定 | `cmake/settings.cmake` 一檔：找 vcpkg、Release、`compile_commands`、PIC、static-pie、C++20 |
| 沒有的 | `CMakePresets.json`、`install()`、`enable_testing`／`add_test`、任何 C++ 寫的測試 |
| `.gitignore` | 每專案一份（`bin/ lib/ build/`）；repo 根也忽略 `build/`、`bin/` |

## 測試怎麼跑、怎麼找東西

- 全部是 Python `unittest`（`python3 -m unittest discover`），一支 C++ 測試都沒有。
- 35 支裡 **19 支寫死 `parents[1]/'bin'/名`**（直接吃自己專案的 `bin/`）；另有幾支拼 `PROTO/'impls'`、`PROTO/'lib'`、`PROTO/'cmd'`（daemon 的 `support.py` 一支就拼三種）。

## C++ 程式自己找不找夾名

不找。`impls`、`lib`、`cmd` 在 C++ 裡只出現在註解；沒有 `getenv("AOS_HOME")`。執行期只讀 `AOS_DAEMON`、`AOS_WS`、`AOS_CLOCK` 這類，與 repo 夾名無關。**所以改名對 C++ 原始碼零影響，成本全在外面。**

## `impls/` 裡不是 C++ 的

35 支測試 `.py`、daemon 的 `examples/root/`（systemd 單元、`.env` 範例、s6 腳本）、`docs/`（4 篇說明：現況地圖、從哪讀起、錯誤代號、命令列與新專案清單）、11 份 README、`aos-daemon/archive/`（2 份 md）、`aos-inst/.vscode/`。

## 跟「標準 C++ 專案」差在哪

| 差在哪 | 標準做法 | 要動的（估） |
|---|---|---|
| 產物寫回原始碼樹、分 10 處 | 全進一個 `build/` | 10 份 CMakeLists、19＋6 支測試、`env.sh` |
| 兩種建法並存 | 一個專案、一種建法 | 11 份 CMakeLists 各刪幾行 |
| 12 份 vcpkg.json | 一份 | 刪 10 份 |
| 沒有 presets | `CMakePresets.json` | 新增 1 檔 |
| 測試沒進 ctest | `add_test` | 頂層加約 15 行 |
| 沒有 `install()` | 有 | 11 份各加 2～3 行（要不要做是題 C-3） |
| 函式庫與執行檔同夾 | `libs/`＋`apps/` 分開 | 9 個 `main.cpp` 搬家、9 份 CMakeLists、README 連結約 150 處 |
| 3 個專案沒有 `include/` | 公開標頭進 `include/` | 它們沒有對外 API，可以不動 |
| 標頭 `include/aos/x.hpp` | 同（namespace 式） | 已合，不動 |
