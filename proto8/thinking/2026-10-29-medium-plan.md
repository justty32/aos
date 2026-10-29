# 2026-10-29 介質後續規劃：投遞、有順序的投遞、daemon 的兩個手把、鎖的用法、父子交代、窗的改口

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜題目來源：[10-28 medium](2026-10-28-medium.md)（決定 1～29）｜相關條文：[N-14～N-17](../docs/NORMS/05-基礎設施-窗.md)、[N-28、N-54](../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-57、N-63](../docs/NORMS/10-基礎設施-定義與工作區.md)、[N-43](../docs/NORMS/01-總則.md)、[P-11～P-14](../docs/CONVENTION/02-題目stack停錯腦.md)、[P-32、P-36、P-39](../docs/CONVENTION/06-巢狀.md)

**這是什麼**：10-28～10-29 的介質討論收線後（medium 決定 29「可以開始規劃了」），照 [user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md)「規劃交給 fable、只把衝突帶給他」寫的**細節設計**。前提是 medium 的決定 1～29，每一條都當定案、不翻；細節照 CONCEPTS／NORMS 的原則自己定，標「照哪條」。寫的時候只寫文件、程式與 NORMS／CONVENTION 正文都沒改；**使用者 10-29 看完最後兩節（衝突、方向題）回「都照建議」**，九條照下面「決定」一節定案，之後才落條文、動程式。

白話總綱：aos 裡兩個程式講話只有三種底：**投遞**（把一封信放進對方的資料夾，每封都算數）、**窗**（一個固定檔，只看最新那份）、**父子交代**（生小孩時給的參數與環境變數、小孩結束時留下的結束碼與檔）。其他都是這三種拼出來的。鎖不是講話，是「這東西我在用」的牌子，只在有順序的投遞那一層用到。

## 決定（使用者 10-29「都照建議」）

使用者看了衝突六條與方向題三條，原文逐字：「都照建議」。所以：

1. 衝突 1：信箱放哪由擁有者定、不強制在 `$AOS_STACK`；N-14 改口，只有窗（state／ctl）強制在 stack。
2. 衝突 2：題目信箱（一題一個 `.txt`）不算標準投遞，是 agent 慣例自己的簡化信箱，P-11 加註；新東西才走標準。
3. 衝突 3：aos-kernel-llm 的回信（`done/`＋`reply.json`）先留著，實作步驟 6 有空再改成 `reply_to`。
4. 衝突 4：kernel 的 flock 檔 `<信箱>/.lock` 改名（`.flock`），資料夾鎖維持 `.lock/`。
5. 衝突 5：`ctl.json` 裡的 `loops*` 過渡期在 `state.json` 的 `ctl_warning` 提醒「已搬到 `loops_ctl.json`」，之後拿掉。
6. 衝突 6：判死活兩套都留（窗與鎖用 pid＋`started_at_ticks`＋`boot_id`；kernel 看寄信人用 flock），各管各的。
7. 方向題 1：信箱模式重起後，`adopt` 接回的子項留在名單上，直到有信把它 `loops_removed`。
8. 方向題 2：信封定 `reply_to`／`in_reply_to`，選填。
9. 方向題 3：人寄信的 `sender`＝`$AOS_WS`，沒設才退回 `~/`（跟程式同一條規則）。

## 一、用詞（照 C-54 命名；決定 19、28）

| 詞 | 意思 | 不是 |
|---|---|---|
| 投遞 | 寄信人把一封信放進一個**信箱**資料夾，處理者一封一封拿走；每封都算、不能漏 | 不是 queue（沒有「隊伍」的保證，只有「每封都在」） |
| 信箱 | 一個資料夾，裡面固定四格 `tmp/`、`new/`、`cur/`（第四格 `done/` 選用，見 § 二 5） | 不是窗 |
| 信 | 一個資料夾，名字叫**信號**，裡面必有 `letter.json`（信封＋內容） | 不是單一檔（衝突 2） |
| 窗 | 一個固定檔（`state.json`、`ctl.json` 這類），只有最新那份算數、舊的被蓋掉無妨（決定 19） | 信箱、鎖都不算窗（跟 N-14 草稿不同，見條文草稿） |
| 手把 | 給人寫的窗（ctl）；狀態窗＝程式自己寫、給人讀的窗（state） | |
| 父子交代 | 上一代生下一代時給的東西（args、stdin、環境變數）、下一代結束時留下的東西（結束碼、stdout、stack 裡的檔）；只在上下兩代之間（決定 28） | |
| 身分 | 一條路徑，通常是資料夾（決定 22）：程式＝它的工作區 `$AOS_WS`（擁有者＝工作區，決定 23）；人＝`~/`（決定 25） | 不是 pid、不是名字 |

## 二、投遞（決定 4、18、19、21）

### 1. 信箱的佈局（照 N-16 Maildir、N-05 暫存再改名）

