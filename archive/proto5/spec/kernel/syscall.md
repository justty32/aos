← [kernel](README.md)｜[spec 總導航](../README.md)

# 2. syscall（`K/requests/`）

| method | params | 回音 |
|---|---|---|
| `add` | `target` 必填（絕對路徑）；`dir_target`／`args` 可省（同範式 §4.1；`args` 沒給就不要放這個鍵）；`name` 可省（省＝數字名最大值加 1）；`once`（預設 false）；`pool`（預設 `default`，必須是 `info.pools` 的 key、且不是保留名 `kernel`；2026-09-24 池式納入改）；`interval_ms`／`timeout_ms`（預設照 info）；（09-24 停車）`park_ms`（預設照 info，[§4](echo.md) 的 102 那列）、`wake`（要叫醒的反覆行程名，見下）；（09-24 tick-gap）`on_bad`（壞了寄通知，見下；只給反覆行程） | **反覆**行程：`{"name": NAME}`。**`once`**：回音等到那一次跑完才寫，內容就是那次的 exec 回音（`result` 或 `error` 原樣）；交件者等 `K/responses/<自己的檔名>.json` 一個檔、讀完放 ack |
| `rm` | `name` | `{"name": NAME}`；不在＝`-32000`／`NotFound`。細節見下 |
| `stop` | notification | `phase` 改 `stopping`（§3 第 9 步）；收完在途後把每個池縮到 0，停好那格請 daemon 別再開 tick（[§6 停機](boot.md)）。daemon 本身不停，由人停（或 `aos down`） |
| `wake` | （09-24 停車）`name` | `{"name": NAME}`；不在＝`-32000`／`NotFound`。照下面「叫醒一個行程」做。多半當 notification 放（`aos-agent say` 就是），不回音 |
| `ack` | 範式 §3.3 | kernel 是一個家，別人收了 `K/responses/` 的回音要放 ack，處理方式照範式（刪回音、刪 ack 檔） |

沒有 `ls` syscall：看狀態就直接讀帳本 `K/ledger.sqlite`（§6 的 `ls`、`proc` 就是這樣做，沒人開 tick 也看得到）。
同名 `add`（不管 `status` 是什麼、含被 rm 但還在 cpu 上跑的）回 `-32000`／`AlreadyExists`；
params 形狀或 pool 不合回 `-32602`。kernel 不解指示詞、不驗 inst、不看檔在不在——那些都是跑起來的回音。
（09-24 補）省略 `name` 時只計 ASCII 十進位名稱：有數字名取最大值加一，沒有就從 `0` 開始。CLI 的 `--once` 沒給 `--name` 時仍用自己的 request 檔名（§6）。

**每則 syscall 都是「先記帳、再出貨」**：收到 `add`／`rm` → 判定 → 把結果（行程紀錄、排隊格、pending）跟
出貨待辦寫進帳本（池式納入後一格的判定合併在一個提交點一次寫，one-boot 叫提交點 B，[§1.2](ledger.md)）→ 出貨。待辦是：原單名進 `deletes`（一定有）；要馬上回的回音進 `replies`
（反覆的 add、rm）；`once` 的 add 只記 `pending`，跑完或取消時才進 `replies`。`ack`／`stop` 照各自的規則，不產生回音。
**`once` 的回音只報執行狀態**（code／kind／timed_out…），不含模型的答案或工具的輸出——要輸出就在工作 inst 裡
指定 `stdout` 檔，收到成功的回音後再去讀那個檔。
重掃看到某份原單，先看 `deletes`：**在裡面＝已收過**，只補刪、不重判——去重憑據是出貨箱，不是行程紀錄
（行程紀錄會被別的 rm 刪掉，靠不住）。`deletes` 在原單真的刪掉之後才清。

**`rm` 的三種情況**：
- 行程 `queued`／`done`／`bad`：從 `procs` 拿掉（排隊格懶刪，§1.2）。`once` 且 `queued`：它 `pending` 的 add 回 `-32000`／`Removed`（進 `replies`）。
- 行程 `running`：用 `on` 找到那顆 `P/<i>`，照範式順序查——`K/pools/P/cpus/<i>/requests/<req>` **在** → 在途，那格 `busy` 標 `discard`、
  行程紀錄留著（回音到了才拿掉，同名 add 在那之前都 `AlreadyExists`）；原單不在再看回音，**在** → 同上；
  兩個都不在 → 上一格記了沒放，直接取消：那格 `busy`、`on` 拿掉、號碼放回、行程拿掉。
- **`once` 不管在途還是取消，`rm` 當下就把 pending 的 add 回 `Removed`**、`pending` 清掉；之後那顆 cpu 的回音只是被 discard 掉。

