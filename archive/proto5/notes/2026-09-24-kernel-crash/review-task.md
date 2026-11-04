# 任務書：審查 kernel 崩潰窗口測試 C-7／C-8（唯讀）

你是審查員，只讀不改、不 commit；不碰 LM Studio／lms／ollama（這條線不需要模型）。

## 背景

- 規範：`proto5/spec/kernel/tick.md`（一格十步；第 4、10 步出貨；第 6 步補放；第 8 步先記後放；第 10 步 log 不保證涵蓋崩潰中途）、`ledger.md`（帳本、出貨箱、§1.3 檔名與 ack digest）、`echo.md`、`impl-notes.md`；cpu 那邊 `proto5/spec/cpu/lifecycle.md` §6.3、`stop.md`。
- 原始題目：`proto5/notes/2026-09-23-rearch/impl-review-report.md` C 節的 C-7、C-8。
- 實作：`proto5/lib/aos_kernel_engine.py`（`step`、`collect`、`dispatch`、`stopping`）、`aos_kernel_ledger.py`（`flush_outboxes`、`apply_syscall`、`ack_ticks`）、`aos_kernel_boot.py`。
- 新測試：`proto5/lib/test/test_kernel_crash.py`。手法：真 daemon 由 HUB（借 `test_daemon_crash.HUB`，subreaper）拉起；boot 時把 `aos_kernel_boot.CLI` 換成測試啟動器 TICK，帳本的 `cli` 就是它，每一格都經過它；TICK 跑真的 `aos_kernel.main()`，只在 driver 內替換函式當閘門（`aos_home.post_request`／`link_json`、`Path.unlink`、`Path.open`（kernel.log）、`Kernel._post_work`、`Kernel.step`、`KernelLedger.flush_outboxes`），產品程式沒改。命中閘門就停住，測試送真 SIGKILL，並把下一格卡在開頭，讓接收者（cpu／交件者）先處理，再放行。

## 要你看的

1. 閘門點是否真的落在宣稱的窗口（before_log、before_post／after_post、四箱的 before_put／after_put、start）。替換的函式有沒有被產品路徑真的用到（模組屬性查找、`from x import y` 綁定）。
2. 斷言夠不夠抓真錯：重派（同一件工作跑兩次）、cpu 收到兩份同名 request、帳本計數錯（runs／fails 重算或漏算）、回音重複處理、鬼回音（交件者 ack 後回音又冒出來）、syscall 重做。trace.jsonl 的「同名只成功一次」檢查是否漏了哪類放檔。
3. flaky 風險：tick_ms 5 的鏈一直在跑、閘門一次性的判定、「下一格要等這格死才開始」這個前提、settle 用 last_seq、6～10 秒 wait_for、收尾一定不留行程（held tick、孤兒）。
4. kernel 在這兩個窗口有沒有真會壞、而測試沒抓到的地方。尤其：
   - stop 出貨箱：cpu 已消化 stop、已退，重放一份同名 `stop-<chain>.json` 留在它家（測試現在把這個釘成現況，說明跟 B-10 同一件事）。你覺得這算不算「雙份 request」要修？
   - ack 重放用新一格的 seq 取名，所以同一則回音會收到兩份不同名的 ack。規範 §1.3 允許嗎？
   - `_daemon_call` 在拿到 spawn 回音、寫帳本之前崩潰，下一格用新名字再 spawn，舊回音永遠沒人 ack（留在 daemon 的 responses/）。
   - `collect()` 裡 `discard=true` 且原單、回音都不在時直接 `continue`，會不會永遠卡住那顆 cpu。
5. 規範不明處：「EEXIST 當已放」對 stop 這種接收者會刪檔的通知是否足夠；kernel.log 缺一格以外還有沒有別的證據會丟。

## 回報

照嚴重度列（真 bug／測試漏洞／flaky 風險／建議），每條附檔案:行號與一句理由。沒有就說沒有。中文、精簡。