```
<信箱>/
  tmp/<信號>/      寄信人正在寫、或正在撤回／丟棄的信；處理者永遠不看這格
  new/<信號>/      寄好了、排隊中
  cur/<信號>/      被處理者認領、處理中
  done/<信號>/     選用：處理者想留紀錄才有（aos 不管紀錄，決定 26）
```

- 四格在**同一個檔案系統**（同一個信箱資料夾底下，rename 才是原子的）。信箱資料夾由擁有者建好四格；沒建好＝寄信人退 1 `MailboxMissing`（沿用 aos-gate 的代號）。
- 信箱放哪由擁有者定：程式的信箱放自己 stack 裡（N-13 精神：是它內部狀態的外顯）；別人怎麼找到它＝hub 型環境變數（N-63，例 `AOS_KERNEL`）或叫它時明給（P-39）。**不強制落在 `$AOS_STACK`**（這是對 N-14 草稿的改口，見條文草稿與衝突 1）。

### 2. 一封信的格式：`letter.json`（決定 4「跟 ctl／state 一起定」、決定 9、22）

一封信＝一個資料夾（跟 aos-kernel-llm 現行一樣），裡面：

- `letter.json`（必有）：

```json
{
  "kind": "letter",
  "sender": "/home/u/proj/ws",
  "sent_at": "2026-10-29T08:12:33.123Z",
  "reply_to": "/home/u/proj/ws/.stack/replies",
  "in_reply_to": "20261029081233123456789.4121.88213",
  "body": { "loops_added": { "bob": "../agent-bob" } }
}
```

| 欄位 | 必填 | 意思 | 照 |
|---|---|---|---|
| `kind` | 是 | 固定 `"letter"`，自述種類 | N-14 窗內自述 `kind`，信也照做 |
| `sender` | 是 | 寄信人的身分＝路徑：程式填自己的 `$AOS_WS`、人填 `~/`（`$HOME` 展開後的絕對路徑） | 決定 22、23、25 |
| `sent_at` | 是 | 寄出時間，ISO 8601 UTC 到毫秒 | C-54 R6 `<發生了什麼>_at` |
| `reply_to` | 否 | 要回信就寫一個**信箱**的路徑；處理完回信投進去（回信也是一封信）。沒寫＝不回 | 決定 9「要定就從請求格式下手」、決定 27 失敗不另外通知 |
| `in_reply_to` | 否 | 這封是回信時，寫原信的信號 | 同上 |
| `body` | 是 | 內容，**形狀由收信的那支程式定**（daemon 的管轄信箱＝管轄手把的那幾個 key，見 § 四）；信封不管內容 | C-52 每層只管自己、N-27 參數怎麼進由程式自己說 |

不認得的 key 一律忽略（C-48），所以 aos-kernel-llm 現在的 `inst`／`env`／`priority` 可以原樣留在 `body` 外面過渡。其他檔（附件、處理時產生的 `stdout.txt`、`reply.json`）隨意，標準不管。

**信號**（資料夾名）：`<sent_at 的 UTC 奈秒 20 位>.<pid>.<started_at_ticks>`，跟 aos-kernel-llm 現行一樣。它只保證同一台機器上不撞名；按名字排序**大致**是時間順序，但標準不保證順序（決定 8 時間差不處理；要順序走 § 三）。pid 在這裡只是湊獨一無二，不是身分。

### 3. 寄信人的流程（只用 Linux 原子動作：mkdir、rename；決定 18）

1. `mkdir <信箱>/tmp/<信號>`——mkdir 本身是原子的，成功就是自己的；失敗（撞名）換個信號再來。
2. 在裡面寫 `letter.json` 與附件（在 tmp 裡寫，不必再暫存改名；N-05 的精神已由 tmp 這一格達成）。
3. `rename(tmp/<信號>, new/<信號>)`——資料夾改名是原子的：處理者**看到就是完整的**，永遠不會讀到半截。
4. 要撤回：`rename(new/<信號>, tmp/<信號>)` 成功＝撤回了，再刪；失敗（ENOENT）＝已被認領，撤不了。**認領是界線**（agent-round 已這樣做）。
5. 寄信人寫到一半死掉：殘骸留在 `tmp/`，處理者不碰、不礙事；收屍照決定 23——寄信人的上一層收，沒上一層就留著（KISS：標準不為這個加機制；要讓人判死，寄信人可以自己照 aos-gate 的 `sender.lock` 做，選用）。

### 4. 處理者的流程

