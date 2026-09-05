> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# loop 的職權
← [machine-shape](README.md)｜[ideas](../README.md)｜[WORKFLOWS](../../../WORKFLOWS.md)

**驗證過**：loop 目前活在 `core/inst/src/run_loop.cpp` 裡，不是獨立專案。

> **貫穿三份的一條線**：`instruction` 第 1、2 條與 `loop` 第 6 條是**同一個決定**——
> **給「批」一個名字和一個 header**，它同時解決 ISA 版本、指令來源、與 loop 分支所需的旗標。

## 6. 「loop 是控制流」目前是志向——它沒有可以分支的狀態

一個回合結束後，**loop 能讀到、可以據以分支的那個值是什麼？** 現在沒有：`exit` 是**單筆**
的、且寫在使用者自己指定的檔案（不指定就沒有）；**批沒有彙總狀態**；`aggregate` 用同一個
`Ok` 回報兩種情況。

改 exit status 是必要的但**不夠**。控制流單元需要**旗標暫存器**：這一批整體發生了什麼
（全成功／部分失敗／逾時／被拒）。那東西該掛在「批」上——又回到第 1 條。

## 7. loop 現在住在 `core/inst` 裡，跟分層規劃不一致

`core/inst/src/run_loop.cpp` 已存在，而 [core-layering](../core-layering.md) 說 `exec_loop`
是**另一個 core 專案**。鐵律是單向分層、下層不知道上層——loop 在 `core/inst` 裡面意味著
「指令」這層知道「迴圈」這層，正是要避免的方向。要落地分層，這個檔得搬出去，並會拖著
`run_internal.hpp` 那一票一起動。

## 8. 一個世界一個 loop ＝ 沒有排程器

N 個世界＝N 個 loop 行程各自輪詢，沒有排程、優先權、全域資源視角。而
[llm-cpu](../llm-cpu.md) 已提到跨資料夾排程與資源有限性。**要決定的是：跨資料夾排程屬於
`exec_loop`，還是更外層？** 答案決定 `exec_loop` 的介面是「跑這個資料夾」還是「跑這一組
資料夾」——那是兩個不同的專案。

## 9. 這顆 CPU 沒有 reset line

loop 中途死掉 → `.runi` 留著 → 下次啟動一律拒絕（已定案）。所以 **loop 崩潰＝那個世界
永久停住直到人介入**。「拒絕比靜靜蓋掉好」是對的選擇，但配上沒有歷史，人被叫來時**手上
只有一個 `.runi`，沒有任何它為什麼死的資訊**。而且**誰監督 loop**——目前沒有 supervisor、
沒有重啟、沒有健康檢查。

---

# 第八輪：讀 `run_loop.cpp` 的實測

迴圈體只有這幾行（`core/inst/src/run_loop.cpp:72-81`）：

```cpp
for (;;) {
    bool did_work = false;
    const int result = run_exec_once(folder, did_work);
    if (result == 3) return 3;
    if (g_stop_requested != 0) return 0;
    if (!did_work && interval != 0) {
        sleep_milliseconds(interval);
        ...
    }
}
```

## 13. 官方寫法 `aos exec --loop 0` 就是忙碌輪詢

[decided-and-open](../turn-based-folder/decided-and-open.md) 定案「持續執行是
`aos exec --loop 0`，不另做 `core/daemon`」。而 **`interval == 0` → 永遠不睡**。

所以那個被寫進「已定案」的標準寫法，行為是**沒有工作時用整顆核心全速空轉，每一圈
`readdir` 整個 inbox**。開放問題裡的「`0` 的語意待定」——**`0` 已經有語意了，只是它是
最糟的那個**，而且是文件唯一示範的用法。

## 14. 失敗算「有做事」，所以失敗會關掉唯一的節流閥

`if (!did_work && ...)`：**只有沒做事才睡**。而「做事」不分成功失敗——exec 那層已定
「非零狀態、訊號終止、找不到命令、逾時，都是一次**已完成的執行**」。

於是一批每回合都失敗的指令會讓 `did_work` 恆為 true，**節流閥永遠不啟動**。
[第五輪](../call-format/feedback-and-failure.md)推測的「全速無限失敗」在程式碼裡確認了：
**唯一的煞車，剛好被失敗解除。**

修法很便宜：節流的判準不該是「有沒有做事」，而是「有沒有**進展**」——而「進展」的定義
又回到「批需要一個彙總狀態」。

