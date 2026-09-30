← [審稿索引](README.md)

# astra 核對第十八批落 spec（2026-09-30）

以 **09 裁定正本優先**，逐條核對方向、審稿裁定、Q1～Q33、延後項，並用 Python 讀完 map 的 **114 列**，再交叉檢查主規格、協議、schema、範例及最近改寫的 commits。交接紀錄中的「暫定」另行辨認，沒有當成使用者裁定。

**結論：大部分內容已落入，但還不能算完整完成；最大缺口是方案 A，協議篇仍保留大量行為規則。**

以下按修正主題計 **15 項問題**：沒落乾淨或來源標錯 4 項、方案 A 殘留 9 組、新矛盾 2 項。同一問題不重複計數。map 的 `原型-01～18` 明列本輪不改，沒有算成漏項。全程唯讀，未改檔、未 commit。

## 一、沒落或落錯

### 1. LLM「必須集中同一池」的舊限制沒有改乾淨

**依據：09 方向 3、5；map `裁-15`。**

應該由各 kernel 決定同 provider 的限制要不要集中、要不要分片。不同 node 的同名 scope 不會自動同步，這個技術限制可以保留。

現在：

- [proto6/spec/protocol/README.md:119](../../../spec/protocol/README.md) 已寫成各 kernel 自己的政策。
- 但 [proto6/spec/scheduling/llm.md:30](../../../spec/scheduling/llm.md) 仍要求共享 provider 帳戶／模型限制的池，交同一池 node 統一計數。
- [proto6/spec/protocol/llm-work.md:15](../../../spec/protocol/llm-work.md) 也保留「必須」集中管理的說法。

**建議：**S-301 改成條件式：「kernel 選擇把多個入口視為同一共享限制時，才使用同一計數域；是否集中、是否分片由 kernel 決定。」P-405 只留 `quota_scope` 的格式與引用。

### 2. Q16 多寫了「第二次 SIGTERM 也立即停」，卻未標為補充

**依據：09 Q16；map `裁定7`。**

09 裁定的是：排空超過上限，或途中再按 Ctrl-C，轉立即停。

現在 [proto6/spec/daemon.md:75](../../../spec/settled/daemon.md) 擴成第二次 **SIGINT／SIGTERM** 都立即停；[proto6/spec/cli/commands.md:25](../../../spec/cli/commands.md) 也跟著擴寫。

**建議：**照正本收窄成第二次 SIGINT／Ctrl-C；若保留 SIGTERM，應明標為工程補充，不能整段都掛使用者裁定。這項是來源與範圍問題，不是漏掉排空功能。

### 3. Q3 已接受，仍被標成「未拍板」

**依據：09「其餘照預填」中的 Q3。**

保留父配額公開檔，已是使用者接受的內容。

現在 [proto6/spec/scheduling/admission.md:42](../../../spec/scheduling/admission.md) 的內容有落，但整段仍標「建議預設，未拍板」。

**建議：**把「保留公開檔」標成第十八批 Q3；「提交後下一格發布」等工程細節可以另外保留預設標記，避免把已裁定與工程補充混在一起。

### 4. map `建-32` 只修了死條號，舊的設定不變保證還在

**依據：map `建-32`，屬 notes 收尾項。**

現在 [proto6/notes/between-ticks-configuration.md:11](../../../notes/between-ticks-configuration.md) 仍說，同一 tick／attempt 執行中途不能換「設定版本」。

但 [proto6/spec/agent/configuration.md:17](../../../spec/agent/configuration.md) 明定：tick 裡不改設定只是軟性原則，不檢查、不阻擋，同格混用風險由任務作者承擔。

**建議：**保留 UID、群組、cgroup 的界線；把「設定版本不能換」改成軟性原則，並引用 A-102。這是 map 尚未收完的歷史文件，不是 spec 本身缺少 A-102。

## 二、方案 A 殘留

**共同依據：09 Q1、審稿裁定 15、map `裁定15` 及相關 `重複-*` 列。**

V-01 和 P-009 已宣告主規格為正本，但「主規格有了、協議加連結」不等於搬完。以下仍能直接讀出操作流程，超過「一句摘要加引用」。欄位型別、JSON、schema、argv、碼表及必要欄位語意沒有算進來。

