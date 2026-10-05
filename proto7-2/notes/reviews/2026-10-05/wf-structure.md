排除封存後，已確認有 **150 份 Markdown 超過 8 KiB**；應優先清理失效待辦、修正現行入口與舊介面說明，再抽離同質資料及拆檔，不能把「全部壓到 8 KiB 以下」當成整理目標。

## 一、審查範圍與完成狀態

本報告只使用收到「立刻收尾」指示前已取得的結果。全程未修改 repo 檔案、未 commit、未 push，也未執行建置、測試、原型或會產生驗收資料的腳本。

- 盤點截點：**2026-10-05 09:52:46，台灣時間**。
- 核對的 HEAD：`6daebe2ef8227021745def649f4e3d86a3a8038c`。
- 大小以實際 bytes 計算，門檻為 **嚴格大於 8,192 bytes**。
- 「封存」以路徑含 `archive/` 判定；不把整個舊原型直接視為封存。
- 審查期間另有兩份未追蹤報告出現：`proto7-2/notes/reviews/2026-10-05/event-store.md`、`test-review.md`。兩份都已納入截點盤點；不是本線寫入。
- 完成：大小盤點、150 份未封存大檔的初步逐檔處置、主要待辦核對、lint 唯讀重現與壞連結分類。
- 未完成：最後一輪同質清單漏網檢查尚未收齊；封存大檔的完整逐檔名錄尚未整併進本報告。詳見第八節。

### 1.1 大小現況

| 範圍 | 全部 `.md` | 全部 bytes | 未封存 `.md` | 未封存且 >8 KiB | 封存且 >8 KiB |
|---|---:|---:|---:|---:|---:|
| `wf/` | 642 | 3,145,624 | 501 | **45** | 25 |
| `proto6/` | 387 | 2,896,516 | 295 | **31** | 52 |
| `proto7/` | 28 | 510,212 | 28 | **18** | 0 |
| `proto7-1/` | 82 | 1,116,073 | 82 | **25** | 0 |
| `proto7-2/` | 69 | 712,358 | 69 | **31** | 0 |
| **合計** | **1,208** | **8,380,783** | **975** | **150** | **77** |

因此，包含封存共有 **227 份**超過 8 KiB；真正需要依現行結構原則判讀的是未封存的 150 份。

`wf/SESSION-LOG.md:22` 的「proto6 15 份、wf 44 份」已不能代表現況，但有歷史依據，不應改寫成當時量錯：

| Git 版本 | `proto6/` 未封存超標 | `wf/` 未封存超標 |
|---|---:|---:|
| `c15aee6f` | 15 | 44 |
| `5a806afc` | 19 | 44 |
| `c1cf5bf2` | 22 | 44 |
| `6143919f` | 31 | 44 |
| 本次 HEAD | **31** | **45** |

相對第一列，proto6 增加 16 份；wf 新增超標的是 `wf/workflows/roadmap.md`。建議把 SESSION 條目更新成「本次盤點完成、整理尚未執行」，不要繼續沿用舊數字。

重現方法見第九節；原審查的舊數字亦見 `proto6/notes/reviews/2026-10-02-astra/10-structure.md:41`。

### 1.2 判讀原則

本報告採以下規則，沒有把大小直接等同違規：

- 工作流程文件以 8,192 bytes 觸發檢視；使用手冊／產品文件另有 300 行門檻。證據：`wf/STRUCTURE.md:27`、`:28`。
- 完整規格、計畫及連貫研究可以保留超標；封存文件不套大小門檻。證據：`wf/STRUCTURE.md:33`、`:59`。
- 同質記錄區塊超過 1,024 bytes，仍應抽成 `wf-table/1`；「整篇研究保留」不豁免其中的需求表、回歸矩陣或候選清單。證據：`wf/STRUCTURE.md:30`、`wf/workflows/common/data-files.md:5`。
- 人用導航留 Markdown；含連結的證據表不會因此自動變成導航。證據：`wf/workflows/common/data-files.md:7`。
- 封存前先抽出仍有效的決策、未完成工作及現行契約；活文件不能改連到 `archive/`。證據：`wf/STRUCTURE.md:82`–`:85`。

---

## 二、優先處理的已確認發現

### P1：先修會誤導下一輪工作的文件

| 發現 | 證據 | 建議 |
|---|---|---|
| 頂層路由仍把 proto6 稱為現行主線，沒有完整導向 proto7-2 | `wf/INDEX.md:21`、`:22`；`wf/WORKFLOWS.md:20`；`proto7/README.md:18` 仍稱 proto7-2 只有 spec 草稿，與 `proto7-2/README.md:5` 不符 | 更新現行入口及狀態；proto7 的原則文件仍保留其權威，不因實作移到 7-2 就封存 |
| `problems.md` 混用舊契約、修復紀錄及現況 | `proto7-2/notes/problems.md:23` 與 `:298` 的 `retry_lost` 位置不同；`:36` 與 `:292` 的 kill `run` 必填規則不同；`:74` 還談 `ctl-failed`，`:338` 已記移除 | 先校正「現行」段落，再把 A2～A7 修復歷史移出；不能直接按篇幅切成數份 |
| core-slimming 的未完成敘述已部分失效 | `proto7-2/notes/core-slimming.md:3`；F47 已由 `daf8d5cf` 處理，step／budget／adapt 分別見 `ca7f5159`、`025d2bfe`、`d3738e04` | 抽出真正剩餘的 kernel／agent／LLM 計畫；已完成部分封存 |
| core-slimming 又不是整份都完成 | `proto7-2/notes/core-slimming.md:337`–`:394` 尚有 kernel-core、aos7-pack、supervise／schedule／relay／observe／agent 等提案；`:431` 的理由仍被 `notes/component-contracts.md:165` 使用 | **不可整份直接封存**；先保留未完成計畫與有效理由 |
| layer-interfaces 是舊版本調查，但局部補過新結果，讀者容易當成最新契約 | `proto7-2/notes/layer-interfaces/02-ticktock-task.md:11`、`:22`、`:36`；`05-gaps.md:17` 的 G3 與 `notes/problems.md:171`、`modules/subd/README.md:23` 不符 | 抽出仍開放缺口及 kernel 遷移事項後，整組標為歷史調查並封存 |
| 真 root 驗收尚未完成，卻指向過時操作手冊 | `wf/WAIT_USER.md:29`；`proto6/notes/2026-10-01-account-manual.md:47`、`:61`、`:134`、`:150` | 保留手動驗收待辦，**先修手冊再讓使用者照跑** |
| 手冊的 mq／ctl 介面已落後 | 現行 `proto6/src/py/lib/aos_mq.py:3`–`:14`、`:39`；`aos_ctl.py:56`；`aos_daemon_mq.py:56`；介面變更見 `52870cbd` | 修正 socket 參數、`AOS_DAEMON_CTL_SOCKET`、subscribers 設定及原始 JSON 訊息格式，不只更新版本號 |
| 舊 spec 有活引用，不能為縮小 wf 直接搬走 | `wf/workflows/spec/README.md:7` 已定位為歷史；但 `wf/workflows/ideas/README.md:33` 仍依賴 spec 的 rulings | 先把有效裁決搬到 ideas 所屬層，再封存舊規格 |
| 整理流程的驗收條件與結構原則矛盾 | `wf/workflows/tidy/README.md:16`、`:22`、`:23` 要求超標歸零；`wf/STRUCTURE.md:33`、`:59` 明列例外 | 先統一驗收規則，否則會逼人硬拆完整規格及研究 |

root 手冊的具體落差包括：

- 手冊的 `aos-mq send c.json ...`／`take` 用法沒有反映現行 socket 參數。
- 舊 mq 設定沒有反映各項 subscribers；現行預設為空清單。
- 舊環境變數寫 `AOS_DAEMON_SOCKET`，現行 ctl 使用 `AOS_DAEMON_CTL_SOCKET`。
- 手冊期待 `from`／`msg` 包裝，现行 mq 的契約是傳遞原始 JSON。

以上是靜態文件與程式對照，**沒有執行 root 驗收**。

### P2：整理重複資料與歷史，再處理篇幅

主要收益集中在：

1. `wf/SESSION-LOG.md`、`wf/wait-user/` 的活狀態清理。
2. `proto7-1/notes/infra-needs.md`、各 problems 清單的資料化。
3. `proto7-2/notes/problems.md` 的「現況／理由／修復歷史」分離。
4. 試玩報告內的回歸矩陣、需求表、驗收表轉 `wf-table/1`。
5. 兩份 90 KB 左右的 OS 調查按主題拆開。
6. 真模型執行 stdout 從 Markdown 移成 `.log`。

### P3：保留具有完整閱讀單位的規格與研究