1. 列 `new/`，照名字排序（只是方便，不是保證），逐封 `rename(new/<信號>, cur/<信號>)`——成功＝認領到了，只有一個人會成功；失敗＝被撤或被別人拿走，跳過。
2. 處理 `cur/<信號>`。有 `reply_to` 的，處理完把回信（一封新的信，`in_reply_to` 填原信號、`body` 自訂）照 § 3 投進 `reply_to` 指的信箱。
3. 處理完：預設刪掉——先 `rename(cur/<信號>, tmp/<信號>)` 再刪（跟 kernel 現行一樣，`cur/` 裡永遠不會出現刪一半的）；想留紀錄的 `rename` 進 `done/`，自己定（決定 26）。
4. **壞信**（`letter.json` 不是 JSON、缺必填、`body` 不合收信程式的形狀）：丟掉（照 3），原因寫進自己狀態窗的 `letter_warning`（同 N-08 對壞 ctl 的做法）；**不另外通知寄信人**（決定 27）。
5. **一個信箱預設只有一個處理者**（同 N-09「一個 state 只有一個寫者」的精神，C-56）。處理者起來時 `cur/` 不空＝上次自己做到一半死掉的，怎麼辦自己定（daemon 建議重做，因為管轄的信是宣告式片段、重做無害）。要多個處理者搶同一個信箱，rename 認領本來就不會重複，但 `cur/` 殘骸就分不出是誰的——要的人自己在信裡加 holder 名牌（照 N-15），標準不做。
6. **同一輪多封**（決定 20 信箱模式）：處理者每圈把 `new/` **全部**認領、照名字順序一封封套用，套完才動手（對 daemon 就是對一次表）；兩封矛盾＝順序定輸贏、後面的蓋前面的。等變化：輪詢保底（照自己的 `interval_ms`），inotify 加速選用（N-14）。

### 5. 跟現有實作的對照

- aos-kernel-llm 的信箱已經是這個形狀（tmp／new／cur／done、信＝資料夾、rename 認領、`tmp/` 刪）；差的只有 `letter.json` 的信封欄位、回信走 `done/`＋`reply.json` 而不是 `reply_to`（衝突 3）。
- agent 的題目信箱（P-11，`$AOS_WS/new cur out done`）與 aos-hub 的代答信箱：一題一個 `.txt` 檔、沒有 `tmp/`、答案另放 `out/`——不是這個標準的形狀（衝突 2）。
- hub-kernel 的指令走 unix socket：照決定 12～15「自己處理、不寫進標準」，不受影響。

## 三、有順序的投遞（決定 7，建在 § 二之上）

使用者的做法：「另外設置一個檔案或資料夾，有鎖的，大家要投遞就去取鎖，取得順序」。細節：

- 有序信箱＝普通信箱多兩樣：`<信箱>/order.lock/`（一把鎖，形狀照 § 五）與 `<信箱>/order.json`（`{"counter_letters": N}`，C-54 R6 計數叫 `counter_*`）。
- 寄信人：**拿鎖 → 讀 `order.json` 的 N → 信號改成 `<N+1 零填 12 位>.<原信號>` → 照 § 二 3 寫進 `tmp/`、rename 進 `new/` → `order.json` 寫 N+1（N-05 暫存改名）→ 放鎖**。鎖握到 rename 完才放，所以**到達 `new/` 的順序＝取號順序**，處理者照名字排序就是有順序的。
- 處理者完全不用改（它本來就照名字排序）。
- 為什麼用計數不用時間：時鐘會倒退（NTP 校時），計數不會；多一個檔是 KISS 允許的最小代價。順序只在「拿到鎖的那一刻」有意義（決定 8 時間差不處理）：先拿到鎖的先排。
- 拿鎖的人死在中間：下一個寄信人照 § 五收屍；`order.json` 要嘛舊值（信沒投進去）、要嘛新值（投進去了），不會壞。

## 四、aos-daemon 的兩個手把、兩扇狀態窗（決定 2、3、20）

### 1. 命名與位置（C-54：窗名由程式自訂、daemon.json 的 key 跟著現行 `ctl`／`state`）

| 面向 | 手把（人寫） | 狀態窗（daemon 寫） | daemon.json 的 key（路徑，相對 `$AOS_STACK`） |
|---|---|---|---|
| loop 面向與自身屬性 | `ctl.json` | `state.json` | `ctl`、`state`（現行，不變；跟 aos-loop 同一套，N-28 超集照舊） |
| 管轄的 aos 函數 | `loops_ctl.json` | `loops_state.json` | `loops_ctl`、`loops_state`（新；沒寫＝預設這兩個名字；寫 `null`＝不開） |

