# 2026-11-09 `_clock` 跟 daemon 解耦（clock-decouple；只規劃、沒改程式與條文，方向題 3 題等裁）

← [2026-11-09](../README.md)｜細節：[01 耦合點全表](01-耦合點全表.md)、[02 解耦方案](02-解耦方案.md)、[03 衝突、邊緣與方向題](03-衝突邊緣與方向題.md)｜相關：[clock-and-hot-writes](../clock-and-hot-writes/README.md)（今天的改名）、[tick-time 03](../../05/tick-time/03-11-06-裁定與新設計.md)（`clock` key 的來源）、[no-pid 15 P6 去耦合](../../05/no-pid/15-P6去耦合.md)（同型先例）

## 使用者原話（11-09，逐字）

> 然後現在的_clock是與daemon耦合很深...我希望別那麼深，幫我想想

同日稍早（daemon 中斷那條線）：

> 這種中斷……與linux或底層相關的各種麻煩事都盡量讓daemon作處理與隔斷，讓aos proc能夠盡量享有純粹抽象……這套希望是可選的。

## 結論

**耦合點（細節 [01](01-耦合點全表.md)）**，最重的五個：
1. daemon.json 的 `clock` key 由 daemon 程式自己展開成一列，預設名 `_clock`、撞名報錯（`daemon.cpp:26-68`）。
2. 那列寫死要跑 `aos-clock` 這支程式、寫死 `auto_restart: true`（`daemon.cpp:62-63`）——daemon 認得一支特定程式的名字。
3. daemon 在自己的行程 `setenv AOS_CLOCK`（和 `AOS_CLOCK_INTERVAL`），全樹靠它拿到鐘；子 daemon 自帶就蓋過去（「近的贏」）（`daemon.cpp:70-74`）。
4. daemon 判子項卡住時讀這個鐘（`stuck.cpp:57`，`stuck_after_cycles`）——跟條文「daemon 自己不讀、不等時鐘」本來就對不上。
5. **鐘看鐘**：`_clock` 自己的卡住也用它自己寫的鐘判，鐘被凍住（SIGSTOP、卡 I/O）時期限永遠不到，表上一直 `running`；條文說「看 `_clock` 列是不是 running」在這種壞法看不出來。

其餘：範本三份帶 `"clock": true`、判官容量要多留一格、搬家食譜與 ctl 說明寫 `_clock`、條文 7 處用語、試驗場三份、桌面四頁。

**四個方案**（由淺到深，細節 [02](02-解耦方案.md)；四案都加一個通用列欄 `stuck_after_ms`，讓跑鐘那列能用牆鐘判卡住，消掉「鐘看鐘」）：
- **A 縫合**：key 全留，只補「鐘看鐘」。改 5 檔、設定不變；但 daemon 還是認 `aos-clock` 這個名字，不算解耦。
- **B 跟 P6 同一招（推薦）**：拿掉 `clock` key；鐘就是 daemon.json 裡一列普通 proc（範本出廠就寫好），`AOS_CLOCK` 改由定義資料夾的 `.env` 一行給、子行程照繼承。daemon 程式刪約 70 行，對鐘只剩「跟任何 proc 一樣讀環境的 `AOS_CLOCK`」。11-06「在daemon的設定中自帶」讀成「範本自帶那一列」，跟今天「別耦合」兩句都成立。代價：手寫 daemon 要抄一列＋一行；鐘檔路徑、`AOS_CLOCK`、頻率分在兩個檔，靠人對上。
- **C B＋一樹一鐘**：只有根帶鐘，子 daemon 只繼承。翻 11-06 晚「三個時鐘都留著」。
- **D C＋daemon 完全不讀鐘**：判卡住全改牆鐘。翻 11-07 #12（人 pause 鐘而不睡 daemon 時會誤判卡住），不推。

**跟「中斷住 daemon、proc 純抽象、可選」**：fable 判時鐘不算「Linux 底層麻煩事」（cycle 是 aos 自己的抽象，Linux 牆鐘才是底層）；晶振是板子（daemon.json）的零件、不是 CPU（aos-daemon 程式）的邏輯，B 把它放回接線，跟方向一致，也仍然可選（不寫就沒鐘、退牆鐘）。

**隊長核實出的坑**（[03 § 五](03-衝突邊緣與方向題.md#五隊長補全opus核實-fable-留的待核實)）：B 的鐘列如果照直覺寫 `{"$env": "AOS_STACK", …}`，會寫到鐘列自己的小格（`.stack/procs/_clock/clock`），而大家讀的是 `.stack/clock`——全樹停在第 0 格、期限永不到。要寫 `AOS_DAEMON`。也不能讓鐘列寫 `$AOS_CLOCK`（遠的贏時會跟父的鐘寫同一檔＝雙倍速）。

## 方向題（等使用者裁；推薦放第一，細節與判準在 [03 § 三](03-衝突邊緣與方向題.md#三方向題原則推不出的每題推薦放第一)）

1. **`clock` key 留不留？** 推薦拿掉（B）｜留 key 只補洞（A）。判準：改完 `grep -rn "aos-clock\|_clock\|expand_clock\|AOS_CLOCK" proto8/impls/aos-daemon/src/` 為 0；試驗場三層 `ctl ls` 看得到鐘列、`cat "$AOS_CLOCK"` 每秒加 1；`kill -STOP` 鐘列 10 秒內表上 `stuck`。
2. **子 daemon 自帶鐘，近的贏還是遠的贏？**（11-06 已裁近的贏；`.env` 預設不蓋＝遠的贏）推薦遠的贏為預設（全樹一個 cycle、凍根＝凍整棵），要近的贏由掛的人把那列寫成 `["aos-exec", "--dotenv-override", "../sub"]`，不加新機制｜維持近的贏（要給 `.env` 加「強制蓋」的通用寫法）｜一樹一鐘（C）。判準：三層試驗場三個 `$AOS_CLOCK` 是不是同一檔。
3. **daemon 判卡住還要不要讀鐘？**（11-07 #12 已裁「鐘停、判卡住一起停」）推薦繼續讀、鐘列自己用 `stuck_after_ms`｜全走牆鐘（D，翻 #12）。

## 代定（fable＋隊長，可翻；全文 [03 § 四、五](03-衝突邊緣與方向題.md#四fable-代定可翻)）

- 加通用列欄 `stuck_after_ms`，跟 `stuck_after_cycles` 擇一、兩個都寫＝`CfgBad`、預設仍 10 cycles。
- 範本鐘列仍叫 `_clock`、`auto_restart: true`、`stuck_after_ms: 10000`、`interval_ms: 1000`、鐘檔寫 `{"$env": "AOS_DAEMON", "$path": "clock"}`；`.env` 只寫 `AOS_CLOCK=${AOS_STACK}/clock`，頻率不是 1000 才寫 `AOS_CLOCK_INTERVAL`。
- 舊 `"clock": true` 當沒看到、不 warning、不遷移（proto8 不寫遷移）；範本與試驗場同一個 commit 改。
- 「只寫 `.env` 沒寫列」「兩處頻率對不上」不加檢查，文件寫一句；要更穩可另做唯讀檢查，不在本次。
- 啟動第一秒「鐘檔不在」的 warning 這次不動。