例如 `proto7-2/spec.md`、step／budget／adapt 的 spec，以及連貫的設計論證，不應只因 bytes 超標就切碎。現役契約也不應因「已實作」就被當成完成計畫封存。

---

## 三、SESSION／WAIT 已過時或已完成的條目

### 3.1 可以移除已完成部分，或改寫目前狀態

| 位置 | 已確認落差與證據 | 處置 |
|---|---|---|
| `wf/SESSION-LOG.md:18` | 仍寫「等使用者說繼續：修 F-01～F-11 與 N-55」。`proto7-1/notes/play/README.md:13` 已記修復 `ddda65a9`，`:14`、`:15` 又記後續 G／H 修復 | 移除這段待修；保留同列尚待使用者閱讀的 S-21 |
| `wf/SESSION-LOG.md:26` | 仍列 09-13 r1 修補、LLM cpu、compact；`wf/session_logs/2026-09/2026-09-13.md:5` 已記相關完成且 open 無，`:7` 已記提醒 compact；`proto4/notes/play/README.md:35` 記 r1 收尾 | 刪除這條 hub 待辦；歷史留 git／原紀錄 |
| `wf/SESSION-LOG.md:17` | 仍將 proto7-1 K 系列列為待修；但 `SESSION-LOG.md:16` 已明說不修 7-1、併入 7-2，`proto7-2/notes/changes-from-7-1.md:37`–`:42` 有承接 | 退出 7-1 活修補佇列；不能改寫成 K 系列全部已修，kernel 等仍有未做部分 |
| `wf/SESSION-LOG.md:16` | A2／A3／P2 修復、歷次測試數佔大量篇幅；修復已記於 `proto7-2/notes/problems.md:93`–`:105`、`:128`–`:142`，相關提交包括 `5cf34d7f`、`9d59e233`、`537ef674`、`79e67233` | 刪除已完成細節；真正的 W1～W12 待決移到 WAIT 所屬位置 |
| `wf/SESSION-LOG.md:15` | 標「進行中」，內文卻記使用者要求下一批前先停，又混入更早的自主工作授權 | 改成最新的暫停／下一步狀態；事件保存、agent／LLM 等仍保留，完成史退出 hub |
| `wf/SESSION-LOG.md:24`、`:25` | 09-22 和 09-21 重複列④⑤；`wf/session_logs/2026-09/2026-09-22.md:4` 直接說同前一天 | 合併成一筆；不是判定工作完成 |
| `wf/SESSION-LOG.md:27` | 舊 kernel v1 缺項中的 syscalls／done／boot 已落地，見 `proto4-3/docs/kernel.md:24`、`:26`、`:46`、`:56`；但 firmware／daemon-kernel 通道仍未做，見 `:180` | 僅移除已完成子項 |
| `wf/SESSION-LOG.md:28` | dev 模型、qa、push 已在 `wf/session_logs/2026-09/2026-09-06.md:8`–`:9` 記完成；`proto4-2/README.md:3` 已記該方向失效 | 清掉已完成／失效子項；不要一併刪除尚未證明完成的預算、cached-token／歷史成本事項 |
| `wf/WAIT_USER.md:24` | 「已裁決／代裁紀錄」明寫非待答，卻仍計 19 open；`wf/wait-user/decided-2026-09-24.md:5`、`wf/wait-user/README.md:7` 也已明示裁決 | 不應再計入「等你一句話」；先抽出執行尾項再封存 |
| `wf/wait-user/company-market.md:26`、`:30` | #56、#59 的額度／預算已依 09-25 董事決定從 20 改 25；現況見 `examples/company/README.md:65`、`examples/company/company.json:7`；提交 `a551b957` | 移除待拍板狀態，保留正式決策來源 |
| `wf/wait-user/company-market.md:35` | #62 權重仍列待答，但 `:37` 及 `brief/2026-09-25.md:196` 記已決；提交 `895ad51b` | 移除待答 |
| `wf/wait-user/company-market.md:55`、`:57` | #74、#75 還是問題句；相鄰 `:56`、`:58` 已記決定和實作；另見 `wf/wait-user/rescore-74-75.md:5`、`:7`、`:8`，提交 `9261eae0`、`895ad51b` | 移除待答，同步刪 `WAIT_USER.md:25`「74、75 最要緊」 |
| `wf/wait-user/proto2.md:17` | #6 的後代層級問題已由 `proto2/docs/kids.md:26`–`:27`、`proto2/packs/kids.py:6`、`:102` 與測試固定；T16 見 `proto2/notes/tools/README.md:63` | 移除待裁 |
| `wf/wait-user/proto2.md:18` | #8 還說 agent 通訊未做；已有 `proto2/docs/communication.md:3`、`:9`、`:17`、kids 文件及 T17；相關提交 `6de6b008`、`cb777da8` | 移除已解問題 |
| `wf/WAIT_USER.md:35` | 「kernel 帳本整份讀寫、agent 每格讀整份」已部分失效。`proto5/spec/kernel/ledger.md:24`–`:26` 已改只寫變更；`proto5/lib/aos_agent_runtime.py:80`–`:84` 已做 O(1) 讀取；提交 `fd6b68e2` | 改成實際剩餘規模限制；kernel 全量讀取、一 cpu 一 Python 等不可順便判完成 |
| `wf/WAIT_USER.md:36` | 還說閒置 agent 每格醒來、K 隊正在提案；`proto5/notes/2026-09-24-idle-wait-impl/README.md:5`–`:6`、`:14` 已記實作與量測；提交 `c56044de` | 移除這段舊待辦 |
| `wf/wait-user/proto5-kernel.md:7` | #14(e) paused tick 子題已處理，見 `proto5/spec/aos-agent/tick.md:7`，提交 `39059930`、`59f85080` | 只移除該子題，其他 kernel 問題保留 |
| `wf/wait-user/proto5-kernel.md:13` | #20(a) 與 #14(a) 跨世代 stop 重複，相關實作筆記仍標未完成 | 合併重複引用；不把它判成完成 |
| `wf/wait-user/company-market.md:31` | #60 仍使用 2M／4M 舊參數；`examples/company/README.md:66` 已是 25M／50M，`:78` 仍要求授權 | 更新背景數字，保留真正的決策問題 |

### 3.2 WAIT A 區的數字可以下降，但不能把尾項弄丟

目前 A 區列數是：

- proto2：9。
- proto5 kernel：7。
- 已裁決 21～39：19。
- 公司／市場 40～75：36。
- 合計：**71**。

已確認至少有 **26 個編號不應再算等待裁決**：

- proto2 #6、#8：2 個。
- 已裁決 #21～#39：19 個。
- 公司 #56、#59、#62、#74、#75：5 個。

按這個有限口徑，剩 **45 個編號**。這不是「整個 repo 只剩 45 件待辦」，也不是所有 45 件都逐一證明仍有效。

尤其已裁決檔仍夾著以下未完成尾項：

| 位置 | 尚須保留的內容 |
|---|---|
| `wf/wait-user/decided-2026-09-24.md:50` | #33 要使用者親自操作 tutorial 08，未找到已完成證據 |
| 同檔 `:58` | #35 仍有 tutorial 08 §9 的親自驗證尾項；可與上一項合併，但不能漏掉 §9 |
| 同檔 `:79` | #39 還有新手試用、額外 agent、tool_draft 與 crash／timeout 後續；`wf/session_logs/2026-09/2026-09-25.md:13`、`:21` 仍有對應工作 |

前兩類應回到「使用者親自做」；agent 能繼續做的工作應回 SESSION，而不是繼續藏在「已裁決」檔。

### 3.3 明確不建議直接刪除的項目

- **W1～W12**：`proto7-2/notes/changes-from-7-1.md:60`、`:62`–`:75` 是推薦與實作選擇，不等於使用者逐題確認。
- **proto6 真 root 驗收**：`wf/WAIT_USER.md:29` 沒有完成證據。
- **公司 #60、#63、#71、#72、#73 等**：有的只有實驗參數，有的明寫另議或只做一半；不能用「程式已有一版」推論全部裁決。證據：`brief/2026-09-25.md:196`–`:197`、`examples/company/README.md:78`、`:110`、`:113`。
- **WSL 的 lms／jq**：不能拿本次環境狀態替代使用者那台機器的驗證。
- **09-25 董事評分與未拆模組**：仍有空白評分及未處理項，未找到足夠證據關閉。證據：`brief/2026-09-25.md:185`–`:188`、`wf/SESSION-LOG.md:23`。
- **較早的 09-05、08-28 項目**：本輪沒有取得足以整批關閉的證據。

---

## 四、lint 唯讀核對與壞連結

### 4.1 做法與結果

讀取了 `wf/tools/wf-lint.sh` 及其呼叫的檢查器，保留一般掃描逻輯，在記憶體中移除 `--self` 分支，設定 `PYTHONDONTWRITEBYTECODE=1` 後重現檢查。

