# r4 命令列改版（fix-r4，2026-09-24）

← [play/](README.md)｜來源：使用者親自拍板的 13 條＋「三支指令的家一律 `--target`」（分三批給）；審查：[astra](fix-r4-review-astra.md)

隊長做 agent 那一半，fork 一隊做 kernel／daemon／exec／cpu／llm 那一半；規範先改（commit b5ef5f1）再改程式（fe6394b）。
測試 1055 → 1089 條（含 astra 審查後補的 6 條），連跑兩次綠；pgrep 空。README「十分鐘上手」＋「每天重開機」照抄全跑：通，約 79 秒（修完 astra 的問題後又重跑一次，一樣通）；模型走 LiteLLM `localhost:4000`／`deepseek-chat`（使用者在打遊戲，沒碰 LM Studio）。

## 逐條

| # | 狀態 | 做了什麼 |
|---|---|---|
| 0 | 已做 | 三支指令的家都用 `--target`：先看 `--target`，再看環境變數（daemon 是 `AOS_DAEMON_HOME`、kernel 是 `AOS_KERNEL_HOME`），都沒有就用目前資料夾；agent 沒有環境變數，沒給就是目前資料夾。三支共用 `aos_home.resolve_target()` 這套找法 |
| 1 | 已做 | `AOS_K` 改名成 `AOS_KERNEL_HOME`，規範、程式、測試、README 一起改；notes 沒動 |
| 2 | 已做 | kernel 每個子命令（含 init）都不用再寫 K。退 1 的錯誤行尾巴會寫「K＝哪個路徑，取自 --target／AOS_KERNEL_HOME／目前資料夾」 |
| 3 | 已做 | agent 九個子命令都用 `--target`。改成 `say TEXT [--target DIR] [--wait [秒]]`：`--wait` 不帶數字等 300 秒（`-h` 有寫），`--timeout-ms` 拿掉 |
| 4 | 已做 | `last` 換成 `listen`，三種模式互斥：`--last`（預設）／`--wait [秒]`／`--follow`。`say --wait` 和 `listen --wait` 共用同一個等待函式 `wait_reply()` |
| 5 | 已做 | 新增 `pause`，做法是在家裡放一個 `paused` 檔：tick 看到它就直接退 0；`continue` 會刪掉它，同時解開連敗暫停的門。`status` 第一行和 `state` 行分得出「手動暫停」和「連敗暫停」；暫停中 `say` 照樣收下，但會提醒 |
| 6 | 已做 | 規範 §2.1 寫了併發怎麼分析。agent 家加 `.tick.lock`（flock 檔鎖）：第二個 tick 退 101、不動任何檔。有兩條「真的兩個程序」的測試 |
| 7 | 已做 | 裸 `aos-daemon` 印用法、退 2。daemon 家的預設不再是 `~/.aos-daemon`。`aos-kernel check`／`boot` 找 daemon 家的方式跟 daemon 自己一樣（見第 9 條） |
| 8 | 已做 | `aos-kernel init --config FILE`，`--cpu`／`--env` 拿掉；沒給 `--config` 就是用法錯，退 2。README 附了一份最小的 `kernel.json`，用 heredoc 寫出來 |
| 9 | 已做 | 指 daemon 家的旗標改名 `--daemon-target`（check、boot），找法跟 daemon 自己一樣 |
| 10 | 已做 | `aos-cpu [DIR]` 可以省略，預設目前資料夾。`aos-exec`、`aos-llm call` 本來就能省略，確認一致 |
| 11 | 已做 | 新入口 `cli/aos-llm`，子命令 `call`；刪掉 `cli/aos-llm-call`。規範改名 `spec/aos-llm.md`。think 批送出去的 argv 改成 `["aos-llm", "call", 家]`。notes 裡指到舊規範檔的連結也改了（只改連結位址） |
| 12 | 已做 | `aos-kernel stop` 改名 `halt`。kernel 內部的 syscall `stop` 沒改 |
| 13 | 已做 | `aos-daemon boot`／`halt` |

## tick 併發：查到的結論

