# 2026-11-05 夜 架構大重構：兩代並存收成一代、proto8 按角色分夾、impls 一次建、code map 改生成（arch-refactor，fable 規劃、未實作）

← [thinking README](../../../README.md)｜日 [2026-11-05](../README.md)｜前情：[10-30 map-review（使用者看現況地圖後的想法）](../../../2026-10/30/map-review/README.md)、[11-04 tests-trim（測試全刪）](../../../2026-11/04/tests-trim.md)、[11-05 stdio-unify § 使用者原則「統一成單一介面」](../stdio-unify/README.md#使用者原則11-05-傍晚)｜規矩：[STRUCTURE](../../../../../wf/STRUCTURE.md)、[refactor](../../../../../wf/workflows/refactor/README.md)、[C-74 分層](../../../../docs/CONCEPTS/01-設計理念/02-C-51.md#分層10-22-使用者定)、[C-54 命名](../../../../docs/CONCEPTS/01-設計理念/04-C-54.md)

狀態：**只規劃、沒改程式、沒 commit；七題等使用者裁**（下方「要使用者裁的」）。四個盤點員（opus×3、sonnet×1）實查 impls、Python 層、code map 對實檔、repo 根舊代；數字與行號都在分檔。同時有三隊在改 lib（die 共用模組已 commit `5deb73a6`）、thought 工具、知識庫 K1～K8——他們的檔這裡沒碰，步驟表標 ⏳ 的要等他們收工。

## 使用者原文（11-05 夜，逐字）

> 給整個程式碼庫、codemap之類，做一次架構上的大重構

隊長記在 SESSION-LOG：「先派 fable 規劃、挑沒別隊在改的時段」。

## 一句話結論

repo 現在是**兩代並存**：根上的 `core/app/docs/…` 是 08～09 月那代 C++（11.4k 行、沒有任何現役程式依賴，但 AGENTS.md 第 3 行與 testing.md 還把它當本體）；現役的 proto8 裡，**四個夾（bin／extras／lib／demo）靠語言和歷史分、不靠角色**，aos-agent 這個主體掛在「周邊」底下、三個 kernel 元件掛在「範本」底下；impls 13 個 CMake 專案要 configure 13 次（aos-util 被重編 12 次）；code map 三處重講同一件事、靠人手同步、實查已有十幾處不符。推薦：**① 甲代整組封存進 `archive/aos-v1/`、根只剩 wf／proto8／archive；② proto8 改成 impls／cmd／lib／kernel／templates（夾名＝指令名、判準寫進 README）；③ impls 加頂層 CMakeLists 一次建全部、各專案仍可單獨建；④ 逐檔 code map 改成腳本從檔頭一句話生成（121／121 個 C++ 檔、全部 `_entry` 都已有一句話）、wf-lint 查、手寫只留地圖；⑤ 順手收重複碼、拆 12 個 >300 行的檔、改 6 個不合 C-54 的代號、清死碼。** 分 11 步，第一波四步（殘渣、封存、頂層 CMake、生成器）現在就能做；搬夾那步等三隊收工。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-現況地圖](01-現況地圖.md) | 根兩代並存圖、proto8 各夾數字與呼叫鏈、impls 實際依賴圖、code map 現況 |
| [02-問題清單](02-問題清單.md)、[02-續](02-問題清單-續.md) | 七類 A～G（02：A 兩代並存、B 四夾沒判準、C 建置重工；續：D 重複碼、E 死碼、F 命名與分層、G code map），附檔案行號 |
| [03-重構方案](03-重構方案.md)、[03-續](03-重構方案-續.md) | 目標形狀（03：§ 1 根、§ 2 proto8 內部、§ 3 impls 建置、§ 4 code map 生成機制；續：§ 5 去重分層、§ 6 拆檔表、§ 7 命名、§ 8 死碼） |
| [04-實作步驟](04-實作步驟.md) | S0～S11 分步表（每步一 commit、建得過、可觀察驗收、派誰、等誰）、波次、不做的 |
| [05-風險與邊緣](05-風險與邊緣.md) | R1～R20 風險與防法、邊緣狀況 |

## 要使用者裁的（白話；推薦放第一）

照 [user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)：只帶原則推不出的方向題；細節（夾名、步驟順序、拆檔切點）fable 代定、可翻案。