### 5. 共用協議入口仍在規定發布與執行行為

位置：[proto6/spec/protocol/README.md:24](../../../spec/protocol/README.md)，另見同檔 27、34、43、111～120 行。

仍寫完整發布步驟、提交後消費／投件、method 處理、key 傳遞限制，以及 once、池政策、unknown 等行為。

**建議搬向：**B-402、B-501、B-503、B-623、B-624、S-301、S-401；P-003～006 留載體、檔名、編碼、argv 與碼表，P-008 留延後清單及導航。

### 6. daemon 協議仍保留啟動、查詢及 helper／runner 流程

主要位置：

- [proto6/spec/protocol/daemon/startup-and-ipc.md:52](../../../spec/settled/protocol/daemon/startup-and-ipc.md)：啟動、socket、helper 生死與授權流程，後續 56～82 行亦有。
- [proto6/spec/protocol/daemon/registration.md:48](../../../spec/settled/protocol/daemon/registration.md)：查詢排序、過濾、分頁與重啟後处理。
- [proto6/spec/protocol/daemon/provision-and-runner.md:29](../../../spec/settled/protocol/daemon/provision-and-runner.md)：helper bind/start/stop、失聯恢復；50～73 行另有 runner 解析、開檔、清後代及產生 `.err`。
- [proto6/spec/protocol/daemon/shutdown.md:19](../../../spec/settled/protocol/daemon/shutdown.md)：狀態寫入與讀回操作。

**建議搬向：**B-303、B-603～611、B-202、inst、S-401。協議只留 method、參數、fd／回報形狀及碼值。主要涉及 `重複-02～07、22、23`。

### 7. node 協議仍保留 tick、git、設定修改及建立流程

位置：[proto6/spec/protocol/node.md:55](../../../spec/settled/protocol/node.md)，另見同檔 61、75～79、94～104、121～141、149～158 行。

仍包含：

- 無人宣告 method 時如何複製、回錯與送回應。
- 取鎖、建立／清殺 `task-*`、框外 tick 拒跑。
- group 成敗、git 基線、提交、還原與修復。
- `aos-config-add` 的鎖與提交流程、共享權限配置。
- node new／resume 的檢查與採用順序。

**建議搬向：**B-202、B-501、B-602、B-620～627、A-102、CLI 主規格；P-200～210 留布局、任務表、介面與範本形狀。主要涉及 `重複-01、08、09、11、23`。

### 8. messages 協議仍保留投件、回址與補投演算法

位置：[proto6/spec/protocol/messages.md:24](../../../spec/protocol/messages.md)，另見同檔 36～40、49、51～61、73～77 行。

仍規定發布／門鈴順序、接納前核回址、固定回址、可信來源、從 git 歷史補投，以及接件後如何執行命令。

**建議搬向：**B-402、B-501、B-503、B-623、B-624、S-406。P-303 留 `reply_to` 語意，P-304 留 ID／bytes 比對格式，P-306 留 method 與輸入輸出表。主要涉及 `重複-09～12`。

### 9. work／LLM 協議仍保留派工及結果判定流程

主要位置：

- [proto6/spec/protocol/work.md:46](../../../spec/protocol/work.md)：建立工作目錄、固定 inst、register／wake、收結果及用量；81～89、115～121 行另有成功／unknown／重試判定。
- [proto6/spec/protocol/llm-work.md:17](../../../spec/protocol/llm-work.md)：三檔執行方式；24、28、38、42～50 行另有 key 使用、轉交、HTTP 與有限重試流程。

**建議搬向：**B-101、B-103、B-202、B-606、S-301～307、S-401、S-207。協議保留材料布局、payload、結果、messages 子集合及程式介面。主要涉及 `重複-13、15、16、18`。

### 10. resources 協議仍保留配額更新與量測政策

位置：[proto6/spec/protocol/resources.md:24](../../../spec/protocol/resources.md)，另見同檔 9～11、32～36、50～52、60～70、74～78 行。

仍包含配額選版／撤回、module 執行、usage 收集、累積值重建、OOM 判定、LLM 冷卻，以及磁碟去重和網路 backend 不足時的停工規則。

