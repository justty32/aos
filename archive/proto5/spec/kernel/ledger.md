← [kernel](README.md)｜[spec 總導航](../README.md)

## 1.2 帳本（第 3 版）：`K/ledger.sqlite`

（2026-09-24 proto5-2 池式納入：`cpus`（每顆一格）換成 `pools`＋`busy`，`queue` 拆成 `ready`＋`delayed`，拿掉 `stops`、加 `sends`、`on`。）
（**2026-09-24 one-boot**：帳本從 `K/state.json` 換成 sqlite 檔 `K/ledger.sqlite`，升第 3 版；拿掉 `kcpu`、`pools.kernel`；`on` 不再存；加 `ticker`、`last_tick_at`；
一格最多存三次，每次一筆交易、只寫變了的列。使用者拍板，見 [§9](README.md)。09-24 tick-gap 多一個只在「出貨時叫醒了停著的行程」才有的提交點 D，那種格最多四次。）
`procs` 每筆的形狀與意思**完全不變**——[aos-agent §10](../aos-agent/pause-clean.md) 靠它判斷「工作還在不在 cpu 上」（改用同一支 lib 查，見下）。kernel 取的檔名見 [§1.3](names.md)。

仍是**唯一的帳本**。帳本裡跟 cpu 有關的只記**忙的**，閒的只記號碼，不再每顆一個物件。
kernel 的家是唯一放寬 cpu 範式「四樣檔」的家：**只有帳本**是 sqlite；`requests/`、`responses/`、`pools/`、cpu 的家都還是檔案。
為什麼換：第 2 版每存一次就整份重寫，上萬個行程時一格要寫好幾 MB、好幾次；agent 每格也整份讀一遍。sqlite 只寫變了的列，查一筆只讀一列。

### 表

| 表 | 一列是什麼 | 欄 |
|---|---|---|
| `meta` | 一個小鍵 | `key`（主鍵）、`value`（JSON 文字）。鍵：`version`（固定 3）、`chain`、`cli`、`ticker`、`last_seq`、`last_tick_at`、`phase`、`halting`、`features`、`recent`、`stale`、`ready`、`delayed`、`acks`、`replies`、`deletes`、`sends`、（09-24 tick-gap）`letters`（壞了的通知信，[§2](syscall.md) 的 `on_bad`） |
| `procs` | 一個行程 | `name`（主鍵）、`status`、`pool`、`body`（整筆 JSON，就是下面 `procs.<NAME>` 那列的形狀） |
| `pools` | 一個池 | `name`（主鍵）、`body`（下面 `pools.P` 的形狀） |
| `busy` | 一顆忙的 cpu | `cpu`（主鍵，`P/<i>`）、`ord`（插入順序，巡檢輪轉靠它）、`proc`（有索引）、`body`（`{req, proc, discard}`） |

- 開法：WAL 模式、`synchronous=NORMAL`、`busy_timeout` 10 秒。保證跟第 2 版的「一次原子寫」一樣：**行程崩潰（含 kill -9）不會留下半筆**；斷電不在保證內。
- tick 一開始**整份讀**進記憶體，變成跟第 2 版同形的一份資料（下面的例子）；存的時候跟讀進來的比，**只寫有變的列、一筆交易**。崩在交易中間＝整筆沒發生。
- `busy` 的順序：`ord` 還照順序的列沿用，被巡檢搬到尾巴的換一個更大的號——只改那幾列。
- 讀的人只讀、不寫，WAL 讓讀不擋寫：`aos-kernel ls`（整份）、`aos-kernel proc NAME`（`procs` 一列＋`busy` 按 `proc` 查一列，O(1)，[§6 proc](cli.md)）、aos-agent（同一支 lib `lib/aos_kernel_store.py`）。
  別的程式要看帳本，用 `aos-kernel proc --json`／`ls --json`，不要自己開 sqlite。