沒有執行 `--self`：該分支會 `mktemp`、呼叫 `wf-init.sh` 並刪除暫存目錄，見 `wf/tools/wf-lint.sh:206`–`:213`。

以下是**原始完整掃描**，尚未加進稍後出現的兩份報告：

| 掃描範圍 | Markdown 數 | BROKEN | OVERSIZE | BIGLIST | BIGLIST-LINKS | residue | 一般／strict 結果 |
|---|---:|---:|---:|---:|---:|---:|---|
| 全 repo `.` | 1,756 | 90 | 30 | 2,084 | 199 | 65 | 失敗／失敗 |
| `./wf` | 501 | **0** | 30 | 353 | 58 | 0 | **通過／失敗** |
| `./proto6` | 295 | 0 | 0 | 288 | 40 | 0 | 通過／失敗 |
| `./proto7` | 28 | 2 | 0 | 96 | 2 | 0 | 失敗／失敗 |
| `./proto7-1` | 82 | 5 | 0 | 180 | 16 | 0 | 失敗／失敗 |
| `./proto7-2` | 67 | 7 | 0 | 147 | 6 | 0 | 失敗／失敗 |

其他已核對指標：

- 壞錨點：0。
- QUERYCMD：0。
- 待處理 inbox：0。
- 資料檔壞連結：0；共檢查 13 份適用資料檔，其中 wf 6 份。
- 以上都是掃描器涵蓋範圍內的結果，不代表所有文字引用或外部網站都已驗證。

兩份新增報告的單檔增量：

| 檔案 | BROKEN 增量 | BIGLIST 增量 | BIGLIST-LINKS 增量 |
|---|---:|---:|---:|
| `proto7-2/notes/reviews/2026-10-05/event-store.md` | 105 | 2 | 6 |
| `proto7-2/notes/reviews/2026-10-05/test-review.md` | 0 | 6 | 0 |

把已核實增量加回原掃描：

- 全 repo：1,758 份 Markdown、BROKEN **195**、BIGLIST **2,092**、BIGLIST-LINKS **205**。
- proto7-2：69 份 Markdown、BROKEN **112**、BIGLIST **155**、BIGLIST-LINKS **12**。
- wf 結果不變。

這是**原掃描加兩檔增量**，不是截點時重新全域掃描的保證。

### 4.2 wf 本身沒有一般壞連結，但有五處違反封存連結規則

下列目標存在，所以原 lint 不報 BROKEN；然而活文件連入 archive，違反 `wf/STRUCTURE.md:84`–`:85`：

| 活文件位置 | 連入的封存位置 |
|---|---|
| `wf/session_logs/2026-09/2026-09-25.md:67` | `wf/workflows/dispatch/trial/archive/sandbox/` |
| `wf/workflows/common/code-map/proto5-lib.md:22` | `proto6/notes/archive/README.md` |
| `wf/workflows/dispatch/trial/README.md:13` | `archive/sandbox/` |
| `wf/workflows/dispatch/trial/sandbox/README.md:4` | `../archive/sandbox/` |
| `wf/workflows/ideas/README.md:3` | `archive/README.md` |

建議改為不帶連結的歷史說明，或改指仍有效的現行內容；不是單純修成另一條 archive 連結。

### 4.3 審查範圍內原有的 14 次壞連結

| 來源位置 | 問題 | 建議 |
|---|---|---|
| `proto7/notes/principles.md:7` | `../user-advice.md` 不存在 | 恢復真正原稿或明示原稿缺失；不能拿摘要假冒原文 |
| `proto7/notes/thinking/2026-10-04-lang-fable.md:5` | `brief4.md` 不存在 | 核對原引用來源；不可未確認就改指 r4-topic |
| `proto7-1/notes/research/2026-10-03-other-os-borrow.md:45` | 三個以 repo 根為起點的路徑，被當成相對目前文件解析 | 改成正確相對路徑 |
| 同檔 `:1037` | 另兩個相同類型的路徑錯誤 | 同上 |
| `proto7-2/README.md:5` | `../proto7/user-advice.md` 不存在 | 與第一項一起處理 |
| `proto7-2/notes/changes-from-7-1.md:3` | `../../proto7/user-advice.md` 不存在 | 與第一項一起處理 |
| `proto7-2/notes/play/2026-10-04-astra-4-infra-evidence/contracts/summary.md:19` | 指向已改名的 `packs/account/README.md` | 改指 budget 的現行入口，保留原命名背景 |
| `proto7-2/notes/play/2026-10-04-astra-5-infra-evidence/budget-crash/summary.md:32` | 兩個 ledger 快照路徑不存在於展開目錄 | 改成封裝檔入口＋成員路徑文字 |
| 同檔 `:33` | 另兩個 ledger 快照路徑同上 | 同上 |

最後四個快照**沒有遺失**：已唯讀查看 `snapshots.tar.gz` 的成員，檔案仍在封裝內；說明見同資料夾的 `SNAPSHOTS.md:3`–`:10`。不應重跑實驗來補一份新的同名證據。

`proto7/user-advice.md` 則不同：

- 目前不存在。
- 沒有找到被 Git 追蹤的歷史版本。
- `proto7-2/notes/play/2026-10-04-astra-6-infra-evidence/baseline.json:4` 記錄它曾是未追蹤檔。
- `wf/SESSION-LOG.md:16` 也說使用者仍會改、未 commit。

目前可以確認引用來源缺失，不能確認其內容可從其他文件無損還原。

### 4.4 新 event-store 報告的 105 次 BROKEN 都是格式問題

`event-store.md` 有 105 次 `/home/guanyu/projs/aos/...:行號` 連結，涉及 35 份来源檔：

- 去掉 `:行號` 後，來源全部存在。
- 行號均在有效範圍內。
- CommonMark 也辨認它們是連結，不是正規表示式誤抓。
- 原 lint 將定位後綴當成檔名，且按相對連結方式串接路徑。

因此它們不是 105 份內容遺失。repo Markdown 建議使用相對目標，把行號留在連結文字，例如：

```markdown
[aos7_tock.py:90](../../../lib/aos7_tock.py)
```

`test-review.md` 沒有 Markdown 連結；其中的 `檔名:行號` 是文字／行內 code，原 lint 不檢查。**BROKEN=0 不等於所有文字引用均已驗證。**

### 4.5 原 lint 的限制

1. **OVERSIZE 只掃 `/workflows/`。**因此 wf 報 30，不是本次全部 45；proto7-2 全部報 0，也不表示沒有大檔。證據：`wf/tools/wf-lint.sh:106`。
2. **BIGLIST 是人工判讀候選。**不是 353 個 wf 命中都必須資料化；論證清單與導航要另判。
3. **BIGLIST-LINKS 不計 strict 失敗，但證據表仍可能需要抽離。**證據：`wf/workflows/common/data-files.md:7`、`:64`。
4. **不檢查 archive 語意規則。**前述五個現存連結因此漏報。
5. **residue 是字面匹配。**全 repo 的 65 次命中不能直接當成 65 處未填模板。
6. **不檢查外部網站可達性，也不核對所有行內程式碼引用。**

原全 repo 90 次 BROKEN 中，另有 74 次是舊 `/home/lorkhan/repo/simple_tools/aos/...` 絕對路徑，分布於 proto4 系列；替換舊根路徑後，70 次可對到現存檔案，4 次仍缺目標。另外兩次是 `proto/README.md:11` 的 `bin/aos` 及 `proto5-2/spec/proto5-diffs.md:39` 的 kernel README 相對路徑。這些屬額外掃到的範圍，不應混算為 wf 的壞連結。

---

## 五、150 份未封存超標檔案：逐檔處置建議

以下大小均為 bytes。表格中的位置以「本表前綴＋檔名:行號」組成完整證據位置。

「保留正文」表示保留完整閱讀單位，不表示其中所有同質清單已通過最後一輪漏網檢查。「封存」均以先抽出仍有效內容、清理活引用為前提。

### 5.1 `wf/`：45 份

#### 入口、歷史紀錄與待辦：16 份

本表前綴：`wf/`。