- `ctl.json` 只認 loop 那幾個：`paused`、`stopped`、`max`、`interval_ms`、`seq`（N-07、N-33）。**不再認 `loops`／`loops_added`／`loops_removed`**：寫了＝不認得的 key、忽略（C-48；「不留舊名」是 NORMS 的既定做法，衝突 5）。
- `loops_ctl.json` 認 `loops`、`loops_added`、`loops_removed`、`seq`，語意照 N-54 一字不改（宣告式、先加後減、整份壞就不採用）。
- `state.json` 照 N-17／N-32：`kind`、`phase`、`counter_runs`、`max`、`interval_ms`、`paused`、`ctl_seq`、`ctl_warning`、心跳四欄（`pid`、`started_at_ticks`、`boot_id`、`recorded_at`）、收尾的 `code`。**拿掉 `loops` 表**。
- `loops_state.json`：`kind: "state"`、`loops` 表（每列照現行：`pid`、`started_at_ticks`、`phase`、`code`、`signal`；超過 100 列照 N-28 切成 `loops_state_loops/<雜湊>.json`，分頁資料夾名跟著窗名）、`ctl_seq`（回的是 `loops_ctl.json` 的 seq）、`ctl_warning`（壞的 `loops_ctl`）、`letter_warning`（信箱模式的壞信，§ 二 4）、同一組心跳四欄（同一個行程、同一個值；讀這扇窗的人才不用再開另一扇判死活，N-17「每扇 state 都帶心跳」）。
- 撞名規則（N-28 10-22 落實）跟著多兩個名字：子項不能叫 `loops_ctl`、`loops_state`、`loops_state_loops`。`adopt` 改讀 `loops_state.json`。

### 2. 同一圈兩邊都改了怎麼處理（決定 3「剩下都是細節」，這裡代定）

每圈開頭先讀 `ctl.json`、再讀 `loops_ctl.json`，各自獨立採用或不採用（一份壞不影響另一份）。順序：`stopped`＝這圈收工（照 P-36 收子項），不再看管轄；`paused`＝**整圈暫停**：不起自己的 `exec`、**也不調表**（名單的變動等解除暫停那圈才生效），但照寫兩扇 state、照讀兩份 ctl、照收已送 SIGTERM 的子項。理由：daemon 的「一次」就是「調整管轄的那一圈」（決定 2），暫停 loop 面向＝暫停那一圈；要凍結名單又讓 daemon 跑 `exec`，就別寫新的 `loops_ctl`。可翻案。

### 3. 管轄的第二種模式：信箱（aos-daemon-2，決定 4、20）

- daemon.json 多一個選填 key `loops_mailbox`（路徑，相對 `$AOS_STACK`，例 `"loops_mailbox": "loops_mailbox"`）。**寫了＝信箱模式**：daemon 建好四格、每圈照 § 二 4 處理全部的信；這時 `loops_ctl` 不開（兩個都寫＝`CfgBad` 退 1——決定 20 說哪個負責由設計者定，aos-daemon 這支就定「二選一」）。
- 信的 `body` 就是管轄手把的片段：`{"loops_added": {...}}`、`{"loops_removed": [...]}`，寫法同 N-54。沒有 `loops`（整份名單）那個 key——信是「增減」，整份宣告留給 ctl 模式。
- **期望表**＝daemon.json 的 `loops` ＋ 重起時 `adopt` 接回的子項 ＋ 依序套用每封信的增減。接回的子項留在名單上，直到有信把它 `loops_removed`（方向題 1）。
- 每圈：全部認領 → 照名字順序套用 → 對一次表 → 信刪掉（預設）或進 `done/`。壞信照 § 二 4。
- 誰能寄：純靠 Linux 檔案權限（C-64、N-54 末；sandbox S17）——信箱 `new/`、`tmp/` 開給誰寫，誰就能寄。aos 不另做名單。
- 回信：寄信人要知道「加進去了沒」，標準做法是**讀 `loops_state.json`**（窗）；寫了 `reply_to` 的，daemon 套用完回一封 `body: {"applied": true}`（或 `{"applied": false, "reason": …}`）。失敗不另外通知（決定 27）。

## 五、鎖：本設計怎麼用（決定 5、10、18；N-15 仍是草稿）

本設計**只有一個地方需要鎖**：有順序的投遞的 `order.lock/`。投遞本身（rename 認領）、窗（N-05 暫存改名）、兩個手把（N-54：多人寫靠 Linux 權限）都不用鎖。鎖的形狀照 medium「留待實作」的頂層四點，只改一處：

1. 只做一種獨佔鎖、不分讀寫；讀的人靠 N-05 暫存改名拿到完整檔。（採）
2. 資料夾的鎖是 `<資料夾>/.lock/`、檔的鎖是 `<檔>.lock/`，`mkdir` 成功＝拿到；不檢查上下層。（採；`order.lock/` 就是「`order.json` 這個檔的鎖」）
3. 名牌 `holder.json`：**多一欄 `holder`＝持有者的身分路徑（決定 22；程式＝`$AOS_WS`、人＝`~/`）**，其餘照四點——`pid`、`started_at_ticks`、`boot_id`（N-17 判死活用）、`acquired_at`、選填 `lease_ms` 與 `note`。放鎖＝先把鎖資料夾改名成獨一無二的名字（`.lock.releasing.<信號>`）再刪，別人不會 mkdir 到一個正在被刪的資料夾。（採，加 `holder`）
4. flock 只拿來同機加速，不當正確性依據。（採）

