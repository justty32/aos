← [在 `aos exec` 上做一條會動的 agent loop](../agent-loop.md)（分檔 13/24）｜所在：第 1 輪評分與意見｜[上一份](12-p3joe-armstrong.md)｜[下一份](14-三哪條路最值得繼續走.md)

### 二、`aos agent` 該收掉什麼——有優先序的清單

這是本節最重要的一塊。排序的判準只有一個：**拿掉它會不會死。** 會花錢、會靜默掉資料的排前面；只是打字多的排後面。每一條都指到證明它值得收的那段輸出。

**P0 — 會花錢或會靜默吃掉資料的，只有這兩條**

**1. 崩潰現場的可判定性 ＋ 復原（`aos exec` 在 fork 前落盤 running marker ＋ 一支唯讀的 `recover`）。**
這是本輪唯一有**實際金額**的一條，四位獨立撞到，三位量到重複計費：Armstrong 的 `thread#1` / `thread#2` `DIFFERENT -> DOUBLE BILLED`、Carmack 的 `total_model_calls=4` 與 31,316 input token、Evans 的 `session-ids.txt` 從 1 變 2。Pike 的貢獻是反面的、同樣有力：他看穿之後**拒絕動手**，「我沒有一個安全的動作可以做」。
**為什麼非收不可**：這是唯一一件**世界內部寫不出來的事**。另外三條（模板、投遞、狀態）四位都用 shell 寫出來了；這一條 Armstrong 用 `test -f final.json` 寫了，然後**輸給了 race**，而那個 race 的窗口等於一次模型呼叫的長度、好幾秒。marker 必須由 `aos exec` 在 `fork` 之前寫，因為只有它在那個時間點上。
**注意這句話的代價**：這一條是 `aos exec` 的 C++，不是一支新子命令。**T5 那句「整個 loop 可以完全不含新 C++」對「跑」成立、對「救」不成立**，而在無人看管又要花錢的前提下，救不是可選的。

**2. 投遞前驗證（`aos deliver --check`，或任何一個「只驗證不執行」的入口）。**
證據是 Evans 的兩組對照：`nuke_everything` 在**投遞前**被他自己的 registry 擋下 → 錯誤變成 `[tool]` 餵回模型 → 下一回合模型改口；`{"path":123}` 在**投遞後**被隔離成 `.bad` → warning 進 stderr → `aos exec` 每次都回 0 → loop 靜默死亡。旁證是 Carmack：他的 `deliver.sh` 投遞前用 `jq -e .` 驗過一次，**整場沒有出現過任何 `.bad`**。
**為什麼是 P0**：它把「loop 悄悄死掉」變成「模型自己修好」，而成本是一次 parse。目前的缺口很具體——Evans 指出 aos 沒有任何「只驗證不執行」的入口可以給腳本用。

**P1 — 四位都重寫過的，收掉省的是打字和打錯**

**3. `aos status --json`（含 `--loop` 的停止條件）。**
Evans：`exit=0` 同時代表回合跑完、無事可做、模型正常結束、模型參數型別錯誤導致投遞被丟掉——**四種處境一個碼**。Pike 的對照更狠：模型講錯工具名和模型宣布任務完成，**產生一模一樣的可觀測結果**（inbox 空、exit 0、世界靜止）。三位各自發明了 sentinel 檔（`DONE`／`state/DONE`），`aos` 一個都不認得。Pike 走到底發現終止條件只能放在世界外面的行程裡，還得先把 driver 的 PID 寫進世界——他的 `空轉=10s` 對照 `空轉=0s` 兩組時間戳就是這條的價碼。

**4. 回合模板 / `aos agent step`（「下一批要跑什麼」只寫一次）。**
四位全中，而且有行號：Evans 的 `grep` 印出三個檔一字不差；Carmack 的 `grep -rln "render-prompt.py"` 印出三個檔、**兩種語言**（shell heredoc ＋ Python dict literal）；Armstrong 3 次；Pike 2 次兩種語法。
**關鍵在 Pike 那句**：「不是我懶，是沒有第二種寫法」——他實測 `$ref` 拼不了 batch。**這條的價值不只在省字，在於它證明了現有指示詞解不掉它。**

**5. pipeline stage 的檔名生成。**
Pike 手打 39 次 `run/<站名>.<out|err|exit>`，並且漏過一次 `stderr` 導致 `put` 的診斷噴到終端機；Armstrong 6 次以上，說「每一筆 instruction 都要抄一遍」。
**但我要標一個但書**：39 這個數字是 Pike 七站管線的架構屬性，不是 aos 的屬性——Carmack 與 Evans 的架構只有個位數。所以這條真的存在，但**它的大小取決於你怎麼切**，不要拿 39 當普遍價碼。

**P2 — 真的重複，但繞得過或已經半解決**

**6. `aos deliver`（temp+rename ＋ 防碰撞檔名）。**
四位都重新發明了一次。**但我站 Pike 這邊**：它是 13 行，任何人寫一次就好。真正該收的不是 temp+rename，是**那個 counter**——三位明講他們寫成 `$$-<counter>` 是因為讀過上一份實測，知道只用 PID 會互蓋。Evans 講得最準：「每個寫 agent loop 的人都要重新發明一次這個 counter。」也就是說，**這是一個只有讀過前人現場的人才躲得掉的陷阱**，那才是收掉它的理由。順帶一提，規格第十二節自己就寫著投遞沒有實作，所以這條是**已知開口被確認了四次**，不是新發現。

**7. 宣告式的 tool registry（name → argv 的表，由 aos 查）。**
證據是一組漂亮的對照：Pike 的整個 registry 是 `[ -x "tools/$tool" ]`，然後 `echo 'TOOL ../../../../../../../../usr/bin/id -un'` 就跑到了 `/usr/bin/id`、`tool.out=[lorkhan]`；Evans 寫了具名 registry，`nuke_everything` 被擋下並餵回模型。Pike 自己的結論才是重點：「**每一個照著 T5 這條路做 agent loop 的人，都會在第 3 次轉換這裡自己發明一次 registry，而且都會發明錯的那一種。**」
**降到 P2 的唯一理由**：`aos tooljson` 已經存在、`libaos_tooljson.so` 就在旁邊，Pike 與 Evans 都看到了、都沒接。**在有人真的去讀它之前，我不同意為這條開新規格。**

**8. adapter 契約（抽最後一則 ＋ 取 session id）。**
Evans 三支各一次、三個都不一樣，並排貼了三段 jq。他自己的判斷是對的：**這收不成子命令，它本質上是廠商差異**，能收的是「一份 adapter 契約 + 三份設定」。優先序低，因為它不會靜默壞——寫錯了會大聲壞（除非你踩到他那個 `jq` 串流陷阱）。

**9. `emit-context` / 回程的型別。**
Armstrong 一個人指出的不對稱：去程有 `--output-schema`、回程只有 `sed -n '1,60p'` 加手拼的 `=== HISTORY ===`。Carmack 獨立撞到同一面牆（四個檔名在兩支腳本裡各約定一次）。真的，但重寫次數只有 2，痛的是形狀不是錢，排最後。

**明確不要收的**

- **不要為了 LLM 往 instruction 加欄位。** Carmack：`stdin`／`stdout`／`stderr`／`exit`／`timeout_ms` 五個欄位剛好夠包一支 agent CLI，四位包了三支不同廠商的 CLI，**沒有一個人需要 schema 以外的東西**。這是一個很強的負面結果，應該直接寫成規則。
- **不要為了效能動 `aos exec`。** 0.4 秒 / 22 秒，其中還含 `--loop 200` 的輪詢間隔。

---