| 檔案／證據位置 | bytes | 建議與理由 |
|---|---:|---|
| `INDEX.md:22` | 9,562 | **拆導航。**原型清單移 `INDEX/prototypes.md`；工具細節移 `tools/README.md`。頂層只列下一層，並補 proto7-2 |
| `SESSION-LOG.md:15` | 8,983 | **先刪已完成內容。**只保留當前 open；仍需詳細追蹤的 7-2 工作移 `session_logs/proto7-2.md`。`:7`「repo 頂層新立 session_logs」也應改成既有 `wf/session_logs/` |
| `WORKFLOWS.md:34` | 9,256 | **拆導航。**開發派發移 `WORKFLOWS/development.md`，維運派發移 `WORKFLOWS/operations.md`；`:79` 的重複格式規則改連權威文件 |
| `salvage/01-已驗證的規格結論.md:36` | 8,972 | **保留正文。**契約與限制須一起讀，尤其 `:47`、`:92` 的適用邊界 |
| `salvage/02-踩過的坑.md:17` | 13,498 | **保留正文。**失敗原因、後果與修法構成連貫經驗；不是僅依篇幅切分 |
| `salvage/03-裁決與其理由.md:20` | 9,036 | **改資料檔。**14 筆裁決抽 `salvage/data/design-decisions.json`；其餘論述保留 |
| `salvage/04-還沒解的問題.md:124` | 12,423 | **局部資料化。**六筆規格問題抽 `salvage/data/unresolved-spec.json`；明示當時未解，不當成目前待辦 |
| `salvage/05-程式碼哪些值得抄.md:176` | 13,608 | **局部資料化。**五筆不應移植項目抽 `salvage/data/do-not-port.json`；保留來源與原因 |
| `salvage/06-協作流程的收穫.md:174` | 13,590 | **保留正文。**屬歷史協作教訓，不能混成新的 always-on 規則 |
| `session_logs/2026-08.md:38` | 13,197 | **先抽 open，再封存歷史。**建議 `session_logs/archive/2026-08.md`；不可因日期舊就清掉未證明完成項目 |
| `session_logs/2026-09/2026-09-06.md:8` | 10,287 | **清完成史後封存。**建議 `session_logs/archive/2026-09-06.md`；預算等剩餘事項另留 |
| `session_logs/2026-09/2026-09-24.md:37` | 28,338 | **清理後封存。**部分待答已被後續裁決取代；建議 `session_logs/archive/2026-09-24.md` |
| `session_logs/2026-09/2026-09-25.md:34` | 17,490 | **抽出真正未完，再封存。**建議 `session_logs/archive/2026-09-25.md`；董事評分、拆模組等不可直接關閉 |
| `wait-user/company-market.md:5` | 16,717 | **先刪五個已決待答，再資料化。**剩餘編號抽 `wait-user/data/company-market-open.json`；已決歷史另存所屬 archive |
| `wait-user/decided-2026-09-24.md:5` | 20,500 | **封存，但先抽尾項。**`:50`、`:58`、`:79` 還有執行工作；完成後移 `wait-user/archive/decided-2026-09-24.md` |
| `workflows/roadmap.md:19` | 8,715 | **拆現行／歷史。**舊 M0～M5 移 `workflows/roadmap/archive/roadmap-core-m0-m5.md`；入口改為目前路線，`:21` 泛稱任意階段的舊敘述需清理 |

#### ideas：13 份

本表前綴：`wf/workflows/ideas/`。

這組完整章節可保留；應抽出同質裁決表，並消除同篇「仍待答／已裁決」互相矛盾。新 JSON 放 `data/`，保留原問題、選項、推薦及裁決原文。

| 檔案／證據位置 | bytes | 建議 |
|---|---:|---|
| `01-what-and-goals.md:96` | 12,147 | A1～A4 抽 `data/01-decisions.json`；`:42`、`:88` 的待答敘述與 `:98` 以後已決內容對齊 |
| `02-folders-as-lists.md:83` | 11,841 | B1～B5 抽 `data/02-decisions.json`；清 `:78` 與 `:87` 的狀態衝突 |
| `03-land-and-life.md:93` | 11,709 | C1～C5 抽 `data/03-decisions.json`；清 `:53` 與 `:95` 的狀態衝突 |
| `04-inside-aos.md:71` | 10,771 | D1～D4 抽 `data/04-decisions.json`；清 `:64`、`:66` 與後方裁決的矛盾 |
| `05-write-compile-run.md:91` | 12,272 | E1～E6 抽 `data/05-decisions.json`；逐題保留狀態，不把推薦一律改成使用者已決 |
| `06-time-and-clocks.md:82` | 11,159 | F1～F7 抽 `data/06-decisions.json`；核對 `:75`、`:84`、`:85` 的待答／升格描述 |
| `07-daemon.md:67` | 10,867 | G1～G6 抽 `data/07-decisions.json`；清 `:60` 與 `:69` 衝突 |
| `08-agent.md:90` | 10,538 | H1～H5 抽 `data/08-decisions.json`；`:31` 的 per-request world 已被後續 F02 取代 |
| `09-call-and-failure.md:110` | 12,218 | I1～I8 抽 `data/09-decisions.json`；`:69`–`:80` 舊待答與後方裁決分清 |
| `10-doorman.md:93` | 11,746 | J1～J6 抽 `data/10-decisions.json`；`:89` 待答與後續 F03 對齊 |
| `11-tools-and-contacts.md:97` | 12,241 | K1～K6 抽 `data/11-decisions.json`；K02 已決內容不可仍當 open |
| `12-cli-and-layering.md:92` | 12,161 | L1～L6 抽 `data/12-decisions.json`；「現行正本」應加歷史日期與現行去向 |
| `13-holes-and-play.md:90` | 12,308 | 舊代碼對照抽 `data/legacy-codes.json`；`:9`、`:20`、`:75` 的已決／升格／待答重新分清；小型真正未決段保留 |

#### 舊 spec：16 份

本表前綴：`wf/workflows/spec/`。

共同建議：**先移出仍有效且被 ideas 引用的 rulings，再封存到 `archive/2026-09-05/` 下同名檔案。**不是把完整章節硬切小。有效裁決的建議新位置為 `wf/workflows/ideas/rulings/2026-09-05/`；最終入站引用清單尚未完成最後補核。

| 檔案／證據位置 | bytes | 保留完整歷史單位的理由 |
|---|---:|---|
| `01-terms.md:94` | 8,336 | 舊術語與當時缺項須保留時點 |
| `02-layout.md:29` | 11,025 | owner／版面與 schemas 互相依存 |
| `03-source-and-compile.md:4` | 12,250 | source／program 格式及編譯模型是一組 |
| `04-inst-format.md:4` | 11,230 | inst／result 格式是一組 |
| `05-series-format.md:52` | 12,266 | series 語意需與既有 05b 格式章一起保存 |
| `06-exec-and-run.md:15` | 12,288 | 有順序的執行流程，不宜切散 |
| `06b-run-rules.md:59` | 8,670 | 恢復規則需與 06 對讀 |
| `07-call-and-delivery.md:31` | 12,288 | 呼叫／送達三態為同一契約 |
| `08-daemon.md:27` | 12,253 | 登記與 registry 規則相關 |
| `08b-daemon-reconcile.md:12` | 12,276 | reconcile 與 daemon 主章相關 |
| `09-llm-world.md:8` | 12,117 | 舊 LLM world、請求與帳本模型須完整保存 |
| `09b-llm-queue.md:62` | 12,078 | 重啟／佇列狀態與 09 相關 |
| `10-agent.md:94` | 10,976 | 包含後續 F02 取代關係，不能抹掉歷史 |
| `11-tools-and-contacts.md:17` | 11,038 | 工具與 contacts registry 相關 |
| `12-cli.md:10` | 12,203 | 舊 CLI 命令集完整保存即可 |
| `13-doorman-l1.md:105` | 12,282 | 「下一步實作」已不是現行任務；整份保留為舊設計 |

### 5.2 `proto6/`：31 份

本表前綴：`proto6/`。

