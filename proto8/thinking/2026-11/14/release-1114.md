# release-1114：aos 公開 demo 發佈版（ok-release 線）——草稿 v2 出來了，等使用者看

← [11-14 日索引](README.md)｜任務書：`wf/temp/ok-release/任務書.md`

## 結論（11-14，第二段）

- **草稿 v1 給使用者看**：入口頁 [06-草稿/v1/index.html](release-1114/06-草稿/v1/index.html)（瀏覽器直接開）。內容：宣傳頁兩版（A 九塊圖解、B 終端×資料夾對照）、README 中英、文件 8 頁（開始用、安裝、需求、教學 01、安全、疑難排解、FAQ、現況）。照推薦的 ★1（中文先）、★3（同 repo）先做，使用者改主意再調。
- **指令都照字跑過**：「開始用」整頁在乾淨複本＋空家目錄跑兩輪；README Quickstart、教學 01 加 bob 也跑過。家目錄只多 `~/aos`、`~/aos-demo` 和 vcpkg 快取 `~/.cache/vcpkg`（第一段說「不寫家目錄」不精確，已更正）。
- **隱私**：草稿全掃 0 命中；全倉與歷史掃描見 [09-掃描報告-1](release-1114/09-掃描報告-1.md)：沒有真金鑰，產品夾零個人值，內部檔的個人值早已公開（★4 交使用者）。
- **審稿**：fable 與 Argon 各自審了草稿 v1（原文 [04-fable原文/1](release-1114/04-fable原文/1-審草稿v1.md)、[04-Argon原文/3](release-1114/04-Argon原文/3-審草稿v1.md)）。兩邊都抓到同一個大洞：主標「資料夾，就是函數」沒有一處讓讀者親手做到。採納表第 3 輪 31 條；能直接修的先做進 v2，A／B 怎麼合、副標換哪句這類方向題交使用者。
- **使用者已答 ★1～★5「都按照推薦」**（經 repo-aos）：核心頁雙語中文先、MIT＋CC BY 4.0、同 repo、不改歷史（清單 [09-掃描報告-1/已公開個人值檔案清單](release-1114/09-掃描報告-1/已公開個人值檔案清單.md)）、頂層加 docs/、README.zh-TW.md、LICENSE。還沒答：挑版、副標、原話逐句、docker（使用者自己開）。
- **草稿 v2**（審稿後的修正版）：[06-草稿/v2/index.html](release-1114/06-草稿/v2/index.html)。主要變化：補上「資料夾，就是函數」的實跑示範與「概念」頁；文件正文拿掉內部代號；修了 6 個事實錯。開始用、README 都在新的空家目錄重跑通過。宣傳頁 A、B 沒動，等使用者挑。
- **發佈前要知道**：repo 根 `.gitignore` 第 2 行 `install/` 會吃掉任何叫 install 的資料夾，原訂的 `docs/zh/install/` 上線會進不了 git。v2 已改名 `docs/zh/setup/`（不動共用的 .gitignore）；v1 的 4 個 install 檔因此只在本機、沒進 commit。
- **意外**：sol-high 每日 1000 次額度用完；沒有換 pack 繞過，改用 Claude sonnet 寫手做完草稿。

## 第一段結論（規劃，舊版全文在 [00-主紀錄/v1-規劃段](release-1114/00-主紀錄/v1-規劃段.md)）

- **第一段（規劃）做完**：sol 備料 → fable 設計 → opus 細化 → Argon 審 → 採納表 → 計劃 v2。Argon 審 v1 的總評是「可進批 0」，3 個高風險漏洞都已在 v2 補上。
- **最重要的新事實**：這個 repo **現在就是公開的**。內部紀錄與歷史早就看得到，所以發佈不是「會不會曝光」的問題，而是「來看的人變多」；掃描因此改成全倉掃。
- **clone 下來能不能用**：在 repo 外的乾淨複本實測過，假腦（不用任何模型）從起 kernel 到回話 6.4 秒、只設三個環境變數、不寫家目錄；接 OpenAI 相容端點也通。**還沒驗**：沒有 vcpkg 的建置、其他發行版——要使用者開 docker 服務。
- **體積**：`--depth 1` 仍有 152 MB（`archive/` 佔 83 MB），產品本身約 6 MB；README 改教只抓產品夾的 sparse clone。
- **卡在使用者**：★1 語言、★3 範圍兩題有答案，就開第二段的草稿 v1（只做本機檔，不碰發佈檔、不 push）。

