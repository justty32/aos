# 2026-10-13 kernel 不是一層：能管任務的 inst 就是 kernel；agent 可以基於 loop 或 daemon

← [討論紀錄](README.md)｜程式現況：[proto8/lib](../lib/README.md)｜概念：[CONCEPTS](../CONCEPTS.md)｜前一份：[JSON 路徑](2026-10-13-json-path.md)

> 10-13 晚（家機），語音輸入。

## 0. 使用者原文（語音，去贅字）

底子其實已經打好了：把檔案系統當 lisp 來做，核心就是 inst 這塊碼在跑；上面包了 loop；loop 上面又有管理多個 inst 在跑的 daemon。到這邊基礎已經打好了，接下來直接針對 agent 的需求，進入 agent。

先前的概念說要先做 tick、再做 task、再做 kernel、再做 agent——其實它們不是分層，都是概念。概念先定下來，再基於 inst 這塊技術去顯化。所以可以直接跳到最終想達到什麼效果。

kernel 本質上就是管排程、管資源之類的概念。先前做過嘗試：kernel 把 loop 當 CPU 在用、去管它——後來發現真的沒有必要。**所有能夠管某個任務是否在執行、管某個任務可以去執行的，就叫 kernel。**

拿 agent 來說：指定一個 inst，它 argv 的第 0 個元素就是 agent。agent 本身也是一個 loop，持續跑某個狀態機變換。所以 agent 既是一個持續執行的 inst，也是一個 loop；它本身的機理元素就是一個 loop 在持續呼叫一個狀態機變換程式。可以拆成這三塊。

agent 可不可以當 kernel？可以。agent 可以基於 loop，也可以基於 daemon。如果基於 daemon，它就可以自己管理底下還可以再跑哪些額外的任務、這些任務什麼時候跑——那 agent 就是 kernel 了。所以 daemon 本身也是一個 kernel：**只要是能管理任務的 instance，就是 kernel。**

在此之上，要想的是如何更有效利用這種管理任務的方式。例如 agent 想執行某個任務：

- 它看一下這個任務可以執行，就操作自己的 ctl，用自己身為 daemon 的能力去跑它；
- 或者 agent 本身只是一個 loop，它下的指令是下給另外一個 daemon，讓那個 daemon 去管是否真的要跑。