收屍（N-15）：想拿鎖的人 mkdir 失敗時讀 `holder.json`，持有者 pid＋`started_at_ticks`＋`boot_id` 對不上（死了）或 `lease_ms` 過期，就照 3 的放鎖步驟替它收，再重新 mkdir；兩人同時收也沒事（改名只有一個會成功）。「約定、不必擋得住」（決定 10）：從 Linux 繞過去 aos 不管。

## 六、父子交代（決定 28）：現有的夠不夠

現有的標準：進＝args、stdin、aos-exec 保證的六個環境變數（N-57）＋hub 型變數（N-63，繼承），參數怎麼進由被叫的程式自己說（N-27、P-26）；出＝結束碼（N-43）、stdout、stack 裡的檔（N-13）。巢狀怎麼給 stack 與工作區（P-32、P-39）。

結論：**夠，缺的只有「集中說一次」**——這三樣散在五條裡，沒有一條說「這就是父子交代」。補一條 N-64（草稿）把它們點名，加兩句：① 下一代要自報身分就報 `$AOS_WS`（決定 22、23），上一代給的工作區就是它的名字；② 上一代要讓下一代找到自己的信箱或窗，用 hub 型變數（N-63）或 args 明給，不另加新的環境變數（C-69 aos 只訂那幾個）。用不用都可以（使用者原話）。

daemon 起子 loop 就是父子交代的一個實例：寫小格 `loop.json`、`AOS_STACK=小格`、起 `aos-exec 小格/loop.json#/_entry`——完全在現有標準內。

## 七、身分、擁有與收屍、介質可套、人算 proc：落在哪裡

| 決定 | 落在 |
|---|---|
| 22 身分＝路徑 | 信封 `sender`、鎖名牌 `holder`、父子交代自報身分（N-64）：都填 `$AOS_WS`；人填 `~/` |
| 23 擁有與收屍（代定） | 信箱的擁有者＝處理者（建它的那支）：`cur/` 殘骸它自己收（§ 二 4 第 5 點）；`tmp/` 殘骸歸寄信人、它的上一層收；鎖的殘骸由下一個要鎖的人照 N-15 收；daemon 死了子 loop 跟著收（P-36 整群殺，現行） |
| 24 介質可套、每層只看底下那層 | 子 loop 自己也可以是 daemon、有自己的信箱與 `loops_ctl`，放在它的小格裡；上一層 daemon 只看自己的表（C-52），不去看孫子 |
| 25 人算 proc、路徑是 `~/` | 人用 aos-say 之類寄信時 `sender` 填 `~/`；人直接寫 `ctl.json` 不留名（窗本來就不記誰寫的） |
| 26 紀錄 aos 不管 | `done/` 選用、信處理完預設刪；`letter_warning` 只是窗欄位，不是紀錄 |
| 27 失敗不另外通知 | 壞信丟掉只記 `letter_warning`；要知道結果讀對方的窗或自己寫 `reply_to` |

## 條文草稿（已定 10-29；照「決定」一節落進 NORMS／CONVENTION）