1. **根上那套舊 C++（core／app／docs／playground…）怎麼辦？**
   - **整組封存進 `archive/aos-v1/`、根只剩 wf／proto8／archive (Recommended)**：沒程式依賴它；代價是改寫約 15 份入口文件、約 50 條連結變純文字，一個人一天。
   - 留著、只在 AGENTS／INDEX 標「舊一代、不再建」：幾乎不用動，但 testing「repo 根改完必跑」那類規矩還在，每次全倉掃改都掃進去（11-05 改英文就掃了）。
   - 刪掉不封存：跟 11-04「舊的 proto1～7 都封存」不一致。
2. **proto8 要不要這次升到 repo 根？**
   - **不升、根變薄只指 proto8 (Recommended)**：你 11-05 說「我們在 proto8 內……畢竟是 prototype-8」，它還是原型；thinking 433 檔與條文裡上千條相對連結不用動。
   - 一起升（`proto8/*` → 根）：根最乾淨，但連結全動、兩台機器與試驗場同時斷一次；等它畢業再做。
3. **proto8 四個夾怎麼重劃？**
   - **按角色：impls／cmd（人打的指令，一支一夾、夾名＝指令名）／lib（腦叫的工具）／kernel（llm-kernel、判官）／templates（agent-fsm、eca-claude）／extras 只留 langs (Recommended)**：判準一句話寫進 README。
   - 按 C-74 層名 base／std／agent 重排：會把 impls 這個 CMake 家族切成三夾。
   - 不動夾、只修 code map：最便宜，但 aos-agent 繼續掛在「周邊」。
4. **impls 怎麼建？**
   - **加頂層 `impls/CMakeLists.txt` 一次建 13 支、各專案仍可單獨 cmake (Recommended)**：13 次 configure 變 1 次；規矩「頂層建與單獨建不同時跑」。
   - 維持 13 個獨立：不動。
   - 合成單一 CMake 專案、拿掉各自 vcpkg.json：失去 dcap「一夾一專案」。
5. **code map 怎麼維護？**
   - **逐檔表由 `wf/tools/codemap_gen.py` 從檔頭一句話生成、wf-lint 查、手寫只留地圖與各專案 README；鐵律 3 改成「新檔寫一句話＋commit 前 `--apply`」(Recommended)**：不會再不同步。
   - 維持手寫、只修這次查出的不符：下個月又不同步。
   - 逐檔表全刪、只留地圖：找檔靠 grep 檔頭。
6. **死碼與殘渣，哪些可以刪／封存？**（一次授權或逐項）：根殘渣 `proto/`（1,891 檔含 `proto/bin/aos`、play-logs）、`proto2/`、`proto4-2…7-2` 空殼、`.stack/`；proto8 空殼 `demo/agent-{gus,hal,kai,meg}`、`extras/human`、`extras/cli_hub`、`__pycache__`；`aos-schema`（沒人連；推薦**封存**，C-51 說之後驗 LLM 回話可能用）；aos-util 沒人叫的 API（`SignalCatcher`、`memfd_*`、`sibling_tool`…推薦刪）；lib `pyfix`＋`agent_tool.py`、`check_inbox`、`claude`／`codex`（沒範本掛；推薦**封存**）；`impls/aos-json/tools`（跟 lib json_read／json_edit 重疊；推薦併進 lib）。推薦：**一次授權，照上列推薦做**。
7. **`/wf-tick` 心跳（routines／schedule）跟著甲代封存嗎？** 清單是空的、十月起沒人跑、proto8 沒有對應機制。**推薦封存**；要時在 proto8 用 daemon＋aos-tick 重做。

## fable 代定（可翻案；細節在 03）

1. 封存夾名 `archive/aos-v1/`；根 `thinking/`（使用者 09 月草稿、CONCEPTS 出處）搬 `proto8/user-advice/2026-09/` 不封存。
2. cmd 夾執行檔放 `<名>/bin/<名>`（跟 impls 同形，install.sh 一條 glob）；eca 兩支同夾 `cmd/aos-eca/`；Python 共用模組一處 `proto8/py/`（tool_io.py 搬不搬問 die 隊）。
3. `lib/base/judge` 搬 `lib/aos/`（它碰 AOS_DAEMON）、補 `_tooldef`／`_metainfo`。
4. C++ 標準照實際改成 20＋`EXTENSIONS OFF`（慣例檔寫 23 是甲代的）。
5. aos-daemon-ctl 變可 import 模組＋薄殼，aos-agent 直接 import、不再開子行程拆 stderr；ctl 命令列與錯誤行不變。
6. `inst`→`aos-inst`；aos-util 標頭進 `aos/util/`；代號改名先對 C-54 現行條文。
7. code map 分冊照夾名不編號；生成表開頭標 generated；impls 各 README 刪逐檔表只留行為。
8. 這次不動 `proto8/docs` 條文結構、不改任何程式行為、不升 proto8。
