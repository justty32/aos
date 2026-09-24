# astra 唯讀審查任務書：proto5-2 第 1 版實作（2026-09-24）

← [實作總報告](README.md)

你是唯讀審查者。**不要改任何檔**，只讀、只寫回報（回報由 `-o` 收，直接輸出成 Markdown，用繁體中文）。

## 審什麼

proto5-2 = proto5 之上的改版：kernel 與 daemon 改成**以池為單位、宣告式**。規範定稿在 `proto5-2/spec/`（16 檔，先讀 `proto5-2/spec/README.md`），沒寫的照 `proto5/spec/`。
實作在 `proto5-2/lib/`（入口 `proto5-2/cli/`），實作中自選的做法在 `proto5-2/notes/2026-09-24-impl/decisions.md`（Q1～Q9、D-n）。真跑紀錄 `proto5-2/notes/2026-09-24-impl/run.md`。

重點檔：
- daemon：`aos_daemon.py`、`aos_daemon_loop.py`、`aos_daemon_pools.py`、`aos_daemon_rpc.py`、`aos_daemon_cli.py`
- kernel：`aos_kernel_info.py`、`aos_kernel_ledger.py`、`aos_kernel_pools.py`、`aos_kernel_engine.py`、`aos_kernel_boot.py`、`aos_kernel_cpu.py`、`aos_kernel_cli.py`、`aos_kernel_health.py`、`aos_kernel_check.py`
- cpu：`aos_exec_cpu.py`（`notify`）
- 測試：`proto5-2/lib/test/`（`test_daemon*.py`、`test_kernel*.py`、`test_p52_e2e.py`、`_kernel_fake.py`、`_kernel_util.py`）

## 請回答四件事

1. **實作有沒有照 16 檔規範**：逐檔對（kernel-info、kernel-home、kernel-ledger、kernel-tick、kernel-pools、kernel-cli、daemon-home、daemon-reconcile、daemon-cli、protocol、handoff、cpu-notify、choices、scale、proto5-diffs）。不一致的列出：規範哪句、程式哪行、差在哪。decisions.md 已記錄的偏離不算錯，但你覺得選錯了可以說。
2. **kernel↔daemon 協定時序的洞**：scale 單的在途／回音／ack、`decl` 與 Stale、`redeclare`、boot 交接（kernel 池縮 0 再拉 1）、halt 縮池順序、搬池等 summary 消失、池 count 0 後被拿掉又被舊單建回來、daemon 在 stopping 時的 scale、兩邊各自崩在任一步。找會讓兩格 tick 同時跑、工作跑兩次、行程永遠卡 running、池永遠收不掉或拉不回來的時序。
3. **reconcile 退避與收縮的競態**：streak／stable_ms、令牌桶、fd 預算、kill 砍掉重來、縮池 drain（kernel 先等 busy 結清才把號從 T 拿掉）、daemon 批次階梯與收屍（waitpid(-1)）、killing 中的號又被加回宣告、target 換新、failed 的等待。
4. **測試沒蓋到的崩潰窗口**：列出你認為重要但測試裡沒有的窗口（誰、崩在哪一步、會怎樣）。

## 回報格式

- 開頭一段總評。
- 然後一條一條編號（P1、P2…），每條標 **必修**（會造成錯誤結果、卡死、資料不一致、與規範明文衝突）或 **建議**（風格、可讀性、邊角、效能），寫：位置（檔:行）、問題、怎麼重現或推理、建議改法。
- 必修放前面。不要灌水；沒有把握的標「待確認」。
