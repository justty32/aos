總評：三份合併**不能定稿**；E-1～E-5 為 **4 已解、1 部分、0 沒解**。
指定的四個崩潰時序都已接通；剩餘缺口是封存憑據的清理邊界、start 新增的環境依賴，以及讀驗錯誤的寫入承諾。
以已提交版本 **835bb4b** 為準，包含下層 2026-09-24 實作補記；全程唯讀。
以下檔名均位於 `proto5/spec/`；三件使用者拍板不重審。

## A. 驗收 E-1～E-5

1. **E-1｜部分。** `agent.md:217`、`:218`、`:220`、`:221`；`aos-agent.md:223`。唯一封存名與 `{src,dst}` 已解決原本正常恢復吞同名檔的窗口，但尚未保護仍被紀錄引用的封存檔，見 C-1。

   四個指定時序逐一走查：

   - **rename 後崩、生產者再投同名 B：通。** A 的 `dst` 已存在，恢復不碰新 `src`，只讀封存的 A；B 留到下一次 idle。`aos-agent.md:225`、`:230`。
   - **rename 前崩：通。** `intake`／`consuming` 已先持久，原檔仍在；生產者不得覆寫未收原檔，恢復照原配對搬。`agent.md:174`；`aos-agent.md:59`、`:224`。
   - **rename 後、state 沒落盤：通。** 必須區分是哪次 state：配對紀錄在 rename **之前**已落盤，尚未落盤的是清紀錄／轉狀態。恢复依 `dst` 判定搬過；若記憶也已寫，按既定長度與相同尾巴重寫，再結清。`aos-agent.md:60`、`:63`、`:224`、`:227`、`:228`。
   - **兩份同名接連投遞：通。** A 搬走後 B 才占原路徑；A 用 id₁ 結清，B 下次用 id₂ 收取。consume 也不會因舊配對仍在而搬走 B。`agent.md:173`、`:217`、`:221`。

   `continue-<批 id>.json` 已分隔各次暫停，不再沿用舊訊號，見 `aos-agent.md:235`。第 2 輪 changes 的 C-6／C-8 也已更正為「沒通」；第 3 輪自走表成立的前提，是封存憑據尚未被清除。

2. **E-2｜已解。** `aos-agent.md:130` 明訂有 `clear` 必須寫出，即使 `$val={}`；只有未 clear 的空物件可省略。符合 `inst-posix.md:108`、`:155`。

3. **E-3｜已解。** `agent.md:62`、`:69`；`aos-llm-call.md:86`。頂層與 `llm` 限字面物件，LLM loader 只解驗六欄，兩端共用依賴須同值；不再因獨立的 `tick.pool`／`tool_pool` 環境變數缺失而失敗。

4. **E-4｜已解。** `aos-agent.md:253`、`:254`、`:255`、`:287`。拒絕 `done_exit=1／101`，允許 0，明訂 `bad_after=0` 不退件，符合 `kernel.md:107`、`:108`。檢查本身另引入 C-2 的可用性缺口。

5. **E-5｜已解。** `agent.md:51`、`:52`、`:91` 限定 system／history 為單一檔案；`aos-agent.md:203` 明訂同檔整份原子重寫，沒有多檔寫回歧義。

## B. 驗收 D、B、C 各項

1. **D-1｜已解：** history 單檔與寫回目的地固定。`agent.md:52`、`:91`。
2. **D-2｜已解：** 工具結構、非空 name、選填欄位及 `_timeout_ms` 型別均寫明，工具檔錯誤統一 `ToolInvalid`。`agent.md:134`、`:135`。
3. **D-3｜已解：** llm config 身分缺漏／錯形與版本不支援已分列。`aos-llm-call.md:72`。
4. **D-4｜已解：** 先刪空 `tool_calls`，再補 null content，順序固定。`aos-llm-call.md:110`。
5. **D-5｜已解：** 明訂只查長度、尾巴與 call id，前綴等長改寫保留。`aos-agent.md:206`、`:209`。
6. **D-6｜已解：** 既有 tick 的字面 `AOS_K` 不同即 `KernelMismatch`，拒絕並提示重建。`aos-agent.md:257`。
7. **D-7｜已解：** start／stop 使用可定位的 request 名；逾時印回音路徑、不撤回，由人讀取及 ack。`aos-agent.md:278`。
8. **D-8｜已解：** 最小流程與未提供的日常 CLI 已分清。`agent.md:237`；`aos-agent.md:311`。
9. **B-6｜已解：** 同池單 CPU 不自等；退出碼相容性已有檢查。`aos-agent.md:108`、`:158`、`:254`。
10. **B-7｜已解：** 記憶不變保證限當前未取消 think，Removed 殘留工作的例外已明列。`aos-agent.md:305`。
11. **B-8｜已解：** 六欄 loader 排除無關環境依賴。`aos-llm-call.md:86`。
12. **C-1｜已解：** 空環境 clear 不再省略。`aos-agent.md:130`。
13. **C-2｜已解：** 不再把 done_exit 固定為 100，且補上 bad_after=0。`aos-agent.md:254`、`:287`。
14. **C-3｜已解：** system／history 不接受資料夾。`agent.md:51`。

