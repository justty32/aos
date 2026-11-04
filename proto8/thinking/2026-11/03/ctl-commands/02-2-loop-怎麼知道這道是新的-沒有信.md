← [入口](README.md)｜涵蓋：規劃（fable，照原則定的細節，可翻案） › 2. loop 怎麼知道這道是新的（沒有信箱）、3. 三個動詞各做什麼（冪等）、4. 「現在暫停中」記在哪、再起時怎麼辦（代定）、5. 跟 daemon 的關係（procs 規劃 § 2c 照本檔改）｜上一份 [01-使用者原文-11-03-逐字](01-使用者原文-11-03-逐字.md)｜下一份 [03-6-條文只加-11-03-註](03-6-條文只加-11-03-註.md)

### 2. loop 怎麼知道這道是新的（沒有信箱）

- **比內容**（N-14「判斷變化比內容或序號」）：每次讀 ctl，把解完的那份跟**上一次讀到的**比，**不一樣＝新指令、照做一次**；一樣＝同一道、不再做（所以人不用急著刪檔，檔留著沒事）。不用 `seq` 當新舊判準：寫的人不必先讀 state 算下一號，「誰能寫就能控制」才真的成立；`seq` 純回音。
- **讀的人只讀不寫**照舊（N-06 後半）：loop 不刪、不改名、不清空 ctl.json——那三種都是「讀的人寫檔」，而且刪了之後第二個人寫進來的就跟第一道分不開。
- **兩個人先後寫、loop 還沒讀**：後寫的蓋掉前寫的，前一道**就沒了**（使用者「誰能寫 ctl.json 就能控制」；N-06「後寫的算」照舊）。要「每一道都算數」是信箱的事，loop 不做；daemon 管名單那邊有 `procs_ctl_mailbox`。
- **同一道寫兩次**（內容一樣）＝不是新的、不重做；三個動詞本來就冪等（§ 3），所以就算重做也沒差。
- **檔不在**＝沒有新指令，維持現狀（今天「檔不在＝還沒人寫」照舊）；寫的人寫完**可以**刪掉它，loop 不在意。
- **起來時的基準線**：loop 起來第一次讀 ctl，那份**當作「已經看過」、不執行**（基準線）；之後跟它不一樣的才是新指令。這一條把「殘留的 `stopped` 再起就馬上退」那個坑**整個拿掉**——舊的 `{"cmd": "stop"}` 留在檔裡，新起的 loop 看一眼就當舊的，不用誰去清。代價：**起來之前**寫好的指令不會被執行（想讓它一起來就暫停，見 § 4）。

### 3. 三個動詞各做什麼（冪等）

| 指令 | loop 在做什麼 | 效果 | 已經在那個狀態時 |
|---|---|---|---|
| `pause` | 跑著 | 這次跑完不起下一次，phase `paused`，每秒再讀 ctl | 已暫停＝不動（回音更新） |
| `resume` | 暫停中 | 起下一次，phase `running`／`waiting` | 沒暫停＝不動 |
| `stop` | 任何 | 這次跑完退 0，state 最後一份 phase `stopped`、`code 0`（同今天的 `stopped`） | 已在收尾＝不動 |
| `max`／`interval_ms` | 任何 | 從下一次起用新值；`max` 改到比 `counter_runs` 小＝這次跑完就 `done` | 同值＝不動 |

- `stop` 壓過同一道裡的其他東西（同 N-07「stopped 壓過 paused」）；`{"cmd": "stop", "max": 5}` 就是停。
- 要當場收掉正在跑的那次照舊送訊號（N-07 10-28 改口），ctl 沒有 `kill`。
- daemon 是 loop：它自己的 ctl.json 同一套——`pause`＝整圈暫停（10-29 § 四 2：不起 exec、不調表）、`stop`＝照 P-36 收掉活著的子項、寫好 state、退 0。

### 4. 「現在暫停中」記在哪、再起時怎麼辦（代定）

- ctl 不再是「暫停的真相」（它只是最後一道指令）。**暫停中這件事記在 loop 的記憶體與 state.json 的 `paused`／`phase`**——state 本來就有這兩格（11-02 state 窗），讀的人（aos-listen `--status`、aos-eca、ai_tools）**一個字都不用改**。
- **再起時要不要繼續暫停**：使用者四態原文「休眠但是可以隨時叫醒**繼續跑指令或繼續暫停**」——醒來要能接著暫停。指令式下 ctl 給不了這個（§ 2 基準線），所以**loop 起來時若開了 state 窗、而且 `$AOS_STACK` 裡已有一份自己的 state.json、它的 `paused` 是 true，就起來先暫停**（第一份 state 寫 `paused`、每秒讀 ctl 等 `resume`）；其他欄位不接（`counter_runs` 從 0、`max`／`interval_ms` 回設定檔——state 不是存檔，只借這一格）。這是 N-28「state 窗就是 save 檔」的精神縮到一格，代定；嫌多就改成「起來一律跑」（§ 要使用者看的 沒列，因為使用者原文偏向「繼續暫停」）。
- 連帶：想讓一支 loop「一起來就暫停」，寫一份只有 `{"paused": true}` 的 state.json 不是辦法（state 只有自己寫，N-09）——正路是起來後馬上寫 `{"cmd": "pause"}`；daemon 下的 proc 用 `aos-daemon-ctl pause`。

### 5. 跟 daemon 的關係（[procs 規劃 § 2c](../procs/05-2c-起-停-暫停-代定.md#2c-起停暫停代定) 照本檔改）

- **daemon 的 stop（loop 型）**＝往子 loop 的 ctl.json 寫 `{"cmd": "stop", "seq": N}`（`seq`＝它自己數的，回音用；寫法 N-05 暫存改名）→子 loop 跑完這次退 0→列留 `stopped`（procs § 2c 第 2 條照舊）。
- **daemon 的 start**＝用列上的 `stack` 再起；**不用先清 ctl**（基準線，§ 2）——procs § 2c 第 3、6 條「start 前清掉 `stopped`」那兩句**作廢**；舊的 `{"cmd": "stop"}` 留著沒事。起來是跑還是暫停照 § 4（它自己的 state.json）。
- **aos-daemon-ctl `pause`／`resume`**＝寫子 loop 的 ctl `{"cmd": "pause"}`／`{"cmd": "resume"}`（不帶 seq 也行；要回音就帶）。`CtlMissing`（exec 型沒有 ctl）照 procs § 2c 第 5 條。
- **daemon 自己的 ctl**：ai_tools `daemon down` 寫 `{"cmd": "stop"}`；`up` 不再清殘留；eca `install` 不再清子 loop 的殘留；常駐 bob `_entry` 的 `clear_stopped` 拿掉。
- **daemon 管別人的 `procs_ctl.json` 不變**（宣告的名單＋`procs_stopped`／`procs_started`，N-54）。`ctl_warning` 兩扇窗各回各的照舊。
- 繞過 daemon、自己往子 loop 的 ctl 寫 `stop`→子 loop 退 0→daemon 看到「退了」→照 11-02 從表上拿掉（procs 衝突 2 使用者「照舊拿掉」）。