| 檔案／證據位置 | bytes | 建議與理由 |
|---|---:|---|
| `notes/2026-09-29-kernel-tree.md:5` | 12,313 | **封存**至 `notes/archive/` 同名檔；`notes/README.md:23` 已說被取代 |
| `notes/2026-09-29-wsl-machine-check.md:11` | 9,583 | 13 筆平台比較抽同名 `.json`；保留日期、量測／推估界線 |
| `notes/2026-10-01-account-manual.md:34` | 12,546 | **保留手冊，先修舊介面。**281 行，仍被 WAIT 的真 root 驗收使用 |
| `notes/2026-10-01-daemon-core-sketch.md:5` | 13,495 | **封存**至 `notes/archive/` 同名檔；是規格未更新時的初稿 |
| `notes/proposals/2026-10-02-plan9/02-Linux上的工具與代價.md:13` | 8,319 | 工具比較抽 `linux-tools.json`；推估不得改成已實測 |
| `notes/proposals/2026-10-02-plan9/03-daemon變成檔案伺服器.md:20` | 8,225 | **保留正文**；`:107` 的 daemon 死亡／等待敘述須與 02 章 `:36` 的 ENOTCONN 情況分開 |
| `notes/proposals/2026-10-02-plan9/05-agent與kernel的namespace.md:7` | 8,746 | **保留正文**；namespace、授權、fd 傳遞是完整方案 |
| `notes/proposals/2026-10-02-plan9/README.md:40` | 8,264 | 細節下放既有 `08-檔位.md`、`09-最小實驗.md`；`:58` 十道問題抽 `questions.json` |
| `notes/proposals/2026-10-03-spacetime/06-跟現況與裁定的差距.md:17` | 8,559 | 24 筆差距抽同目錄 `differences.json`，保留分層與處置欄 |
| `notes/reviews/2026-10-02-astra/06-kernel-proposal.md:9` | 9,077 | 已吸收內容封存至 `notes/archive/reviews-2026-10-02-astra/`；未決問題先留在現行提案 |
| `notes/reviews/2026-10-02-astra/07-agent-proposal.md:11` | 10,393 | 同上；先核對五道問題是否完整承接至提案，不抹除未決 |
| `notes/reviews/2026-10-02-astra/08-plan9-proposal.md:11` | 10,398 | 同上；`:76` 的來源缺口及等待語意先保留於現行提案 |
| `notes/reviews/2026-10-03-astra-alt/01-kernel-alt.md:28` | 22,539 | **保留三方案正文**；末尾五題抽 `01-kernel-alt-questions.json` |
| `notes/reviews/2026-10-03-astra-alt/02-agent-alt.md:17` | 19,710 | **保留三方案正文**；五題抽 `02-agent-alt-questions.json` |
| `notes/reviews/2026-10-03-astra-alt/03-plan9-alt.md:30` | 22,007 | **保留四方案正文**；七題抽 `03-plan9-alt-questions.json` |
| `notes/reviews/2026-10-03-astra-alt/04-whole-redesign.md:36` | 28,815 | **保留論證，抽表。**建 `04-whole-redesign/`，放 `facts.json`、`a-costs.json`、`b-costs.json`、`a-verdicts.json`、`b-verdicts.json`、`improvements.json`、`questions.json` |
| `notes/reviews/2026-10-03-astra-alt/05-prior-art.md:47` | 24,997 | 11 個先例抽 `05-prior-art-comparison.json`，`:539` 五題抽 `05-prior-art-questions.json`；保留未外查、憑既有知識的限制 |
| `notes/reviews/2026-10-03-astra-alt/06-subtractive.md:557` | 22,593 | 18 項能力取捨抽 `06-subtractive-capabilities.json`；保留刪減論證 |
| `notes/reviews/2026-10-03-astra-layering.md:3` | 23,143 | **封存**至 `notes/archive/reviews-2026-10-03/` 同名檔；原文已標較早版本 |
| `notes/reviews/2026-10-03-astra-spacetime.md:564` | 28,471 | **保留正文＋抽表。**`:574` 差距抽 `2026-10-03-astra-spacetime-gaps.json`；`:588` 裁決映射抽 `2026-10-03-astra-spacetime-verdict-map.json` |
| `notes/verdicts/11-tick-as-unit/04-1001-結束碼慣例.md:9` | 8,261 | 保留原裁決，清除「當前正本／尚待改」舊狀態；現行條號另指正本 |
| `notes/verdicts/11-tick-as-unit/07-1001-最核心daemon.md:7` | 10,550 | 同上；`:18`、`:45`、`:57` 等舊狀態不能當現況 |
| `plan/m1-tick-core/08-待問.md:7` | 16,747 | 18 題已有答覆，**封存**至 `plan/archive/m1-tick-core/` 同名檔 |
| `plan/m3m-daemon-modules/05-模組四-訊息.md:5` | 8,773 | 已完成舊模組計畫，**封存**至 `plan/archive/m3m-daemon-modules/` |
| `plan/m3m-daemon-modules/09-做完了沒.md:5` | 11,937 | 完成核對史封存；`:50` 的真 root 驗收先保留在 WAIT |
| `proto/README.md:19` | 8,867 | `:19`–`:80` 操作細節拆 `proto/docs/quickstart.md`；入口保留導讀 |
| `proto/notes/codex-task-1.md:3` | 20,433 | **封存**至 `proto/notes/archive/` 同名檔；工作樹、時限與任務指示已完成失效 |
| `proto/notes/spec-gaps.md:5` | 9,456 | G1～G15 抽 `spec-gaps.json`；保留 G15 未實作，不因資料化改狀態 |
| `spec/protocol/tick.md:5` | 12,605 | **保留現役契約**；198 行，與格式權威需完整閱讀；`:110` 的 archive 活引用另清理 |
| `src/py/README.md:7` | 9,404 | 來源表抽 `docs/source-provenance.json`；合併 `:30` 以後重複導航 |
| `src/py/docs/tick.md:35` | 8,730 | 刪除重複規格，改連 protocol 正本；`:81` 已完成計畫映射移出，保留操作與讀碼導引 |

這組最後一輪「完整保留文件是否仍有同質大表漏抽」補核未完成；上述已指定的抽取位置可直接當下一輪整理清單。

### 5.3 `proto7/`：18 份

本表共同前綴：`proto7/notes/thinking/2026-10-04-`。

| 檔案／證據位置 | bytes | 建議 |
|---|---:|---|
| `axes-astra.md:5` | 20,986 | 保留九軸論證正文；同質表漏網補核未完成 |
| `lang-fable.md:5` | 22,296 | 保留單一語言問題的完整論證；先修 `brief4.md` 缺失引用 |
| `r1-astra.md:31` | 40,577 | **拆同名資料夾四章**：模型代數、目標邊界、核心格式、探針問題 |
| `r1-fable.md:21` | 45,350 | **拆四章**：模型遞迴、目標複製、信任時間核心、格式探針問題 |
| `r1-synthesis.md:17` | 19,111 | 保留正文，抽共識、分歧、需求、拍板題、探針；`:94`–`:99` 使用者回應原文保留 |
| `r2-astra.md:24` | 34,162 | **拆四章**：事實出處、時鐘拓樸決策、延遲 RTOS、格式探針問題 |
| `r2-fable.md:28` | 46,629 | **拆四章**：node 事實、時間拓樸 LLM、延遲資源核心、格式探針問題 |
| `r2-synthesis.md:30` | 21,808 | 抽共識、分歧、需求、kernel 任務、拍板題與探針；保留 `:17`–`:24` 使用者更正 |
| `r3-astra.md:7` | 19,977 | 保留受限 node 的連貫推演正文 |
| `r3-fable.md:15` | 30,795 | 保留回應／adapt／時間例子的論證正文；不只因 327 行切碎 |
| `r3-synthesis.md:17` | 20,325 | 抽共識、分歧、任務契約、拍板題、未決與探針；「尚未實作」保留當時時點 |
| `r4-astra.md:3` | 18,085 | 保留三個互相關聯主題及 `:158` 圖解 |
| `r4-fable.md:5` | 32,077 | 保留時間、語言、九軸整合論證 |
| `r5-astra.md:3` | 12,144 | 保留重新檢討前提的正文 |
| `r5-fable.md:5` | 19,994 | 保留撤回與保留骨架的推理，尤其 `:64`、`:115` |
| `r5-synthesis.md:9` | 8,202 | 只超 10 bytes，不硬拆；七項分歧收斂抽資料檔 |
| `r6-astra.md:7` | 19,462 | 保留指定 baseline 的分析；不能把建議當已完成 |
| `r6-fable.md:5` | 23,516 | 同上 |

四份拆檔的具體新檔名：

| 原檔 stem | 同名子資料夾內的新檔 |
|---|---|
| `2026-10-04-r1-astra` | `01-model-algebra.md`、`02-objectives-boundaries.md`、`03-core-and-formats.md`、`04-probes-and-questions.md` |
| `2026-10-04-r1-fable` | `01-model-recursion.md`、`02-objectives-cloning.md`、`03-trust-time-core.md`、`04-formats-probes-questions.md` |
| `2026-10-04-r2-astra` | `01-facts-provenance.md`、`02-clocks-topology-decisions.md`、`03-latency-rtos.md`、`04-formats-probes-questions.md` |
| `2026-10-04-r2-fable` | `01-node-facts.md`、`02-time-topology-llm.md`、`03-latency-resources-core.md`、`04-formats-probes-questions.md` |

原 `.md` 保留導讀及各章入口，不再重複全文。

已核實的 synthesis 資料抽取，放在原檔同層的 `<stem>-tables/`：

