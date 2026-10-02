# 文件結構與殘留 審查（astra，2026-10-02）

## 一段話結論

**spec 已宣告唯一事實，但入口、plan、操作說明還沒同步收乾淨。** 從不同入口進來，仍會讀到互相矛盾的「現況」。封存批次有標明歷史，主要漏在上層索引。非封存文件的連結與錨點掃描沒有發現壞連結。

## 必修

1. **現行入口仍把舊架構當正本。**  
   [proto6/README.md:5](/home/guanyu/projs/aos/proto6/README.md:5) 還寫四件核心、系統級任務與舊通道；第 11 行又稱現行程式在 proto5。[notes/README.md:17](/home/guanyu/projs/aos/proto6/notes/README.md:17) 仍把舊 kernel／LLM 設計列成現行方向。[wf 的 spec 入口:7](/home/guanyu/projs/aos/wf/workflows/spec/README.md:7) 也仍要求新實作照舊規格寫。這些與 [現行 spec:7](/home/guanyu/projs/aos/proto6/spec/README.md:7) 不符。  
   **改法：** 現行入口統一指向 proto6/spec、src/py；舊文件明標適用世代，不再稱現行。

2. **plan 還會引導人照過時內容實作。**  
   [六段總覽:9](/home/guanyu/projs/aos/proto6/plan/readme/01-六段總覽-一至三段.md:9) 說互斥不做，第 11 行叫人找 `tick/current.json`；但 [現行 tick:15](/home/guanyu/projs/aos/proto6/spec/tick.md:15) 已有鎖，第 31 行已改成 `tick/current/record.json`。[plan 入口:19](/home/guanyu/projs/aos/proto6/plan/README.md:19) 還把已擱置的第二段寫成「等使用者裁定」。  
   **改法：** 入口只列已完成、暫緩、未完成；已完成細節標歷史，不再當驗收正本。

3. **roadmap 與進度表還派發已完成的工作。**  
   [roadmap:11](/home/guanyu/projs/aos/wf/workflows/roadmap.md:11) 與 [SESSION-LOG:22](/home/guanyu/projs/aos/wf/SESSION-LOG.md:22) 都說下一件是更新 plan 的分工；但 [plan:7](/home/guanyu/projs/aos/proto6/plan/README.md:7) 已更新。SESSION-LOG 第 20 行也混留已撤回的 mq 介面與大量完成紀錄。  
   **改法：** 移除完成項，只保留真正 open 的一行狀態與連結。

4. **指示詞展開規則仍有互相矛盾的版本。**  
   [spec/tick.md:22](/home/guanyu/projs/aos/proto6/spec/tick.md:22) 說先合併再展開；[操作說明:59](/home/guanyu/projs/aos/proto6/src/py/docs/tick.md:59) 說只展開到 tasks 層。實際是開格先展開，跑到該項才合併，見 [讀表程式:106](/home/guanyu/projs/aos/proto6/src/py/lib/aos_tick_table.py:106) 與 [load_inst:236](/home/guanyu/projs/aos/proto6/src/py/lib/aos_tick_table.py:236)。  
   [conventions:65](/home/guanyu/projs/aos/proto6/spec/conventions.md:65) 又把 daemon、tick 的例外混寫；daemon 會遍歷所有一般物件鍵，tick 每項則只展開已知鍵。  
   **改法：** 移除重複行為敘述，指向各自程式與測試；若保留摘要，分開描述。

5. **Python 操作說明仍有失效的功能清單。**  
   [tick 說明:34](/home/guanyu/projs/aos/proto6/src/py/docs/tick.md:34) 說目前沒有模組；[daemon 說明:37](/home/guanyu/projs/aos/proto6/src/py/docs/daemon.md:37) 說只有 control。實際已有 tasks-blocked，以及 [六個 daemon 模組:31](/home/guanyu/projs/aos/proto6/spec/terms.md:31)。daemon 說明第 60 行還稱完整收齊輸出，實際 [drain:44](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_output.py:44) 只保留上限內的尾端資料。  
   **改法：** 刪掉舊句，直接連到現行模組與輸出說明。

6. **名詞篇仍描述舊的 daemon 存檔方式。**  
   [terms.md:39](/home/guanyu/projs/aos/proto6/spec/terms.md:39) 寫「停機存 state.json」；[state.md:9](/home/guanyu/projs/aos/proto6/spec/daemon/state.md:9) 則明定由設定指定檔案，只存暫停／已停，狀態一變就寫。  
   **改法：** 拿掉名詞篇括號內的行為細節，連到 state 模組。

7. **最小操作範例照抄會找不到執行檔。**  
   [tick 說明:15](/home/guanyu/projs/aos/proto6/src/py/docs/tick.md:15) 先切到 `/tmp/n`，再呼叫相對路徑 `proto6/src/py/bin/aos-tick`；下一行也受影響。  
   **改法：** 使用執行檔絕對路徑，或先設定 PATH。

## 建議

- **補上封存索引。** [archive/README.md:7](/home/guanyu/projs/aos/proto6/notes/archive/README.md:7) 的表漏掉整批 `spec-2026-10-02/`。補一列即可。該批自己的入口已標明歷史，不必修內部舊連結。
- **先刪過時內容，再考慮拆大檔。** 排除封存等目錄後，proto6 有 **15 份** Markdown 超過 8 KiB，wf 有 **44 份**，其中 workflows 占 **29 份**。優先處理 [SESSION-LOG:15](/home/guanyu/projs/aos/wf/SESSION-LOG.md:15)（10,141 bytes）與 [tick 操作說明:19](/home/guanyu/projs/aos/proto6/src/py/docs/tick.md:19)（17,525 bytes）：兩者都有大量已完成或已撤回內容。依 [STRUCTURE:34](/home/guanyu/projs/aos/wf/STRUCTURE.md:34)，超標只是檢視訊號，不必為數字硬拆連貫內容。

## 疑問

無需新增方向題。以上可依「程式即 spec、歷史退出現行入口」處理。

## 看過的範圍

- proto6：入口、spec 原則、plan、notes 與封存入口、Python README／docs、舊 proto 操作入口；抽查相關程式與測試作對照。
- wf：三軸、WORKFLOWS、INDEX、roadmap、舊 spec 入口、code map、結構規則與 lint 邏輯。
- 靜態掃描 **730 份非封存 Markdown**：失效路徑 **0**、失效錨點 **0**。封存內部連結依規則不列缺失。
- 全程唯讀；未改檔、未 commit、未跑測試。