- **C-75（新，概念；只收使用者說過的）** proc 之間的交流有三種基本概念：**投遞**（「通常會有一個資料夾，大家就將請求投遞過去」，10-28 第三段）、**窗**（「窗可以跟投遞並列」，10-29 第十段）、**父子交代**（「父子交代...可以算基本概念，用不用都可以，用了的話我們也提供一些aos標準供人遵守」，10-29 第十四段）。其餘是組合。鎖是「宣告某個資料夾或檔案正在被佔據着」（第四段），不是交流。管線、檔案串流、訊號不寫進標準（決定 12～15）。
- **N-14（改口）** 窗＝**只看最新那份的固定檔**：state、ctl、公告（只有一人能寫的窗）。共通規則照舊：落在 `$AOS_STACK`、名字由程式自訂（N-13）、自述 `kind`、內容 JSON、原子性只靠 rename（N-05）、判斷變化比內容或序號、回音以 `seq` 為準、等變化輪詢保底 inotify 加速。**刪掉**「鎖、號誌、信箱、一問一答都是窗」那句：信箱歸投遞（N-16）、鎖另算（N-15）、一問一答＝投遞＋`reply_to`、號誌＝鎖的用法。（10-29 使用者「窗可以跟投遞並列」）
- **N-16（改口＋補）** 投遞與信箱：信箱＝一個資料夾、四格 `tmp/`、`new/`、`cur/`（`done/` 選用）、同一檔案系統；一封信＝一個資料夾（信號 `<UTC 奈秒 20 位>.<pid>.<started_at_ticks>`），必有 `letter.json`：`kind: "letter"`、`sender`（寄信人身分＝路徑）、`sent_at`、選填 `reply_to`（信箱路徑）、`in_reply_to`、`body`（形狀由收信程式定）。寄＝mkdir `tmp/` → 寫 → rename 進 `new/`；認領＝rename 進 `cur/`，成功的那個人才算；撤回＝rename 回 `tmp/`，進了 `cur/` 就撤不了；處理完預設刪（先 rename 回 `tmp/`）、要留進 `done/`；壞信丟掉、原因記自己 state 的 `letter_warning`、不通知寄信人（決定 27）；位置由擁有者定、別人靠 hub 型變數或明給找到（N-63）。一個信箱預設一個處理者；`tmp/` 殘骸處理者不碰。**有順序的投遞**：信箱多 `order.lock/`（N-15 的鎖）與 `order.json`（`counter_letters`），寄信人拿鎖→取號→信號前綴 12 位序號→投進 `new/`→寫回計數→放鎖，鎖握到 rename 完。aos-kernel-llm 現行的 `done/`＋`reply.json` 是它自己的回信方式（決定 9 允許），過渡期照舊。
- **N-15（補一句，仍草稿）** 名牌 `holder.json` 多一欄 `holder`＝持有者身分路徑（決定 22）；放鎖先改名成獨一無二的名字再刪。其餘照 10-28「留待實作」四點，實作時定。
- **N-28（補）** daemon.json 多三個選填 key：`loops_ctl`、`loops_state`（路徑，預設 `loops_ctl.json`、`loops_state.json`，`null`＝不開）、`loops_mailbox`（路徑；寫了＝信箱模式、`loops_ctl` 不開，兩個都寫＝`CfgBad`）。state 窗拿掉 `loops` 表、搬到 `loops_state`；分頁資料夾叫 `loops_state_loops/`；`adopt` 讀 `loops_state`。子項撞名多擋 `loops_ctl`、`loops_state`、`loops_state_loops`。
- **N-54（改口）** 「daemon 表上有誰，寫在 daemon 的 **管轄手把** `loops_ctl.json`」——`loops`、`loops_added`、`loops_removed`、`seq` 語意不變；`ctl.json` 不再認這三個（寫了忽略，C-48）。末句補：多人要改名單，除了靠 Linux 權限讓一人寫 ctl，也可以改開信箱模式（`loops_mailbox`），信的 `body` 是 `loops_added`／`loops_removed` 片段，每圈全部認領、照順序套用。（使用者 10-28「一個控制loop面向和自身屬性，一個控制管轄的aos函數」、10-29「ctl和投遞信箱並存...這就是兩套模式」）
- **N-07（補一句）** daemon 的 `paused`＝整圈暫停（不起 `exec`、不調表；照寫 state、照讀 ctl、照收已送 SIGTERM 的子項）。
- **N-64（新）** 父子交代（選用）：上一代給下一代的＝args、stdin、六個環境變數（N-57）與 hub 型變數（N-63）；下一代留給上一代的＝結束碼（N-43）、stdout、stack 裡的檔（N-13）。參數怎麼進由下一代自己說（N-27）。下一代自報身分＝`$AOS_WS`（決定 22、23）；上一代要讓下一代找到自己的信箱或窗，用 hub 型變數或 args 明給，不另加環境變數（C-69）。（使用者 10-29「用不用都可以，用了的話我們也提供一些aos標準供人遵守」）
- **CONVENTION P-11（加註）** 題目信箱（`$AOS_WS/new cur out done`，一題一檔）是 agent 慣例自己的簡化信箱、不是 N-16 的標準投遞（沒有 `tmp/`、沒有信封）；要不要改成標準形狀見衝突 2。
- **NORMS 待定** 加一條【基礎設施／窗】：投遞、有序投遞、daemon 兩手把、N-64 的草稿在本檔，等使用者看完衝突與方向題再落正文。

## 實作步驟（每步可驗；程式都在 `proto8/impls`，C++；順序照依賴）