| 原檔 | 起行 → 新 JSON |
|---|---|
| `r1-synthesis.md` | `:17` → `consensus.json`；`:34` → `comparison.json`；`:73`、`:81` → `requirements.json`；`:105` → `decision-questions.json`；`:128` 起三個探針 → `probes.json` |
| `r2-synthesis.md` | `:30` → `consensus.json`；`:47` → `comparison.json`；`:94` → `requirements.json`；`:108`、`:118` → `kernel-tasks.json`；`:128` → `decision-questions.json`；`:146` 起三個探針 → `probes.json` |
| `r3-synthesis.md` | `:17` → `consensus.json`；`:32` → `comparison.json`；`:65` → `task-contracts.json`；`:112` → `decision-questions.json`；`:118` → `open-questions.json`；`:129` 起兩個探針 → `probes.json` |
| `r5-synthesis.md` | `:9` → `convergence.json` |

另外兩份雖未超過 8 KiB，仍命中獨立資料規則：

- `2026-10-04-r4-synthesis.md:46` → 同 stem 資料夾的 `open-questions.json`。
- `2026-10-04-r6-synthesis.md:33`、`:49` → `comparison.json`、`technical-questions.json`。

這些是歷史研究的提案／比較，不得在抽取時改成現行裁決。

### 5.4 `proto7-1/`：25 份

本表前綴：`proto7-1/`。

| 檔案／證據位置 | bytes | 建議 |
|---|---:|---|
| `notes/eval/2026-10-03-batch-tick.md:5` | 30,963 | 保留 baseline 明確的完整評估；原始資料已有 JSON，見 `:88`；同質摘要表的最後补核未完成 |
| `notes/infra-needs.md:42` | 71,553 | **資料化＋分流。**86 個唯一 N 編號抽 `infra-needs.json`；已答 Q1～Q6 移 `notes/decisions/2026-10-03-infra.md`；`:321` 後變更史移 `notes/infra-needs/2026-10-03-changes.md` |
| `notes/play/2026-10-03-astra-2.md:9` | 19,459 | 保留方法／結論，抽評分、檔案判讀、覆蓋矩陣 |
| `notes/play/2026-10-03-astra-3.md:11` | 17,535 | 保留方法／限制，抽評分、判讀、回歸、交錯情境 |
| `notes/play/2026-10-03-astra-4-infra-evidence/crash/fragment.md:13` | 8,889 | 保留故障推理；矩陣與需求抽 `fragment-tables/cases.json`、`requirements.json` |
| `notes/play/2026-10-03-astra-4-infra-evidence/tasks/fragment.md:7` | 9,726 | 保留負載方法；案例与需求抽同目錄 `fragment-tables/cases.json`、`requirements.json` |
| `notes/play/2026-10-03-astra-4-infra-evidence/time/fragment.md:7` | 8,478 | 保留時鐘注入方法；抽 `fragment-tables/measurements.json`、`requirements.json` |
| `notes/play/2026-10-03-astra-4-infra.md:50` | 38,303 | 保留報告正文，抽時間、任務覆蓋、既知問題證據、R1～R17 需求與判讀表 |
| `notes/play/2026-10-03-astra-5-infra.md:13` | 28,215 | 保留 F 系列發現論證，抽 I 回歸、F06 隔離案例與需求調整 |
| `notes/play/2026-10-03-astra-6-infra.md:15` | 26,447 | 保留 G 系列論證，抽 F／I 回歸、覆核與需求建議 |
| `notes/play/2026-10-03-astra-7-infra.md:15` | 27,871 | 保留 H 系列／長跑解讀，抽回歸、邊界操作、長跑樣本與需求建議 |
| `notes/play/2026-10-03-astra-8-infra.md:19` | 30,090 | 保留 K 系列原始發現，抽回歸、runner 案例、文件驗收與需求建議 |
| `notes/play/2026-10-03-astra.md:9` | 15,165 | 保留首次試玩正文，抽評分與覆蓋紀錄 |
| `notes/problems-agent.md:7` | 8,343 | 9 筆 A 問題抽 `problems-agent.json`，保留固定 ID |
| `notes/problems-core.md:11` | 15,938 | 19 筆 P 問題抽 `problems-core.json` |
| `notes/problems-real.md:7` | 24,349 | 18 筆 R 問題抽 `problems-real.json` |
| `notes/problems.md:119` | 40,659 | 移除 R1／R2／R15 的整段重複，回到 real 正本；自有 D／I／M 共 24 筆抽 `problems.json`；64 列總導航改為領域入口 |
| `notes/research/2026-10-03-linux-kernel-borrow.md:80` | 91,519 | **按 12 個主題拆同名資料夾**；D 需求表抽 `requirements.json` |
| `notes/research/2026-10-03-other-os-borrow.md:59` | 92,855 | **按 11 個主題拆同名資料夾**；E 需求表抽 `requirements.json`；先修五處相對連結 |
| `notes/runs/2026-10-03-real-1.md:52` | 69,887 | 原始 stdout 移同名資料夾的 `round-4.log`、`round-2.log`、`round-3.log`；正文保留前段分析 |
| `notes/runs/2026-10-03-real-2.md:79` | 77,388 | stdout 移同名資料夾的 `run-1.log`、`run-2.log`、`run-3.log`；不是同質表，不套 wf-table |
| `probes/README.md:16` | 10,715 | 保留導航，結果細節回到各探針 README／需求帳；`:39` 的 N77 待答與 `infra-needs.md:193` 已決狀態對齊 |
| `probes/chaos/README.md:6` | 9,068 | 清掉「B 還會失敗」舊狀態，`:78` 已記 B1～B10 修復；舊發現移 `probes/chaos/archive/2026-10-03-findings.md` |
| `probes/hsched/README.md:76` | 13,833 | 評估結果拆 `probes/hsched/2026-10-03-evaluation.md`；README 留操作及必要限制 |
| `spec.md:34` | 58,592 | **依角色／契約拆 11 章**；保留原路徑入口，不因 7-2 出現就把 7-1 自身規格全封存 |

`infra-needs.md` 另有狀態一致性問題：

- 共有 86 個唯一 N 編號，但出現摘要與正文重複；不可把重複列直接當成 106 個需求。
- `:21`、`:73` 的 N20 已完成敘述，與 astra-8 的 K01／部分完成判斷需要另作狀態核對。
- 資料化本身應逐字保留原狀態與日期，不順便重新裁決。

#### proto7-1 試玩報告的具體 JSON 名稱

各報告放入同層 `<原 stem>-tables/`：

| 報告 | 已確認抽取位置 → 新檔 |
|---|---|
| `2026-10-03-astra.md` | `:9` → `scores.json`；`:103` → `coverage.json` |
| `2026-10-03-astra-2.md` | `:9` → `scores.json`；`:45` → `file-observation.json`；`:139` → `coverage.json` |
| `2026-10-03-astra-3.md` | `:11` → `scores.json`；`:23` → `file-observation.json`；`:43` → `regression.json`；`:55` → `coverage.json` |
| `2026-10-03-astra-4-infra.md` | `:50` → `timing.json`；`:69` → `task-coverage.json`；`:193` → `known-issues-evidence.json`；`:216`、`:233` → `requirements.json`；`:257` → `file-observation.json` |
| `2026-10-03-astra-5-infra.md` | `:13` → `regression.json`；`:95` → `isolation-cases.json`；`:159`、`:173` → `needs-review.json` |
| `2026-10-03-astra-6-infra.md` | `:15`、`:31` → `regression.json`；`:134` → `coverage.json`；`:150` → `needs-review.json` |
| `2026-10-03-astra-7-infra.md` | `:15`、`:30` → `regression.json`；`:38` → `boundary-cases.json`；`:69` → `longrun-samples.json`；`:165` → `needs-review.json` |
| `2026-10-03-astra-8-infra.md` | `:19` → `regression.json`；`:54` → `runner-cases.json`；`:88` → `docs-acceptance.json`；`:193` → `needs-review.json` |

同一 JSON 合併不同系列時，增加 `series` 或 `group` 欄，保留原分組，不刪看似重複但證據時點不同的列。

#### 兩份研究與 spec 的拆法

`notes/research/2026-10-03-linux-kernel-borrow/`：

```text
01-scope.md
02-accounting.md
03-resource-control.md
04-fairness-admission.md
05-policy-interface.md
06-pressure.md
07-multiresource.md
08-lifecycle.md
09-time.md
10-isolation.md
11-related-systems.md
12-workflow-validation.md
requirements.json
```

`notes/research/2026-10-03-other-os-borrow/`：

```text
01-scope-namespace.md
02-rtos.md
03-microkernels.md
04-protection-persistence.md
05-shares-accounting.md
06-scheduling-research.md
07-distributed-contracts.md
08-aios-schedulers.md
09-token-delegation.md
10-differences-needs.md
11-experiments.md
requirements.json
```

`proto7-1/spec/`：

