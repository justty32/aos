# r4 共同痛點修正（fix-r5，2026-09-24）

← [play/](README.md)｜來源：試玩 r4 兩份報告（[Opus](2026-09-24-r4-opus.md)、[astra](2026-09-24-r4-astra.md)）的共同痛點，調度者整理成八條；審查：[astra](fix-r5-review-astra.md)

規範先改（對應小檔：aos-agent、agent、kernel 三個資料夾），再改程式、測試、README。
測試 1100 → 1138 條（新檔 `test_agent_fix_r5.py` 25 條、`test_kernel_fix_r5.py` 13 條，含 astra 審查後補的 5 條；舊測試改了 9 處期待值），連跑兩次綠。
README「十分鐘上手」＋「每天重開機」照抄全跑：通（家放 scratchpad，只換 `W`；模型走 LiteLLM `localhost:4000`／`deepseek-chat`，沒碰 LM Studio）。跑完 `pgrep` 裡沒有我的行程。

## 逐條

| # | 狀態 | 做了什麼 |
|---|---|---|
| 1 | 已做 | kernel 健康多一種 `recovering`：daemon 孩子表裡 cpu 是 `dead`（等重拉）＝「恢復中（llm cpu dead，daemon 重拉中）」。`aos-agent status` 第一行多三種：恢復中、`重試中（連敗 N/3）`、已解除暫停（第 2 條）；恢復中排在暫停、bad 之後（暫停不會自己好，要先講）。`aos-kernel ls` 在 daemon 沒活時 cpu 行印 `dead（daemon 沒在跑）`，不再照抄孩子表裡留下的 `running` |
| 2 | 已做 | `continue` 解到連敗暫停時在家裡放一個 `resumed` 檔，印「已解除暫停，等下一次成功」；tick 在 think **成功**結清時刪它。`status` 看到它就標「已解除暫停，等下一次成功」，刪了才標「已恢復」。舊錯那行改成 `last-error  （已恢復） 時間  短版`；短版去掉 `aos-agent: ` 前綴、舊 `touch … 繼續` 改寫成 `aos-agent continue --target …`、批次名縮成 `aw-…`、超過 120 字截斷；`-v`／`--json` 是原文。新的 stuck 行本身也不再叫人 touch |
| 3 | 已做 | `listen --last`：這一輪還沒走完（印的那則帶 `tool_calls`、後面還有訊息、不是 idle、有批次或沒收的輸入）就在 stderr 加「還在處理中（tool_calls: …）」或「還在處理中（新輸入還沒回）」；一律附一行 `aos-agent: time: 月-日 時:分:秒`（記憶檔的修改時間） |
| 4 | 已做 | `start` 撞 `AlreadyExists` 時再讀一次帳本：就是這個家、沒被 rm、不是 bad＝印 `already started agent-bob`、退 0。其他三種仍退 1，但訊息補一句原因 |
| 5 | 已做 | `aos-kernel check --probe`：每個模型設定（endpoint＋model＋金鑰一樣的只打一次）先 `GET /models`，404／405 就改問一句話（`max_tokens: 1`）；連不上＝bad。最後一行總結：沒 `--probe` 寫「設定檢查通過；未測模型連線（--probe 會測）」 |
| 6 | 已做 | 沒登記的 `say`：stdout 多一行「已投入，start 後會處理，不要再說一次」。`say --wait`／`listen --wait` 每輪（含開始前）看 health：kernel 家有問題（缺目錄、停機、daemon 沒活、cpu missing、tick 停住、帳本讀不到）、沒登記、手動暫停、連敗暫停、被判 bad，都立刻退 101 並印原因；`say --wait` 另說「已投入 …，不要再說一次」 |
| 7 | 已做 | `aos-agent continue --all`：從 `AOS_KERNEL_HOME` 帳本找 `agent-*` 反覆行程、target 是某個家的 `tick.json`，逐個解，每個印一行，最後 `continued 解了幾個／共幾個`。`aos-kernel ls` 的 agent 行尾標 `連敗暫停中`／`手動暫停中`／`重試中（連敗 N/3）`／`已解除暫停，等下一次成功`；kernel 本身沒事時，第一行也改講 agent（`agent 暫停中：…（aos-agent continue --all）`） |
| 8 | 已做 | `boot` 成功印 `booted <N> cpus`；`NotAnAgent` 碰到別種家直接說「… 是 kernel 家，不是 agent 家」（`tick` 讀驗的訊息也改）；`init` 在非空又不是 agent 家的資料夾退 1（`NotEmpty`，列出已有的檔），加 `--force` 才生；README 第 4 段補「agent 多了要多開 cpu」、第 6 段改成「`log/agent.err` 不會有這一行」 |

