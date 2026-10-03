# 單項故障隔離補驗

`python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/robustness/probe.py`，三案都用原版 tick/tock CLI。部分 task metadata 是 fixture，無需常駐任務便可確認會阻斷後面的 `/bin/true` 工作。每案三輪；有 subreaper 只供探針清理，finally 清除自己 root 的程序與空間。

| 案例 | 觀察 | 證據 |
|---|---|---|
| tasks 第一項 `name:123`、第二項 healthy | tick 三次 rc1、tock 三次 rc0；healthy 從未出生，錯誤是 `new_tid` 的 re.sub 不收 int | numeric-name.json |
| 一個 ended 任務有未知 op 的 ctl，ctl-done.json 是目錄 | tick/tock 三次都 rc1；正常任務從未出生，總結不寫。`run_all_ctl` 在兩個動作的 per-task 防護之外 | ctl-receipt-dir.json |
| born 任務的 mount-done/x.json 是目錄，提交正常 inbox 加掛 | 請求先刪除、birth.mounts 已更新、symlink 存在；回條寫失敗，首 tick rc1。第二輪起健康任務，但原加掛請求與回條都不存在 | mount-receipt-dir.json |

前兩案是〔bug〕：S-06、S-09、S-11，N-21 不能標全面已做，N-13 也只是部分路徑有結構化錯誤。N-34 毒 batch 的相同 name 型別問題見 controls，不重複計根因。驗證與隔離須含實際 start_task、run_all_ctl、serve_mounts，不只 should_start 與 tock 通知。

加掛案是 N-19 原已承認的缺口新證據〔bug〕，S-01、S-06、S-23：至少一次 spawn 修好不代表加掛具同等可追蹤性。應先保留 pending 身分，生效與回條都有紀錄再 retire 請求；本案**掛載實際已生效**，不能描述成資料或掛載完全丟失。回條失敗也不應拖住健康工作。
