# 第一輪：格式與序列化的缺口
← [call-format](README.md)｜[ideas](../README.md)｜[WORKFLOWS](../../../WORKFLOWS.md)

問的是**這份記錄格式與它的序列化標準**夠不夠好。依「有多威脅到『通用呼叫格式』這個
宣稱」排序。依據是實際 schema（[`core/inst/docs/format.md`](../../../../docs/archive/aos-folder.md)、
[`exec.md`](../../../../docs/archive/aos-folder.md)、`core/inst/include/aos/inst.hpp:53`）。

## 真的會痛的

### 1. 這個呼叫格式沒有回傳值

通用呼叫格式至少要有四樣：被呼叫者、引數、回傳、錯誤。`inst_t` 有前兩樣；**結果的
位置必須由呼叫者在呼叫之前自己挑好並寫進記錄裡**（`stdout`、`exit`）。不是
`y = f(x)`，是「你先租一個信箱，我把東西丟進去」。

**引數 inline、結果 out-of-band**——這個不對稱是後面所有組合問題的單一源頭。A→B 要
接起來，得挑暫存路徑、寫進 A 的 `stdout`、再寫進 B 的 `stdin`。匯聚、鏈接、資料流，
全都在繞這一件事。

### 2. `exit` 檔把結果壓成 8 bit，而且丟掉了最需要的那一位

exec 層在記憶體裡分得很清楚：`timed_out`、`signalled` 是獨立旗標，doc 還特地寫了
「`timed_out` 用來區分函式庫發起的期限與別處送出的同一個訊號」。但**寫進 `exit` 檔的
只有十進位數字加一個 LF**。

於是下一回合只看得到檔案系統，它讀到 `143`，**無法分辨是自己逾時被 SIGTERM 還是別人
殺的**。126／127 doc 自己也承認撞得到真實 exit code。回合制模型要靠這個數字決定下一
回合做什麼，而這條回傳通道是全系統最窄的地方。

### 3. 記錄不自足——同一份 `inst_t` 在兩個地方是兩個不同的呼叫

`env` 是「對一個沒被命名的 base 做 diff」；`cwd` 為空時是 `<folder>`；相對路徑從
`<folder>` 起算；PATH 查找吃繼承來的環境。所以這份 JSON 不是完整的呼叫描述，是
**呼叫描述 ⊕ 執行現場**。作為交換標準這是純度破口：序列化了也搬不動。

（`env` 繼承開關那條在 [inst-execution](../inst-execution.md)，那是這個問題的一個切面。）

### 4. `$env` / `$ref` 已經是一套惰性表達式語言，而且坐在最內圈還會讀檔

`ResolveState` 裡有 `ReferenceCycle`——**有循環偵測代表 ref 可以鏈**。那不是呼叫格式，
那是求值圖。

這直接打臉 [core-layering](../core-layering.md) 的最內圈定義（「`inst_t` ＋ 執行它的
函數」）：`$ref` 讓你**沒有檔案系統就無法把一個 `inst_t` 求值到可執行狀態**，而且那次
讀檔屬於**引數求值**，跟跑行程無關。`timeout_ms` 要移出最內圈是同一類問題，而
`resolve` 這一整層比它更大。

### 5. 依賴存在，但執行器看不見

`parallel` 是「位置＋旗標」：下一筆立刻開始。真正的依賴邊藏在「B 的 `stdin` 剛好等於
A 的 `stdout`」這件事裡，runner 完全看不到。一整批裡三筆要求偏序關係，格式表達不了。
這是 make／ninja 那道經典題，而目前選了「邊不可見」那一側——選了就沒有排程、沒有錯誤
傳播、沒有 dry-run。

## 設計債，還沒爆

### 6. `sh -c` 是逃生門，而旗艦範例就在用它

`format.md` 那個「完整記錄」範例是 `["sh","-c","read line; printf ... >&2"]`。一寫下去，
argv 陣列擋掉的引號地獄、結構化、可機器生成，全部退化成一個字串。管線、`&&`、fd 4、
glob，格式都沒有，答案都是 `sh -c`。

所以要老實回答：**inst 相對於「一個 shell script 檔」到底多給了什麼？** 大概是「可機器
生成、不依賴 shell 存在」——那很好，但那是一句很窄的話，跟「通用呼叫格式」不是同一個
宣稱。

### 7. JSON 字串表達不了 POSIX argv 的定義域

POSIX argv／env 是「除了 NUL 什麼位元組都行」；JSON 字串是 Unicode。Linux 檔名是位元組
串，**非 UTF-8 的檔名寫不進這個格式**，目前也沒有 base64 之類的逃生門。
**序列化標準比它序列化的呼叫格式窄。**

### 8. `UnknownKey` 嚴拒 vs. `exec_loop` 把選項寫進同一份 json——已經撞上了

format 刻意拒絕未知 key（理由正當：舊執行檔不該無聲忽略）。而
[core-layering](../core-layering.md) 說 loop 的 `timeout_ms`／thread 選項「都在 json 中，
在 exec 讀之前納入並套用」。兩條不能同時成立，除非格式長出一塊**具名的擴充區**（每層
一節，或 `$ext`），或每個外圈負責先剝乾淨。這是**格式層**的決定，不是 loop 的實作細節。

### 9. 「POSIX」寫死在名字裡，而開發機是 Windows

沒有 `fork`；argv 是單一命令列字串（`CommandLineToArgvW` 的引號規則不一樣）；env 是
大小寫不敏感的 UTF-16。POSIX-only 是完全正當的選擇，但那要是一句**明講的決定**，不是
預設。