**建議搬向：**S-203、S-205、S-207、S-301～304、B-204、B-304。協議留下資源形狀、cgroup 檔案對照與量測欄位。主要涉及 `重複-17、18`。

### 11. ops 協議仍保留完整清理與事項生命週期

位置：[proto6/spec/protocol/ops.md:11](../../../spec/protocol/ops.md)，另見同檔 25～27、37～39、47、51～65、83～96 行。

仍規定事項授權、去重、完成與彙整；`aos-clean` 的到期判斷、鎖、提交、遍歷、archive/delete、故障恢復；以及設定修復流程。

**建議搬向：**S-405、B-404、B-607、A-102。協議只留事項／清理設定／報告格式及指令介面。主要涉及 `重複-07、20`。

### 12. agent 協議仍保留大部分 agent 狀態機

位置：[proto6/spec/protocol/agent-tasks.md:75](../../../spec/protocol/agent-tasks.md)，另見同檔 27～37、81～124、135～174、178～190 行。

仍完整寫每格收件與推進、context、LLM／工具等待、正式回覆、恢復、usage、輪詢，以及清理遍歷。

**建議搬向：**A-102、A-201～203、A-302～303、A-401～403、A-503、S-207、B-404、CLI 主規格。協議只留設定、狀態檔、訊息、範本與介面。主要涉及 `重複-09、15、16、19、20`。

### 13. kernel 協議仍保留完整同步、排程及資源流程

位置：[proto6/spec/protocol/kernel-tasks.md:39](../../../spec/protocol/kernel-tasks.md)，另見同檔 9～26、58～88、92～103、107～169、175～179、203～209 行。

仍規定成員配額選版、增刪／同步／重建、wake、失聯、資源套用、阻擋派工、取消、forward／pool、usage 及清理。

**建議搬向：**S-201～207、S-301～307、S-401、S-405、S-406、B-203、B-404、B-603、B-606。協議留各 state 欄位、argv 與範本表。主要涉及 `重複-04、14、15、17～20`。

因此，map 的重複列不能只因「已建立正本、加上連結」就判全部完成；上面九組還需要真正縮掉協議中的操作流程。

## 三、新引入的矛盾

### 14. 排空模式要求繼續開格，協議驗收卻仍說全部停止開格

**依據：09 裁定 7、Q15；map `裁定7、重複-03`。**

- 新規則：[proto6/spec/daemon.md:72](../../../spec/settled/daemon.md)——排空時，已登記 node 照常開格，只拒新 once／新成員。
- 舊驗收：[proto6/spec/protocol/daemon/shutdown.md:13](../../../spec/settled/protocol/daemon/shutdown.md)——Ctrl-C／SIGTERM 後「都不開新格」。

這會讓排空實作無法同時符合兩處文字。

**建議：**刪掉協議的行為驗收，改引 B-604；若保留說明，必須明確限定前半句只適用 `stop_mode:"immediate"`。

### 15. B-203 同時保留兩套取消與正常結束的判定

**依據：map `建-3、重複-14`。**

- 本輪新增：[proto6/spec/base/execution.md:50](../../../spec/base/execution.md)——記 `canceling` 後，正常結束並完整發布，仍照原結果；因 TERM 產生的 signal 結果才記 canceled。
- 原有段落：[proto6/spec/base/execution.md:54](../../../spec/base/execution.md)——先處理取消後，即使取得 exit 0，也記 canceled。

例如：取消先開始，程序接到 TERM 後正常 exit 0，再發布結果。兩段會得出不同狀態。git 核對確認，第 50 行是本輪新增，第 54 行是留下來的舊規則。

**建議：**統一取消判界，並明寫「TERM 後 exit 0」算哪一類；若採新三窗口，第 54 行取消部分應改成引用上段判定，逾時規則另寫，不能繼續保留兩套。

第一節的 LLM 集中政策也形成跨篇不一致，已在第 1 項計數，這裡不重算。

## 四、檢查結果