- **舊的第 2 版 `K/state.json`**：boot 時整份匯入 sqlite、原檔改名 `state.json.v2-old`（[§6 boot](boot.md)）。還沒換過的家：tick 退 1（`LedgerVersion`），`ls` 的 health 是 `legacy`。
  **只要 `state.json` 還在就算還沒換好**（匯入成功才改名；崩在建好 sqlite、還沒提交或還沒改名之間，下次 boot 整份重匯）。
  boot 先把舊 kernel 池縮到 0、等舊的 tick 停妥，才重讀 `state.json` 匯入（舊程式的 tick 沒有 `.tick.lock`）。第 1 版（`cpus` 表）照舊拒絕。

### 每個鍵的意思

tick 讀進記憶體後的樣子（例子）與每個鍵的意思在 [ledger-keys.md](ledger-keys.md)。

NAME 是非空檔名，不能是 `.`／`..`、含 `/` 或 NUL。kernel **不讀 target 指的檔**，只記路徑。
重拉節奏、孩子活不活這種執行中的東西不在帳本裡（那是 daemon 的）。

**排隊的格帶 `request`**：`request` 就是 `procs.NAME.request`（那次 `add` 的檔名，每次 add 都不同）。
拿出來時 `procs` 沒有 NAME、`status` 不是 `queued`、`request` 對不上、或（`delayed` 的）時間不等於 `procs.NAME.not_before`，就是舊格，丟掉。
所以 `rm` 排隊中的行程只刪 `procs` 那筆（懶刪），同名重 add 也不會撿到舊格的位置。
**舊格累積**：每池記舊格數（`stale`），超過活格數就整條壓縮一次（O(那條長度)，攤還到每次 rm 是 O(1)）。

**一個行程在哪**：`queued` 的有且只有一個有效格（`ready` 或 `delayed`）；`running` 的在某格 `busy`（`on` 就是從這裡反推的）；`done`／`bad` 只在 `procs`。

## 什麼時候存帳本

第 1 版是「每則 syscall、每筆出貨寫一次」；第 2 版改成四個提交點。one-boot 拿掉第 2 版的提交點 1（「先放下一格、再記 `last_seq`」，沒有鏈了），剩三個：

| 提交點 | 在第幾步 | 包含 |
|---|---|---|
| A | 第 4 步出貨完（有出貨才存） | 拿掉已出貨的項目；連同這格的 `last_seq` |
| B | 第 5～9 步全部決定完（一定存） | syscall 結果、收回音判定、池的決定、派工記錄、停機判定，連同新增的出貨項目、`last_seq`、`last_tick_at` |
| C | 第 10 步出貨完（有出貨才存） | 拿掉已出貨的項目 |
| D | （09-24 tick-gap）C 出貨時帶 `wake` 的回音把停著的行程推進 `ready`，才有這一步 | 同一格再跑一次第 8 步派工：派工記錄。存完才放**這一輪新派的**單（前面放過的不重放） |

每個提交點是**一筆 sqlite 交易**，只寫變了的列。
- 出貨是「全部放完（或刪完）→ 一次存帳本拿掉」。中間崩了，下一格重放——`link` 的 EEXIST、刪檔的 ENOENT 都當成功，所以合併存不改正確性，只是崩了會多放幾次。
  scale 單重放前先看對方 `responses/` 有沒有同名回音，有就不再放（實作 D-25）。
- 派工仍是「先記後放」：提交點 B（和 D）之後才放派工單。崩在 D 之後、放檔之前＝下一格靠 `recent` 補放，跟 B 一樣。
- （09-24 tick-gap）D 為什麼要有：回音在第 10 步出貨時才叫醒 agent，以前要等 daemon 下一次開格（最多 `tick_ms`，實測每次約 1 秒）才派得出去。
- syscall 仍是「先記後出貨」：判定進提交點 B，回音與刪原單在第 10 步出貨。崩在提交點 B 之前＝這格的判定全部沒發生，下一格重讀同樣的原單重判，冪等。

帳本每格還是整份讀，大小跟 `procs`＋`busy`＋`free`＋`skip` 成比例；寫只寫變了的列（[§11](scale.md)）。
