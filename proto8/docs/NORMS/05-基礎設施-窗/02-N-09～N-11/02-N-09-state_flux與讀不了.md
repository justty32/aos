← [回入口 02-N-09～N-11.md](../02-N-09～N-11.md)｜段落：控制：ctl 與 state／N-09、N-11｜上一份：[01-N-09-state與計數器](01-N-09-state與計數器.md)｜下一份：[03-N-11-設定檔與旗標](03-N-11-設定檔與旗標.md)

N-09 接續（上一份的子項到這裡繼續）：

  - **state 與 state_flux：state 拆成兩扇，`state`（穩定）＋`state_flux`（回音）**（使用者 11-09「state可以拆成不太變動的，和容易變動的，頻繁變動的從state拉出來」，新窗名使用者裁「那就state_flux」、`responded_at` 更新時機「不縮小」，[thinking clock-and-hot-writes 05](../../../../thinking/2026-11/09/clock-and-hot-writes/05-state拆分規劃.md)）：
    - **三扇窗**：`ctl.json`＝別人寫給我的指令；`state.json`＝我現在是什麼樣（只在狀態真的轉換時重寫）；`state_flux.json`＝我聽到了什麼（外面敲一下我回一聲的回音欄）。三扇一起落在 `$AOS_STACK`，都只有自己寫（本條開頭）；state_flux 跟 ctl／state 一樣是公開窗，名字與欄名在 aos-loop 公開標頭 `aos/loop.hpp` 定義，任何程式都能照寫。
    - **怎麼判一欄去哪**：對程式做三種不改它狀態的敲——寄一封 ping、把生效中的 ctl 原樣再寫只換 `seq`、寫一道壞 ctl 或一封壞信；這欄跟著變＝回音→state_flux。只在 phase 改變、起或停（含子項起落）、設定生效值改變、行程換了、結束時才變＝穩定→留 state。灰色欄照字面（事件是起停就算穩定），不照頻率判。
    - **欄位**：state 留 `phase`、`paused`、`max`、`interval_ms`、`daemon`（aos-daemon）、`body_code`（有身體的 aos-daemon）、`code`、`pid`／`started_at_ticks`／`boot_id`、最後一欄 `updated_at`。state_flux：aos-loop 是 `responded_at`、`ctl_seq`、`ctl_warning`；aos-daemon 再加 `procs_ctl_seq`、`procs_ctl_warning`（`procs_ctl.json` 的回音）、`adopt_warning`（開門接回舊表的警告，沒事＝`null`）與 `mailbox_warning`（開信箱才有）。**一個程式一份 state_flux**：daemon 不另開 `procs_state_flux.json`，管轄手把的回音加 `procs_ctl_` 前綴進同一份；`responded_at` 只放這一處。
    - **設定與旗標**：loop.json／daemon.json 選填 key `state_flux`（沒寫＝`state_flux.json`、`null`＝不開）、旗標 `--state-flux 檔` 鏡射 key（N-11）。它是窗不是計數器，父要讀，所以沒有開關旗標、預設開；關掉＝父不判這列卡住（N-17）。
    - **怎麼寫**：JSON 一檔多欄（窗族同一種格式，不是一欄一 `.txt`）；照 N-05 先寫 `.state_flux.json` 再改名。啟動後第一份一定寫（帶接回的 `ctl_seq`、`responded_at: null`），之後整份有變才寫，結束不另寫；沒有 `updated_at`。
    - **寫序：state／procs_state 先、state_flux 後**：看到回音時狀態已經落地。例：`aos-daemon-ctl pause` 看到 state_flux 的 `ctl_seq` 追上就回成功，這時去讀 state 一定已是 `paused: true`；反過來寫會出現「說好了但 state 還是 running」的一瞬間。
    - **誰讀**：父判卡住讀子 ctl 的 mtime＋子 state_flux 的 `responded_at`（不讀子 state，N-17）；aos-daemon-ctl 等回音讀 `ctl_seq`；loop 起來從舊 state 接 `paused`、從舊 state_flux 接 `ctl_seq`（N-06 首次讀取）；壞信警告讀 daemon state_flux 的 `mailbox_warning`。沒有讀者需要 state 與 state_flux 同一瞬間的快照。
    - **image**：state_flux.json 跟 ctl／state 一樣進 git image（`ctl_seq` 是 stop→start 不被同一道 stop 再停要讀的）；暫存 `.state_flux.json.<pid>.tmp` 被 `**/.*` 擋。
  - **state／state_flux 讀不了要說話**（使用者 11-09「剩下都OK」＝照推薦，[thinking format-versioning](../../../../thinking/2026-11/09/format-versioning/README.md#使用者-11-09-裁定)、[03 S3](../../../../thinking/2026-11/09/format-versioning/03-正式版機制與種子.md)）：「讀不了」＝檔在但讀不出、不是 JSON、根不是物件；檔不在照舊安靜。
    - **主人**（自己寫、起來時自己讀回的窗：aos-loop 與繼承它的 aos-daemon 的 `state`、`state_flux`；daemon 的 `procs_state` 另見 [N-28 `adopt`](../../04-基礎設施-loop與daemon/02-N-28.md)）讀不了＝把壞檔改名 `<名>.bad-<UTC 毫秒時間>`、stderr 印 `程式: warning: <名> is unreadable (<原因>); kept it as <保留檔名> and started fresh`、當沒有繼續（例：接不回 `paused`、`ctl_seq`）；改名失敗＝`WriteFailed` 起不來。留證檔 `.bad-*` 不自動清，範本 `stack.gitignore` 擋掉、只留原機（使用者 11-09「擋掉，不自動清」，[format-versioning 05](../../../../thinking/2026-11/09/format-versioning/05-種子施工結果.md#留給使用者不急不擋)）。
    - **旁觀者**（讀別人的窗：daemon 讀子格的 state／state_flux、llm kernel／aos-llm 讀 daemon 的窗、aos-daemon-ctl、aos-agent）讀不了＝每個行程每個路徑印一次 `程式: warning: <路徑> is unreadable (<原因>); treating it as missing`，不動別人的檔，其餘照「沒有這份檔」的路走。
    - 只做「讀不了就說話」，不加版本檢查；這不是 [C-48](../../../CONCEPTS/01-設計理念/01-C-01～C-48.md) 的「不認得的 key 當沒看到」——程式寫的狀態檔讀不了要看得出壞了（N-28 `adopt` 同理）。
