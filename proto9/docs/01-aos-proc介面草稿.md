aos proc 介面草稿第 0 版：一個 aos proc 的目錄長什麼樣、每個檔怎麼讀寫、daemon 多哪幾樣；把使用者 11-25 兩輪談話定下來的寫成一頁，沒定的與 eca-aos 自己擬的都標出來。

# aos proc 介面（草稿第 0 版，11-25）

← [proto9](../README.md)｜原話與每輪定了什麼：[9P proc 談話紀錄](../../proto8/thinking/2026-11/25/9p-proc-1125.md)

**怎麼讀這頁**：每一條前面有一個記號。

- 【定】使用者說過的。原話在談話紀錄裡，這裡只寫結果。
- 【擬】eca-aos 自己挑的，還沒有使用者的話；他看了不對就改。
- 【開】還沒談。

寫這頁的是 `eca-aos`。還沒有任何程式照這頁做。

## 1. 一句話

【定】一個 **aos proc** 是一個活著的行程，加上它擺出來的一個目錄。別人要控制它、看它的狀態、找它的東西，都是讀寫那個目錄裡的檔。擺得出這個目錄、照這頁的格式回答的，就是 aos proc；是誰寫的、用什麼語言都不管。

【定】介面＝目錄的長相＋每個檔的內容格式。

【定】proto9 裡的 aos proc 要**當場回答**：有一支活著的程式在你讀寫的那一刻接手。第一步的做法是每隻 proc 用 FUSE 把自己的目錄掛出來。

## 2. 幾個詞

| 詞 | 意思 | |
|---|---|---|
| 身體（stack） | 一隻活著的 proc 的目錄。行程死了就走不到 | 【定】 |
| persist | 這隻 proc 要留下來的東西放的地方。身體沒了它還在 | 【定】 |
| daemon | Linux 與 aos 之間的橋。本身是 aos proc，另外多一個放「底下的 proc」的夾 | 【定】 |
| 根 | 最上面那台 daemon | 【定】 |
| kernel | 普通的 aos proc，只是帶了某種功能（發模型額度、管權限…） | 【定】 |
| 名字路 | 從根往下一路的名字，例 `repo-aos/eca-aos`。這是一隻 proc 的身分；名字可以自己指定 | 【定】 |

## 3. 怎麼走進去

- 【定】入口是根 daemon 的 PID：`AOS_ROOT=/proc/<根的 PID>/cwd`。Linux 的 `/proc/<PID>/` 不加任何東西；`cwd` 是核心本來就給的，指到那支行程站的資料夾，所以每隻 proc 都站在自己的目錄裡。
- 【定】`AOS_ROOT` 由人手動維護：根重開後提示自己的 PID，人自己 export。可以有方便的做法（例：用特殊指令起根，順手設好）。
- 【擬】樹裡的 proc 不用人管：daemon 起它時，把 `AOS_ROOT` 放進它的環境。要手動的只有樹外的殼。
- 【定】往下走：`$AOS_ROOT/procs/<名>` 就是那隻 proc 的目錄，一層一層可以一直走。`proc` 與 `procs` 兩個名字指同一處。
- 【擬】用舊的 `AOS_ROOT` 之前先認一下：根死了、PID 被別的行程拿走之後，舊值會安靜地指到別人的資料夾。讀 `$AOS_ROOT/status` 有 `aos_name` 那一行、而且是根，才算數。
- 【定】沙箱裡走不進來是本來就要的，有需要再開口子。換 Linux 帳號的 proc 怎麼進來，之後再想。

**容易看錯層的名字**：Linux 自己的東西在 `/proc/<PID>/` 那一層，aos 的在再下一層 `/proc/<PID>/cwd/`，兩邊不會撞。但 Linux 那層有 `status`、`attr`（少一個 s）、`stack`、`root`，跟 aos 的 `status`、`attrs` 長得像，下指令時看清楚有沒有 `cwd`。

## 4. 目錄裡有什麼

每隻 aos proc：

| 名字 | 是什麼 | 讀寫 | 格式 | |
|---|---|---|---|---|
| `ctl` | 控制它 | 只寫 | 純文字，一行一道 | 【定】 |
| `status` | 它現在怎樣 | 只讀 | 純文字，一行一個「名稱: 值」 | 【定】 |
| `settings` | 它的東西放哪（起來時就定的） | 只讀 | 同 `status` | 【定】 |
| `attrs` | 它是哪一種身體、能不能當場回答；要用它的人看了自己決定怎麼做 | 只讀 | 同 `status` | 【定】有這個檔；裡面的行【擬】 |
| `_metainfo.json` | 它是什麼（定義帶來的那份） | 只讀 | json，照 aos 現有的 | 【定】 |
| `persist` | 走到它要留的東西 | — | 一個夾（或指過去的連結） | 【定】推薦位置；怎麼擺【開】 |

daemon 另外多：