**（09-24 停車）`add` 的 `wake`**：合法名稱就記下，不管那個行程現在在不在、是哪一代——`stop` 再 `start` 的新一代會接手舊批（[aos-agent §11](../aos-agent/register.md)），舊批回來叫它才對；多叫一格無害。
這張 add 的**最後一則回音不管怎麼來都帶著** `wake`：`once` 記在 `pending` 裡，跑完、失敗、`Removed`、`Stopping` 都從 `pending` 帶進 `replies`；收單當場就回的（反覆 add 的 `{"name"}`、各種退件）直接帶進 `replies`。
出貨時（§3 第 4、10 步）回音檔放好（EEXIST 當已放）就叫醒，跟「把這筆從 `replies` 拿掉」同一次存帳本。舊 kernel 看不懂 `wake` 會忽略，不退件。

**叫醒一個行程**（`wake` 單與出貨共用）：行程不在、`once`、`status` 是 `bad`／`done`、或它正跑的那格標了 `discard` → 什麼都不做。否則：
`running` → 記 `woken: true`（跑完退 0／101／102 都馬上再排，[§4](echo.md)；09-24 tick-gap 以前是「102 當 101」）；`queued` 而 `not_before` 還沒到 → `not_before`＝現在、接到它池的 `ready` 尾（`delayed` 裡那格變舊格，照 [§1.2](ledger.md) 攤還）、`parked` 拿掉；
`queued` 而 `not_before` 已到 → 什麼都不做（免得 `ready` 疊兩格）。叫醒只代表「最早下一次派工就能派」，池滿照樣排隊。

**（09-24 tick-gap）`add` 的 `on_bad`：壞了寄一封通知**。反覆工作連錯 `bad_after` 次被判 `bad` 之後，kernel 不再派它；以前只寫 `kernel.log`、`ls` 列出來，沒人會知道（T5 真跑：郵差停了十幾分鐘）。
登記時帶 `on_bad`，判 `bad` 那格就往一個資料夾放一封信（跟團隊郵差投信同一招：放檔，要的話再叫醒收件的 agent）：

| 鍵 | 必填 | 意思 |
|---|---|---|
| `dir` | 是 | 絕對路徑，信放這裡（人的收件匣、某個 agent 家的 `input/`…）。kernel 不建這個資料夾 |
| `body` | 否 | 信的內容，任意 JSON（序列化成 UTF-8 後 ≤ 64 KB，09-25 起算位元組）。字串、或物件第一層的字串值裡的 `{id}` `{proc}` `{fails}` `{at}` `{look}` 換成這次的值（檔名去掉 `.json`、行程名、連錯次數、本機時間 ISO 8601、要看的 stderr 檔——同 `ls` 的 look）。沒給＝一句白話字串（agent 的 `input/` 也吃） |
| `wake` | 否 | 放好信之後叫醒這個反覆行程（收件的 agent），同「叫醒一個行程」 |

- 帶在 `once` 的 add 上＝退件（`FieldTypeMismatch`，once 不會被判 bad）；形狀不對同樣退件。
- 檔名 `bad-<行程名>-<chain>-<序號>.json`。判 `bad` 的那格把這封排進帳本的 `letters` 出貨箱（跟判定同一次存，提交點 B），出貨時放（`link`，EEXIST 當已放）、再叫醒。
  （09-25 astra 審查代裁）**崩潰時可能多一封、不會少**：放好信、還沒把它從出貨箱拿掉就被 kill -9，而收件人又剛好在恢復前把信搬走，下一格會再放一封同名、同 `{id}` 的信。檔案和帳本沒辦法同一刻寫好，只能選「可能多寄」或「可能漏寄」；通知選前者。收件人要去重就認檔名／`{id}`。
- 填 `{look}` 時要讀 target 的 inst 找 stderr：只讀普通檔、最多 1 MB、不阻塞；target 被換成 FIFO 之類的就直接指 target 本身（09-25 astra 必修 M4）。
- 信任邊界（09-25 代裁）：`dir` 只驗是絕對路徑，不擋 `..` 和 symlink。會登記 `add` 的人本來就能在自己的權限內寫檔，kernel 跟他同一個使用者，沒多給權限；kernel 不建資料夾、不覆蓋既有檔（`link`）。
- **寄不出去不擋 kernel**：資料夾不在、沒權限，記一行 `kernel.log`（`bad_letter_failed`）、丟掉這封，這格照常退 0。寄出去了也記一行（`bad_letter`）。
- 命令列：`aos-kernel add … --on-bad DIR [--on-bad-wake NAME]`（body 用預設那句）。團隊的 `aos-team start` 登記郵差、心跳時預設帶 `on_bad`，寄給人（`team/human/`，一封團隊信的形狀、`from: kernel`、`status: FAILED`）。
