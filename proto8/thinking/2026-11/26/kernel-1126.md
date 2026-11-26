daemon 收窄之後談 kernel：init 做最小的（照設定起第一批、把別人「請起一隻」轉給 daemon、記誰起了誰），kernel 登記表、准不准、重起規則都做成 init 起的其他 kernel、可以不裝；其餘幾題一題一題談。

# kernel（11-26 午後，公司）

← [2026-11-26](README.md)｜前情：[daemon當容器-1125](../25/daemon當容器-1125.md)（kernel 四種、提供與選用分開、按需起）、[daemon職責-1126](daemon職責-1126.md)（只有 init 碰 daemon）、[報告 14：kernel 過去的規劃對照新模型](../25/aos-proc介面架構規劃-1125/報告/14-kernel過去的規劃對照新模型.md)（寫在 daemon 收窄之前）

使用者原話逐字在 [9p-proc-1125](../25/9p-proc-1125.md) 第 125 段起。

## 前提（之前定的）

- kernel 就是普通的 aos proc，接手天空裡的某個名字。四種：`dir`、`exec`、`fuse`、`socket`；前兩種不用自己的行程。
- 提供和選用分開；只能往下傳自己有的；天空起來時定好、改要明確下指令。
- 只有 init 碰 daemon；kernel 登記表、重起、判卡住、准不准都不在 daemon。

## 定了的

1. **init 做最小的。**（第 126 段，選甲）只做三件：照自己的設定檔起第一批 proc；收別人「請起一隻」的要求、轉給 daemon 的 `ctl`；記下誰起了誰。kernel 登記表、准不准、重起規則都做成 init 起的其他 kernel，可以不裝（呼應 11-20「兩件+最小核心。然後弄一串可選的」）。
   - 代價：「請起一隻」要先問准不准的 kernel，多一次來回；准不准的 kernel 沒裝就全准。

2. **別的 proc 跟 init 說話，走同一套介面，不另開一條路。**（第 127 段）init 那邊擺出一個目錄，有 `__meta/__interfaces/xxx` 宣告它符合哪個介面；背後用 socket、FUSE 還是一般檔案都行，只要符合介面（界面＝檔案布局＋格式＋存取得到，見 [aospl循址與元介面-1126](aospl循址與元介面-1126.md)）。
   - 補（第 128 段）：意思是 init 宣告相關的 **ctl 介面**，別的 proc 照那個介面寫 ctl。
   - 宣告長這樣（第 129 段他提、第 130 段三小題照推薦）：介面名 **`aos/ctl`**；`__meta/__interfaces/aos/ctl/` 是一個夾，底下寫怎麼講：
     - `kind`：`file`（寫一行進那個檔、做完才回、失敗在寫入那一下回錯誤）或 `socket`（連上、送一行、讀回一行）。背後是不是 FUSE 是提供者的事，寫入的一方只分這兩種。
     - `path`：以宣告所在的目錄起算（`ctl` 就是 `/aos/ctl`），整個目錄掛到別處也照通。
     - `commands`：有哪些指令，例 `start kill mount umount forget`。
     - 同時給兩種講法就開兩個夾（`aos/ctl/file/`、`aos/ctl/socket/`）。
   - 起點固定：每隻 proc 先到自己天空裡的 `/aos`，讀宣告才知道去哪寫。`/aos` 在天空裡唯讀，只有 ctl 本身能寫（誰能改宣告，誰就能把別人的指令導走）。
   - daemon 也宣告 `aos/ctl`（下一批原本的空檔 `aos/daemon` 改成這個夾）。init 對別人擺出同一份介面，所以每隻 proc 在 `/aos` 看到的都是「管我的那一方」，程式不用知道背後是 daemon 還是 init，疊 daemon 也不用改。init 可以拒絕某些指令、只讓每隻看到它自己起的。
   - 「登記 kernel」不放進這份 ctl，交給登記表那個 kernel 自己宣告的介面（第 3 題）。

## 還沒談的（照該先談的排）

3. 登記表的格式與放哪。
4. 按需起 kernel（現在歸 init 這一層）。
5. proto8 的 llm kernel 怎麼搬過來。
6. 就緒與事件。