- **同一個 kernel 不會同時派兩格**。反覆行程一派出去就從 `queue` 拿掉，要等那顆 cpu 的回音收回、判完，才排回 `queue`（kernel.md §3 第 6、8 步，§4）。所以前一格還沒回，下一格不會派，池裡有幾顆 cpu 都一樣。
- **stop 完馬上 start 也疊不出第二格**。`rm` 正在跑的那格只會標 `discard`，回音到之前，同名的 `add` 一律回 `AlreadyExists`。
- **會疊的是這四種**（都不在 kernel 的保證範圍內）：
  1. 人手動打 `tick`。
  2. 同一個家用兩個名字登記，或登記到兩個 K。
  3. cpu 被 KILL，但它跑的 tick 還活著；kernel 收到 `Interrupted` 就再派一格。
  4. 設了 `timeout_ms`，逾時被砍時子行程沒死乾淨。
- **沒鎖會怎樣**：兩格讀到同一份 state，可能各建一批、各問一次模型，誰後寫 state 誰贏；輸的那批工作留在 K 裡，沒人收、也沒人清。收輸入的時候，記憶可能被接兩次，或撞 `HistoryChanged`。
- **有鎖之後**：第 3、4 種情況裡，舊的 tick 還活著的時候，新派來的格都會退 101 讓掉。kernel 把 101 當「在等」，不算失敗，所以不會一路累積把 agent 標成 `bad`。

## 隊長裁決（替使用者定的）

1. **鎖被佔時退 101，不是 1。** 退 1 會被 kernel 算一次失敗，連續 10 次就把 agent 標 `bad`，但這不是 agent 的錯。stderr 另外有 `busy:` 那一行，分得出是鎖被佔。
2. **鎖檔放在家裡的 `.tick.lock`**，內容寫持有者的 pid，永遠不刪（刪了會出現兩把鎖）。家裡有 `info.json` 才建鎖檔，所以非 agent 家不會被亂建。順序是：先看環境變數（缺了退 2）→ 拿鎖 → 看手動暫停 → 讀驗。規範原本說「起始讀驗錯什麼都不寫」，現在補一句「鎖檔除外」。
3. **手動暫停放成一個 `paused` 檔，不放進 `state.json`。** `state.json` 只有 tick 在寫，外人去改會跟正在跑的那格互相蓋掉。
4. **`--wait` 預設 300 秒**，可以帶小數。`say --wait "你好"` 裡，緊接在 `--wait` 後面的字如果不是數字、而且還沒有 TEXT，就把它當 TEXT。
5. **兩種等法各印什麼**：
   - `listen --wait` 等「一整輪結束」才印最後那則。模型中途只叫工具的那則不算，這樣跟 `say --wait` 一致。
   - `listen --follow` 每則 assistant 都印，只叫工具的那則印成 `(tool_calls: …)`。Ctrl-C 退 0；遇到暫停或沒登記也不退出。
6. **`say --wait` 和 `listen --wait` 什麼時候立刻退 101**：先判沒登記，再判手動暫停，最後判連敗暫停。
7. **連敗暫停中 `say` 也會警告**，內容是「修好原因後 continue 才會處理」。
8. **`status` 的 health 先後**：kernel 有問題 → 沒登記 → 手動暫停（兩種暫停同時就合成一句）→ 連敗暫停 → bad → 設定讀不到。`--json` 多三個欄位：`manual_paused`、`manual_paused_since`，health 的 code 多一個 `manual_paused`；原本的 `paused` 還是只指連敗暫停。
9. **`continue` 先刪 `paused`**，就算 `state.json` 壞了也先把手動暫停解掉。`pause` 只要求家裡有 `info.json`，不讀驗內容，設定壞了也停得住。
10. **舊版 `tick.json` 自動升級**：舊版只有 `AOS_K`、argv 是位置參數。`start` 時如果舊鍵記的 K 跟現在的相同，就照新格式重寫；不同就是 `KernelMismatch`。`stop`、`status`、`say` 讀的時候也認舊鍵。
11. **`NotAnAgent` 的錯誤訊息會寫家的來源**（`--target` 還是目前資料夾）。用法錯先判，退 2 優先於退 1。
12. （fork 定、我照收）kernel／daemon 的參數解析關掉縮寫，免得舊的 `--daemon` 被當成 `--daemon-target` 的縮寫，悄悄生效。
13. （fork 定、我照收）錯誤行的來源尾巴只加在退 1 的時候。
14. （fork 定、我照收）`--config` 沒給就報錯，不去猜 `./kernel.json`。config 裡不認得的鍵照抄；寫了 `daemon` 就拒絕。
15. （fork 定、我照收）`check` 不再優先用 info 裡記的 daemon；兩者不同時多印一行 warn。
16. （fork 定、我照收）kernel 的 `tick` 不收舊的位置參數。**換版後要重新 boot 一次**，README 已經寫了。
17. （fork 定、我照收）`aos-llm` 的 stderr 前綴改成 `aos-llm: `。模組名 `aos_llm_call.py` 保留，就是 `call` 子命令的實作。
18. `aos-daemon boot` 還是前景程式，沒有自己放到背景；README 照舊用 `&` 或 `setsid`。

