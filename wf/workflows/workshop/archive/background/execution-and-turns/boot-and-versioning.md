# 名詞表：回合開頭的固定步驟與版本
← [名詞表：回合、執行與喚醒](README.md)｜[BACKGROUND](../../BACKGROUND.md)｜[workshop](../../README.md)｜[待答問題](../../OPEN-QUESTIONS.md)

每回合開頭由執行器（而非上一回合自己）套上的固定步驟、扮演者名單，以及它們怎麼一起版本化。

### `kernel.json`（核心序言／尾聲描述檔）

**白話**：每批作業前後都必須跑的固定步驟，不靠上一批作業自己把它再塞回去。
**嚴格**：版本化的 per-world kernel descriptor，由 executor 在 claim 一批後合成 prologue＋業務 batch＋epilogue；本地完整檔或分層合成仍未定案。
**在 aos 裡具體是什麼**：目前還不存在 `aos-folder` 或程式中；使用者已表態「kernel.json 收」，但檔案內容、失敗邊界與升級機制尚未拍板。
**為什麼會冒出這個詞**：[核心行程場](../../records/core-process-and-subprocess.md) 四位都指出「尾指令自我複製」會因 crash 斷鏈或重跑增殖，所以提出類 init(1) 與 reset vector 的版本化開機流程。

### init(1) 與 reset vector

**白話**：一個是系統啟動後固定先起來的管理者，一個是處理器剛開機時固定從哪裡開始跑；都不靠上次工作自我複製。
**嚴格**：`init(1)` 是傳統 Unix 的第一個 userspace process 與服務生命週期根；reset vector 是 CPU reset 後的既定取指位置。這裡只借「啟動入口由機器保證」的直覺。
**在 aos 裡具體是什麼**：沒有 `init(1)` 或硬體 reset vector；對應的提案是 `aos exec` 每回合都從 `kernel.json` 取得序言／尾聲。所以可以照那個直覺理解，但差別是 aos 是回合級、不是開機級。
**為什麼會冒出這個詞**：[核心行程場](../../records/core-process-and-subprocess.md) 用它們解釋為何「永久序尾」應由 executor 套用，不是由尾指令重生自己。

### 角色表（role table）與 `boot.json`

**白話**：一張「誰扮演哪個角色」的名單——上面寫「收件的是誰、下單的是誰」，而不是把那個人的名字直接抄進每天的工作清單裡；名單可以改版，抄進清單裡的名字改不掉。
**嚴格**：per-world 的間接層，把「哪支程式扮演 aggregate／claim／release／deliver」從 instruction 內容裡抽出來，由 executor 在回合開頭讀取並直接 execve、不經 `inst.json`；提出者主張它與 `kernel.json` 是同一張表，且應納入 `.aos/version` 的版本化範圍。
**在 aos 裡具體是什麼**：**提案，目前不存在**（`kernel.json` 本身也還不存在）。候選形狀包含 `"aggregate": "@self"` 這種預設值、`aos world kernel set` 這種修改入口，以及「內建預設編進執行檔、外部檔只在存在時覆蓋」的雙層寫法。
**為什麼會冒出這個詞**：[純 CPU 場](../../records/exec-as-pure-cpu.md) 同時要解兩件事——bootstrap 悖論（彙整若自己也是一筆 instruction，就得先被彙整才跑得起來），以及「argv 字串一旦寫進 instruction 就變成磁碟格式、永遠收不回來」。

### 單一執行檔多子命令（busybox applet）與 `/proc/self/exe`

**白話**：像一把瑞士刀，很多工具長在同一把刀身上，換的時候整把一起換，不會出現「刀身是新的、開瓶器是舊的」；`/proc/self/exe` 則是「我這支程式自己的檔案在哪」，照著它叫自己就不會不小心叫到機器上另一份舊的同名程式。
**嚴格**：把多個子命令編進同一個 binary、以 `argv[0]` 或子命令字串分派（busybox 的 applet 模型），使全部子命令共用同一次 build 與同一個版本；驅動器注入 `/proc/self/exe` 而非依賴 PATH 解析，可排除同一台機器上多份安裝造成的版本錯配。
**在 aos 裡具體是什麼**：子命令分派**已存在**（`aos exec` 就是），一次 `cmake --build` 之後全部落在 `build/bin/aos`；但「機制那幾支也做成子命令、且由 executor 注入 `/proc/self/exe`」與 `aos --list-core`（對照 `busybox --list`）都是**提案，目前不存在**。
**為什麼會冒出這個詞**：[純 CPU 場](../../records/exec-as-pure-cpu.md) 三位獨立地把「都算 core」讀成同一個答案——**同一支執行檔、同一次 build、版本一起走**，而不是同一個 repo 裡的幾支散裝執行檔。