## 檔案

| 檔 | 內容 |
|---|---|
| [01-備料](release-1114/01-備料.md) | sol 三份＋同類專案研究的匯總（原始答案在 [01-備料/](release-1114/01-備料/)） |
| [02-fable稿](release-1114/02-fable稿.md) | fable 的設計（主稿） |
| [02-astra稿](release-1114/02-astra稿.md) | astra 的另一版（白名單乾淨 repo、VitePress） |
| [03-計劃](release-1114/03-計劃.md) | **現行計劃 v2**；舊版 [03-計劃/v1](release-1114/03-計劃/v1.md) |
| [04-Argon原文](release-1114/04-Argon原文/) | [1 早審備料](release-1114/04-Argon原文/1-早審備料.md)、[2 審計劃 v1](release-1114/04-Argon原文/2-審計劃v1.md)、[3 審草稿 v1](release-1114/04-Argon原文/3-審草稿v1.md)，都是原文 |
| [04-fable原文](release-1114/04-fable原文/) | [1 審草稿 v1](release-1114/04-fable原文/1-審草稿v1.md) |
| [05-採納表](release-1114/05-採納表.md) | 每輪每條意見怎麼處理；第 2 輪 20 條、第 3 輪（審草稿 v1）31 條 |
| [08-批0實測](release-1114/08-批0實測.md) | 14 項事實，哪些通、哪些沒驗、為什麼 |
| [06-草稿](release-1114/06-草稿/) | [v2/index.html](release-1114/06-草稿/v2/index.html)（現行）、[v1/index.html](release-1114/06-草稿/v1/index.html) 入口頁；`v1/_src/` 是原始 md／html；[文案表.json](release-1114/06-草稿/文案表.json) 宣傳句單一正本 |
| [09-掃描報告-1](release-1114/09-掃描報告-1.md) | 草稿、產品夾、全倉、git 歷史的個人資料與金鑰掃描；附件：★4 清單 |
| 07-使用者意見 | 等使用者看完草稿 |

## 方向題（詳見 [03 第 12 節](release-1114/03-計劃.md)）

| 題 | 推薦 |
|---|---|
| ★1 語言 | 核心頁雙語、參考頁只英文；中文先審再出英文 |
| ★2 授權 | 程式 MIT、文件 CC BY 4.0 |
| ★3 範圍 | 同 repo 發佈，網站只連產品；另案：白名單匯出乾淨 repo |
| ★4 已公開的個人資料 | 不改歷史；掃描清單給使用者看再決定 HEAD 要不要改 |
| ★5 頂層新增 | `docs/`、改寫 `README.md`、`README.zh-TW.md`、`LICENSE`、`.gitignore` 追加 |
| 6～12 | 名稱、原話、願景大小、預編檔、issue／PR、改程式（11A 純新增、11B 改 CMake）、開 docker 服務 |

## 規矩怎麼守的

- 活樹沒碰：開工與收尾的 `pgrep` 與 repo-aos stack 對照存在 `wf/temp/ok-release/baseline-*.txt`。
- 所有 aos 指令經 `wf/temp/ok-release/bin/clean-run`（bash、逐一 unset `AOS_*`、有殘留或不在暫存夾就拒絕）；暫存樹在 `~/code/release-1114/`，收行程只用 `aos-daemon-ctl -d <絕對路徑> shutdown`。
- 掛過的 agent：ok-release-sol-1～6、ok-release-astra-1～2，都已移除（stack 保留）。
- 中途核對（`wf/temp/ok-release/baseline-mid-1.txt`）：開工時的 aos-daemon 有四支（929050、1287451、1288373、1288918）後來不在了；本線沒對它們下過指令，回報後 repo-aos 查明是 ok-limits 收線時收掉自己的 sol 子 daemon。
- repo 只寫本紀錄與 `wf/temp/ok-release/`；沒改程式、沒 push。