| 新檔 | 原 `spec.md` 行 |
|---|---|
| `01-common-space.md` | 7–33 |
| `02-daemon-lifecycle.md` | 34–75 |
| `03-daemon-control.md` | 76–113 |
| `04-daemon-observation.md` | 114–132 |
| `05-rounds-tick.md` | 133–179 |
| `06-mounts.md` | 180–198 |
| `07-task-runtime.md` | 199–232 |
| `08-task-control.md` | 233–246 |
| `09-tock-tools.md` | 247–271 |
| `10-kernel.md` | 272–302 |
| `11-agent.md` | 303–350 |

`02-daemon-lifecycle.md` 的預估本文仍略超 8 KiB，但屬完整生命週期契約，可保留，不必再切碎。

### 5.5 `proto7-2/`：31 份

本表前綴：`proto7-2/`。

| 檔案／證據位置 | bytes | 建議 |
|---|---:|---|
| `README.md:38` | 14,818 | 測試導引拆 `tests/README.md`；`:85` 結構圖移 `INDEX.md`；修 `:14` 等已落後的 packs 狀態 |
| `modules/diag/README.md:37` | 9,203 | 復原細節拆 `modules/diag/recovery.md`；這是人用操作手冊，不硬轉資料表 |
| `modules/subd/README.md:15` | 11,239 | 保留完整 77 行契約；`:5` 的廣泛 kill 描述須與 `:22`–`:25` 的界線一致 |
| `notes/blueprint-loop4.md:6` | 10,349 | 已完成藍圖封存至 `notes/archive/` 同名檔；先保留仍有效理由 |
| `notes/blueprint-loop5.md:11` | 11,803 | 同上；subd／budget 的有效理由先搬現行文件 |
| `notes/blueprint-loop6.md:6` | 16,582 | 同上；budget／adapt 理由先移各自 `packs/*/design.md` |
| `notes/changes-from-7-1.md:24` | 12,732 | 舊比較正文封存；`:60` 後 W1～W12 抽 `notes/problems/decisions-pending.json`，保留未裁決身分 |
| `notes/component-contracts.md:27` | 19,563 | 元件表抽 `notes/component-contracts/components.json`；`:42` writer／輸入責任表抽 `ownership.json`；方法與人用導航保留 |
| `notes/core-slimming.md:322` | 32,421 | 未完成計畫拆 `notes/plans/kernel-packs.md`；`:431` 有效決策移 `notes/decisions/2026-10-04-core-slimming.md`；完成史封存，原路徑留入口 |
| `notes/layer-interfaces/01-daemon-ticktock.md:11` | 8,478 | 保留有效契約後，舊調查移 `notes/archive/layer-interfaces/` 同名檔 |
| `notes/layer-interfaces/02-ticktock-task.md:11` | 9,425 | 同上；restart、ctl-seen、retry_lost 等舊敘述不可當現況 |
| `notes/layer-interfaces/03-kernel-agent.md:33` | 10,004 | 15 筆遷移事項抽 `notes/plans/kernel-agent-migration.json`，再封存舊調查 |
| `notes/layer-interfaces/04-cross-layer.md:44` | 9,887 | 舊 core／subd 責任分法封存；仍有效規則歸現行契約 |
| `notes/layer-interfaces/05-gaps.md:9` | 9,266 | 真正 open 抽入 `notes/problems/open.json`；G1／G2／G17 已完成、G3 已修，不能整表當待辦 |
| `notes/layer-interfaces.md:27` | 10,960 | 遷移／缺口抽完後整組封存；避免再維持一份重複現況圖 |
| `notes/play/2026-10-04-astra-1-infra-evidence/once-report.md:15` | 8,379 | 抽 `once-claims.json`、`:33` 的 `once-k-comparison.json`；保留分析 |
| `notes/play/2026-10-04-astra-1-infra.md:27` | 30,574 | 抽 promises／K 比較／建議／文件驗收表；正文保留歷史觀察 |
| `notes/play/2026-10-04-astra-2-infra-evidence/daemon-review.md:7` | 10,452 | 抽 `daemon-regression-verdicts.json`、`:41` 的 `daemon-stop-review.json` |
| `notes/play/2026-10-04-astra-2-infra.md:23` | 29,137 | 抽 A2 verdict、矩陣核對、stop 核對三表 |
| `notes/play/2026-10-04-astra-3-infra.md:9` | 22,004 | 抽結果、回歸、元件核對三表 |
| `notes/play/2026-10-04-astra-4-infra.md:27` | 9,558 | 抽 `report-a4-verdicts.json`；歷史 G3 引用保留日期 |
| `notes/play/2026-10-04-astra-5-infra.md:5` | 12,909 | **保留完整報告。**已檢視表格各自低於 1 KiB，且 baseline 清楚 |
| `notes/play/2026-10-04-astra-6-infra.md:11` | 14,255 | 抽結果與 `:66` adapt verdict 兩表 |
| `notes/problems.md:9` | 57,463 | **優先重整。**open → `notes/problems/open.json`；A2～A7 歷史 → `notes/archive/problems.md`；`:351` 的 43 筆理由 → `rationales.json` |
| `notes/reviews/2026-10-05/event-store.md:5` | 36,047 | 保留研究正文；抽七份資料檔、八個表塊；先修 app 式路徑連結 |
| `notes/reviews/2026-10-05/test-review.md:22` | 37,295 | 保留分析正文；六塊缺口矩陣抽資料檔；維持「未執行／靜態風險」界線 |
| `packs/adapt/spec.md:16` | 9,106 | **保留現役契約。**115 行；將舊 loop6 理由連結改指現行 design |
| `packs/budget/README.md:22` | 8,620 | 保留簡潔卡片；`:9`–`:20` 重複政策濃縮成連到 spec 的摘要 |
| `packs/budget/spec.md:22` | 12,214 | **保留完整交易契約。**103 行，reserve／call／settle／重播須一起讀 |
| `packs/step/spec.md:19` | 10,424 | **保留完整恢復契約。**99 行，不按 bytes 硬拆 |
| `spec.md:5` | 31,147 | **保留现役核心契約。**298 行；`:267` 連向舊 problems 的規劃內容應改指抽出的現行計畫 |

#### proto7-2 試玩報告的資料檔

資料檔放各輪既有 evidence 目錄，避免另建第二份原始證據：

| 報告位置 | 新資料檔 |
|---|---|
| `2026-10-04-astra-1-infra.md:27`、`:83`、`:98`、`:113` | `report-claims.json`、`report-k-comparison.json`、`report-advice.json`、`report-doc-checks.json` |
| `2026-10-04-astra-2-infra.md:23`、`:43`、`:93` | `report-a2-verdicts.json`、`report-matrix-review.json`、`report-stop-review.json` |
| `2026-10-04-astra-3-infra.md:9`、`:27`、`:45` | `report-results.json`、`report-regression.json`、`report-components.json` |
| `2026-10-04-astra-4-infra.md:27` | `report-a4-verdicts.json` |
| `2026-10-04-astra-6-infra.md:11`、`:66` | `report-results.json`、`report-adapt-verdicts.json` |

這些是報告的判讀資料，不能覆寫既有原始實驗 JSON。

#### 新 event-store 報告

前綴：`proto7-2/notes/reviews/2026-10-05/`。

| `event-store.md` 起行 | 新資料檔 |
|---|---|
| `:24` | `event-store-boundaries.json` |
| `:40`、`:55` | `event-store-loss-inventory.json`，保留 F01～F12 |
| `:90` | `event-store-history-limits.json` |
| `:119` | `event-store-crash-windows.json` |
| `:149` | `event-store-options.json` |
| `:353` | `event-store-acceptance.json` |
| `:409` | `event-store-decisions.json` |

八個表塊合計約 14.7 KB。其餘正文保留，尤其：

- `:11`：靜態推導與實測的區分。
- `:147`：方案 A／B 與 C 可組合。
- `:236`：契約仍未定案。
- `:351`：驗收尚未執行。
- `:407`：建議不是授權。

#### 新 test-review 報告

同一前綴。

| `test-review.md` 起行 | 新資料檔 | 列數 |
|---|---|---:|
| `:251` | `test-review-flaky.json` | 7 |
| `:291` | `test-review-core-coverage.json` | 10 |
| `:353` | `test-review-subd-coverage.json` | 6 |
| `:364` | `test-review-step-coverage.json` | 6 |
| `:379` | `test-review-adapt-coverage.json` | 6 |
| `:388` | `test-review-budget-coverage.json` | 8 |

共 **43 列、11,353 bytes**。`finding_id` 保留原 T8 編號；一個發現下的六個測試缺口，不應憑空變成六個新發現編號。

保留 `:22`、`:28`–`:32`、`:479` 的界線：案例數不是本輪執行結果、風險分級不是全部已重現、效能估算尚未實測。

---

## 六、資料化與封存時必須保留的資訊

### 6.1 `wf-table/1` 不是把內容縮成摘要

