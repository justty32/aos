# 任務：proto7-1 第八輪基礎設施回歸（回歸＋可靠性測試）

（說明：這是 repo 擁有者委託的軟體品質工作——對自己寫的本機排程原型做回歸測試與故障注入，找出 bug，產出是一份測試報告。不涉及任何外部系統。）

你在 proto7-1 的一份副本裡（目前目錄），可以隨意跑、改這份副本、寫腳本。**不要碰副本以外的路徑**（/tmp 可以用，但跑完要清掉你建的 /tmp 資料夾與程序；收程序用 PID，不要用 `pkill -f`；列資料夾用 `/bin/ls` 或 python，不要用 `ls`）。不要呼叫任何 LLM；嚴禁 LM Studio、ollama、`lms`。繁體中文（台灣用語）寫報告。

## 背景
proto7-1 照 `proto7/spec/core.md` 試做 daemon → tick/tock → kernel → agent；使用者關注 daemon/tick 基礎設施。細部規格 `proto7-1/spec.md`，需求清單 `proto7-1/notes/infra-needs.md`。

你上一輪報告：`proto7-1/notes/play/2026-10-03-astra-7-infra.md`（證據在同名 `-evidence/`）。之後 commit `b3bd7f44` 宣稱修好 H-01～H-09（測試 `proto7-1/tests/test_astra7.py`）。摘要：H-01 tock 後回合仍 open 就補 tock，補不上停在 error 退避、不開新回合；H-02 tick 不寫 owner.json，改用 `AOS7_OWNER_*` 環境變數，子 daemon 拿到鎖才寫；H-03 audit hook 先補半行；H-04 read_jsonl 以 bytes 逐行解碼；H-05 Popen 前與 aos7-run 起任務前都比對 node 與 fd 一致；H-06 out.log 開不了寫 exit 127，tick 寫 runner.json（pid＋starttime）擴大 lost 判定；H-07 ctl-failed 排他命名；H-08 可選 `keep_old_rounds`、`.aosd/retention.json`、status 的 `disk`；H-09 aos7-run 無效 fd 退出碼 2。

## 要做
1. **回歸**：H-01～H-09 逐條用上一輪的重現判定已修／部分／未修，附證據；也重看上一輪仍「部分」的 G-01、G-02、G-04、G-08。
2. **測新改動的邊界**（可靠性與故障注入）：H-01 的 error 退避（持續失敗時控制檔 pause／stop 是否仍有效、status 是否看得懂）、H-02 的環境變數交接（子 daemon 被人手直接起、`AOS7_OWNER_*` 被任務改、巢狀三層、子 daemon 重開）、H-06 runner.json 與 lost 判定（runner 被 SIGKILL 的各時間點、pid 重用）、H-08 保留設定（設成 0、負數、非整數、log 輪替與讀 log 的人同時進行、`disk` 的計算成本）。
3. **整體健康檢查**：從頭用一個「新使用者」的角度，只看 `proto7-1/README.md`、`spec.md`、`probes/llm_card.md`，判斷文件與實作是否一致；挑 10 個文件宣稱的行為實測，列出不一致處。
4. **找新問題**：編號 K-01 起，分〔bug〕〔技術選型〕〔要使用者決定〕（最後一類要少而精）。另外請給一段「**這一層離穩定還差什麼**」的總評：剩下的問題是邊角還是結構性的，還值不值得繼續這種回歸。

## 產出
- `proto7-1/notes/play/2026-10-03-astra-8-infra.md`：開頭摘要；回歸表；文件一致性表；K- 新問題；總評；對 infra-needs 的建議。
- 證據 `proto7-1/notes/play/2026-10-03-astra-8-infra-evidence/`（腳本＋精簡 JSON，不放大檔）。
- 只寫這兩處，不改程式或其他文件。結束前確認沒有你的殘留程序與 /tmp 資料夾。