| 名字 | 是什麼 | 讀寫 | |
|---|---|---|---|
| `procs/`（別名 `proc/`） | 底下每隻 proc 一項，走進去就是它的目錄 | 讀 | 【定】 |
| `procs_ctl` | 管底下的 proc（加、拿掉、起、停、強制收） | 只寫 | 【定】 |
| `procs_status` | 底下每隻 proc 的狀態，**死了、停著的也在** | 只讀 | 【定】 |

以後才有的：

- 【定】每個純文字檔另給一份 json：`settings.json`、`status.json`…（跟 `_metainfo.json` 同一種叫法）。之後再做。
- 【定】`status` 以外可以再多給別的檔，例：報 token 用量的檔。名字與內容【開】。
- 【開】收訊息的 unix socket 叫什麼（見第 9 節）。

【擬】上面這些名字是保留的；proc 自己要多擺什麼檔都可以，別用這些名字就好。

## 5. 純文字的寫法

【定】一行一個「名稱: 值」。以下細節【擬】：

- 名稱：小寫英文字母、數字、底線。冒號後一個空白，之後到行尾都是值，原樣。沒有值寫 `-`。
- **`aos_` 開頭的名稱是 aos 標準的**，意思照這頁；其餘的名稱 proc 自己用，愛叫什麼叫什麼。（【定】`aos_ctl_` 開頭的是標準；把同一條規則推到所有標準行是【擬】。）
- 不認得的行跳過。現在不標版本。
- 行的先後沒有意思，照名稱找。

## 6. ctl

- 【定】一行一道，純文字。寫回來＝**收到**；做完沒有，看 `status`。
- 【定】字表不訂死。只訂基礎且通用的，其餘各 proc 想收什麼收什麼。
- 【擬】基礎的三個字：

  | 字 | 做什麼 |
  |---|---|
  | `stop` | 做完手上這一步就結束 |
  | `pause` | 做完手上這一步就停住，行程還在 |
  | `resume` | 解除 pause |

- 【定】**鎖**：一個人搶到之後，從他寫進指令到 proc 做完那個動作，都鎖住；另一個人會發現自己寫不進去。
- 【擬】鎖的細節：
  - 寫不進去＝那一次寫入當場失敗（忙），**不動 `aos_ctl_*`**，先搶到的人的回饋才不會被蓋掉。
  - 「做完」：`pause` 是停住了就算做完（鎖放開，才收得了 `resume`）；`stop` 是行程結束。
  - 鎖著的時候要強制收：寫它 daemon 的 `procs_ctl`（第 8 節）。proc 自己的 ctl 只有客氣的字。
- 【定】**回饋放 `status`，行名 `aos_ctl_` 開頭**，講的一定是最後一次 ctl。被拒的原因也在這裡。
- 【擬】回饋的四行：

  | 行 | 值 |
  |---|---|
  | `aos_ctl_cmd` | 最後收下的那一道，原樣；還沒收過＝`-` |
  | `aos_ctl_state` | `doing`（在做，鎖著）／`done`（做完）／`rejected`（不做，原因看下一行） |
  | `aos_ctl_error` | `代號 原因`，例 `CommandUnknown frobnicate`；沒事＝`-` |
  | `aos_ctl_count` | 起來之後收下過幾道；下指令的人記著自己那道是第幾，就知道回饋有沒有被後來的人換掉 |

- 【擬】不認得的字：收下、記成 `rejected`；做得到的實作同時讓那次寫入失敗。

## 7. status、settings、attrs

三個檔照「誰決定、什麼時候會變」分：`settings` 是起來時定的，之後不變；`attrs` 是這種身體天生的；`status` 一直變。

**`status` 第一批**（【定】由 eca-aos 定；所以整張【擬】）

| 行 | 值 |
|---|---|
| `aos_name` | 名字路，例 `repo-aos/eca-aos`；根自己是 `/` |
| `aos_phase` | `running`／`paused`／`stopping` |
| `aos_pid` | 回答的這支行程的 PID |
| `aos_started_at` | 這個身體起來的時間 |
| `aos_ctl_cmd`、`aos_ctl_state`、`aos_ctl_error`、`aos_ctl_count` | 見第 6 節 |
| （daemon）`aos_procs` | 底下有幾隻 |
| （daemon）`aos_procs_ctl_cmd`、`_state`、`_error`、`_count` | `procs_ctl` 的回饋，規則同 `aos_ctl_*` |

proto8 的 `updated_at`、`responded_at`、`boot_id`、`started_at_ticks` 沒收：那些是「檔會活得比行程久」才需要的；當場回答的 proc，讀得到就是活著。proc 自己的行（agent 的 `stage`、排著幾封信…）不帶 `aos_`，自己加。

**`settings`**（行【擬】）

| 行 | 值 |
|---|---|
| `aos_persist` | 它要留的東西在哪（硬碟上的真實位置） |
| `aos_mailbox` | 它掛了的時候，信投到哪 |

【定】persist 在哪，以 proc 自己在 `settings` 說的為準；daemon 起它之後來讀。daemon 可以給預設位置，在 `/tmp` 開一塊。proc 沒說就死了，daemon 就不知道。

