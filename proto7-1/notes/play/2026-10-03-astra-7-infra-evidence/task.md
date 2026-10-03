# 任務：proto7-1 第七輪基礎設施回歸（回歸＋可靠性測試）

（說明：這是 repo 擁有者委託的軟體品質工作——對自己寫的本機排程原型做回歸測試與故障注入，找出 bug，產出是一份測試報告。不涉及任何外部系統。）

你在 proto7-1 的一份副本裡（目前目錄），可以隨意跑、改這份副本、寫腳本。**不要碰副本以外的路徑**（/tmp 可以用，但跑完要清掉你建的 /tmp 資料夾與程序；收程序用 PID，不要用 `pkill -f`）。不要呼叫任何 LLM；嚴禁 LM Studio、ollama、`lms`。繁體中文（台灣用語）寫報告。

## 背景
proto7-1 照 `proto7/spec/core.md` 試做 daemon → tick/tock → kernel → agent；使用者關注 daemon/tick 基礎設施。細部規格 `proto7-1/spec.md`，需求清單 `proto7-1/notes/infra-needs.md`。

你上一輪報告：`proto7-1/notes/play/2026-10-03-astra-6-infra.md`（證據在同名 `-evidence/`）。之後 commit `94ad4168`、`5a3d97fb` 宣稱修好 G-01～G-10（測試 `proto7-1/tests/test_astra6.py`）。修法摘要：G-01 daemon 控制檔逐件邊界、失敗搬 `.aosd/ctl-failed/`；G-02 tick 起任務前確認 node 仍是抓著的 fd，否則寫 exit 127，aos7-run 改收 taskdir fd（命令列第二參數）；G-03 daemon 的 `.aosd` 經 root fd 讀寫，root 被搬走就當消失、stop＋kill；G-04 子根 daemon.lock 已被持有就不起、不改 owner（記 tasks_error），仍有啟動前幾十 ms 的窗口；G-05 reload 先完整驗證；G-06 被宣告接管的掛載不再標 dyn；G-07 `_proc` atexit 沿用 group/grace；G-08 jsonl 半行先補換行、tock 讀回確認後才寫 ended；G-09 文件寫明合作式協定；G-10 身分不可驗時不殺、記原因。另有新探針 `probes/namespace`、`probes/ledger`。

## 要做
1. **回歸**：G-01～G-10 逐條用你上一輪的重現判定已修／部分／未修，附證據；順帶看 F-05、F-09、F-11 的部分項。
2. **測新改動的邊界**（可靠性與故障注入）：root fd 檢查（root 是 symlink、bind mount、root 被 chmod、root 在 daemon 啟動後才變成 symlink、正常的 rename 回原位）、aos7-run 的新 fd 參數（舊式單參數呼叫、fd 無效、fd 指到別處）、ctl-failed 的累積與命名衝突、G-04 窗口、G-08 tock 讀回確認失敗時的行為、jsonl 修復對其他 jsonl（log.jsonl、writes.jsonl、decisions.jsonl、sent.jsonl）的影響。
3. **長跑**：一個 daemon、20 條時間線、混合 keep／each／spawn／restart／reload／加掛／子 daemon，跑至少 10 分鐘（或你判斷足夠的時間），每分鐘取樣：回合數、程序數、fd 數、檔案數與磁碟用量、log 大小、ctl-done 數。看有沒有洩漏或無界成長（記成新問題）。
4. **找新問題**：編號 H-01 起，分〔bug〕〔技術選型〕〔要使用者決定〕（最後一類要少而精）。

## 產出
- `proto7-1/notes/play/2026-10-03-astra-7-infra.md`：開頭摘要；回歸表；長跑數據表；H- 新問題（重現、看到、需要、對應 S-／N-）；對 infra-needs 的建議。
- 證據 `proto7-1/notes/play/2026-10-03-astra-7-infra-evidence/`（腳本＋精簡 JSON，不放大檔）。
- 只寫這兩處，不改程式或其他文件。結束前確認沒有你的殘留程序與 /tmp 資料夾。
