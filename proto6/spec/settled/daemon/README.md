# daemon：定期叫 aos-exec

← [整理區](../README.md)｜[慣例](../conventions.md)｜[名詞](../terms.md)｜[通用 tick](../tick.md)｜[daemon 協議](../protocol/daemon/README.md)｜[暫緩區的舊設計](../deferred/daemon/README.md)

## daemon 是什麼

**daemon（`aos-daemon`）就是一個定期叫 `aos-exec` 的 cron。** 設定檔列一串 inst，它照每一項自己的週期叫一次 `aos-exec <inst>`，等它結束，印一行結果。

- 它**不認得 tick 的工作資料夾**（舊稱 node；〔使用者 2026-10-01〕改名）。要定期跑一個 `aos-tick`，就放一份 `argv` 開頭是 `aos-tick` 的 inst（例如 `["aos-tick", "<資料夾>"]`，或只寫 `["aos-tick"]`），把它加進清單。
- 它**不是 tick 存在的前提**。tick 誰來跑都行：daemon、cron、人手直接跑（[B-627](../tick.md)）。
- 它**不在任何一格裡**，也不在任何任務表上。

依據：[第二十批篇末「2026-10-01：最核心 daemon」](../../../notes/verdicts/11-tick-as-unit.md#2026-10-01最核心-daemon待統一更新-spec)；現行程式 [proto6/src/py](../../../src/py/README.md)。

## 核心與模組

- **核心**（[B-640](core.md)）：讀設定檔、照週期叫 `aos-exec`、印結果、非 0 時停不停、Ctrl-C 直接退出。只有這些。
- **模組**：設定檔頂層 `modules` 物件裡一個模組一個鍵，**有寫就開**。核心只認得這個位置，不解讀內容。
- 目前只有一個模組：**控制模組**（[B-641](control.md)），開一個 socket，讓人或任務對某一項下 `wake`／`pause`／`resume`／`status`，小工具是 `aos-ctl`。
- 之後打算另做的模組（還沒排程）：管 node（掃資料夾找 node、上下層與叫醒往上傳）、訊息、cgroup、helper。方向見[第二十批「node 模組方向」](../../../notes/verdicts/11-tick-as-unit.md#node-模組方向2026-10-01記錄用未排程)。

**第一版默認一切正常**〔使用者方向 2026-10-01〕：設定檔讀得懂、路徑都對、`aos-exec` 叫得起來。不為異常寫處理，出事讓程式自然丟錯、回 1。結束碼照 [C-08](../conventions.md)，環境變數總表見 [C-10](../conventions.md)。

## 分檔目錄

| 檔案 | 條號 | 內容 |
|---|---|---|
| [core.md](core.md) | B-640 | 最核心 daemon：清單、起點、指示詞展開、週期、非 0 停不停、輸出、停機、`modules` |
| [control.md](control.md) | B-641 | 控制模組：socket、四個指令、wake 的選項、環境變數、`aos-ctl` |
| [協議 core.md](../protocol/daemon/core.md) | P-120 | `aos-daemon` 的 argv、設定檔欄位、輸出格式、結束碼 |
| [協議 control.md](../protocol/daemon/control.md) | P-121 | 控制 socket 的一行 JSON、錯誤代碼、`aos-ctl` 的 argv 與結束碼 |

行為寫在這個資料夾，格式（欄位、JSON、argv、結束碼）寫在 [daemon 協議](../protocol/daemon/README.md)。

## 舊設計在暫緩區

2026-10-01 之前寫的完整 daemon（記憶體登記、runner 與收屍、重啟清理與 `state.json`、收尾與排空停機、熱重載、通道與憑證、掛行程、佈建與 helper、cgroup、訊息、五個部件開關、systemd 範例）第一版都不做，整批搬到[暫緩區的 daemon 目錄](../deferred/daemon/README.md)。條號保留、不重用；每條標了是「暫緩」還是「已被 B-640／B-641 取代」。舊設計的時間單位表（哪些用毫秒、哪些用格數）也在那裡。

開機自動啟動：舊的 systemd 範例寫的是舊設定，也在暫緩區（[service](../deferred/daemon/service.md)）。新版要用 systemd 的話，`ExecStart=` 直接寫 `aos-daemon --config <設定檔>` 就行；停服務送 SIGTERM，daemon 立刻回 0 退出、自己不收尾正在跑的 `aos-exec`（systemd 會不會照它的 `KillMode` 一起收掉，看服務檔怎麼寫）。
