← [第三段之二：控制模組](../m3n-control-module.md)（分檔 3/5）｜[上一份](02-步驟2-週期迴圈.md)｜[下一份](04-步驟5-7-aos-ctl與待問.md)

## 步驟 3：socket 與協議

- **要做到**：daemon 在 `socket` 路徑開一個 unix socket（`SOCK_STREAM`），一條執行緒收連線；**一連線一請求**：讀一行、回一行、關掉。
- **依據**：使用者「必須用 socket」；舊 spec 通道（[P-117](../../spec/settled/deferred/protocol/daemon/channel.md)）只取「一行 JSON」，method、封包、憑證都不沿用。
- **請求**（一行 JSON 物件，`\n` 結尾）：**指令名當鍵、inst 字面值當值**，wake 的選項另外放欄位：

  ```text
  {"wake":"a"}
  {"wake":"jobs/report.json","skip_while_running":true,"keep_schedule":true}
  {"pause":"a"}   {"resume":"a"}   {"status":"a"}
  ```

  - 四個指令名裡剛好出現一個；值一定是字串（inst 字面值，跟設定檔 `insts` 的鍵逐字比對）。
  - 其他鍵：wake 認 `skip_while_running`、`keep_schedule`（要是布林）；其餘一律忽略（照 m3「其他鍵一律忽略」；使用者 2026-10-01 確認「socket收到看不懂的欄位就不理他」，C-07 已單列控制 socket 放寬）。
- **回應**（一行 JSON，`\n` 結尾）：

  | 狀況 | 回應 |
  |---|---|
  | wake／pause／resume 成功（含「正在跑、記補一次」「正在跑、`skip_while_running` 作廢」「本來就暫停」） | `{"ok":true}` |
  | status | `{"ok":true,"inst":"a","running":false,"pending":false,"paused":false,"stopped":false,"last_exit":0,"last_end":"2026-10-01T15:04:05+08:00","next":"2026-10-01T15:05:05+08:00"}` |
  | `insts` 裡沒有這個 inst | `{"ok":false,"error":"unknown_inst","detail":"<inst>"}` |
  | wake 一個被 `stop_on_nonzero` 停掉的項 | `{"ok":false,"error":"stopped","detail":"<inst>"}` |
  | 讀不到一行、不是 JSON 物件、指令名不是剛好一個、值或選項型別不對 | `{"ok":false,"error":"bad_request","detail":"<白話>"}` |

  - status：還沒跑完過時 `last_exit`、`last_end` 是 `null`；正在跑、暫停、已停時 `next` 是 `null`，否則就是 `due`。時間格式跟 m3 stdout 那一行一致（`now()`：本地時間、ISO 8601、帶時區、到秒）。
  - 不認得的指令名（例如 `{"kill":"a"}`）算「指令名不是剛好一個」，回 `bad_request`；不另設 `unknown_cmd`。
- **回的時機**：狀態記好那一刻就回，**不等那一項跑完**；wake 成功的意思是「收到了」，不是「跑成功了」（結果照 m3 看 stdout 那一行，或之後 status）。
- **連線**：客戶端連上、送一行、讀一行、雙方關。daemon 一次處理一條連線（只是改狀態或抄狀態，很快）；每條連線 1 秒逾時，免得一個連上不送的客戶端卡住後面的人（逾時就關掉、不回）。
- **權限**：能連就能做所有事；能不能連照 socket 檔的檔案權限（建出來照 daemon 的 umask），不另驗身分。
- **不讓 daemon 掛**：單一連線出的任何錯（壞 JSON、對面先關、逾時）只影響那一條連線，回 `bad_request` 或直接關，收連線的執行緒繼續跑。這是本段唯一的「異常處理」：外面送壞東西不該把整個 cron 打掉。
- **要使用者裁定的點**：無。
- **驗收**：
  - 用 Python 標準庫直接連 socket 送 `{"wake":"a"}`：回 `{"ok":true}`，而且 `a` 立刻跑一次。
  - `{"status":"a"}` 回 `a` 一項；跑 `sleep 0.5` 的項中途查是 `running:true`、`next:null`；欄位跟實際一致。
  - 不存在的 inst 回 `unknown_inst`；`{"kill":"a"}`、`{"wake":"a","pause":"a"}`、`{"status":null}`、`{"wake":"a","keep_schedule":"yes"}`、送 `hello` 都回 `bad_request`；之後再送正確的請求照樣成功。
  - 連上不送東西：1 秒多一點被關掉，期間別人的請求最多晚約 1 秒。

## 步驟 4：往下傳環境變數

- **要做到**：模組掛著時，daemon 開每一次 `aos-exec` 都在環境裡加 `AOS_DAEMON_SOCKET=<socket 絕對路徑>`、`AOS_DAEMON_INST=<這一項的 inst 字面值>`（蓋過 daemon 自己環境裡同名的）。
- **依據**：使用者定的兩個名字；`AOS_DAEMON_SOCKET` 沿用舊 spec [P-117](../../spec/settled/deferred/protocol/daemon/channel.md)，`AOS_TICK_TOKEN`（憑證）不做。
- **一路傳下去不用寫新程式**：`aos-exec` 照 inst 的 `envs` 規則用繼承的環境；`aos-tick` 開任務時也是繼承的環境加 `AOS_*`；下層 `aos-tick 下層` 本身就是上層的一個任務，它的任務又繼承下去。所以**每一層的任務看到的都是頂層那一項的 inst**，指到的永遠是頂層（使用者「不要管上下層」「daemon 只需要管理最頂層」）。inst 或任務寫了 `envs` 清空時，那一支往下就沒有這兩個變數，是 inst 自己的選擇。
- **inst 字面值是相對路徑也沒關係**：傳下去的只是一個名字，`aos-ctl` 原樣送回，daemon 跟 `insts` 的鍵逐字比對，不在任務的工作目錄解析。
- **模組沒掛時不動環境**：daemon 自己的環境若已有這兩個變數（例如它本身是別的 daemon 底下某個任務開的），照樣傳下去、不清。照默認一切正常，不為這種套疊另寫規則。
- **要使用者裁定的點**：無。
- **驗收**：
  - 假 inst 把兩個變數寫進檔：值是 socket 絕對路徑與 inst 字面值（例如 `jobs/report.json`，不是轉過的絕對路徑）。
  - node 資料夾 `a`（inst 跑 `aos-tick`）的任務表有一項寫檔、另一項跑 `aos-tick b`，`b` 的任務也寫檔：三個檔裡的 `AOS_DAEMON_INST` 都是 `a`。