所有建議 JSON 都應保留：

- `contract: "wf-table/1"`。
- `source`，相對於資料檔位置。
- `extracted` 日期。
- `columns`。
- 原始編號、完整問題／選項／推薦／使用者回答。
- 原狀態及觀察日期，避免把歷史提案變成目前已決。
- 證據欄及適當 `link_columns`。

對 problems／需求帳，可用：

```text
id, title, category, status, observation, proposal,
user_response, followup, observed_at, evidence_path
```

對回歸／验收表，可用：

```text
id, series, promise_or_case, verdict, evidence, limitation
```

對裁決表，可用：

```text
id, question, options, recommendation, ruling, status, evidence
```

欄位應依原表調整；缺值不能由整理者臆補。規則證據：`wf/workflows/common/data-files.md:19`–`:20`。

### 6.2 搬檔不能只修目錄連結

必須一併處理：

- 文內相對路徑。
- `#標題錨點`。
- 別檔指向原檔內標題的連結。
- 同名標題的 `-1`、`-2`。
- 資料檔內相對路徑。
- 舊問題／裁決 ID 的引用。

證據：`wf/STRUCTURE.md:43`、`:49`、`:51`；資料路徑解析規則見 `wf/workflows/common/data-files.md:28`–`:31`。

### 6.3 封存前的依賴順序

本次已確認的關鍵順序：

1. **loop5／loop6 → pack design**：`packs/budget/spec.md:5`、`packs/adapt/spec.md:5` 仍取用藍圖理由。
2. **core-slimming → decisions／remaining plan**：`notes/component-contracts.md:165` 仍引用其理由。
3. **layer-interfaces → open gaps／kernel migration**：`03-kernel-agent.md:40`–`:50` 的遷移工作不可消失。
4. **problems → kernel plan**：`notes/problems.md:397`–`:399` 的 usage 規劃仍被 `spec.md:267` 使用。
5. **舊 wf spec → ideas rulings**：`wf/workflows/ideas/README.md:33` 的有效裁決來源先搬。

不能先把來源塞進 archive，再把活連結一起改指 archive。

### 6.4 封存的 77 份超標文件

已確認大小盤點結果：

- `wf/`：25 份。
- `proto6/`：52 份。

依 `wf/STRUCTURE.md:59`、`:85`，這 77 份的預設處置是**保留封存原文，不為 8 KiB 進一步拆分或資料化，也不要求修復其內部連結**。

本報告未完成這 77 份的逐檔名錄整併及內容覆核，因此沒有把「位於 archive」擴張成「每份都已確認封存得正確」。可用第九節盤點指令完整列出。

---

## 七、建議執行順序

這是後續建議，**本輪沒有執行任何修改**。

1. **先修活狀態與入口。**清 SESSION 完成史、修 WAIT 的已決編號及統計、更新 proto7-2 路由、修 root 驗收手冊。
2. **處理會誤導的現況矛盾。**優先 `proto7-2/notes/problems.md`、core-slimming、layer-interfaces；保留真正未決事項。
3. **修連結。**先缺失原稿與 account→budget，再修快照封裝入口及新報告的 app 式連結。
4. **抽離需求／問題／回歸資料。**先做 infra-needs、problems、company-market，再做試玩報告；這批收益較直接。
5. **按主題拆真正多職責的大文。**兩份 OS 調查、proto7-1 spec、r1／r2 原始研究、入口导航。
6. **最後封存舊計畫及舊 spec。**前提是有效理由、open 尾項、活引用都已處理。
7. **驗收不追求超標歸零。**應列清楚保留例外、確認無意義變更、無失效活連結、固定 ID 不遺失。

---

## 八、做到一半與沒來得及做的部分

### 已做到一半、不能宣稱驗完

1. **保留型大檔的最後一輪同質清單檢查。**  
   已補完 proto7 synthesis、proto7-1 試玩報告及新 test-review 的多處漏抽候選；但收到收尾指示時，以下補核尚未收齊：
   - proto7 的 astra／fable 原始論證。
   - proto7-1 batch-tick、兩篇 OS 調查及 spec 中的其餘同質區塊。
   - proto6 保留型規格、手冊及六份替代方案報告。
   - wf salvage 保留型文章。

   因此，逐檔表中的「保留正文」不是對其所有表格的最終豁免。

2. **舊 wf spec 封存前的完整入站引用核對。**  
   已確認 ideas 仍引用 rulings，也提出歸層位置；沒有完成全部引用逐一遷移設計。

3. **WAIT C 區 `:45`、`:46` 的補核。**  
   `:46` 明寫 proto2 T01～T77 已完成，偏向應退出 only-open hub；但「top-down-cli 已裁、實作時順便解決」是否仍有執行尾項，最後補核未完成，本報告不把它併入確定可刪數字。

4. **封存 77 份的逐檔輸出。**  
   大小已量到，未完成完整名錄的報告整併，也未逐份審其封存合理性。

5. **截點後工作樹變動。**  
   沒有追查。lint 最新總數是原完整掃描加兩份指定報告的已核實增量。

### 沒有執行，亦不應解讀為本輪已驗證

- 任何文件修改、JSON 建立、搬檔、封存或連結修復。
- 建置、ctest、Python 測試或試玩重跑。
- 真 root／帳號驗收。
- 外部網站與 artifact 可達性。
- 對已缺失的 `proto7/user-advice.md`、`brief4.md` 做內容重建。
- 對所有歷史待辦逐一證明完成；本報告只關閉有足夠證據的部分。
- 對 event-store／test-review 內的技術主張重新做實驗驗證；本線只審其文件結構及引用形式。

---

## 九、唯讀重現指令

以下指令是供重現使用，沒有在收到收尾指示後再次執行。

### 9.1 列出指定範圍所有超標 Markdown

從 repo 根目錄執行；不建立檔案：

```sh
python3 -B -c '
from pathlib import Path

roots = [Path("wf"), Path("proto6")]
roots += sorted(p for p in Path(".").glob("proto7*") if p.is_dir())

for root in roots:
    files = sorted(p for p in root.rglob("*.md") if p.is_file())
    live = [p for p in files if "archive" not in p.parts]
    big = [p for p in files if p.stat().st_size > 8192]
    print(
        "SUMMARY", root,
        "all", len(files),
        "live", len(live),
        "big_live", sum("archive" not in p.parts for p in big),
        "big_archive", sum("archive" in p.parts for p in big),
        sep="\t",
    )
    for p in big:
        print(
            "archive" if "archive" in p.parts else "live",
            p.stat().st_size,
            p,
            sep="\t",
        )
'
```

### 9.2 重現歷史版本的 15／44 與目前差異

```sh
python3 -B -c '
import subprocess

refs = ["c15aee6f", "5a806afc", "c1cf5bf2", "6143919f", "HEAD"]
for ref in refs:
    raw = subprocess.check_output(
        ["git", "ls-tree", "-rlz", ref, "--", "wf", "proto6"]
    )
    counts = {"wf": 0, "proto6": 0}
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        fields = meta.split()
        name = path.decode()
        if fields[1] != b"blob" or not name.endswith(".md"):
            continue
        if "archive" in name.split("/") or int(fields[3]) <= 8192:
            continue
        counts[name.split("/", 1)[0]] += 1
    print(ref, counts)
'
```

各完成證據可用相同唯讀方式檢查：

```sh
git show --format=fuller --stat ddda65a9
git show --format=fuller --stat 52870cbd
git show --format=fuller --stat 895ad51b
git show --format=fuller --stat c56044de
```

### 9.3 重現 lint 一般掃描，排除會寫入的 self 分支

```sh
python3 -B -c '
from pathlib import Path
import os
import subprocess
import sys

p = Path("wf/tools/wf-lint.sh").resolve()
s = p.read_text()

head = s.split("\nif [[ $self -eq 1 ]]; then\n", 1)[0]
tail = s[s.index("\necho \"TOTAL broken="):]

safe = head + """
[[ ${#dirs[@]} -eq 0 ]] && dirs=(.)
for d in "${dirs[@]}"; do lint_dir "$d" "$d"; done
""" + tail

assert "--self" not in sys.argv[1:]
assert not any(x in safe for x in ("mktemp", "rm -rf", "wf-init.sh", "tee "))

env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("BASH_ENV", None)
env.pop("ENV", None)

result = subprocess.run(
    ["bash", "--noprofile", "--norc", "-c", safe, str(p), *sys.argv[1:]],
    env=env,
    capture_output=True,
    text=True,
)
print(result.stdout, end="")
print(result.stderr, end="", file=sys.stderr)
sys.exit(result.returncode)
' --strict ./wf
```

將最後的 `./wf` 換成 `.` 可重現全 repo 掃描。結果會反映執行當時的工作樹，未必等於本報告的固定截點。