| 檢查 | 結果 |
|---|---|
| `python3 proto6/spec/check_ids.py --strict` | **通過**：2053 個引用、223 個定義；找不到、重號、只剩索引、預留未寫均為 0 |
| 指定的 `uv run --no-project --with jsonschema …/validate.py` | **受沙盒阻擋**：無法建立 uv 快取鎖所需的暫存檔 |
| 用既有 uv 環境的 Python 加 `-B` 執行同一支 `validate.py` | **通過：57 schemas、232 examples**；未安裝套件、未建立檔案 |
| 工作樹 | `git status --porcelain` 無輸出；未改檔、未 commit |

驗證通過的是條號、schema、正反例及驗證器既有的關聯檢查，不能消除上述文字規則矛盾。

交接紀錄中的自訂 kind 命名、重建完成判準、`aos-clean` 保持 custom 但算基底、壞件 issue_id 算法等，均有工程預設標記；沒有僅因它們是「暫定」就列成漏項。

## 五、已確認落實

下表列已找到的正文落點；**＊表示仍有前述缺口或矛盾，不能整條判完成**。協議行為重述另外統一列在第二節。

| 09 條目 | 落點條號 |
|---|---|
| 方向 1 | T-06 |
| 方向 2 | T-06 |
| 方向 3＊ | T-06、B-620、S-203 |
| 方向 4 | B-301、B-605 |
| 方向 5＊ | T-06、S-203、S-206、S-301 |
| 方向 6 | T-06、P-008 |
| 裁定 1 | T-07、B-626、P-008 |
| 裁定 2 | T-08、B-301、B-501、S-301 |
| 裁定 3 | B-303、B-609 |
| 裁定 4＊ | B-203、P-411 |
| 裁定 5 | B-202、B-605 |
| 裁定 6 | B-606～608 |
| 裁定 7＊ | B-604、P-114 |
| 裁定 8 | B-605、B-609、S-205 |
| 裁定 9 | C-07、P-007、H-004 |
| 裁定 10 | A-403、P-707、P-008 |
| 裁定 11 | A-201、S-406、P-008 |
| 裁定 12 | A-201、P-008 |
| 裁定 13 | B-623、B-624、B-404、P-706 |
| 裁定 14 | B-103、B-404、B-503、P-403、P-008 |
| 裁定 15＊ | V-01、P-001、P-009 |
| 裁定 16 | B-627、H-004 |
| 裁定 17 | B-605、B-622 |
| 裁定 18 | B-610、H-004、H-037 |
| Q1＊ | V-01、P-001、P-009 |
| Q2 | T-06、B-620、S-203 |
| Q3＊ | S-203、P-804 |
| Q4 | S-301、P-008 |
| Q5 | B-608 |
| Q6 | B-608 |
| Q7 | B-608 |
| Q8 | B-606、B-607、S-205 |
| Q9 | B-606 |
| Q10 | B-606 |
| Q11 | B-607 |
| Q12 | B-606、B-608 |
| Q13 | B-608 |
| Q14 | B-604、P-114 |
| Q15＊ | B-604、P-114 |
| Q16＊ | B-604、H-004 |
| Q17 | B-609、S-205、P-804 |
| Q18 | B-605 |
| Q19 | B-603、B-605、B-606、B-608 |
| Q20 | B-603、B-606、B-609 |
| Q21 | B-609、P-108 |
| Q22 | T-07、B-626、P-814 |
| Q23 | B-627、H-004 |
| Q24 | T-08、B-501、S-301 |
| Q25 | B-203 |
| Q26 | B-624、P-008 |
| Q27 | B-623、B-404、P-601 |
| Q28 | B-103、B-503、P-403 |
| Q29 | A-403、P-008 |
| Q30 | C-07、P-007、H-004 |
| Q31 | B-622、P-205 |
| Q32 | B-610、P-101、H-004 |
| Q33 | H-004、H-037 |
| 編輯決定：收尾／排空用詞 | T-09、B-604 |
| 延後：其餘外殼、隨機性量化 | T-06、T-07、P-008 |
| 延後：kernel／agent／custom 逾時取消 | B-626、B-203、P-008 |
| 延後：agent 拒收、unknown 輸入、檢查結束碼 | P-008 |
| 延後：agent 問答、自開 once 回查／取消 | A-201、A-403、P-008 |
| 延後：鬧鐘 Q26、通用外部資源池、git 歷史回收 | B-624、S-301、B-404、P-008 |