## 實際跑出來的（照抄＋三樣實驗）

- **照抄**：第 1～4、6 段、附錄 amy、第 5 段停機、每天重開機，全部照 README 字面跑過。`check --probe` 印 `ok probe/default: endpoint 通，模型清單裡有 deepseek-chat`；`boot` 印 `booted 4 cpus`；`say --wait` 約 15 秒拿到時間、add 工具回 `5555`。
- **沒停就關機**：`kill -9` daemon 與全部 cpu 後，`ls` 第一行「daemon 沒在跑」、cpu 行全是 `dead（daemon 沒在跑）`。再照「每天重開機」在 `set -e` 子殼裡跑：`start` 印 `already started agent-bob`、退 0，沒斷。
- **port 改壞**（兩個 agent 同時在說話）：`check --probe` 立刻 bad。第一行依序是 `重試中（連敗 1/3）` → `重試中（連敗 2/3）` → `連敗暫停`；`ls` 第一行從 `重試中：agent-bob（連敗 1/3）、agent-alice（連敗 1/3）` 走到 `agent 暫停中：agent-bob（連敗）、agent-alice（連敗）（修好原因後 aos-agent continue --all）`。暫停中 `say --wait` 立刻退 101，並說「已投入 …，不要再說一次」。修好 port 後 `continue --all` 印兩行「解除連敗暫停（等下一次成功）」＋`continued 2／2`；第一行變「已解除暫停，等下一次成功」，約 3 秒後問成功才變 `ok`，舊錯行變 `（已恢復）`。
- **llm cpu `kill -9`**：`ls` 與 `status` 第一行都是「恢復中（llm cpu dead，daemon 重拉中）」，約 1 秒後回 `ok`；在途那句自己重問、`listen --wait` 拿到回話。
- 另外看到：`listen --last` 在中途印 `(tool_calls: date)` 時附「還在處理中（tool_calls: date）」；新話還沒回時附「還在處理中（新輸入還沒回）」。搬走 `K/requests/` 後 `say --wait` 0.05 秒就退 101、印 K 家缺目錄。`status --target K` 說「是 kernel 家，不是 agent 家」；`init` 在有 `a.txt` 的資料夾退 1 要 `--force`。

## 隊長裁決（替使用者定的）

