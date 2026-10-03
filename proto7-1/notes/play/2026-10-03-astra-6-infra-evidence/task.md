# 任務：proto7-1 第六輪基礎設施試玩（回歸＋可靠性測試）

（說明：這是 repo 擁有者委託的軟體品質工作——對自己寫的本機排程原型做回歸測試與故障注入，找出 bug，產出是一份測試報告。不涉及任何外部系統。）

你在 proto7-1 的一份副本裡（目前目錄），可以隨意跑、改這份副本、寫腳本。**不要碰副本以外的路徑**（/tmp 可以用，但跑完要清掉你建的 /tmp 資料夾與程序；殺程序用 PID，不要用 `pkill -f`）。不要呼叫任何 LLM；嚴禁 LM Studio、ollama、`lms`。繁體中文（台灣用語）寫報告。

## 背景
proto7-1 是照 `proto7/spec/core.md` 做的試做：daemon → tick/tock → kernel → agent。使用者把 kernel/agent 當探針，**關注的是 daemon/tick 這層基礎設施**。細部規格 `proto7-1/spec.md`，需求清單 `proto7-1/notes/infra-needs.md`。

你上一輪（第五輪）的報告：`proto7-1/notes/play/2026-10-03-astra-5-infra.md`，證據與重現腳本在 `proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/`。之後：
- commit `ddda65a9` 宣稱修好 F-01～F-11 與新增 N-55（測試 `proto7-1/tests/test_astra5.py`、`tests/_proc.py`）。修法摘要：F-01 stop 時最後掃一次 /proc 收 AOS7_NODE 屬本 daemon 的程序；F-02 `aos7_fs.task_read` 搬走後重定位、找不到算 unknown；F-03 只有 ENOENT/ENOTDIR 算消失，其他 OSError 記 scan-error；F-04 `.aos/action.owner.json`，舊世代且 starttime 相符才 SIGKILL；F-05 tock 已有同回合總結就只補收尾、標 replayed，timeout 殺 tock 後 daemon 立刻再 tock；F-06 逐項錯誤邊界、interval 先範圍檢查；F-07 先寫回條再刪請求；F-08 掃描跳過祖先 tasks.json／spawn 宣告的 subroot；F-09 tick/tock 用 node 目錄 fd（/proc/self/fd/N）讀寫；F-10 主迴圈每圈最多 200 件或 50 ms 控制檔；F-11 測試先收程序再刪空間。
- 使用者裁定 Q5、Q6（commit `6261a304`）：子 daemon 歸起它的 node，`allow_stop` 欄位、`<subroot>/.aosd/owner.json`、允許時 stop 寫 `stopped.json`、父 tick 見到就不起；restart 加 `"reload": true` 照 tasks.json 同名項目重起，找不到整個不執行。見 spec.md 第 2、4、6 節。

## 要做
1. **回歸**：F-01～F-11 逐條用你上一輪的重現（必要時調整掛鉤點，例如 F-09 改走 fd 後舊掛鉤不觸發）判定：已修／部分／未修，附證據。也看第五輪回歸表裡「部分」的 I-01、I-03、I-04、I-06、I-11 現況。
2. **測新功能的邊界情況**（這是我們自己系統的可靠性與故障注入測試）：Q5（owner.json 被任務自己改、owner.json 壞掉、子 daemon 自己刪 stopped.json、父 node 搬家、多層巢狀所有權、`allow_stop` 型別錯）、Q6（reload 與 spawn、keep、max_live、mounts_dyn、連續 reload、tasks.json 同名多項）、F-04 owner 檔（pid 重用、starttime 讀不到）、F-09 fd 讀寫（node 換成 symlink、跨檔系統 rename、fd 數量）、F-10 預算（預算內 stop 是否仍及時）、F-01 stop-sweep（會不會收到不屬於本 daemon 的程序？巢狀子 daemon 的程序？）。
3. **找新問題**：任何 daemon/tick 層的 bug 或缺口，編號 G-01 起，分〔bug〕〔技術選型〕〔要使用者決定〕（最後一類要少而精，只有真的方向問題才列）。

## 產出
- `proto7-1/notes/play/2026-10-03-astra-6-infra.md`：開頭摘要；第一節回歸表；第二節 G- 新問題（重現、看到、需要、對應 S-／N-）；第三節對 infra-needs 的建議（哪些 N- 狀態該改）。
- 證據放 `proto7-1/notes/play/2026-10-03-astra-6-infra-evidence/`（腳本＋精簡結果 JSON，不要放大檔）。
- 只寫這兩處，不要改程式或其他文件。
- 結束前確認：沒有殘留程序（`pgrep -af aos7-`）、你建的 /tmp 資料夾已清。