## astra 審查挑的（[全文](fix-r4-review-astra.md)）

他在唯讀沙箱裡跑不了測試（沒有可寫的暫存目錄），改用 mock 與 CLI 實查。挑出九條必修，**全修**：

1. `init --config` 給 JSON `null` 會落回 lib 的預設表建家 → lib 用哨兵值區分「沒給」和 `null`，`null` 退 1、什麼都不建。
2. `pool` 寫成 `$env` 時，舊邏輯看原始值判斷要不要補 `k`，會多補 → 先照原樣讀驗，過了就不補；過不了才補 `k` 再驗。規範 kernel.md §6 補了這句。
3. tick 鎖在寫 pid 失敗等 I/O 錯誤時沒關 fd，同一個行程下次 tick 會被自己擋住 → 所有還沒把 fd 交出去的失敗路徑都關掉。
4. `--wait inf`／`1e309` 會丟 traceback → 限制在 0～604800 秒，超出是用法錯 2（規範同步）。
5. `aos-kernel check` 和 `aos-agent tick／start／stop` 的錯誤沒寫家的來源 → 補上。
6. 幾個提示還是叫人打沒帶 `--target` 的指令（listen 的警告、status 的 wait 行、say 的 InputBusy、check 的 envs warn、README 的 continue）→ 都補上 `--target <家>`。
7. README 升級步驟叫人在舊版上打新版才有的 `halt` → 改成換版前用舊指令停。
8. say --wait 等待條件的幾條反例測試，因為沒登記，先被「沒登記」擋下，其實沒測到那些條件 → 改成先登記，並斷言是 `Timeout`，另加一條條件全齊就成功的對照。
9. 家裡有 `info.json` 就建鎖檔，所以 kernel／daemon 的家也會被建鎖檔，有 `paused` 甚至直接退 0 → `_metainfo._type` 字面寫著別種家的，不建鎖檔、不看 paused，`pause` 也拒絕。

「可以之後」的也順手做了：
- lib README 的 `aos-cpu [DIR]`。
- daemon.md「整個系統唯一的一把鎖」改了措辭。
- `say -h`／`kernel init -h` 的 usage 行改對。

沒動的兩項：
- 讀舊版 tick.json 的 `AOS_K` 鍵：這是故意留的相容，規範有寫。
- 規範檔尾〈調度者裁決〉裡的舊位置參數寫法：那是歷史紀錄。

**沒做**：提示指令裡的路徑沒有做 shell quoting。README 用的路徑都沒有空白；路徑含空白的情況留給下一輪。

## 沒做

- `aos-daemon boot` 沒有改成自己放到背景（任務書沒要求）。
- agent 家沒有對應的環境變數（照任務書，省略 `--target` 就是目前資料夾）。
- kernel 的 `tick` 不相容舊鏈：升級前 boot 的鏈會停住，要重新 boot。
- r4 兩份試玩報告的建議不在這一輪（調度者另開）。
