# daemon：定期叫 aos-exec

← [整理區](../README.md)｜[慣例](../conventions.md)｜[名詞](../terms.md)｜[通用 tick](../tick.md)｜[daemon 協議](../protocol/daemon/README.md)｜[暫緩區的舊設計](../deferred/daemon/README.md)

程式是正本：[proto6/src/py](../../../src/py/README.md) 的 `lib/aos_daemon*.py`、`lib/aos_ctl.py`、`lib/aos_mq.py`，測試在 `src/py/tests/`。本資料夾每篇只留程式看不出的原則。

## daemon 是什麼

`aos-daemon` 就是一個定期叫 `aos-exec` 的 cron：設定檔列一串 inst，每一項照自己的週期叫一次 `aos-exec <inst>`，印一行結果。

- 它不認得 tick 的工作資料夾，也不是 tick 存在的前提；要定期跑 `aos-tick`，就放一份 `argv` 開頭是 `aos-tick` 的 inst。tick 誰來跑都行（[B-627](../tick.md)）。
- 核心之外的功能都是**模組**：設定檔 `modules` 一個模組一個鍵，有寫就開，沒寫就像沒有這個功能。
- 模組一覽：[B-640 核心](core.md)、[B-641 控制](control.md)、[B-642 重讀設定](reload.md)、[B-643 記住狀態](state.md)、[B-644 收屍／cgroup](cgroup.md)、[B-645 訊息](mq.md)、[B-646 帳號](account.md)。格式（欄位、JSON、argv、結束碼）在 [daemon 協議](../protocol/daemon/README.md)。
- node 模組不做（使用者：「node這塊不要動，我有預感，node相關概念以後會不存在。」）。

## 共通原則

- **默認一切正常**（使用者 2026-10-01）：設定檔讀得懂、路徑都對、`aos-exec` 叫得起來。不為異常寫處理，出事讓程式自然丟錯、回 1。唯一例外是重讀設定時設定壞了：舊的照跑（B-642）。結束碼照 [C-08](../conventions.md)。
- **socket 一律 666，權限靠所在資料夾**（第二十五批）：控制的 socket、訊息的每一扇門，daemon 都 chmod 666；誰能連由 socket 所在資料夾的擁有者／群組／權限決定，資料夾由管理者事先建好，daemon 不建不改。daemon 自己不驗身分，能連就能做。
- **任務能控制別項，全靠這個權限**：任務拿到控制 socket 與各扇門的路徑（環境變數），能不能對別項下指令、取別項的信，不在 daemon 裡判斷，只看它進不進得了那個資料夾。要限制，就把 socket 放在只有該進的人進得去的資料夾。
- **同一份設定只能開一個**：靠鎖檔（預設設定檔路徑加 `.lock`），不靠 socket 檔，因為 socket 會有很多個、權限各自不同。

SIGTERM 立刻回 0、不收尾正在跑的 `aos-exec`。舊的完整 daemon 設計（登記、runner、收尾、通道、helper）整批在[暫緩區](../deferred/daemon/README.md)，條號保留。
