# proto8/cpp：aos 的 C／C++ 實作（總入口）

**一句話：這一家小工具做的是同一件事——「在工作區起一個程式、等它、看它的結束碼」——由小到大疊起來：
`aos-inst`（C lib，跑一次）→ `aos-exec`（在工作區執行一個資料夾程式）→ `aos-loop`（一次次跑）／`aos-fsm`（一次跑一格）→ `aos-daemon`（顧一群 proc）；
旁邊兩個幫手：`aos-util`（全家共用的函式庫）、`aos-directive`（解 `$ref`／`$env`）。**

語意以 [NORMS](../docs/NORMS.md) 為準；各支 README 只寫用法、跟規範不同或規範沒寫的實作細節、實作注意、建置與測試。這一頁講「全家一樣的東西」。

## 編法：頂層一份 Makefile

11-17 起不用 CMake、vcpkg（使用者裁定外部依賴 D-1「單檔收進 repo」、D-2「換頂層 Makefile」）：[`Makefile`](Makefile) 一份編全家（11 個庫、9 支執行檔），nlohmann json 是收進 repo 的單檔 [`third_party/nlohmann/json.hpp`](third_party/nlohmann/json.hpp)（官方 v3.12.0，附 `LICENSE.MIT`）。細節見 [04「建置」](docs/04-命令列-設定-旗標-三扇門-指示詞與新專案照這張清單.md#建置)。

- **平常**：在 proto8 跑 `python3 install.py`——先查相依（必需 g++ ≥ 10、gcc、make、ar），清空再填 `proto8/bin/`（9 支執行檔）與 `proto8/include/`（公開標頭）；中間檔與 `.a`／`.so` 在 `cpp/build/`，log 在 `cpp/build/build.log`，另產 `cpp/compile_commands.json` 給 clangd。重跑＝全新安裝，C++ 沒改時幾秒。
- **開發時只重編一支**：`make -C proto8/cpp -j8 BINDIR=$AOS_HOME/bin aos-exec`（目標名就是執行檔名，會連帶重編它要的庫；或直接重跑 install.py）。不給 `BINDIR` 時執行檔在 `cpp/build/bin/`。
- **sanitizer**：`make STATIC= CXXFLAGS="-O1 -g -fsanitize=address"`（sanitizer 不能全靜態）。**改 CXXFLAGS 要先 `make clean`**，Makefile 不會因為旗標變了自己重編。
- 測試到 `proto8/bin/` 找執行檔，所以跑測試前要先 `python3 install.py`。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-現況與地圖與依賴](docs/01-現況與地圖與依賴.md) | 現況；地圖與依賴 |
| [02-從哪開始讀與慣例](docs/02-從哪開始讀與慣例.md) | 從哪開始讀；慣例（全家一樣；新專案照這張做）：開頭、命名、寫法（不要太難） |
| [03-錯誤](docs/03-錯誤.md) | 慣例（全家一樣；新專案照這張做）（續）：錯誤 |
| [04-命令列-設定-旗標-三扇門-指示詞與新專案照這張清單](docs/04-命令列-設定-旗標-三扇門-指示詞與新專案照這張清單.md) | 慣例（全家一樣；新專案照這張做）（續）：命令列：設定、旗標、三扇門、指示詞、目錄（照 dcap，三處偏離）、建置、測試；新專案照這張清單 |

<a id="現況"></a>
<a id="地圖與依賴"></a>
<a id="從哪開始讀"></a>
<a id="慣例全家一樣新專案照這張做"></a>
<a id="命名"></a>
<a id="寫法不要太難"></a>
<a id="錯誤"></a>
<a id="命令列設定旗標三扇門指示詞"></a>
<a id="目錄照-dcap三處偏離"></a>
<a id="建置"></a>
<a id="測試"></a>
<a id="新專案照這張清單"></a>
