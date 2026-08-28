# 呼叫格式本身好不好：對 inst-POSIX 的拷問

← [ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

aos 的核心本質是三層：**一個簡單的通用呼叫格式＋它的標準實現**、**該格式的序列化
標準**，然後在此之上才是「檔案系統作為 CPU process」（loop、`inst.json` 版面——那些
在 [turn-based-folder](turn-based-folder.md) 與 [core-layering](core-layering.md)）。

這個主題只問前兩層：**`inst` 這個 POSIX 呼叫格式，真的好嗎？** 內容按四輪拷問拆開。

> **使用者的總裁決**：這些都是**工程問題**，稍微調整設計就差不多能解決，不動搖
> inst-POSIX 這個大方向。而 fork/exec **只是呼叫機制、不是呼叫約定**，它不能成為通用
> 契約——它只作為「**fork/exec as CPU instruction**」這個概念的**基石**。所以這裡是
> 待解清單與邊界說明，不是「該換掉格式」的論證。

內容已拆進 [`call-format/`](call-format/README.md)。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [format-gaps](call-format/format-gaps.md) | 第一輪九條：沒有回傳值、`exit` 檔壓成 8 bit、記錄不自足、`$ref` 是坐在最內圈的求值語言、依賴邊執行器看不見、`sh -c` 逃生門、JSON 表達不了位元組 argv、`UnknownKey` 撞 loop 選項、POSIX 寫死在名字裡 | 要改格式或序列化之前 |
| [universality](call-format/universality.md) | 第二輪：fork/exec 是呼叫**機制**不是呼叫**約定**；界外六樣（共用記憶體、常駐、串流、微秒粒度、最小權限、跨機器）**＋使用者對每一條的裁決** | 想知道哪些東西天生不能是 inst、哪些已經拍板 |
| [cpu-analogy](call-format/cpu-analogy.md) | 第三輪：照真實 CPU 的標準驗這個類比——原子性／封閉 ISA／確定性三樣無解（已認），控制流那樣有解**就是 loop**；daemon 讓世界外溢的答案是 **GPU mailbox 模型**；外層契約、plan 9 的 rename 原子性、沒有停機仍開著 | 想知道「CPU 指令」這個說法撐得住多少、loop 為什麼在 core 裡 |
| [handoff-and-world](call-format/handoff-and-world.md) | 第四輪：交接協定的三個**實作缺陷**（`.runi` 不是鎖→同回合可能跑兩次、無 `fsync`、`<pid>` 不唯一）＋世界沒圍牆（**用 git 解**）、沒有回合歷史（**要補在 loop**）、PC 不自己前進（**刻意**）、嚴解析鬆執行（**刻意**）、delta time 從 loop 走回來 | 要碰 handoff／loop 之前 |
| [keep](call-format/keep.md) | 被拷問完也別動搖的部分：argv 是陣列、未知 key 拒絕、刻意不設上限、stream 是檔案；以及五十年 ABI／崩潰隔離／可觀察／與世界模型同構 | 想改格式時先讀，免得把對的東西改掉 |
