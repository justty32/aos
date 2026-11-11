# kernel 回歸「資源管理＋排程」：從寄件人看進去的身分、一律寄 AOS_KERNEL、判官收進通用框架（11-11，只釐清概念）

← [2026-11-11](../README.md)｜[thinking](../../../README.md)｜原話與經過 [01](01-原話與經過.md)｜現況查核 [02](02-現況查核.md)｜過時清單與日後清單 [03](03-過時清單與日後清單.md)｜前情：[10-15 general-kernel](../../../2026-10/15/general-kernel.md)、[11-05 kernel-daemon](../../05/kernel-daemon/README.md)、[11-07 kernel-nest](../../07/kernel-nest/README.md)｜條文：[C-47](../../../../docs/CONCEPTS/04-kernel.md)、[N-42](../../../../docs/NORMS/09-kernel.md)、N-63 [01](../../../../docs/NORMS/10-基礎設施-定義與工作區/07-hub-型環境變數與父子交代/01-N-63-三件事與跟實作對不上的.md)／[02](../../../../docs/NORMS/10-基礎設施-定義與工作區/07-hub-型環境變數與父子交代/02-N-63-實例-AOS_DAEMON與沒有AOS_HUB.md)｜文件：[kernel/docs/02-kernel-modes](../../../../kernel/docs/02-kernel-modes.md)

> **狀態：只釐清概念，沒有排任何施工**；沒改程式、沒改 CONCEPTS／NORMS 條文（條文改寫是之後的事，使用者還沒排）。會變成過時的條文與文件只列在 [03](03-過時清單與日後清單.md)，沒去改。使用者原話（一字不改）與每段頂層推出什麼在 [01](01-原話與經過.md)。

## 結論（白話）

1. **kernel 的定義回歸初始：「資源管理＋排程」**。而且 kernel 是**從外面看進去的身分**：你有個請求（掛 proc 或其他 syscall），你把它寄到哪，那裡對你就是 kernel——因為收到之後要不要處理、什麼時候執行，是對方說了算（「啥都不管也是一種管理」）。收件的 proc 自己不必知道自己是 kernel；只會處理掛 proc 或只會處理 llm call 的都算，不太限制。
2. **一律寄 `AOS_KERNEL`**：像 Linux 的 user space proc 只看得到 kernel、看不到硬體，一般 proc 寄請求只寄 `AOS_KERNEL`，寄出去之後背後是黑盒子，不管信會去哪。**`AOS_KERNEL` 沒設就走 `AOS_DAEMON`，兩個都沒設＝報錯**（代表你沒辦法用 syscall）。
3. **多種 syscall**：有一個通用的基礎 kernel（像 Linux kernel），普通的掛 proc 請求都去它那；但 aos 有多種 syscall，有些 syscall 走另一個 kernel（例：問腦走 `AOS_LLM_KERNEL`，兩個變數維持分開）。
4. **鏈是自然形成的**：agent→kernel_1→kernel_2→…→daemon，中間站可以本身也是一台 daemon（loop 裡有 kernel 功能）。站與站之間一律走 aos-post；**共通的只有 aos-post 信封，請求放在 body、body 裡各類自理、不多做限制**。鏈上的站不必有「鏈」的概念，只知道這份請求的 src／dst、自己做點處理；格式日後有需要再改。
5. **回信怎麼走看各站設定**：靠信封上既有的 `reply_to`，每站轉寄時二選一——不動它＝回信跳過我；改成我自己＝回信先回我。不記走過哪些站、不帶最初寄件人，所以後站無法跳過已把回信位址改成自己的前站。風險使用者自擔。
6. **安全的保底是 Linux 本身**（使用者、權限）；非正規操作的風險由使用者自行承擔。人也改用 kernel；想直接碰 daemon 或更深的 kernel，靠 Linux 權限。
7. **狀態位址用問的，不用 symlink**：「狀態在哪」是又一種請求信；aos 體系不硬性依賴 symlink。
8. **通用 kernel 框架**是一包方便零件（收信、規則＋hook、下一站、回信、排隊），不是概念——手寫一個也算 kernel。現有判官（`lib/aos/judge`）以後收進這個框架。

## 裁定（選項框，使用者選的；引號內是選項文字）

| 段 | 題 | 裁定 |
|---|---|---|
| (2) 鏈 | 判官的下一站寫在哪 | 「寫進 judge.json」（沒寫照舊寄給 `AOS_DAEMON`） |
| (2) 鏈 | `max_running` 在下一站不是 daemon 時 | 「數量另外指一台」（沒寫且下一站不是 daemon 時設了 `max_running`＝報設定錯） |
| (2) 鏈 | 判官 hook 時機 | 三個都要：「判決前」「判決後」「回信經過時」（最後一個只在選了回信先回我時才有；沿用 agent 的 hook 契約） |
| (2) 鏈 | daemon 收到壞的掛 proc 信 | 「改成會回」（`applied:false` 加原因） |
| (4) 定義 | 一般 proc 讀狀態 | 「kernel 給一個狀態位址」 |
| (4) 定義 | 問腦要不要也走 `AOS_KERNEL` | 「維持兩個變數」 |
| (4) 定義 | `AOS_DAEMON` 還傳不傳給一般 proc | 「照傳，約定不用」 |
| (4) 定義 | 11-05「判完自己 fork 去跑的不算 kernel」 | 「整句刪掉」 |
| (5) syscall | aos-daemon-ctl | 「維持直寄，它就是『指名 daemon』的工具」 |
| (5) syscall | 問來的狀態位址要不要記 | 「工具自己決定」 |

(2) 的四題依 (7) 收尾的解讀（頂層的解讀）是**通用框架要有的能力**，不急著改在現有判官身上。(3)「骨架一份、問腦＝骨架＋專屬那包、翻掉 10-16 兩支不併」是頂層的理解，使用者未明確確認、後續發言方向一致。

## 頂層列過、使用者沒回的

- 寄信（mailbox）與時鐘算不算資源、要不要過 kernel——頂層傾向不算，歸 Linux 權限管。使用者沒回；照[他的通則](../../../../../wf/workflows/common/user.md)（沒回答的邊緣狀況不追問、不列待辦），只留在這裡。

## 順帶

- WSL 的 `proto8/impls/` 底下兩個未追蹤的 `aos-kernel-llm/`、`aos-gate/` 是 10-30 改名前的舊建置產物（只有 `bin`、`lib`、`build`），可以刪，待使用者點頭；這次沒刪。
