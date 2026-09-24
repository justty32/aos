← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 2. 一次 `tick` 的順序

0. （09-24 fix-r4 補）`AOS_KERNEL_HOME` 沒設或不是絕對路徑＝退 2。家裡沒有 `info.json`，或 `info.json` 字面寫著別種家（`_metainfo._type` 是字串但不是 `llm_agent`，例如 kernel、daemon 的家）就直接到第 1 步（會是 `NotAnAgent`，不建鎖檔、不看 `paused`）；`info.json` 讀不懂的照常拿鎖（壞設定的家也要能暫停）。
   否則拿 **tick 鎖**（§2.1）：拿不到＝stderr `aos-agent: busy: 另一個 tick 正在跑（pid <N>），這格不做事`、**退 101**、不動任何檔。
   拿到了再看**手動暫停**：家裡有 `paused`＝什麼都不做、退 0（§1.6）。
1. 讀驗 `info.json`、`state.json`、記憶、工具檔（[agent.md](../agent/README.md)）。不過＝退 1，**什麼都不寫**（第 0 步的鎖檔除外）。
2. `consuming` 非空 → 逐對照 [agent.md §4.4](../agent/state.md) 的搬法搬（`dst` 在就不碰 `src`）→ 寫 `consuming: []`。
3. 清檔（§10），盡力做，K 的帳本讀不到就跳過。
4. 看門（§3）。沒開＝退 101。
5. `batch` 不是 `null` → 收回（§6），全收齊就接著結清（§7）。不管 `state` 是什麼，有批先收批。
6. `batch` 是 `null` → 照 `state`（§4）。

第 2 步以後崩了，下次從第 1 步重來；每一步做到一半都能照 `batch`／`intake`／`consuming`／`sweep` 接下去。

## 2.1 同時兩個 `tick`（09-24 fix-r4 補）

**kernel 自己不會同時派兩格**：反覆行程派出去時就從 `ready` 拿掉、`status=running`，要等那顆 cpu 的回音收回來、判完（[kernel.md §3 第 6、8 步，§4](../kernel/tick.md)）才回 `ready`；
所以前一格 `aos-agent tick` 還沒退出，同一個 kernel 下一格、下下格都不會再派它——不管池裡有幾顆 cpu。`stop`（`rm`）正在跑的那格只標 `discard`、行程紀錄留著，
回音到之前同名 `add` 一律 `AlreadyExists`，所以「stop 完馬上 start」也不會疊出第二格。kernel 的格本身也同時只准一格（daemon 只開一格、再加 `K/.tick.lock`，[kernel §7](../kernel/no-overlap.md)；2026-09-24 one-boot 改，以前靠那一顆 kernel cpu）。

**會疊的來源**（都在 kernel 的保證外）：
1. 人手動打 `aos-agent tick`，剛好 kernel 派的那格也在跑。
2. 同一個家用兩個名字登記（手動 `aos-kernel add` 那份 `tick.json`），或登記進兩個不同的 K。
3. cpu 被 KILL、它跑的 tick 還活著（[cpu.md §5.3](../cpu/stop.md) 的保證外）：kernel 收到 `Interrupted` 就把行程排回 `ready`、再派一格，舊的那格還在跑。
4. kernel 的 `timeout_ms` 不是 0 而 tick 剛好超時被砍、子行程沒死乾淨（同上，保證外）。

**沒有鎖時會怎樣**：兩格讀到同一份 `state.json`，各自以為輪到自己——例如都在 `think` 就各建一批、各放一次單（模型被問兩次），誰後寫 state 誰贏，
輸的那批的工作在 K 裡沒人收、沒人 ack、`work/` 檔沒人清；都在 `idle` 就可能各搬一次輸入、記憶被接兩次或撞 `HistoryChanged`。崩潰恢復的設計只防「同一格重做」，不防兩格同時做。

**所以上鎖**：`tick` 在第 0 步對 `<家>/.tick.lock` 拿**非阻塞的獨占 flock**（同 [daemon.md §6.1](../daemon/lifecycle.md) 的 `.daemon.lock` 做法），拿到就把自己的 pid 寫進去（覆蓋舊內容），**持到退出**；行程死了鎖就自動消失，沒有「鎖沒人解」。
拿不到＝另一個 tick 正在跑：讀鎖檔裡的 pid（讀不到印 `pid 不明`）、stderr 一行 `aos-agent: busy: 另一個 tick 正在跑（pid <N>），這格不做事`、退 **101**、不動任何檔（鎖檔早就在，開它不算動）。
退 101 而不是 1：kernel 把 101 當「在等」、不算失敗（[kernel.md §4](../kernel/echo.md)），被擋下的那格不會累積 `fails` 把 agent 推到 `bad`；上面第 3、4 種情況裡，舊的那格還活著時新派的格就一直這樣讓掉，直到舊的退出。
鎖檔不刪（刪了會讓等鎖的人跟新建的檔各拿一把）；`.tick.lock` 不是 `.json`，不會被當成輸入。
只有 `tick` 拿鎖；`start`／`stop`／`say`／`pause`／`continue`／`init`／`listen`／`status` 只投檔或只讀，不拿。人要手改 `state.json` 可以借這把鎖：`flock <家>/.tick.lock -c '<改的指令>'`（這期間 kernel 派來的格會退 101）。
flock 只在同一台機器的本機檔案系統上算數（同 [cpu.md §8](../cpu/README.md) 的範圍）。

# 12. `tick` 的退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 這格做了事：收輸入、送一批、收到新回音、結清（含問模型失敗、連敗暫停）；（09-24 fix-r4 補）手動暫停中（什麼都沒做） |
| 101 | 在等：門沒開；（09-24 fix-r4 補）拿不到 tick 鎖（另一個 tick 正在跑，§2.1） |
| 102 | （09-24 停車）**停車**：批在途、這格什麼都沒收到、什麼都沒寫（§6 第 5 步）；`idle` 沒輸入（§8 第 1 步：沒有 `intake`、也列不到輸入檔，自動壓縮也沒做事）。kernel 等到它等的回音出貨、或有人投 `wake`（say／talk／郵差投完輸入就投）才再派，最晚 `park_ms`（預設 5 分鐘，[kernel §4](../kernel/echo.md)）。門關著照舊 101：門是外人開的，kernel 叫不到 |
| 1 | §2 第 1 步的起始讀驗錯（[agent.md §5](../agent/errors.md) 的代號；**只有這種什麼都不寫**）；之後的讀驗錯（輸入檔、回音、K 帳本）、`HistoryChanged`、I/O 錯 `aos-agent: io: …`——可能已寫一部分，紀錄照留，下次照 `batch`／`intake`／`consuming` 接著做 |
| 2 | 用法錯（含 `AOS_KERNEL_HOME` 沒設） |

一行一件，開頭 `aos-agent: `；問模型失敗 `aos-agent: engine: …`、暫停 `aos-agent: stuck: …`、（09-24 fix-r4 補）鎖被佔 `aos-agent: busy: …`。