**`attrs`**（【定】有這個檔、用途；行【擬】）

| 行 | 值 |
|---|---|
| `aos_kind` | 這個目錄是怎麼擺出來的：`fuse`／`file`（硬碟上的普通檔）／`tmp`（記憶體裡的普通檔）／… |
| `aos_live` | `yes`＝當場回答（寫 ctl 回來就是收到、鎖擋得住）；`no`＝沒人當場接，寫進去只是放著 |

【擬】要用它的人照 `aos_live` 決定怎麼做，`aos_kind` 只是說明（以後會有新的種類）。沒有 `attrs` 就當 `aos_live: no`。

## 8. daemon 多的三樣

- 【定】`procs/<名>`：走進去是那隻 proc 的目錄。只有活著的走得進去。
- 【定】`procs_ctl`：管底下的 proc 的字寫這裡，不寫 daemon 自己的 `ctl`（那個只管 daemon 自己）。
- 【擬】`procs_ctl` 的字：

  | 字 | 做什麼 |
  |---|---|
  | `add 名字 路徑` | 加一隻並起它。路徑是定義夾，或一份 json 檔（其餘參數放裡面） |
  | `rm 名字` | 收掉、從表上拿掉（persist 不刪） |
  | `stop 名字`／`start 名字` | 叫它好好收尾後留在表上／再起 |
  | `kill 名字` | 現在就收（強制；proc 卡住、ctl 鎖著時用） |
  | `register 名字 PID` | 只登記、不起：一支已經在跑的行程來說「我是 aos proc」 |

  proto8 的 `sleep`／`wake` 要不要留【開】。鎖與回饋的規則同第 6 節。

- 【定】`procs_status`：底下每隻 proc 的狀態，純文字。proc 死了，它自己的 `status` 就沒了，這張表是唯一還答得出來的地方。
- 【擬】行名是 `名字.欄名`：

  ```
  arena.phase: stopped
  arena.want: up
  arena.pid: -
  arena.code: 1
  arena.reason: exited within 3s of start
  arena.persist: /tmp/aos/persist/repo-aos/arena
  arena.mailbox: /tmp/aos/persist/repo-aos/arena/mailbox
  ```

- 【定】照報告的推薦走的四件（細節都還【擬】）：
  - 想要的樣子（`want`：人要它活著還是停著）與實際的樣子（`phase`）分開記。
  - 死因（結束碼、被什麼訊號收的、原因一句）由 daemon 留在這張表。
  - 起了卻一直不登記（讀不到它的 `settings`）的，等到期限就收掉、記成起動失敗。
  - 強制手段歸 daemon。

## 9. 送訊息

- 【定】proc 活著：直接走 unix socket。
- 【定】socket 上送來的算進對話的話（queue）還是信（mailbox），proc 自己決定；預設希望是 queue。
- 【定】proc 掛了或睡了：收不到。要送的人去問它的 daemon（或某個 kernel）信箱在哪，改走寄信（落檔、留得住）。
- 【擬】「問」＝讀 daemon 的 `procs_status` 裡那一行 `名字.mailbox`。
- 【定】問的時候要不要順手叫醒：daemon 自己的可選設定，以後再說。
- 【開】socket 叫什麼、上面講什麼、回條長怎樣、兩條路之間的先後。（報告 20 有一份選項單。）

要知道的一點：預設 queue 的話，同一句話活著時是直接進對話，掛了改寄信則是進信箱等它自己看，兩邊意思不一樣。

## 10. 留下來的東西與搬家

- 【定】`.stack` 這個夾以後沒有；身體是活的，要留的各自處理，推薦放 `persist`。
- 【定】可遷移性現在不動，設計時先考慮著。遠期目標：`cp AOS_ROOT` 就能把一切搬走。
- 【擬】為了那個目標，現在先守兩條：
  - 每隻 proc 要留的東西，從它自己的目錄走得到（`persist`）。
  - 留下來的檔裡，指別人用名字路，不用絕對路徑、不用 PID。

## 11. 還沒定的（照我覺得該先談的排）

1. FUSE 小實驗的結果（`../experiments/fuse-proc-1125/`）：這台做不做得順、掛載點放哪、行程被強制收掉後掛載怎麼收。
2. `aos_` 開頭這條規則要不要推到所有標準行（第 5 節），還是只有 `aos_ctl_*`。
3. `status` 第一批、`attrs` 的兩行、`procs_ctl` 的字、`procs_status` 的欄——都是我擬的，等使用者看。
4. `persist` 在目錄裡怎麼擺（真的夾、連結、還是 proc 當場回答）；proc 死了以後別人怎麼走到它的 persist（現在只有 `procs_status` 那一行路徑）。
5. socket 那一塊（第 9 節的【開】）。
6. 報 token 用量的檔。
7. 只登記、不起的入口（`register`）：誰可以登記誰、登記後 daemon 對它有多少權力。
8. proto9 的程式放哪幾個夾、用什麼語言、agent 的身體怎麼搬過來。
9. 換 Linux 帳號的 proc 怎麼進樹。