1. **拆 aos-daemon 的窗**：daemon.json 認 `loops_ctl`／`loops_state`；`ctl.json` 不認 `loops*`；`state.json` 拿掉 `loops`；`loops_state.json` 帶表、心跳、`ctl_seq`、`ctl_warning`；分頁與 `adopt` 跟著搬。驗：現有 daemon 測試改過全綠；新測「`ctl.json` 寫 `loops_added` 沒反應、`loops_ctl.json` 寫才起」「同一圈 `ctl.json` 改 `interval_ms` 且 `loops_ctl.json` 加子項，兩邊都生效」「`ctl.json` 壞、`loops_ctl.json` 好，只有 `state.json` 有 `ctl_warning`」「paused 時 `loops_ctl` 的變動不生效、解除後生效」。demo/daemon 與 README、code map 同步。
2. **投遞的小工具 `aos-post`**（名字可翻案；C++ 命令列＋可 link 的 lib，像 aos-json）：`send <信箱> [--reply-to 路徑] < body.json`（印信號）、`claim <信箱>`（印一個信號，沒有退 10）、`claim-all <信箱>`（全部）、`finish <信箱> <信號> [--keep] [--reply < body.json]`、`withdraw <信箱> <信號>`、`init <信箱>`（建四格）。`sender` 自動填 `$AOS_WS`（沒設＝`~/`）。驗：20 個寄信人並發寄 200 封、一個處理者 claim-all，不漏不重；`tmp/` 裡手放一個半截資料夾永遠不被 claim；撤回：`new/` 裡的成功、`cur/` 裡的失敗；壞 `letter.json` 被 finish 丟掉。
3. **鎖的小工具 `aos-lock`**（只做 § 五那四點：`acquire <目標> [--lease-ms N]`、`release`、名牌 `holder`）。驗：兩個行程搶同一把只有一個拿到；把持有者 kill -9 後第二個人能收屍拿到；`boot_id` 不同的舊名牌也能收。
4. **有順序的投遞**：`aos-post send --ordered`（§ 三）。驗：50 個寄信人並發，`new/` 裡名字的 12 位序號連續無缺、順序＝`order.json` 計數；中途 kill 一個拿著鎖的寄信人，其他人仍能繼續。
5. **aos-daemon 信箱模式**：`loops_mailbox`（§ 四 3），每圈 claim-all → 套用 → 對表；`letter_warning`；`reply_to` 回 `applied`。驗：兩個寄信人同一圈各寄一封（一加 bob、一刪 bob）→ 名字排序後面的贏；重起 daemon 後接回的子項不被收掉（方向題 1 定了再寫死）；壞信不影響好信。
6. **回信過渡**（可延後）：aos-gate／aos-kernel-llm 的 `letter.json` 補信封欄位（`kind`、`sender`、`sent_at`），回信改走 `reply_to`（寄信人在自己 stack 開一個小信箱）；`done/` 保留當它的紀錄。驗：既有 kernel 測試全綠、沙箱裡的 agent 照 S14 綁信箱仍能寄。
7. **條文落地**：使用者看完衝突與方向題後，把上一節草稿寫進 NORMS／CONVENTION 正文（N-14、N-15、N-16、N-28、N-54、N-07、新 N-64、C-75、P-11 加註），條號表、各批出處、NORMS 待定、code map 同步，`wf-lint` broken=0。
8. **demo**：`demo/daemon-2`——一個信箱模式的 daemon、兩個寄信人腳本（一個人手寫 `aos-post send`、一個 agent 的格），README 一頁。

## 衝突（要給使用者看的；設計跟既有原則或實作對不上的地方）

1. **信箱可以不在 `$AOS_STACK` 底下** vs **N-14 草稿「窗一族位置都落在 `$AOS_STACK`」**。現在三個信箱已經三個地方：agent 的題目在工作區 `$AOS_WS/new/`、hub 的在 `.stack/`、kernel 的由 `AOS_KERNEL` 指到哪就在哪。我的設計說「信箱放哪由擁有者定，別人靠環境變數或明給找到」。選項：(a) 照我的——N-14 改口，只有窗（state／ctl）強制在 stack，信箱不管；(b) 硬性信箱也在 stack——kernel 的信箱得搬、沙箱綁路徑的設定要改。建議 (a)：信箱是給外人投的，外人本來就不知道你的 stack 在哪，位置用 hub 變數說清楚比較實在。 **已定：照建議**（使用者 10-29「都照建議」）。
2. **一封信＝一個資料夾、必有 `letter.json`** vs **P-11 題目信箱一題一個 `.txt` 檔**（aos-say／listen、agent-round 的 queue、aos-hub 的代答信箱都是這個形狀）。這三個東西長得很像投遞（也有 new／cur／done、也靠 rename 認領），但沒有 `tmp/`、沒有信封（不知道誰寄的、何時寄的）、答案另放 `out/`。選項：(a) 它們**不算**標準投遞，當 agent 慣例自己的簡化信箱（P-11 加一句註），新東西才走標準——什麼都不用改，但 aos 裡就有兩種長得像的信箱；(b) 把它們改成標準形狀——`aos-say` 寄出去的變成一個資料夾、裡面 `letter.json` 的 `body` 放題文，queue／hub／say／listen 四支都要改，人手寫題目會變麻煩（不能 `echo 題目 > new/q1.txt`）；(c) 標準放寬成「一封信可以是單一檔，單一檔沒有信封」——人手寫方便，但「誰寄的」就不保證有。建議 (a)：題目信箱是人跟 agent 講話的地方，手寫方便比較重要；真要追誰寄的、要回信的場合（daemon 管轄、kernel）才用標準。 **已定：照建議**（使用者 10-29「都照建議」）。
3. **回信走 `reply_to`（寄信人給一個信箱）** vs **aos-kernel-llm 現行回信放在原信資料夾裡、信搬到 `done/`、寄信人去 `done/<信號>` 撈**，還有它用 `sender.lock` 的 flock 判寄信人死活。決定 9 說回信可以各自處理，所以 kernel 這樣做不違規；但兩種回信法並存。選項：(a) 先留著、步驟 6 有空再改；(b) 現在就改，kernel 測試與沙箱設定跟著動。建議 (a)。 **已定：照建議**（使用者 10-29「都照建議」）。
4. **鎖是資料夾 `<檔>.lock/`** vs **kernel 的 `<信箱>/.lock` 是一個檔、拿來 flock**。同名、一個是檔一個是資料夾，放在一起會撞。選項：(a) kernel 那支改名（例 `.flock`），資料夾鎖維持 `.lock/`；(b) 資料夾鎖換名字（例 `.held/`）。建議 (a)：N-15 草稿早就寫了 `.lock/` 是資料夾，kernel 是後來照 flock 順手取的名。 **已定：照建議**（使用者 10-29「都照建議」）。
5. **`ctl.json` 裡的 `loops`／`loops_added`／`loops_removed` 會被靜默忽略**（搬去 `loops_ctl.json` 後，照 C-48「不認得的 key 一律忽略」、NORMS「不留舊名」）。後果：用舊寫法的人寫了沒反應、也沒有錯誤訊息。選項：(a) 照原則，靜默忽略；(b) 過渡期在 `state.json` 的 `ctl_warning` 提一句「`loops*` 已搬到 `loops_ctl.json`」，等於替舊名留一個提醒，跟「不留舊名」有一點點打架。建議 (b) 做一陣子、之後拿掉——現在只有 demo 與測試在用舊寫法，代價小。 **已定：照建議**（使用者 10-29「都照建議」）。
6. **判死活有兩套**：窗與鎖用 pid＋`started_at_ticks`＋`boot_id`（N-15、N-17）；kernel 看寄信人用 `sender.lock` 的 flock 有沒有人拿著（sandbox S15「純靠 Linux」）。本設計的投遞標準**不判寄信人死活**（`tmp/` 殘骸不碰），鎖照 N-15 那套，所以不新增第三套；但 kernel 那套跟 N-15 並存。選項：(a) 兩套都留，各管各的；(b) 統一成 N-15 那套，kernel 的 `sender.lock` 拿掉。建議 (a)，flock 在 N-14 本來就是「同機加速」的合法手段。 **已定：照建議**（使用者 10-29「都照建議」）。

