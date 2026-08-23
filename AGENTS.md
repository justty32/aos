# aos — AI agent 專案備忘

aos = **一個 monorepo：只有一支執行檔 `aos`，靠子命令把陸續長出來的各個小專案掛上去**（例如 `aos inst jobs.json`）。第一個小專案 `core/inst/` 是讀 JSON instruction、`fork`/`exec` 跑起來的 POSIX 指令執行器。用 C++23 寫，CMake + vcpkg 建置，**只能從 repo 根目錄 build**。

本檔是**最頂層路由器**：只指向下一層，**durable 細節一律不寫這裡**。

## 先讀哪裡

- **使用者要你動手做某件事** → **[wf/WORKFLOWS.md](wf/WORKFLOWS.md)**：依使用者意圖派發到對應工作流，再讀該工作流入口。
- **想看專案長怎樣** → **[wf/INDEX.md](wf/INDEX.md)**：repo 頂層結構地圖。
- **要改程式、先找檔** → **[wf/workflows/common/code-map.md](wf/workflows/common/code-map.md)**：哪個檔負責什麼，改東西之前先看這張圖。

> **本專案採「非侵入式」佈局**：頂層只留 `AGENTS.md` 與 `CLAUDE.md` 兩個入口，工作流的其餘檔案全部收在 [`wf/`](wf/) 裡，不去弄亂原本的 C++ 專案結構。唯一的例外是 `.claude/commands/`——slash 指令只有放在那裡才會被讀到，但它是隱藏資料夾，不影響觀感。

## 分層思想（本專案的組織原則）

整個 repo 是一棵**分層樹**，每一層**只指向下一層、不存下層的細節**：

```
AGENTS.md（本檔，最頂）→ wf/WORKFLOWS.md / wf/INDEX.md → 各工作流入口 → 工作流內容 → 子工作流…
```

- **README**＝初入一個資料夾**先讀的入口／導引**；**INDEX**＝**描述該資料夾頂層結構**的索引。小資料夾兩者合一，大了才分出獨立 INDEX。
- **durable 知識歸到它所屬的那一層／那個工作流**，絕不往上堆——所以 AGENTS.md 才這麼薄。要某主題的細節，順著上面的樹往下走，不在本檔找。
- **鐵律（always-on，任何工作流任何時候都遵守）**：
  1. 重構／整理必須**不改變原意**：程式的行為不變、文件的原意不變。改完一定要**從 repo 根目錄**跑驗證 `cmake --build --preset default && ctest --preset default`，**ctest 要全綠**（有哪些測試見 [wf/workflows/testing.md](wf/workflows/testing.md)）。
  2. **未經確認不 push、不開新工作**（commit 到 `main` 是慣例，push 到 `origin` 先確認）。
  3. **改了程式碼就要同步 [code map](wf/workflows/common/code-map.md)**：新增／刪除檔案、或某個檔的職責變了，commit 之前一定要把 code map 補上。
  4. 各工作流的**具體流程在它自己的入口檔**，不在頂層。
- **[wf/DEV-GUIDE.md](wf/DEV-GUIDE.md) 是被動參考**（結構整理原則 + 四級成長軌跡）——**只在你要重構／整理結構時才取用**，不貫穿日常每個動作。只在**碰原始碼**時適用的**程式碼慣例 + code map 維護鏈**在 [wf/workflows/common/conventions.md](wf/workflows/common/conventions.md)。

## 開發環境

單機開發，沒有跨機或離線的特殊情況。需要的只有兩樣：

- vcpkg：本機裝在 `~/dev/vcpkg`，根 `CMakeLists.txt` 會自動找到，不用設 `VCPKG_ROOT`。要用別的路徑就設 `VCPKG_ROOT` 環境變數，或把個人 preset 放 `CMakeUserPresets.json`（已 `.gitignore`）。
- 建置與測試指令、測試分類見 [wf/workflows/testing.md](wf/workflows/testing.md)。

## 主工作流（活狀態：進度 / 待測 / 信件）

事情告一段落、因應需求結束、或臨時中止時 → 把**還沒完成**的活狀態記到進度；需要**使用者親自做／驗證**的（實機環境、外部工具實跑、需權限／本機環境）→ 記到待使用者。兩者都**只列 open**，完成即移除、不留已完成清單。

- **進度**（我自己的 open in-flight）→ [wf/SESSION-LOG.md](wf/SESSION-LOG.md)
- **待使用者**（等使用者親自做／驗證）→ [wf/WAIT_USER.md](wf/WAIT_USER.md)
- **信件**（agent 之間的訊息交換，像 email；放信處是 [`wf/inbox/`](wf/inbox/)）→ 使用方式見 [wf/workflows/inbox/](wf/workflows/inbox/README.md)

> 三軸各管一種「還沒完的事」：進度＝我手上的、待使用者＝卡在人、信件＝agent 之間收發（寄失敗／不回都無妨）。使用者說「**看看信箱**」＝掃 [`wf/inbox/`](wf/inbox/) 的待辦。
