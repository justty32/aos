← [本輪報告](README.md)

# astra 唯讀審查任務書：one-boot（開機合一、家不合一＋kernel 帳本換 sqlite）

你是唯讀審查者。repo 在目前目錄（git worktree）。不要改任何檔、不要跑會用到模型的東西（不准碰 LM Studio、localhost:1234、ollama）。可以跑單元測試：`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p 'test_one_boot.py'`。

## 這次改了什麼

使用者 2026-09-24 拍板：daemon 與 kernel「開機合一、家不合一」，kernel 帳本換 sqlite。
- 計畫：`proto5/notes/2026-09-24-one-boot/plan.md`。改動：`git diff c56044d..HEAD -- proto5 wf`（c56044d 是 P 隊開工時的 main；測試檔還在另兩組手上遷移中，未提交的測試改動不用看）。
- 程式：新檔 `proto5/lib/aos_kernel_store.py`（sqlite 帳本）、`aos_daemon_ticks.py`（daemon 替 kernel 開 tick）、`aos_up.py`＋`cli/aos`（aos up／down）；改 `aos_kernel_engine.py`、`aos_kernel_ledger.py`、`aos_kernel_boot.py`、`aos_kernel_info.py`、`aos_kernel_health.py`、`aos_kernel_ls.py`、`aos_kernel_cli.py`、`aos_kernel_check.py`、`aos_kernel_cpu.py`、`aos_kernel_rows.py`、`aos_daemon_loop.py`、`aos_daemon_rpc.py`、`aos_daemon.py`、`aos_daemon_cli.py`、`aos_agent*.py`（改用 store 查帳本）、`aos_team_post.py`（兩行）。
- 規範：`proto5/spec/kernel/`、`proto5/spec/daemon/`（新 `ticks.md`、`up.md`）、`proto5/spec/cpu/`、`proto5/spec/aos-agent/` 相關句子。
- 測試：`proto5/lib/test/test_one_boot.py`（新）與遷移過的舊測試。

## 請重點看

1. **同時只准一格**：daemon 同一 K 只開一格＋`K/.tick.lock`。有沒有路徑讓兩格同時改帳本（boot 與 tick、人手跑 tick、daemon 重開、兩個 daemon 登記同一 K）？鎖在 kill -9 後會不會卡住？
2. **sqlite 交易**：`Store.save` 只寫有變的列、一筆交易。比對用的 `orig` 會不會跟實際 DB 不同步（例如交易失敗後、boot 匯入時、`write()`）？`busy` 的 `ord` 保序邏輯對嗎？`on` 從 busy 反推會不會跟以前的語意不同？讀的人（ls、proc、agent）在 WAL 下會不會讀到半筆？
3. **提交點**：以前的提交點 1（先放下一格再記 last_seq）拿掉後，seq 可能重用（被砍的格沒存到提交點）。檔名（派工單、ack、scale 單）會不會撞到而造成錯誤？「先記後放」「先記後出貨」還成立嗎？
4. **daemon 開 tick**：何時開（時間到／`K/requests/` 有新檔的 mtime＋列名判斷）會不會漏觸發或空轉？退 75、失敗退避、逾時 KILL、停機時的收法、`waitpid(-1)` 跟 Popen 共處、daemon 被 kill -9 後孤兒 tick。daemon 有沒有讀 K 家任何檔的內容（不該讀）？
5. **boot**：拿鎖、舊 state.json 匯入（改名 `.v2-old`）、舊 kernel 池縮 0、寫帳本、向 daemon 登記。崩在各步之間能不能再 boot 救回？
6. **停機**：停好那格送 `tick off` 撤登記；`aos down` 的順序與「daemon 沒別人要用才停」。
7. **停車喚醒（K2）與 T2 申請**有沒有被弄壞（`wake` 單、102、park_ms、routine／驗收申請）。
8. **agent 相容檢查**：`aos-agent start` 對舊 state.json、沒 park 的帳本、沒 boot 的 K 的處理。
9. **規範與程式一致**：兩條前提的改寫、`ls --json` 第 3 版的欄位表、`aos-kernel proc --json` 形狀、health 判定順序。

## 回報格式

用中文。分兩節：**必修**（會壞帳、會卡死、會兩格同時跑、跟規範矛盾的）與**建議**。每條：檔:行、問題一句、為什麼、建議怎麼改。沒問題的面向也各寫一句「看過、沒問題」。
