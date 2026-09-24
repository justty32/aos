← [工具大開發時代](README.md)

# 審查任務書：隊 2 郵差「五題裁決」追加（唯讀）

你是唯讀審查者。**不要改任何檔、不要跑模型、不要開 daemon／kernel、不要碰 LM Studio／ollama。** 可以讀檔、跑單元測試（`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p 'test_team_*.py'`；`test_team_post_live.py` 開真 daemon，可略過）。繁體中文、白話。

**只審這次的改動**：`git diff c56044d HEAD -- proto5`（兩個 commit）。第一輪審查見 [review-post-astra.md](review-post-astra.md)，那些已修，不用重提。

## 使用者的五題裁決（要照這個做）

1. 郵差巡信箱間隔可設定：`team.json` 的 `post.interval_s`，預設 5 秒。
2. 心跳用自己的身分 `beat` 派工，不再用人類名義；信上看得出是定時器派的；名冊與 `routes.json` 要認得它。
3. 一次性例行的欄位叫 `once`（catalog 跟程式一致）。
4. 檢查器本身壞掉（跑不起來、環境缺東西、done_when 寫錯）≠ 隊員沒過：不扣隊員次數，寄信給人說檢查器壞了，任務停在那等人修。「沒過」與「檢查器壞」是兩種結果。
5. 例行做完不再每次寄 DONE 給人，只寄失敗、逾時、檢查器壞這類異常。

## 請回答

1. 五題每一題有沒有做到、有沒有漏的路徑（例：`beat` 寄的信／申請在 `read_outbox_file`、`may_send`、`on_handoff`、`_notify`、`render_handoff`、BLOCKED 時 `waiting_on`、郵差投遞、`team_say` 各處是否一致；`beat` 能不能被濫用——成員冒充 beat、beat 替人答題、routes 派給 beat）。
2. 「不過」與「檢查器壞」的分類（`aos_team_verify.py` 的 `NotMet`／`CheckError`）合不合理；`broken` 結果在郵差那邊（`collect_job`、`checker_broken`、`check_result`）會不會卡住、重寄、或漏掉；`aos-team verify --again`／`reverify` 申請的冪等與權限；檢查器壞時單子停在 verifying，看停滯、期限會不會誤動它。
3. 例行只報異常：有沒有該報沒報的（例：驗收三次沒過、負責人 FAILED、逾時、重派用完、檢查器壞、BLOCKED 等人）或反過來仍在吵人的。
4. `post.interval_s`：驗證、預設、`start` 讀名冊、改了要重啟這件事的說法。
5. 改到隊 1 的共用檔（`aos_team_format.py`、`aos_team_task.py`、`spec/team/layout.md`、`roster.md`、`examples/routes.json`）有沒有破壞原本的契約或別隊的用法。
6. 規範（`spec/team/post.md`、`verify.md`、`beat.md`）跟程式對不對得上。

## 格式

**必修**（不改會做錯、違反裁決、或可被濫用的；每條：檔、函式、怎麼觸發、建議改法；M1、M2…）、**建議**（S1…）、**確認沒問題的**（簡短）。
