# mail 測試與紅燈紀錄

← [ADVANCED](../ADVANCED.md)

## 驗證

在 repo 根跑：

```sh
systemd-run --user --scope -p TasksMax=300 python3 -B proto7-2/tests/run_all.py modules/mail/tests
sh proto7-2/modules/mail/examples/two_nodes.sh
```

35 項測試全綠，範例印 OK，第一次跑整段已在真實檔案系統執行，最後 audit 退出 0。
測試 import base 啟用 SIGKILL 鉤子；既有 10 項保留，新增審查 1–7 各一項與人類介面一項。
新增分鐘信名／歸檔避撞與模板 ROSTER 段內追加兩項；另確認讀信及終局回信後、原信歸檔前皆不 ack。
涵蓋 160 封固定同分鐘並行投遞、辦結中斷與 handler 一次、連續 must ack，以及輸出 flush 前／後中斷、flush／讀檔失敗、真的 retention gap、並行送／辦／audit。

前輪七項退化驗證各只跑對應 `test_review<N>_`，全部退出 1，還原後清除 `__pycache__` 再跑全套全綠：

| 審查 | 拿掉的修法 | 對應測試／紅燈訊息 |
|---|---|---|
| 1 | 移除 done 檔名避撞，歸檔退回 rename | `test_review1_archive_never_overwrites`：`投遞必須避開 done 檔名`（兩封檔名相等） |
| 2 | seen／orders 提交搬到輸出前 | `test_review2_seen_only_after_flush`：`True is not false : flush 前不得保存 .seen` |
| 3 | 舊版退化：只信本地 `.acked` 且不處理 retention（現在從本地起步並跳過 retention） | `test_review3_ack_reconciles_after_retention`：`2 != 4 : 本地落後與舊段淘汰不得卡住後續 ack` |
| 4 | 歸檔與 audit 移除共用 delivery 鎖 | `test_review4_archive_and_scan_share_delivery_lock`：`BlockingIOError not raised : 歸檔必須持 delivery 鎖` |
| 5 | 移除日誌前完整回信驗證 | `test_review5_invalid_title_cannot_poison_journal`：`True is not false : 非法回信不得建立日誌` |
| 6 | frontmatter 退回 `split('---', 2)` | `test_review6_three_hyphen_names_parse`：`KeyError: 'id'` |
| 7 | 移除 done／handle／read 個人名驗證 | `test_review7_only_people_can_read_done_handle`：`0 != 2`（團隊 done 誤成功） |

另單獨退化歸檔防覆蓋（保留投遞避撞），審查 1 同測試紅：`歸檔不可覆蓋舊信`；只移除 audit 的 delivery 鎖，審查 4 同測試紅：`BlockingIOError not raised : audit 必須在 delivery 鎖下列檔讀信`。

原始防撞／日誌也重新退化實跑：直接 rename 投遞令 `test_parallel_delivery` 紅：`8 != 160 : 160 封同秒投遞不可被覆蓋`；省略日誌令 `test_handle_crash_side_effect_once` 紅：`'2' != '1'`。前輪審查完整輸出在 `/tmp/x1/red1.txt`～`red7.txt`，額外證據在同處 `red-1-archive-only.txt`、`red-4-audit-only.txt`、`red-delivery-link.txt`、`red-journal.txt`。

第二輪新增 6 項：序號綁快照（同分鐘插入／已辦冪等／quiet 快照）、序號 journal 中斷重跑、flush 前不改快照、ROSTER replace 前 SIGKILL、team publish 前 SIGKILL／重試／冪等、團隊 REQUEST 先拒絕。每條拿掉修法實跑退出 1，還原後再驗證全綠：

| 條目 | 拿掉的修法 | 紅燈證據 |
|---|---|---|
| 1 插入 | 保留快照檢查，但改依即時未辦信排序選信 | `test_round2_numbers_bind_snapshot`：`False is not true : 序號不得辦掉後插入的信` |
| 1 journal | 同上，排除已 journal 信再選序號 | `test_round2_numbers_resume_journal`：`False is not true : 重跑序號必須復原原 journal 的信` |
| 2 | replace 前先 truncate／寫入原檔 | `test_round2_roster_atomic_replace`：`replace 前被殺原 ROSTER 必須不變` |
| 3 | 改在公開 teams 目錄直接準備 | `test_round2_team_atomic_publish`：`('dev', 'lead') is not None : 中斷時 team_of 不得看到半份名冊` |
| 4 | 移除團隊 REQUEST 拒絕 | `test_round2_team_request_rejected_first`：`0 != 2` |

第二輪完整紅燈輸出：`/tmp/x1/round2/{numbers-insert,numbers-journal,roster,team,request}.txt`。

本輪新增真 wfnode 雙 node 整合與雜檔過濾兩項：init alice／bob 後在模板「現役成員」段追加身份格，其餘內容逐字保留；REQUEST → read／done → 終局回信，`.gitkeep` 不列信。找不到 `AOS7_WF_HOME`（預設 `~/repo/workflows`）的 `tools/wf-init.sh` 時整合測試 skipTest。本機實跑未 skip，alice／bob 的 `aos7-wfnode check` 退出碼都是寄信前 0、收辦回信後 0。清除 mail 的 `__pycache__` 後再跑指定指令，兩輪都是 28 項全過；`aos7_mail.py` 357 行。

10-09 回改（新手試用不過）：加 `--help`（不需 root）、send 省略 STATUS 預設 REQUEST、done 只給一句話預設 DONE、錯誤訊息改白話並附例子；README 只留日常三指令（send／read／done），audit 與其餘移來本檔。新增 `test_newbie_help_and_defaults`，共 29 項。

## 現行測試分檔

`_mailcase.py` 共用 setUp／CLI；`test_mail_deliver_1/2.py` 為投遞、復原、團隊與整合測試；`test_mail_review_1/2/3.py` 為前輪審查、人類介面與快照原子性；`test_mail_errors_effects.py` 為本輪 6 項（四類需求加缺口／錯誤保護）。既有 29 個測試名稱保留，另加 6 個，共 35 項。patch 投遞用 aos7_mail，辦結／輪詢用 aos7_mail_box，ack 內部用 aos7_mail_ack。

10-09 ER-mail（副作用與錯誤路徑）每條拿掉修法用 `python3 -B` 實跑 `-k <測試>` 都退出 1，還原後全套 35 項綠：

| 拿掉什麼 | 紅的測試：訊息 |
|---|---|
| send 不看 events/ 一律 publish | `test_request_events_opt_in`：無 events 的對象被建了 events/ |
| poll 加回 audit | `test_read_only_own_lock`：別人持 delivery 鎖時 read 逾時 |
| ack 起點加回 `event_ack(events, 0)` | `test_ack_one_call_and_idle_zero`：`2 != 1` |
| ack 遇 errors 不停 | `test_ack_stops_at_unproven_gap_or_error`：event_ack 被呼叫 1 次 |
| OSError 退回 2 | `test_error_oserror_unknown`：`2 != 3` |
| 用法錯誤去掉前綴與第二句 | `test_error_usage_format_and_help`：四個 subTest 紅 |
| 撞名／被拒（`Refused`）退回 2 | `test_team_orders_quiet`、`test_round2_team_atomic_publish`：`2 != 1` |
