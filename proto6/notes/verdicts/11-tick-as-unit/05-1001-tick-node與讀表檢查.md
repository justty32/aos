← [2026-09-30 使用者方向（十一）：tick 是 aos 的衡量基準](../11-tick-as-unit.md)（分檔 5/26）｜所在段落：2026-10-01：POC 默認一切正常｜[上一份](04-1001-結束碼慣例.md)｜[下一份](06-1001-互斥-狀態資料夾-user.md)

<a id="aos-tick---node-怎麼認待統一更新-spec"></a>

### aos-tick `--node` 怎麼認（已寫入 spec（commit 前由我補號））

〔使用者方向 2026-10-01〕使用者原話：「如果--node xxx，xxx沒指定，那就是默認./。然後這邊我要加個機制：如果xxx是檔案，那該檔案必須符合task.json格式，而該檔案所在的資料夾yyy，將其作為--node yyy，後續正常執行。aos-tick --node xxx，判斷是否合法，應該是要判斷是否有.aos/task.json，和inst.json分開。」（`task.json` 即現有的 `tasks.json`。）

**這節是正本，已寫入 spec（commit 前由我補號）**（見上面「待改的 spec 處」P-203 argv 那條）。取代上一節「`--node` 底下必須有 `.aos/inst.json`」那半句；退路照舊拿掉。

- **沒給 `--node`**：用目前目錄 `./`。**相對路徑**一律轉成絕對路徑再用（拿掉「必須絕對路徑」）；node id 仍是絕對路徑。
- **`--node` 是資料夾**：合法＝有 `.aos/tasks.json`；不看 `.aos/inst.json`（tick 跟 inst.json 分開）。沒有就回 1、stderr 一行。
- **`--node` 是檔**：這個檔就是這一格的任務表；它所在的資料夾 yyy 當 node，擋板檔、停格檔、紀錄都在 `yyy/.aos/` 下。`yyy/.aos/tasks.json` 在不在都不管。`yyy/.aos/`、`yyy/.aos/tick/` 不在就建（只建資料夾）。「必須符合 tasks.json 格式」：~~照 POC 默認一切正常，不另驗，讀壞了自然丟錯回 1~~（同日再改：照下一節的極簡檢查，不過回 1）。
- **`--node` 指的東西不存在**：回 1。
- 結束碼照上一節碼表（0／1／2），不變。
- **表裡的相對路徑與指示詞**（同日追加）：以 node 根為中心——給檔時就是該檔所在的資料夾（叫 `.aos` 時是它的上一層，見下）。
- 實作時自己定的（使用者沒講，可改）：給的檔所在資料夾叫 `.aos` 時（例如 `yyy/.aos/tasks.json`），node 取 `.aos` 的上一層 `yyy`，不照字面當 `yyy/.aos`；舊的 `--node yyy/.aos/inst.json` 因此變成「拿 inst.json 當任務表」，沒有 `tasks` 陣列、過不了極簡檢查回 1。stderr 代碼 `no_tasks`（資料夾沒有 `.aos/tasks.json`）、`no_node`（不存在）。

<a id="aos-tick-讀任務表的極簡檢查待統一更新-spec"></a>

### aos-tick 讀任務表的極簡檢查（已寫入 spec（commit 前由我補號））

〔使用者方向 2026-10-01〕使用者原話（依序）：「task.json的格式錯誤的話，那aos-tick就是回1，這應該算在非正常錯誤」「所謂的格式錯誤，就是該填的沒填，然後不符合{"tasks":[]}這樣的格式，其他就不檢查。」「kind不填」「最外層不用檢查_metainfo，每一項也只需要檢查argv」「拿掉」（指任務表的 `methods`）「沒寫id的時候，那就是以其在tasks陣列中的index做id。直接數字轉字串。默認不重複」。檔名確定是 `tasks.json`。

**這節是正本，已寫入 spec（commit 前由我補號）。** 取代上面「POC 默認一切正常」裡「任務表不合法：拿掉驗表」那條與「表壞自然丟錯」的做法。

- **格式錯算 tick 自己的錯**：stderr 一行（`bad_table: …`）、回 1。給檔（`--node` 是檔）時一樣。
- **只查這幾件**：讀得到、合法 JSON、頂層是物件且有 `tasks` 陣列；每一項（整份 `$ref` 先展開，展開不了也算格式錯）是物件且有 `argv`。
- **沒寫 `id` 的項**：id＝它在 `tasks` 陣列的位置（從 0 起，跟 `AOS_TASK_INDEX` 同）直接轉字串，例如 `"0"`、`"3"`；紀錄、`AOS_TASK_ID`、`stopped_after` 都用它。跟別項寫的 id 撞了也不管（默認不重複）。
- **其他一概不查**：外層與每項的 `_metainfo`、`id`、`kind`（不必填，「kind不填」）、值的型別、`kind` 的值、`id` 重不重複、陌生鍵。格式上 `_metainfo` 外層與每項仍照寫、不省略，只是 tick 不擋。
- **`methods` 從規範拿掉**：寫了就當陌生鍵照收、不理（跟 `group`、`needs` 一樣）。理由：第二十批後檔案收件是普通程式、`aos-mq` 不看 `methods`，aos 自己沒有程式用它。
- 每項沒寫 `_metainfo`：從 proto5 複製的 `aos_inst` 本來就當 posix 第 1 版，照跑；寫了但值不對，跑到那一項展開成 inst 時自然丟錯（traceback）、回 1（前面的項已跑，紀錄停在 `ended:false`），`aos_inst` 不改。
- 實作自己定的（可改）：
  - ~~檢查在「換紀錄」之後（照 B-620 順序），所以表壞的那格仍佔一個 `seq`、紀錄停在 `ended:false`。~~（同日改：移到換紀錄之前，見下一節）
  - `id` 不是字串時 `AOS_TASK_ID` 用 `str()`（紀錄照原值寫）。

**待改的 spec 處**（統一更新時照這節改）

- [P-202](../../../spec/settled/protocol/tick/02-P-202-任務註冊表.md#p-202任務註冊表建議預設未拍板) 的欄位表與 `node-tasks` schema 的 `required`：`kind` 改不必填；`id` 不再是核心必查（schema 是否仍列必填，統一更新時定）；`methods` 與其「同一項不重複」檢查刪掉。
- [B-620](../../../spec/settled/tick/core/03-B-602-互斥鎖與B-620開頭.md#b-620任務註冊表照表依序跑)「讀表與誰驗什麼」：核心只做上面的極簡檢查，不過回 1。
- [B-633](../../../spec/settled/tick/core/08-B-633-紀錄與格數.md#b-633每項結束碼紀錄與格數)／P-213 與 `node-tick-record` schema：`id` 的說明補「任務表沒寫 `id` 時是位置字串」；上面「任務環境變數命名」那條的 `AOS_TASK_ID` 同。
