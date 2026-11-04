# kernel 樹與註冊式 tick（09-29 架構方向）

← [筆記索引](README.md)｜裁定見[裁定紀錄](2026-09-29-verdicts.md)第三、四批

2026-09-29 使用者指出：proto6 前面的 spec 把 proto5 的 kernel／daemon 拆法改成「一支常駐控制端＋一本總帳本」，偏離原意。原意是 **kernel 本身也是一個靠 tick 推進的資料夾**，因為將來會有多個 kernel 混在 agent 團隊裡：某個團隊有自己的 kernel，只管自己成員的排程與資源，而這個 kernel 又只是上一層 kernel 的一件工作。本篇把這個方向和同日定下的「註冊式 tick」合起來寫清楚，作為重寫 spec 的依據。**以本篇為準；前面 spec 裡「單一控制寫入者、總帳本」的寫法要改掉。**（標註：09-29 晚起 spec 已依此重寫，現行以 [spec](../spec/README.md) 為準，本篇改為架構背景；下列已被後批推翻或已定的處所另有標註；09-30 第十八批方向見 [09](verdicts/09-special-computing-os.md)，最新為準。）

> **第七批更新**：kernel 與 agent 合併成一種東西 **node**。「kernel」「agent」改當概念／角色：管資源分配與排程的叫 kernel，會自主行動（牽涉 LLM）的叫 agent，都由 node 的註冊表內容決定；一個 node 可以兩者皆是或皆非。下文的 kernel／agent 都讀成「扮演該角色的 node」。

## 一、角色

| 角色 | 是什麼 | 常駐 |
|---|---|---|
| daemon | 程序的爸爸：替 kernel 開 tick（定時或有新單）、啟動／重拉／停止程序。不讀任何家的內容 | 唯一常駐 |
| kernel | 一個資料夾：收件資料夾、自己的狀態檔，加上 `aos-tick` 與一份註冊表，註冊表放排程任務（收單、派工、收結果、管資源） | 否，一次一格 |
| agent | 一個資料夾，加上 `aos-tick` 與註冊表，註冊表放 agent 任務（吃訊息、想、送工具、回覆） | 否 |
| root helper | 唯一有 root 的小程式，只做固定動作：查登記→建資源框→切帳號→exec 固定 runner | 依部署 |
| LLM 代發 | 每個 endpoint 池一個代發服務，手上有該池的 key，替成員打 LLM | 依部署 |

kernel 和 agent 都是「資料夾＋`aos-tick`＋註冊表」，差別只在註冊表裡放了什麼。

## 一之一、daemon 怎麼運作（使用者方向 09-29）

- daemon 記憶體裡有一張表，放被註冊的資料夾；**資料夾路徑就是它的 id**（kernel id）。**agent 資料夾也一樣註冊**：對 daemon 來說兩者都是「有 inst 的資料夾」（使用者已確認）。
- daemon 依每個資料夾的設定定期跑它的 inst（也就是 tick）；同一資料夾同時只跑一格。agent 通常不設定期，只在被叫醒時跑；什麼時候叫醒誰、同時跑幾個，由它所屬的 kernel 決定。daemon 是所有 tick 程序的爸爸，kernel 的 tick 跑完就退出，不用等 agent。
- 其他程式可用 IPC（本機 socket）找 daemon：**註冊／解除註冊資料夾**、**叫醒**（某資料夾有要緊事，把它的 tick 提前到現在）。
- 誰能對哪個資料夾做這些事，看 socket 對面的 Linux 帳號：擁有該資料夾的帳號，或它上層 kernel 的帳號（建議預設）。
- daemon 不讀資料夾內容、不做排程決定、不存狀態。〔標註：後續 spec 的 daemon 有 `state.json`，見 [daemon.md](../spec/daemon/README.md)；以 spec 為準。〕**重啟後**：設定檔只列最頂層 kernel；開機先跑它一格，每個 kernel 的 tick 會把自己底下的成員（kernel 與 agent）重新註冊一次（重複註冊無害），整棵樹一層層長回來（使用者已確認）。

## 二、kernel 樹

