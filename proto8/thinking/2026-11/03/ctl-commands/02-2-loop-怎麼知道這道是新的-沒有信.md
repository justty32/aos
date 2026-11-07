← [入口](README.md)｜涵蓋：規劃（fable，照原則定的細節，可翻案） › 2. loop 怎麼知道這道是新的（沒有信箱）、3. 三個動詞各做什麼（冪等）、4. 「現在暫停中」記在哪、再起時怎麼辦（代定）、5. 跟 daemon 的關係（procs 規劃 § 2c 照本檔改）｜上一份 [01-使用者原文-11-03-逐字](01-使用者原文-11-03-逐字.md)｜下一份 [03-6-條文只加-11-03-註](03-6-條文只加-11-03-註.md)

### 2. loop 怎麼知道這道是新的（沒有信箱）

- **比內容**（N-14）：每次讀 ctl，把解完的那份跟**上一次讀到的**比，**不一樣＝新指令、照做一次**；一樣＝同一道、不再做（檔留著沒事）。後續讀取不用 `seq` 當新舊判準（寫的人不必先讀 state 算下一號）；11-07 #15-2 起，`seq` 除回音外另供第一次讀去重。
- **讀的人只讀不寫**（N-06）：loop 不刪、不改名、不清空 ctl.json。
- **兩個人先後寫、loop 還沒讀**：後寫的蓋掉前寫的，前一道**就沒了**。要「每一道都算數」是信箱的事；daemon 管名單那邊有 `procs_ctl_mailbox`。
- **同一道寫兩次**（內容一樣）＝不是新的、不重做。
- **檔不在**＝沒有新指令，維持現狀；寫的人寫完**可以**刪掉它。
- **起來第一拍（11-07 #15-2 改）**：先接回上一份 state 的有效 `ctl_seq`；ctl 的有效 `seq` 相同＝已套用、不重做且保留回音；不同、缺 state／有效 `ctl_seq`、或 ctl 沒帶 `seq`＝照一般指令處理。起來前或凍住時寫的新指令，第一拍會照做；壞指令也會警告並更新 `responded_at`。取代 11-03「首份一律當基準線不執行」的代定。

### 3. 三個動詞各做什麼（冪等）

| 指令 | loop 在做什麼 | 效果 | 已經在那個狀態時 |
|---|---|---|---|
| `pause` | 跑著 | 這次跑完不起下一次，phase `paused`，每秒再讀 ctl | 已暫停＝不動（回音更新） |
| `resume` | 暫停中 | 起下一次，phase `running`／`waiting` | 沒暫停＝不動 |
| `stop` | 任何 | 這次跑完退 0，state 最後一份 phase `stopped`、`code 0` | 已在收尾＝不動 |
| `max`／`interval_ms` | 任何 | 從下一次起用新值；`max` 改到比 `counter_runs` 小＝這次跑完就 `done` | 同值＝不動 |

- `stop` 壓過同一道裡的其他東西；`{"cmd": "stop", "max": 5}` 就是停。
- 要當場收掉正在跑的那次照舊送訊號（N-07），ctl 沒有 `kill`。
- daemon 是 loop：它自己的 ctl.json 同一套——`pause`＝整圈暫停（不起 exec、不調表）、`stop`＝照 P-36 收掉活著的子項、寫好 state、退 0。

### 4. 「現在暫停中」記在哪、再起時怎麼辦（代定）

- ctl 不是「暫停的真相」（它只是最後一道指令）。**暫停中這件事記在 loop 的記憶體與 state.json 的 `paused`／`phase`**。
- **再起時要不要繼續暫停**：使用者四態原文「休眠但是可以隨時叫醒**繼續跑指令或繼續暫停**」——醒來要能接著暫停。所以**loop 起來時若開了 state 窗、而且 `$AOS_STACK` 裡已有一份自己的 state.json、它的 `paused` 是 true，就起來先暫停**（11-07 #15-2：第一拍若有尚未套用的 resume，先解除暫停再寫 state）；另接回有效 `ctl_seq` 供第一拍去重，其他欄位不接（`counter_runs` 從 0、`max`／`interval_ms` 回設定檔）。代定；嫌多就改成「起來一律跑」。
- 想讓一支 loop「一起來就暫停」：起來前寫尚未套用的 `{"cmd": "pause", "seq": N}`，或起來後寫新指令（11-07 #15-2）；daemon 下的 proc 用 `aos-daemon-ctl pause`（不是自己寫 state.json，N-09）。

### 5. 跟 daemon 的關係（[procs 規劃 § 2c](../procs/05-2c-起-停-暫停-代定.md#2c-起停暫停代定) 照本檔改）

- **daemon 的 stop（loop 型）**＝往子 loop 的 ctl.json 寫 `{"cmd": "stop", "seq": N}`（N-05 暫存改名）→子 loop 跑完這次退 0→列留 `stopped`。
- **daemon 的 start**＝用列上的 `stack` 再起；**不用先清 ctl**（11-07 #15-2：舊 state 的 ctl_seq 已回音同一道 stop，就不重做，§ 2）。起來是跑還是暫停照 § 4。
- **aos-daemon-ctl `pause`／`resume`**＝寫子 loop 的 ctl `{"cmd": "pause"}`／`{"cmd": "resume"}`。exec 型沒有 ctl＝`CtlMissing`。
- 寫 daemon 自己的 ctl 停它＝`{"cmd": "stop"}`；loop 不清 ctl；11-07 #15-2 起，沒帶 seq 的 stop 在下次重起仍會照做，要避免重複須帶 seq 並有 state 回音。
- **daemon 管別人的 `procs_ctl.json` 不變**（宣告的名單＋`procs_stopped`／`procs_started`，N-54）。`ctl_warning` 兩扇窗各回各的。
- 繞過 daemon、自己往子 loop 的 ctl 寫 `stop`→子 loop 退 0→daemon 照 11-02 從表上拿掉（procs 衝突 2 使用者「照舊拿掉」）。
