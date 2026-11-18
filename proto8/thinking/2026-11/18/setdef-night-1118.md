set-def 走 kernel 格滿時的修法、cooldown 兩小題、套 kit 後 tools ls 的誤導提醒：使用者 11-18 晚三個裁定照做的結果（線 setdef-night-1118）。

← [11-18](README.md)｜起因：[verify-night-1118 件 1](verify-night-1118.md#件-1set-def-走-kernel-排隊)、[cooldown-1118 交接](交接-各線/cooldown-1118.md)、[aos-kit-併進ctl](aos-kit-併進ctl.md)

## 使用者裁定（11-18 晚選項框）

- set-def 格滿那題（甲／乙／丙）：選「**信帶等待期限**」＝丙。set-def 的掛回信帶等待期限，逾時由 kernel 直接拒掉、不會晚到；錯誤行的手動掛回指令補上 `-d`（名字不在 kernel 允許名單那種也一樣）。乙（停著／睡著的不算一格）沒選，所以停著、睡著的在格滿時照樣失敗，只是不會晚到。
- cooldown 兩小題：選「**前綴補回、清單只限 set-def (Recommended)**」。
- 套 kit 後 `tools ls` 那行「是不是從別隻抄來的」提醒：讓它在套 kit 的情況下不出現。

## 結論

**A. set-def 的掛回信帶期限。** kernel 本來就有寄件人期限 `queue_wait_ms`（add／start／wake 的 `--on-queued fail` 在用），沒有另加欄。set-def 掛回那封（`procs_added`）現在也帶 `queue_wait_ms`＝`--timeout-s`：站的格滿、信進隊，期限一到站就回 `SlotMissing`，set-def 報 `SlotMissing queued … ms, no slot freed …`，之後騰出格也不會再套上。錯誤行的手動指令改成 `aos-agent -d <daemon> ctl add …`。

順手修的一個舊毛病（沒修 `-d` 提示就沒用）：`aos-agent -d D ctl …` 讀表是直讀 D，但控制信在 `AOS_KERNEL` 設著時還是寄給 kernel（`daemon_ctl.mailbox_of` 沒給 `direct`）。現在明給 `-d` 就寄 D 自己的 ctl 信箱、也不印 `routing via AOS_KERNEL`，跟 README「明給 `--daemon` 就指名那一台、不問 kernel」一致。

**B. cooldown 兩小題。** listen／ask 的問腦失敗照 `2b4320644` 之前的做法：一律讀 stderr 結尾的錯誤行（停下的取往上連著最多三行、重送中的取最後一行），所以又帶程式名前綴與 aos-llm 原話。`cooldown.json` 的 `retry`／`error` 兩欄、fsm 與 eca 寫欄、`ctl ls` 帶欄都留著。延後關畫面的到期單（`screen_close.json`）改成只有 set-def 清（拔掉之後、掛回之前），`aos-eca-screen close`、`ctl rm`、`aos-agent close` 不再清。

**C. 套 kit 後 tools ls 不再問「是不是抄來的」。** 判法：stack 那份的 `$override` 指的全是出廠工具包（`lib/packs/`）就不印，因為 kit 的 tools.json 直接疊在工具包上；指到別的定義那份照樣提醒。

## 實測（家機，`f275cccca` 的 clone 加本線改動，暫存 `~/.aos/scratch/setdef-night-1118/`，沒刪）

- 重現（改前）：新加的測試在 kernel 站 `max_running` 滿、`queue` 開時，跑著／停著／睡著三種都報 `DaemonFailed … could not withdraw it; it may still be applied`（跟 verify-night 1b 一樣）。
- 改後：同三種都報 `SlotMissing`、站的 `queue.json` 是空的；照錯誤行原樣打（殼裡還設著 `AOS_KERNEL`）掛得回去；再把格放寬、停掉別隻，等 1.5～3 秒，手動掛回的那隻還在跑、定義沒被換。暫存樹（`templates/start-eca`，eca-claude）也手跑一遍：三種格滿、名字不在 `allowed`、有空格的三種、停著開畫面後 set-def 清掉到期單、`aos-agent close` 不清、套 gather kit 後 `tools ls` 不再印那行。沒問過真腦。
- 小事（沒動）：停著／睡著的掛回失敗後，照錯誤行手動 `ctl add` 會變成跑著（提示沒帶 `procs_stopped`），跟以前一樣。