1. **`init` 選「拒絕＋`--force`」**，不選「警告後照生」：照生之後才警告就來不及了。空資料夾、不存在的資料夾照舊直接生；`info.json` 已在的，`--force` 也不覆蓋。
2. **「已解除暫停」落成一個 `resumed` 檔**（**先放 `resumed` 再建門檔**：門開之前 tick 不會重問，所以成功後刪它一定排在後面，不會被蓋回去；門檔已在就不再放）（跟 `paused` 同一招），不放進 `state.json`：`state.json` 只有 tick 在寫。只有解到**連敗**暫停才放；只解手動暫停不放（手動暫停不是失敗，沒有「等成功」可言）。
3. **tick 只在 think 成功結清時刪 `resumed`**。再失敗就顯示「重試中」／「連敗暫停」（比「等下一次成功」優先）；崩在寫 state 與刪檔之間，只是多標一陣子，下次成功再刪。
4. **health 的先後**：kernel 有問題 → 沒登記 → 手動暫停 → 連敗暫停 → bad → 恢復中 → 重試中 → 已解除暫停 → 設定讀不到 → ok。恢復中與重試中會自己好，所以排在「要人動手」的後面。
5. **`ls` 第一行講 agent**：kernel 本身沒事時才講（kernel 壞了先講 kernel）。這幾個 code（`agents_paused`／`retrying`／`resuming`）只在 `ls`，`aos_kernel_health.health()` 本身仍只管 kernel，`aos-agent status` 不受影響。
6. **`--wait` 的 kernel 檢查每輪都看**，不只開始前看一次：K 等到一半壞掉也該馬上講。恢復中、重試中不退（會自己好）。`listen --wait` 沒投話，不印「已投入」。
7. **回話時間放 stderr**（`aos-agent: time: …`），stdout 照舊只有回話本身，`--json` 也不加欄位：有人會把 stdout 接進別的程式。時間是記憶檔的修改時間；印的不是最後一則時註明「這則更早」。只加在 `--last`（`--wait`／`--follow` 印的本來就是剛到的）。
8. **「還在處理中」的訊息**：帶 `tool_calls` 的一律算中途那句（就算還附了「讓我查查」）；已經有暫停／門關著的警告時不再疊這句。
9. **`start` 已登記**：只有「帳本那筆的 target 就是這個家的 `tick.json`、沒有被 rm 還在跑、不是 bad」才退 0；其他 AlreadyExists 照舊退 1，但補一句是哪一種。
10. **`check --probe` 先打 `/models`**（不花 token、不需要模型真的回話）；清單裡沒有這個模型只給 warn（有些代理不列全）；404／405 才退回問一句話。每個請求最多 10 秒。
11. **`continue --all` 認帳本**，不去掃資料夾：只救「登記在這個 K 的」agent。跟 `--target` 一起給＝用法錯；有 agent 的 state 讀不了就跳過它、最後退 1，其他的照救。
12. **stuck 行改寫**：新寫的 stuck 行直接是「修好原因後 aos-agent continue --target …」；舊 agent.err 裡的 `touch … 繼續` 在一般 `status` 顯示時改寫，`-v`／`--json` 保留原文。
13. **「已投入」的字**：調度者給的是「已投入 intake…」，我改成「已投入，start 後會處理，不要再說一次」——`intake` 是內部欄位名，使用者看不到它。

## astra 審查挑的（[全文](fix-r5-review-astra.md)）

唯讀沙箱跑不了測試，他改用讀碼與 mock。挑出六條必修，**全修**：

1. `continue` 先建門檔、最後才放 `resumed`：中間若停頓，tick 可能已經問成功、刪過標記，`continue` 再把它放回去，就一直卡在「等下一次成功」（`--all` 同病）→ 改成先放 `resumed` 再建門檔；門檔已在（上次 continue 過）不再放。規範 §1.4 補這個順序，加一條測試驗先後。
2. `status` 收資料時就把舊錯截成 300 字，`-v`／`--json` 拿不到原文 → 收原文，只有一般輸出縮短；補 400 字的測試。
3. `listen --last` 取到帶 `tool_calls` 的那則、但 state 已經是 idle 時不警告 → 帶 `tool_calls` 本身就算「還在處理中」；補測試。
4. `check --probe` 對空的模型清單回 ok → 清單讀得懂就一律比對，空清單＝warn；補測試。
5. `check --probe` 遇到回覆中途斷掉（`IncompleteRead`）會噴例外 → 接住轉成 bad；補一個只傳一半的假伺服器測試。
6. README 第 6 段叫人用 `listen --follow` 看工具錯誤，但 follow 只印 assistant → 改成看 `prompts/history.json`，註明 `listen` 只印 assistant 的話。

「可以之後」的兩項也做了：測試名稱不再宣稱驗了遮金鑰（實際沒驗到）；lib README 的 listen／say 摘要補上本輪新行為。

## 沒做

- 路徑沒做 shell quoting（上輪就記的，這輪沒動）。
- `aos-daemon boot` 還是前景程式（沒要求）。
- `--wait`、`--follow` 印回話不附時間（見裁決 7）。
- `say` 不帶 `--wait` 時，kernel 家有問題不另外警告（只有 `--wait` 會看）。