## 方向題（原則推不出、要使用者拍板的）

1. **信箱模式的 daemon 重起後，名單怎麼算？** 背景：ctl 模式下名單永遠能從兩份檔（daemon.json＋`loops_ctl.json`）算出來，重起不會變。信箱模式下信處理完就刪了，重起後只剩 daemon.json 的名單；可是 `adopt` 會把還活著的子 loop 接回來——它們不在 daemon.json 裡，照 N-54「名單上沒有的就收掉」會被殺。例：daemon.json 只有 ann，有人寄信加了 bob，daemon 重開，bob 還活著被接回——然後呢？選項：(a) **接回的留在名單上**，直到有信叫它走（我在 § 四 3 先這樣寫）：直覺、不會誤殺，但「名單」變成算不出來的東西，得看 `loops_state.json` 才知道；(b) 回 daemon.json 的名單、多的收掉：規則乾淨，但重開一次就把別人加的全殺了；(c) daemon 自己把目前的期望表寫成一份檔（像它替自己寫 ctl），重起時讀回：名單算得出來，但多一個檔、而且 daemon 寫自己的手把跟 N-06「讀的人只讀不寫」打架。建議 (a)。 **已定：照建議**（使用者 10-29「都照建議」）。
2. **信封要不要定 `reply_to`？** 決定 9 說回信可以不定標準。定了（選填）的好處：想回信的人有共同寫法，kernel 以後能改成同一套，一問一答就是「投遞＋`reply_to`」不用另外發明；壞處：標準多兩個欄位，而且回信得再開一個信箱（寄信人自己 stack 裡一個小資料夾），比 kernel 現在「去 `done/` 撈」多一步。不定的話，daemon 管轄信箱的「加進去了沒」只能看 `loops_state.json`（決定 27 本來就是這個態度）。建議：定，選填——因為一問一答（ask_round 那類）遲早要有共同寫法。 **已定：照建議**（使用者 10-29「都照建議」）。
3. **人寄信時 `sender` 填什麼？** 決定 25 說人的路徑是 `~/`。但人常常是在某個專案資料夾裡下 `aos-say`，那個資料夾也是一條路徑。選項：(a) 一律 `~/`（照原話）；(b) 人在哪個工作區裡寄就填那個工作區（跟程式同一條規則：`sender`＝`$AOS_WS`，沒設才退回 `~/`）。差別只在事後看信能不能知道「是哪個專案的人」。建議 (b)：規則只有一條，而且 `$AOS_WS` 沒設時自然就是 `~/`，跟原話不衝突。 **已定：照建議**（使用者 10-29「都照建議」）。
