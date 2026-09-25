# 唯讀審查任務書：tick-gap P2 改動

你是唯讀審查員。repo 是 proto5（Python 原型，在 `proto5/`）。只讀、不改檔、不跑會叫模型或開 daemon 的東西（可以讀檔、git show/diff、grep）。

## 審什麼

`git diff f30ebd7^ fdc93d6 -- proto5/lib ':!proto5/lib/test'` 這批程式改動（先 `git show --stat f30ebd7 fdc93d6` 看清單）。
背景說明在 `proto5/notes/2026-09-24-tick-gap/README.md` §3、§5；規範在 `proto5/spec/kernel/tick.md`、`echo.md`、`syscall.md`、`ledger.md`、`health.md`、`proto5/spec/cpu/notify.md`、`lifecycle.md`、`proto5/spec/aos-agent/tick.md`。

重點（依序）：

1. `aos_kernel_engine.dispatch_woken` 與 `aos_kernel_ledger.readied`（提交點 D）：同一格二次派工會不會重放第一輪的單、會不會漏存帳本、崩在 D 前後能否正確恢復（只放一次、不重派）。
2. `aos_kernel_info.classify`：退出碼 103 與 woken 的判定。失敗會不會變成連環馬上重試？舊帳本沒有 `again` 時的行為？
3. `aos_agent.py`／`aos_agent_batch.py`（send／collect／settle）／`aos_agent_inputs.py` 退出碼：什麼時候退 103／102／0。有沒有「退 102 停車但沒人會叫醒」導致永遠卡住的路徑？有沒有「退 103 但其實沒事做」導致空轉燒 CPU 的路徑？
4. `aos_home.Doorbell`／`ring` 與 `aos_exec_cpu._loop`：FIFO 開啟會不會阻塞、會不會寫到普通檔或 symlink、門鈴讀不乾淨會不會忙等、cpu 不在時按鈴會不會卡住 kernel。
5. `aos_exec_run._wait_full` 的 pidfd：逾時殺子行程、pidfd 洩漏、沒有 pidfd 的退路。
6. `aos_kernel_ledger` 的 `letters`（on_bad 出貨箱）、`aos_kernel_cli` 的 `--on-bad`、`aos_kernel_health` 的 `bad`、`aos_team_post.bad_notice`：崩潰後只寄一次？路徑能不能被登記的人拿來寫到任意地方（跳出、symlink）？寄不出去真的不擋 kernel 那格？
7. `aos_hops.py`：沒設 `AOS_HOPS` 時真的什麼都不做；設了時寫檔失敗不會讓主程式壞掉。

## 產出格式（中文白話）

```
## 必修
M1. 檔:行 — 問題一句 — 會怎樣出事（具體情境）— 建議修法一句
...
## 建議（不修也不會壞）
S1. ...
## 看過沒問題的
- 一行一項
```

只列你有把握的；沒把握的放「建議」並註明不確定。必修要能說出會出事的具體情境。