- 每個 kernel 管一群成員：agent，或下一層 kernel。下一層 kernel 在上一層眼中就是一件工作。
- **資源一層層往下分**：上層分給下層一塊（CPU／記憶體／pids 的 cgroup 子樹、同時能跑幾件、LLM 額度、磁碟記帳），下層在這塊裡再分給自己的成員。cgroup v2 的樹剛好對上：上層 kernel 的框包住下層 kernel 的框，再包住成員的框。
- **LLM 也是資源**：和 CPU 一樣由 kernel 分配與排程。
- **沒有帳本**（第五批）：狀態就是資料夾裡的檔案。每個資料夾同時只有一格 tick 在改它；沒有全域唯一寫入者。
- 上層只看下層的摘要，不讀下層成員的內容。
- **資源管理是可插拔的模組**（第五批）：kernel 管哪些資源由它註冊了哪些資源 module 決定。例如某個團隊不想管網路消耗，它的 kernel 就不裝網路 module，網路就不記也不限。CPU、記憶體、pids、LLM、磁碟記帳、網路都是同一種 module；裝 module 就是在 kernel 註冊表加一項（使用者已確認）。

## 三、權限

- **最頂層 kernel 和其他 kernel 沒有不同**，只是被設定了一些高級的系統面權限，例如可以使用 root helper。
- 權限是設定出來的，不是寫死在某個角色上；照[通則](archive/spec-2026-10-02/readme/01-來源原則平台與交付.md#原則能下指令能管檔案就能交給-agent)，能下指令、能管檔案的事，開放權限就能做。
- **LLM endpoint 池**：通常由最頂層掌管，但其他 kernel 也可以有自己的 endpoint 池。key 只在該池的代發服務手上，agent 與工具讀不到（延續裁定 9）。〔標註：已被第八批改：沒經 helper 的不受保護、直連 key 必須 agent 讀得到，現見 [llm.md](archive/spec-2026-10-02/scheduling/llm.md)。〕

## 四、註冊式 tick（第三批裁定）

- loop 只做「跑一次 inst」，inst 的程式就是 `aos-tick`。
- `aos-tick` 依註冊表順序跑任務：系統性任務 → agent（或 kernel）任務 → 自訂任務。
- **group**：組內全部成功，才把這組交給帳本的結果一起寫進去〔標註：「帳本」已不存在，現見 [tick.md](../spec/tick.md)〕；任一失敗整組不算。任務自己直接改的檔案不回滾。
- **needs**：前置任務成功才執行。
- 要 root 的步驟固定在 root helper，不進註冊表；註冊表的系統任務不是 root。
- 用 LLM、跑工具一律先送出去，下次 tick 收結果。
- group 失敗時撤回的範圍改由 git 決定：追蹤中的資料夾變動一起還原，`.gitignore` 的不管，外部不可逆後果不管（第五批，取代第三批「只撤回交給帳本的結果」）。

## 五、資料夾變動用 git 做原子套用（第五批）

使用者原意：「帳本」要的其實是**原子操作紀錄**——先把可能的後果記下來，條件都滿足後才一起套用到實際狀態。這件事只管**資料夾內的變動**，用 git 做；不像要管的就寫進 `.gitignore`。工具造成的不可逆外部後果（打 API、寄信等）不管。

使用者已確認（09-29）：收件區 `.gitignore`、吃訊息＝搬進追蹤區；資源 module 走 kernel 註冊表；**不用 sqlite**；帳本原本做的其他事（去重、先後、到期、查詢）靠檔案，但**設計要精簡**，不要用檔案重做一套帳本。

做法：
- 每個 agent／kernel 資料夾是一個 git repo。一格 tick 開始時工作區應該是乾淨的（等於上一次 commit）。
- group 的任務跑完，**全部成功就 commit** 這組造成的變動；任一失敗就把追蹤中的檔案還原到上一次 commit（`git checkout`／`git clean` 追蹤範圍），整組當沒發生。
- 別人投進來的東西（新訊息、工具／LLM 結果）落在 `.gitignore` 的收件區，不會被還原掉；tick 吃掉一則訊息，就是在 group 裡把它搬進追蹤區，跟著 commit 一起生效。
- 當機或 daemon 重啟：下一格開始前，工作區若有沒 commit 的變動，一律還原到上一次 commit——沒交完的 group 就當沒發生。這取代原本帳本的恢復邏輯。
- 去重、先後、到期這些原本靠帳本的東西，改靠檔案：請求 ID 當檔名（檔案在就是收過）、序號寫在檔名或狀態檔、到期時間寫在狀態檔。
- 送出去還沒回來的 LLM／工具請求，重啟時一律殺掉；沒有結果檔就標 unknown，不自動重做（照舊）。

## 五之一、身分：inst 宣告＋註冊時發的身分額度（第六批）

- **通用 user**：預設就是開 daemon 的那個 user，可另外設定。沒有 root helper 時整棵樹都用它。
- **inst 宣告身分**，不看資料夾放在哪。沒寫就繼承上層 kernel 的身分；最頂層 kernel 的身分是通用 user。
- **身分額度**：上層 kernel 向 daemon 註冊成員時，一併給它准用的身分；只能給自己手上有的。最頂層的額度寫在 daemon 設定檔（沒 helper 時只有通用 user）。額度只在 daemon 記憶體裡，重啟時隨重新註冊長回來。
- 開 tick 時 inst 宣告的身分必須落在額度內，否則不跑並寫一件待處理事項。身分就是通用 user 時 daemon 自己開；不是時交給 root helper 切帳號。

### inst 格式（proto6 第 1 版，使用者已確認）

proto6 的 inst 以 proto5 [inst-posix](../../proto5/spec/inst-posix/README.md) 為底，多一個頂層欄位 `user`，其他六欄與指示詞規則不變。**不管 proto5 舊版相容**，這就是 proto6 的第 1 版：

```json
{
  "_metainfo": {"_type": "posix", "_version": 1},
  "user": "aos-a0042",
  "argv": ["aos-tick"],
  "cwd": "."
}
```

1. 執行者必須認得 `user`；不認得就不能執行這份 inst（不能默默忽略後用自己的身分跑）。
2. **`user` 型別**：Linux 帳號名稱字串，或非負整數 UID。沒寫或空字串＝繼承。補充群組照該帳號在系統裡的設定（等同 `initgroups`），inst 不另寫群組。
3. **`user` 不吃指示詞**（`$env`／`$fmt`／`$ref` 都不行，寫了就是錯）：身分要讓人一眼看檔案就知道，也讓 daemon 不必解析其他內容就能先做授權檢查。
4. **授權先於一切**：daemon 只讀 `user` 這一欄做額度檢查；不過就是「根本沒跑」（沿用執行者自己失敗的 125，錯誤代號例如 `UserNotGranted`），不寫 `exit`。
5. **其他欄位在切完身分之後才解**：`$ref` 讀檔、`$env`、`cwd` 的 `mkdir`、開 `stdin`／`stdout`／`stderr`／`exit` 檔，全部由切成目標身分後的 runner 做。否則 daemon（或 root）會用自己的權限替 agent 讀別人的檔、寫別人的位置——等於借權限偷看或亂寫。沒有 helper、身分就是通用 user 時，這條自然成立。
6. **資源框不寫在 inst**：程序放進哪個 cgroup 由 kernel 樹與註冊決定，inst 只管「用誰、跑什麼」。

## 六、照舊的

一個 agent 一個 UID；root helper 極小；控制端重啟（現在是 daemon 重啟或 VM 關機）在途全殺、結果不明標 unknown、不自動重做；同一資料夾同時只准一格 tick，舊程序確定清掉才開下一格；排隊用序號；磁碟額度可選、只記帳；原生 Linux 與 WSL 同一套；工具就是工具。

## 七、待定（附建議）

1. ~~下層 kernel 用不用自己的 Linux 帳號~~：已解（第九批），kernel node 用自己 inst 的 `user`。
2. **下層 kernel 怎麼啟動成員**：成員要切 UID，得經 root helper。建議把「可用 helper」當成可授予的權限，並限定在被授權 kernel 的子樹內：helper（或替它把關的 daemon）核對「這個成員確實登記在發出請求的 kernel 底下，且這個 kernel 有 helper 權限」。另一種作法是一律往上交給最頂層代開，但每層多一趟轉手。〔標註：已定，見 [P-104](../spec/deferred/protocol/daemon/registration.md)。〕
3. **登記鏈**：誰屬於哪個 kernel，要從最頂層一路接下來，防止下層 kernel 冒名開別隊的成員。〔標註：已定，見 [registration.md](../spec/deferred/protocol/daemon/registration.md)。〕
4. ~~下層自有 endpoint 池的代發服務用誰的帳號跑~~：已解（第九批），用該 kernel node 的帳號。
5. ~~跨隊傳訊~~：已定（第九批），有權限就直投對方收件處。
6. **延遲**：每多一層 kernel，一件工作多轉一手；proto5 量 tick 間隔時吃過虧，要在設計時控制層數與喚醒路徑。