## 15. loop 忽略除了 3 以外的所有回傳值

`run_exec_once` 回 **1** 是**函式庫層級的失敗**：fork 失敗、行程群組設定失敗、等待失敗、
寫 `exit` 檔失敗——不是「子行程跑壞了」，是**這台機器本身出問題**。loop 把它們整個丟掉：
沒有計數、沒有退避、沒有回報、沒有停機條件。`result` 只有 `== 3` 被用過。

**這就是「loop 是控制流」目前的全部內容：一個 `if`。** 而它檢查的還是唯一一個不該由
loop 決定的情況（`.runi` 存在＝有人在跑）。

## 20. 並行度沒有上限 × loop 忽略失敗 ＝ fork bomb 不被察覺

`threads.reserve(instructions.size())`，一筆 `parallel` 一個 thread。一批一萬筆並行就是
一萬個 thread ＋ 一萬個行程。

「不設上限」的理由是「資源有更好的邊界」——確實有（`RLIMIT_NPROC`、thread 上限），但那些
邊界**表現出來的形式是 fork 失敗**，也就是函式庫層級失敗回傳 1，而 **loop 把 1 整個丟掉**
（第 15 條）。

三個各自有道理的決定（不設上限、失敗不中止、有做事就不睡）相乘：**一批指令可以把機器
打到 fork 不出東西，每筆都失敗，loop 完全不知道，而且因為 `did_work` 為 true 連睡都不睡，
立刻再來一輪。滿速、無聲、自我惡化。**

## 21. `did_work = true` 設在執行之前

`run_exec.cpp:170` 把 `did_work = true` 放在 `execute_batch` **之前**。所以連「resolve
全批失敗、一筆都沒執行」也算有做事 → 不睡。比第 14 條更寬：**連沒執行都算做事。**

`did_work` 的真正語意是「這一圈有沒有**取到**批次」，卻被當成「有沒有**進展**」用。在補上
批次彙總狀態之前，這兩者無法區分——又是同一個決定。

---

# 第十輪（換 Fable 重打）：身份判準、時間窗口、PC

**全部未裁**——使用者：之後慢慢想，更可能邊實作邊想。

## 25. loop 的身份危機：control unit 還是 kernel？

timeout、歷史、delta-time、停機、中斷、排程——**每個 open question 的答案都是「放
loop」**＝ microcode 陷阱：機器靠硬體改版長大。CPU 類比自己有答案：監督／排程／日誌是
kernel 做的，而 **kernel 是跑在 CPU 上的程式**，不是包在 CPU 外的圈。已擁抱 von
Neumann（指令可寫指令），就該收紅利：**系統軟體用這個 ISA 自己寫**。

**待裁判準**：loop 只收「**無法成為 inst 的東西**」——必須在沒有任何 inst 可跑的時刻
運作的：claim、崩潰恢復、睡眠、doorbell。其餘（寫歷史、輪詢外部 CPU、排程器）都是
inst＝這台機器上的 OS。此判準一次回答第 8 條（排程是 OS，不屬 exec_loop）與中斷欠帳
（doorbell 必須在回合之間醒著＝真硬體，歸 loop）。代價：彙整層需要「系統 inst 注入
策略」——但那是**一個**新機制換掉 N 個 loop 功能，且注入物是可讀可版控的 JSON。

## 26. 回合邊界在協定上存在、在時間上不存在

release → 下一個 claim 是**零寬度瞬間**（`did_work` 時連 sleep 都沒有）。「使用者在
回合間介入」是核心賣點，但介入靠手快——不是缺功能，是**週期定義裡沒有「開放窗口」這個
相位**，所以介入機制是 ISA 級規範、不是外掛。待裁分岔：控制面（hold／step／stop）
**走投遞協定本身**（control inbox，claim 前看一眼；「控制機器」與「下指令」同構），
還是另開 signal／pid 檔的 ad-hoc 通道（每個 daemon 都長成的樣子）？

## 27. PC 暫存器不存在

回合編號在整個系統裡**沒有任何表示**，而它是歷史編號、兩顆 CPU 的排序基準、status
回報、git tag 對應、去重 epoch 的**共同前提**。最便宜的缺件：一個檔案、三個小裁決——
誰持有（`.aos/turn`？）、誰遞增（release 成功時？）、進不進 git（大概是唯一**該**進
git 的 `.aos/` 檔，因為它就是 state N 的那個 N）。