下層新 CLI 無引用衝突：`aos-agent.md:279` 提示手動放 ack 仍合法，新增的 `aos-kernel ack K NAME` 只是更方便的出口（`kernel.md:359`）；`:303` 用 ls 觀察行程消失，也符合新版文字摘要。沒有把 `init --cpu`、`ls --json` 或 `aos-daemon stop` 寫成不相容用法。

## C. 新洞與新增機制核對

1. **要修｜封存檔是恢復憑據，人工清理邊界未限定。**

   `agent.md:175` 說封存檔由人清，`:221` 卻以 dst 是否存在判斷本次消費是否完成。

   反例：consume A → rename 到 dst → 清 `consuming` 前崩 → 人清 dst，再投同名 B → 恢復依 `aos-agent.md:48` 搬 B，將 B 當成舊消費完成。intake 已寫記憶後也有同類問題：通常卡 `HistoryChanged`；B 若與 A 內容相同，還可能被誤認為已接回而消失。

   須明訂被 `intake`／`consuming` 引用的 dst 不可清；解除引用後才能清。`aos-agent.md:226` 允許拿走壞 dst 的修復流程，也須同步取消對應配對，不能只刪檔後讓恢復重新抓 src。

2. **要修｜start 整份解析 K/info，新增無關的呼叫端環境依賴。**

   `aos-agent.md:253` 要照 kernel 規範解析 K/info；`kernel.md:110` 是整份解析。

   合法反例：`cpus.w.pool={"$env":"WORK_POOL"}`，kernel cpu 有 `WORK_POOL=default`，呼叫 start 的 shell 沒有。既有 K 正常，start 卻在查 done_exit 時因缺變數拒絕登記（`kernel.md:102`；`directives.md:55`）。

   應只解驗相容檢查需要的欄位，保留原文件供 `$ref` 定位；或明訂 start 端也須具備整份 K/info 的解析依賴。這不是原退出碼衝突未解，而是新增的可用性限制。

3. **要修｜「讀驗錯什麼都不寫」與先搬再驗直接矛盾。**

   `aos-agent.md:295` 仍承諾讀驗錯不寫任何東西；但 `:224` 先寫 intake，`:225` rename，`:226` 才讀驗輸入，壞檔會在已變更磁碟後退 1。

   應將無寫入承諾限定於 §2 第一步的起始讀驗；後段讀驗失敗保留恢復紀錄。這也是第 1 輪 R-6 要求的界線。

4. **未發現新增阻擋｜其餘新增機制。**

   `aa-` 避開管理前綴，`KernelMismatch` 的字串相等判準明確（`aos-agent.md:257`、`:278`）。六欄 loader 與兩端 `$env` 同值契約可成立（`agent.md:69`；`aos-llm-call.md:86`）；實作挑欄位時仍須保留原 JSON 的文件與位置，不能切成小物件後破壞 `$ref:""`／相對 `$at`（`directives.md:141`、`:151`）。

## D. 定稿判定

**整組：不能。** 分檔判定：`agent.md` 不能；`aos-agent.md` 不能；`aos-llm-call.md` 本輪可定稿。

定稿前必改：

1. **封存憑據生命週期：** 禁止清理仍被 state 引用的 dst，補齊壞輸入放棄時的配對處理。`agent.md:175`、`:221`；`aos-agent.md:226`。
2. **start 的解析範圍：** 移除無關 K/info 環境依賴，或明確列為呼叫前提。`aos-agent.md:253`。
3. **錯誤寫入承諾：** 區分起始讀驗與恢復流程內讀驗，刪除後者「什麼都不寫」的承諾。`aos-agent.md:295`。

可先放：已結清封存檔的自動清理、日常 CLI、取消殘留工作的輸入快照，以及 `.tmp` 殘檔管理；不必因此擴大本輪方向。