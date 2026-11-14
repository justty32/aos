這份是 board-1114 的架構設計稿（fable 寫）：布告欄、信件分級、頻道合成一套協議 `comm/1`，只讀 [01-備料](01-備料.md) 設計，給 opus 深化用，還沒施工、還沒經使用者裁。

# board-1114 02 fable 稿：`comm/1` 協議（布告欄＋信件分級＋頻道）

← [board-1114](../board-1114.md)｜上一份 [01-備料](01-備料.md)｜2026-11-14

## 〇、先講結論

1. **一套協議、三節、一個版本號**，叫 `comm/1`。三節各有自己的載體：布告欄是一個檔、分級是信件 body 裡的一個欄位、頻道是一個 proc 加兩個檔。共用同一組詞（級別、時間寫法、怎麼指一隻 proc）。
2. **布告欄＝每隻 proc 的 stack 根放一個 `board.json`**。使用者專區 `~/.aos/user` 本來就是一份 stack，所以使用者的布告欄也在同一個相對位置。誰都用「找到 stack → 讀這個檔」一招讀。
3. **分級只有三級：`urgent`（急件）、`normal`（平信）、`low`（知會）**，放在 `body.comm.level`。沒寫＝平信，所以舊信全是平信。
4. **分級只動「通知」與「先讀哪封」，不動投遞**。信一律馬上進信箱，aos-post 的排序一個字不改；「請勿打擾」只是把通知壓住，信不丟、不退。
5. **布告欄與分級是同一張表的兩個邊**：收件人布告欄的 `mode` × 這封信的 `level` → 現在通知、壓到之後、還是告訴寄件人「他不在」。表在第三節。
6. **寄信時順手把對方布告欄帶回來**。這一步就做到使用者說的「寄信給我發現很久沒回，他就會去看」，而且不花模型；另有一支每分鐘的 hook 在「等太久沒回」時自動把對方布告欄貼給寄件人。
7. **頻道＝一隻不用模型的 loop proc**。寄到它信箱的信就是發言（舊的 `aos-mailbox send` 不改就能發言），它照成員表每人轉一份；加入／退出是帶 `comm.op` 的信。管理員、加入權、發言權的欄位第一版就在檔裡，只實作最寬鬆的值。
8. **不改 aos-post、不改 aos-mailbox**。新東西全部在新指令 `aos-comm`、新庫 `lib/aos/comm`、新 pack 裡；唯一建議動的既有本體是 `mail_notify` 這支 hook（不在禁改名單內，且沒有新欄位時輸出逐字不變）。
9. 身分在 aos 這層都是「自己報的」，所以防濫用第一版靠**收件端說了算**（額度、降級、頻道封頂）；真正擋得住的要等 ok-sec 的 uid 層，第六節分開列。
10. 待使用者裁 6 條，在第十二節，每條有預設建議，不裁也能照預設往下走。

跟既有原則對過，沒有衝突，三點說明：
- user.md「proto8 不做舊格式相容」講的是不寫遷移；這裡的「相容」是新舊程式同時在跑時互不弄壞，兩件事。本稿也不寫遷移（使用者布告欄搬家就直接搬）。
- NORMS N-16／N-66 明載「aos-post 不加協議版本、不驗 body、body 由接收者定」。本協議把版本與欄位全放在 body 與自己的檔裡，正好落在這條留的空間內。
- NORMS 附錄4「持久檔帶 `format`、不符拒讀」。布告欄與頻道檔都帶 `format`；「拒讀」在這裡的意思是「當成沒有布告欄」，不報錯給寄信的人。

---

## 一、協議怎麼切（題 1）

| 決定 | 內容 | 理由 |
|---|---|---|
| 一份協議三節 | `comm/1`：§board、§letter、§channel | 三者共用級別、時間、身分的寫法；分三份會各定一套。分三節是因為載體不同、可以分批上線 |
| 版本號放哪 | 檔：`"format":"board/1"`、`"channel/1"`、`"channel-members/1"`。信：`body.comm.v = 1` | 檔照附錄4 的 `format` 慣例。信的版本不能放信封：kernel 轉寄會丟信封欄位（備料三），aos-mailbox 也沒有寫信封欄位的介面 |
| 三節同升同降 | 版本數字三節一致，升版一起升 | prototype 階段不值得維護版本矩陣 |
| 信裡用一個物件 `comm`，不攤平 | 所有新欄位收在 `body.comm` 一個鍵底下 | 只佔一個名字，不會撞到 llm kernel 的 `priority`、使用者專區的 `urgent`／`deadline`，也不會撞到 `aos-mailbox read` 攤平時的十三個既有鍵（已對過原碼 `flat()`：letter、sender、sent_at、reply_to、in_reply_to、from、to、status、title、what、outputs、not_done、decide） |
| 機讀定義 | JSON Schema 2020-12，四份：`board.json`、`letter-comm.json`、`channel.json`、`channel-members.json`，`$id` 取 `comm/1/board` 這種形狀（照 `user-zone/1/letter` 的前例） | 跟使用者專區同一種工具鏈；普通 proc 可以不驗，只照欄位表讀寫 |
| 放哪 | schema：`proto8/schema/comm/1/`；規格文件：`proto8/docs/` 下一份「comm 協議」；知識庫：`aos/comm.json`（agent 查得到） | 位置由 opus 對 code map 定，這裡只定「三處都要有」 |
| 時間寫法 | 一律照信封 `sent_at`：ISO 8601 UTC 到毫秒，`2026-11-14T06:30:00.000+00:00`；欄名一律 `_at` 結尾 | 跟 aos-post 同一種（post.hpp:11），命名照 NORMS 命名.md |
| 怎麼指一隻 proc | 對人顯示用名字；程式認的是 **stack 絕對路徑** | 名字會重複、會被重用；路徑不會 |
| 未知欄位 | 讀的人一律**忽略不認得的鍵**、不報錯；寫的人不得依賴別人認得 | 這是「舊程式不壞」的另一半：以後的 `comm/2` 也不能弄壞 `comm/1` 的讀者 |
| 壞資料 | 布告欄讀不了／`format` 不認得 → 當沒有布告欄。`comm` 不是物件／`v` 大於 1／`level` 不認得 → 當平信、照常處理 | 協議是加分項，壞了只能退回「沒有這套」的行為，不能讓信寄不出去 |

**進 NORMS 的建議**（NORMS 只收使用者已定的，所以這是待裁 U1）：試用一輪後收三條新號，接在目前最大號 N-69 後面，放第 05 章「窗」N-16 旁邊；沒定之前放「08-待定」。

| 暫稱 | 內容 | 附錄4 要補的持久檔 |
|---|---|---|
| N-70 布告欄 | stack 根的 `board.json`、欄位、過期、只有本人寫 | `<stack>/board.json`（writer＝本 proc；reader＝任何人；on_bad＝當沒有） |
| N-71 信件級別 | `body.comm`、三級、只動通知不動投遞、缺省＝平信 | 無（信件已在 N-16） |
| N-72 頻道 | 頻道 proc、`channel.json`、`members.json`、`log/`、迴圈規則 | `channel.json`、`members.json`、`log/*.jsonl` |

---

## 二、布告欄（題 2）

### 2.1 決定一覽

| 決定 | 內容 | 理由 |
|---|---|---|
| 存哪 | `<stack>/board.json`，一隻一張；沒有檔＝沒貼 | 固定位置，shell 一行就讀得到；跟 `state.json` 同層，讀者已經會找 stack |
| 這是 aos 本體 | 位置與欄位進規格；工具在 aos 本體的 pack | 使用者要「普通 proc 也好處理」，放在 view 或 wf/tools 就只有那邊的程式懂 |
| 誰能寫 | 只有本人（本 proc 的工具、hook、或它自己的程式） | 五條規則第 1 條本來就禁止動別人的 stack |
| 怎麼寫 | 同資料夾寫暫存檔再 rename 蓋過去 | 讀的人永遠讀到完整的一份 |
| 只記「自述」，不抄機器事實 | phase、busy 這些繼續留在 `state.json`／`ctl ls`；讀布告欄的工具把兩邊**合併後回傳**（多一塊 `live`），不寫回檔 | 抄一份就會過期（當掉時沒人更新）。自述與事實分開，讀的時候再併 |
| 四種 `mode` | `here` 在、`busy` 在忙、`dnd` 請勿打擾、`away` 不在／睡了 | 見 2.3；`busy` 只是告知，`dnd` 與 `away` 才影響通知 |
| 一定會過期 | `expires_at` 到了就失效；沒寫的話，`mode` 不是 `here` 的貼文在 `updated_at` 後 24 小時失效 | 忘了撕的「請勿打擾」不能擋一輩子。現在的使用者布告欄沒有到期判斷（備料一），這次補上 |
| 過期怎麼算 | 讀的人算，不靠寫的人回來清 | 寫的人可能就是睡著了 |
| 「在等誰」是結構化欄位 | `waiting_on[]`，`who` 是名字或 `"user"` | ok-view 要數「幾隻在等人」、把「等使用者的」放進待辦，自由文字數不出來 |
| 代理人 | `deputy`：我不在時急事找誰 | 寄件人讀到「睡了」之後要有下一步，不然只能乾等 |
| 歷次留底 | 選用：`<stack>/board.log.jsonl` 每次寫追加一行；不是協議必備 | view 想畫「最近貼過什麼」時有得讀；不想留的 proc 不用管 |
| 大小上限 | 整檔 16 KB；`text` 1000 字、`doing` 200 字、`waiting_on` 20 筆 | 讀的人可以放心整檔讀進來 |

### 2.2 欄位表（`board/1`）

| 欄位 | 型別 | 必填 | 意思 |
|---|---|---|---|
| `format` | `"board/1"` | 是 | 版本標記 |
| `updated_at` | 時間 | 是 | 這次寫的時間 |
| `mode` | `here`／`busy`／`dnd`／`away` | 是 | 見 2.3 |
| `seq` | 整數 | 否 | 每寫一次加一；讀的人不看時鐘也知道有沒有變 |
| `by` | `self`／`auto`／`user` | 否 | 本人工具寫的／hook 自動寫的／使用者從網頁寫的 |
| `text` | 字串 ≤1000 | 否 | 想說的話（自由文字） |
| `doing` | 字串 ≤200 | 否 | 現在在忙什麼（一句） |
| `waiting_on` | 陣列 ≤20 | 否 | 每筆 `{who, what, since_at, ref?}`；`who` 是 proc 名字或 `"user"`，`ref` 是那封信的名字（有的話） |
| `back_at` | 時間 | 否 | 預計幾點回來（機器可比較） |
| `back_text` | 字串 ≤100 | 否 | 預計回來的白話（「明早」），沿用使用者布告欄現有的 `back` |
| `expires_at` | 時間 | 否 | 這張貼文幾點失效；沒寫照 24 小時規則 |
| `accept` | `low`／`normal`／`urgent`／`none` | 否 | 現在最低收到哪一級才通知我；沒寫照 `mode` 的預設（2.3） |
| `allow_from` | 名字陣列 | 否 | 這些人寄的不管幾級都通知（接 quiet 的 `urgent_senders`） |
| `wake_on_urgent` | 布林，預設 false | 否 | 我睡著時，急件可以把我叫醒（待裁 U3） |
| `clear_on_start` | 布林 | 否 | 我重新起來時自動撕掉這張（睡前貼的「睡了」用） |
| `deputy` | 名字 | 否 | 我不在時找誰 |
| `ext` | 物件 | 否 | 各實作自己的附加資料；協議不解釋 |

### 2.3 四種 `mode`

| `mode` | 白話 | `accept` 預設 | 寄件人該怎麼想 |
|---|---|---|---|
| `here` | 在，照常 | `low`（全收） | 照常寄 |
| `busy` | 在忙，信照收，會回得慢 | `low`（全收） | 照常寄，別催 |
| `dnd` | 請勿打擾：人在，但只有急件會通知到我 | `urgent` | 不急就寄平信，他忙完會看到 |
| `away` | 不在／睡了：現在沒在看 | `urgent` | 回信要等 `back_at`；急事找 `deputy` |

`dnd` 與 `away` 分開的理由：對寄件人是兩種下一步，一個是「晚點會看」，一個是「先找別人」。

### 2.4 讀的人怎麼算「現在算數的狀態」

照順序做，四步：

1. 檔不存在、讀不了、`format` 不是 `board/1` → 結果 `none`（沒貼）。讀失敗重試一次再放棄。
2. 過期：現在時間超過 `expires_at`；或沒有 `expires_at`、`mode` 不是 `here`、且超過 `updated_at` 加 24 小時 → 標 `stale`。過期的貼文**文字照顯示（標灰）**，但 `mode` 當成 `here`，不再擋通知。
3. 時鐘怪：`updated_at` 比現在晚超過 5 分鐘 → 標 `clock_odd`，把 `updated_at` 當成現在來算過期。
4. 併入機器事實（有 daemon 表可查時）：phase 是 sleeping／stopped → `live.asleep = true`，算數的狀態是 `away`，就算布告欄寫 `here` 或根本沒貼。`busy` 取 `ctl ls` 的 think／act／cli。

`back_at` 已過但貼文還沒過期 → 標 `overdue`（「說八點回來，現在九點」），只顯示、不改行為。

### 2.5 讀：單隻、整隊、全部、嵌套

| 要讀的 | 做法 | 理由 |
|---|---|---|
| 單隻 | `ctl where NAME` 拿 stack → 讀 `board.json`；`user` 固定是 `~/.aos/user/board.json` | 沿用現成的找法；設了 `AOS_KERNEL` 時 `where` 本來就會先問 kernel，不繞過 |
| 自己 | 工具看到的 `AOS_STACK` 是 `tools/<名>/` 不是根（備料五），所以工具用 `ctl who` 找自己的根；非 agent 的普通 proc 直接用 `$AOS_STACK` | 兩種 proc 的差別寫明，免得工具把布告欄寫進自己的小格 |
| 整隊 | 列一張 daemon 表（`ctl ls --json`），逐隻讀 | 一張表＝一隊 |
| 嵌套 | `ctl ls` 不遞迴，所以工具自己往下走：表裡哪一隻自己也是 daemon（`daemon` 欄連得到）就再列它那張表；廣度優先、記走過的 stack 防繞圈、最深 5 層、最多 500 隻，超過就停並標 `truncated` | kernel 鏈不是父子樹，只能照「表連表」走；設上限是防表互相指 |
| ok-view | 它本來就有自己走樹的結果（`view-tree/0`），對每個已知 stack 多讀一個檔就好，不必呼叫我們的工具 | 少一層依賴 |

### 2.6 自動的部分（都不花模型）

| 什麼時候 | 做什麼 | 誰做 |
|---|---|---|
| 讀的時候 | 併入 phase、busy（2.4 第 4 步） | 讀的工具 |
| after_start | 貼文有 `clear_on_start` → 撕掉（改回 `here`、清文字） | 新 hook `comm_tick` |
| 每分鐘（on_clock） | 等回信等太久 → 把對方布告欄貼一行給我（3.5）；自己的 `dnd` 結束 → 補一則「壓住的信有幾封」 | 同一支 hook |
| 寄信時 | 帶 `wait` 的信自動在自己的 `waiting_on` 加一筆；收到回信（`in_reply_to` 對上）自動拿掉 | 寄信工具＋hook |
| 睡著時 | 什麼都不寫 | 沒有 sleep 事件（備料五），也不需要：睡著是機器事實，讀的人會併 |

不做「after_stop 自動寫睡了」：這是抄機器事實，當掉時會留下錯的貼文。

### 2.7 跟現有東西的關係

| 現有的 | 處理 | 理由 |
|---|---|---|
| `state.json`、`ctl ls` 的 busy | 並存，讀的時候併 | 一個是事實、一個是自述 |
| 隊長留話（`aos-view note`） | 並存、不合併 | 那是一隊一串的**進度流水**（start／done／blocked…），布告欄是一隻一張的**現況**；全景頁隊伍卡照舊顯示留話，員工卡顯示布告欄 |
| 使用者布告欄（`~/.aos/view/board/user.json`） | 搬進同一協議：改存 `~/.aos/user/board.json`；網頁「貼上布告／清空」改寫這個檔；`aos-view board` 改讀這個檔（待裁 U4） | 使用者原話 2「這個公告欄，agent自己也可以有」——是同一種東西；agent 不必學兩種讀法。照 proto8 慣例不寫遷移，舊檔直接不用 |
| 使用者專區 door／`quiet_hours` | 並存，單向引用：`aos-user tick` 把「布告欄現在是 `dnd`／`away`」當成第三個安靜來源；布告欄不去改 door | door 是專區自己的投遞政策，布告欄是對外宣告；兩邊互改會打架 |
| 員工 bot、助手觀察 | 並存；員工 bot 可以把布告欄當輸入之一 | 那是「別人看我」，布告欄是「我自己說」 |
| wf/tools 的 quiet、autoreply | 功能被布告欄 `dnd`＋「寄信帶回布告欄」涵蓋；wf/tools 那套照留，兩套不要同時裝在同一隻身上（裝了也只是多壓一次通知，不壞） | 那套不是 aos 本體，這條線不動它；汰換時機交 ok-onboard |

---

## 三、信件分級（題 3）

### 3.1 決定一覽

| 決定 | 內容 | 理由 |
|---|---|---|
| 三級 | `urgent` 急件、`normal` 平信、`low` 知會 | 使用者舉的是「急件、平信…」。每多一級寄件人就多猜一次；三級剛好對應三種通知方式（馬上、照常、可彙整）。llm kernel 也是 low／normal／high 三級，數量一致好記 |
| 跟 `status` 是兩個維度 | `status` 講「這封是什麼事」（REQUEST、DONE…），`level` 講「多快要讓他知道」 | DONE 可以很急（擋著別人）、REQUEST 可以不急；合併就得為每個組合發明新 status，而 status 白名單在 aos-mailbox 裡，不能改 |
| 欄位位置 | `body.comm.level` | body 會被 kernel 轉寄保留、會被 `read` 印出；信封會被丟 |
| 缺省 | 沒有 `comm`＝`normal` | 所有舊信自動合規 |
| 標題記號 | 急件標題前加 `[URGENT] `（寄信工具自動加）；**只給人和舊程式看，新程式不得解析標題** | `peek` 與 `mail_notify` 不印未知欄位，xiaosi 只看 status 與標題；加記號讓舊程式也看得出急。已有前例：autoreply 的 `[auto] ` |
| 急件要寫理由 | `comm.why` 一句 ≤200 字，急件必填 | 逼寄件人想一下，也讓收件人與事後稽核看得到為什麼 |
| 信可以過期 | `comm.expires_at`：過了就當 `low` 處理、顯示「已過期」，**不刪信** | 「十分鐘內要答覆」的急件，隔天醒來不該再插隊 |
| 機器信 | `comm.auto = true`：自動產生的信；收到的人不自動回、頻道不轉發 | 斷迴圈用，把 `[auto] ` 標題慣例變成正式欄位 |
| 分級不動投遞 | 信照 aos-post 原樣寄、原樣排；分級只影響三處：通知、讀的順序、寄件人拿到的回報 | 硬框「不改 aos-post」；也讓「協議壞了」的最壞結果只是通知不準 |

名字避開：不用 `priority`（llm kernel 已用，意思是排程）、不用 `urgent` 布林（使用者專區已用）。

### 3.2 `body.comm` 欄位表

| 欄位 | 型別 | 必填 | 意思 |
|---|---|---|---|
| `v` | `1` | 是（有 `comm` 就要有） | 協議版本 |
| `level` | `urgent`／`normal`／`low` | 否，預設 `normal` | 級別，小寫 |
| `why` | 字串 ≤200 | 急件必填 | 為什麼急 |
| `expires_at` | 時間 | 否 | 過了當 `low` |
| `auto` | 布林 | 否 | 機器產生 |
| `wait` | 布林 | 否 | 寄件人在等這封的回覆（對方可據此知道有人卡住） |
| `channel` | 名字 | 頻道轉出的信才有 | 來自哪個頻道 |
| `seq` | 整數 | 同上 | 頻道內的發言序號（去重用） |
| `via` | 名字陣列 ≤3 | 同上 | 經過哪些頻道（防迴圈） |
| `origin` | `{from, sender, sent_at}` | 同上 | 原發言人 |
| `op`、`args` | 字串、物件 | 寄給頻道的管理信才有 | 見第四節 |
| `result` | `{ok, code?, reason?}` | 頻道回覆才有 | 管理信的結果 |

### 3.3 核心表：布告欄 × 級別

信一律**馬上進信箱**。下表講的是「通知」與「寄件人拿到什麼」。

| 收件人現在 | 急件 `urgent` | 平信 `normal` | 知會 `low` |
|---|---|---|---|
| `here`／`busy` | 馬上通知，通知行帶寄件人、標題、理由 | 照現在：每分鐘合併通知一次 | 只算進封數，不點名 |
| `dnd` | 馬上通知（急件就是用來穿過 dnd 的） | 壓住；`dnd` 結束補一則「期間來了 N 封」 | 壓住，同左 |
| `away`（人不在，proc 還在跑） | 馬上通知；同時寄件人被告知「他不在、幾點回、找誰」 | 壓住 | 壓住 |
| 睡著（phase sleeping／stopped） | 通知不到。寄件人被告知；布告欄有 `wake_on_urgent` 才發叫醒請求（走 kernel，可被拒） | 等在信箱 | 等在信箱 |
| 沒貼布告欄、或貼文過期 | 同 `here` | 同 `here` | 同 `here` |

`accept` 與 `allow_from` 可以覆蓋這張表的預設（例：`dnd` 但 `accept: none`＝連急件都不通知；`allow_from: ["repo-aos"]`＝頂層寄的都通知）。

### 3.4 三個落點（誰實作這張表）

| 落點 | 做什麼 | 動到誰 |
|---|---|---|
| **寄件端**：新工具 `comm_send`／`aos-comm send` | 組 body（跟 aos-mailbox 一樣的八個欄位＋`comm`）→ 用 `aos-post send` 寄 → 讀對方布告欄與 phase → 把「他現在的狀態」放進工具回傳。急件且對方睡著且有 `wake_on_urgent` → 發 `ctl wake`（照常走 kernel） | 全新；body 的八個欄位要跟 aos-mailbox **逐欄一樣**（優先 import 它的常數與檢查來用，不改它；import 不了就照抄並加一條對照測試） |
| **收件端通知**：`mail_notify` hook | 讀每封未通知信的 `body.comm.level` 與自己的布告欄，照 3.3 決定通知、壓住、或補報 | 建議改這支既有 hook（待 opus 定案，見下） |
| **收件端閱讀**：新工具 `comm_read`／`aos-comm read` | `aos-post take-all` 把信都認領進 `cur/` → 照「級別、再照信名」排 → `see`＋`done` 最前面那封。沒讀的留在 `cur/` | 全新。已對過原碼：舊的 `aos-mailbox read` 本來就先讀 `cur/` 裡的，所以兩支工具混用不會漏信、不會重複 |

**為什麼插隊做在讀的工具，不做在信箱**：`aos-mailbox read` 不能指定讀哪一封（已對原碼：`read takes no arguments`），而信箱順序是 aos-post 定的。`--ordered` 可以讓信排到前面，但那是「保證先後」的機制，拿來當急件會讓真正要保序的信被插隊，不用。

**`mail_notify` 怎麼辦**：建議直接改它，條件是「信裡沒有 `comm`、自己沒貼布告欄時，輸出跟現在逐字相同」（它的既有測試一行不改就要過）。理由：另做一支新 hook 會跟舊的同時通知兩次，還得教每個範本關掉舊的。它是 aos 本體但不在禁改名單。若 opus 查後認為風險高，退路是新 hook `comm_notify` 加範本裡關掉 `mail_notify`。

通知行的樣子（英文，照慣例）：

```
[aos] new_mail: 1 URGENT from ok-sec: "uid plan blocks your send path" (why: you ship today); 3 other letter(s) from ok-view, xiaosi
[aos] dnd_over: 5 letter(s) arrived while do-not-disturb, from ok-view, ok-misc
[aos] no_reply: user has not answered "board schema, 6 questions" for 30m; board: away until 2026-11-15T00:00 (sleeping), deputy repo-aos
```

### 3.5 「很久沒回就去看布告欄」（使用者原話 1）

| 情況 | 發生什麼 | 花模型嗎 |
|---|---|---|
| 用新工具寄信 | 回傳就帶對方布告欄（不是 `here` 才帶，省字） | 不花 |
| 寄了帶 `wait` 的信，30 分鐘沒回（急件 10 分鐘） | `comm_tick` 每分鐘檢查，逾時就往自己 queue 塞一行 `no_reply`（上面第三行），每封信只提醒一次 | 不花 |
| 「比較有自覺的 agent」 | 自己呼叫 `board_read` | 一次工具呼叫 |
| 用舊工具寄信的 agent | 沒有自動回報；自己 `board_read`，或照舊靠 wf/tools 的 autoreply | — |

「在等回信」的帳記在寄件工具自己的小格（`tools/comm/waiting.jsonl`），不進協議。

### 3.6 防濫用（人人寄急件就沒意義）

aos 不驗寄件人，所以第一版的原則是**收件端說了算**，四道：

| 道 | 做法 | 預設值 |
|---|---|---|
| 理由必填 | 急件沒有 `why` → 寄信工具拒寄（`UrgentWhyMissing`） | — |
| 收件端額度 | 同一寄件人一小時內第 4 封急件起，通知時當平信，通知行標 `(urgent downgraded: rate)` | 每寄件人每小時 3 封 |
| 留帳 | 收到的急件記一行到 hook 的小格 `urgent.jsonl`（誰、何時、理由、有沒有被降級） | 留 30 天 |
| 頻道封頂 | 經頻道轉出的信最高 `normal`（第四節） | — |

誰能用急件：第一版人人可寄，靠上面四道約束。「只有隊長能寄急件」這種名單是配給包的事（ok-onboard 可以不發 `level` 參數給某些角色），協議不內建。

### 3.7 跟其他「優先」概念的關係

| 別處的 | 關係 |
|---|---|
| llm kernel `body.priority` | 無關、不互通。那是排程用的，在 llm kernel 的信箱；我們不往那種信加 `comm` |
| 使用者專區 `urgent`／`deadline` | 寄給 `user` 時，`comm_send` 轉交 `aos-user send`：`level: urgent` → `urgent: true`、`expires_at` → `deadline`；`comm` 物件照留（已查專區 schema 沒有禁止多餘欄位） |
| xiaosi | 不改也能用（看得到 `[URGENT] ` 標題）。之後 wf 可在它的 system.txt 加一句「信上有 `comm.level` 就照它分；沒有才照舊判斷」——屬 wf，不屬這條線的本體 |
| quiet／autoreply（wf/tools） | 見 2.7；autoreply 要補一條「有 `comm.channel` 或 `comm.auto` 的信不回」，防頻道迴圈（屬 wf/tools） |
| 全景頁 | 信箱列表每封前面標級別；急件未讀數上卡片（細節歸 ok-view） |

---

## 四、頻道與廣播（題 4）

### 4.1 決定一覽

| 決定 | 內容 | 理由 |
|---|---|---|
| 頻道是什麼 | 一隻不用模型的 loop proc，照 `procs-kernel` 的形：`_entry=["aos-loop","loop.json"]`，每輪 `take-all` 自己的信箱、處理、`done` | 使用者原話 6「這個頻道就是一個簡單proc」；現成有同形的例子 |
| 寄到它信箱的信＝發言 | 沒有 `comm.op`（或 `op: "post"`）的信就是發言 | 舊的 `aos-mailbox send --to 頻道名` 不改就能發言；「將信寄到那個頻道」字面成立 |
| 加入／退出是信 | 帶 `comm.op: "join"`／`"leave"` 的信；頻道回一封結果 | 成員表在頻道的 stack 裡，別人不能直接寫（規則 1）；用信就不必開新的通道 |
| 成員怎麼收 | 預設**每人一份**：頻道往每個成員的信箱各寄一封。同時一律寫進頻道自己的歷史檔，成員也可以選「不要複本，我自己來讀」（`deliver: "pull"`） | 每人一份：通知、已讀未讀、舊的讀信工具全部照舊能用。歷史檔：晚加入的人、人多的頻道有得讀（待裁 U5） |
| 已讀未讀 | 複本模式＝成員自己的信箱。自己讀模式＝成員工具小格裡的游標（讀到第幾號） | 不在頻道那邊替每人記已讀，頻道保持笨 |
| 歷史 | `<頻道 stack>/log/YYYY-MM-DD.jsonl`，一則發言一行，留 30 天（`keep_days` 可調） | 一天一檔好刪、好 `tail` |
| 建頻道 | ＝起一隻 proc，照常走 `ctl`／kernel | 「誰能建頻道」直接交給現成的 kernel_gate，不用新做權限 |
| 認頻道 | stack 裡有 `channel.json` 的 proc 就是頻道；不靠名字前綴 | 名字留給使用者取 |
| 廣播 | ＝成員是「這張 daemon 表上所有人」的頻道（`members_from: "daemon"`），不必加入；一張表至多一個，慣例叫 `all`；不自動建（待裁 U6） | 不另發明第二套機制；備料說沒有「自動給所有 agent」的管道，動態取表就繞過了 |
| 寄給幾個人（不建頻道） | `comm_send` 的 `to` 接受名單，一封封寄 | 補現在「只能單一收件者」的洞，不值得為三個人開頻道 |
| 頻道信封頂 | 轉出的信最高 `normal`，原信寫 `urgent` 也降 | 回答「頻道急件會不會叫醒全員」：不會。一封信吵醒五十隻是最貴的濫用 |
| 睡著的成員不灌信 | 成員 phase 是 sleeping／stopped → 不寄複本、記「欠到第幾號」；它醒來後補**一封**摘要（「你不在時有 N 則，第 a 到 b 號」） | 睡三天的成員醒來不該面對三千封信 |
| 嵌套隊伍 | 第一版不自動串。要跨隊就讓上層頻道把下層頻道加為成員（頻道也是 proc，有信箱），靠 `via` 防迴圈 | 用現有零件就能組，不先設計樹狀廣播 |

### 4.2 頻道 stack 的樣子

```
<channel stack>/
  channel.json        設定（format: channel/1）
  members.json        成員表（format: channel-members/1），只有頻道 proc 寫
  mailbox/            普通 aos 信箱：發言與管理信都寄這裡
  log/2026-11-14.jsonl  歷史
  rejected.jsonl      被拒的信一行一筆（誰、為什麼）
```

`channel.json` 欄位：

| 欄位 | 值 | 第一版實作 | 意思 |
|---|---|---|---|
| `format` | `channel/1` | 是 | |
| `name`、`title` | 字串 | 是 | 名字、一句說明 |
| `created_at`、`owner` | 時間、名字 | 記錄 | 誰建的 |
| `admins` | 名字陣列 | **只存不用** | 管理員接口 |
| `join` | `open`／`invite`／`closed` | 只做 `open` | 誰能加入。不認得的值一律當 `closed`（寧可擋） |
| `post` | `members`／`anyone`／`admins` | 做 `members`、`anyone` | 誰能發言 |
| `members_from` | `list`／`daemon` | 都做 | `daemon`＝廣播頻道 |
| `max_level` | `normal`／`urgent` | 只做 `normal` | 轉出信的級別上限 |
| `deliver_default` | `copy`／`pull` | 都做 | 新成員預設收法 |
| `keep_days` | 整數，預設 30 | 是 | 歷史留幾天 |
| `auth` | `claimed`／`uid` | 只做 `claimed` | 身分怎麼認；`uid` 等 ok-sec |
| `limits` | `{post_per_min: 30, members_max: 500, what_max: 20000, batch: 50}` | 是 | 每人每分鐘發言數、成員上限、內文字數、每輪轉幾份 |

`members.json`：`{"format":"channel-members/1","seq":N,"members":{ "<stack 絕對路徑>": {name, box, joined_at, deliver, role, sent_seq, fails, gone_at} }}`。用 stack 路徑當鍵，因為名字會重複。`role` 第一版只有 `member`。

歷史一行：`{"seq":42,"at":"…","from":"ok-sec","sender":"<stack>","status":"PROGRESS","level":"normal","title":"…","what":"…"}`。

### 4.3 管理信（`comm.op`）

| `op` | 第一版 | 行為 |
|---|---|---|
| （沒有）／`post` | 做 | 發言 |
| `join` | 做 | `args: {name, box, deliver?}`；照 `join` 政策；回信 |
| `leave` | 做 | 拿掉自己；回信 |
| `info` | 做 | 回成員數與設定（其實直接讀檔也行） |
| `invite`、`kick`、`set`、`close` | **留名字不做** | 回 `ChannelOpUnsupported` |

回信是普通信：status `DONE` 或 `FAILED`，`comm.result`，`comm.auto: true`。CLI 的 `join` 寄完後等幾秒看 `members.json` 有沒有自己，給人一行結果。

### 4.4 轉出的那封信長怎樣

| 項 | 值 | 理由 |
|---|---|---|
| 信封 `sender` | 頻道自己的 stack | 這是事實：信是頻道寄的 |
| `body.from` | 原發言人名字 | 成員用舊工具回信會回給發言人本人（私下回）；要回到頻道就用 `channel_post` |
| `body.to` | 成員名字 | |
| `body.status` | 原信的 status；原信沒有就 `PROGRESS` | 一定是白名單內的值，舊程式才認得；`PROGRESS` 在 xiaosi 眼裡是例行，會進彙整，正合適 |
| `body.title` | `[#頻道名] 原標題` | `peek` 只印標題，要讓人一眼知道是頻道信 |
| `body.what`、其餘 | 原樣 | |
| `body.comm` | `{v:1, level（封頂後）, channel, seq, via, origin}` | 去重、防迴圈、追來源 |

### 4.5 迴圈與洪水（五條規則）

1. **不轉給發言人自己**。
2. **`via` 規則**：轉出時把自己的名字加進 `comm.via`；收到的發言若 `via` 已含自己、或 `via` 長度已到 3 → 丟進 `rejected.jsonl`，不轉。
3. **機器信不轉**：`comm.auto` 為真、或標題以 `[auto] ` 開頭的信不當發言。（autoreply 的回信就是這種，這條擋住「頻道 → 成員自動回 → 頻道」。）
4. **限速**：同一發言人每分鐘超過 `post_per_min` → 拒收並回一封 `FAILED`（一分鐘內只回一封，免得回信也成洪水）。
5. **只認明確的管理信**：`op` 不認得 → 拒絕，不猜。

### 4.6 人很多時

| 問題 | 做法 |
|---|---|
| 一則發言要寄很多份 | 每輪最多寄 `batch`（50）份，剩的下一輪；每個成員記 `sent_seq`（寄到第幾號），頻道中途被殺，重起後接著寄 |
| 重複 | 中斷續寄最多重複一封；複本帶同一組 `channel`＋`seq`，新工具據此去重 |
| 成員超過 50 | 新加入的預設改 `pull`（自己讀） |
| 成員上限 | `members_max` 500，超過 `join` 回 `FAILED` |

### 4.7 權限：aos 層做得到的 vs 要等 ok-sec

| 事情 | aos 層（第一版就有） | 要等 ok-sec uid 層 | 為什麼 |
|---|---|---|---|
| 誰能建頻道 | kernel_gate 的 `allowed` 名單、hold／pass／refuse | — | 建頻道＝起 proc，正是 gate 管的 |
| 誰能加入 | 頻道照 `join` 政策與成員表決定 | 身分是真的 | 信上的 `sender` 是寄件端自己寫的 |
| 誰能發言 | 頻道照 `post` 政策比對成員表 | 同上 | 同上 |
| 管理員 | `admins` 欄位、管理信 | 管理員身分是真的 | 同上 |
| 繞過頻道直接往成員信箱丟「假頻道信」 | 擋不住；新工具可比對信封 `sender` 是不是該頻道的 stack（也能假造） | 成員信箱只收特定 uid／經跨 uid helper 蓋真實 uid | 能寫信箱夾的行程都能投信 |
| 非成員偷看歷史 | 擋不住（同帳號都讀得到） | `log/` 只給成員群組讀 | 目錄權限 |
| 竄改成員表、歷史 | 只有規則擋 | 頻道 proc 自己一個 uid，檔只有它能寫 | 同上 |
| 私密頻道 | 做不到，第一版所有頻道等同公開 | 可以 | 同上 |
| 布告欄真偽（別人替我寫） | 只有規則擋；`by` 欄供參考 | `board.json` 的檔案擁有者＝那隻 proc 的 uid，讀的人可以查 | 同上 |
| 急件濫用 | 收件端額度、降級、留帳 | 額度按真實 uid 算 | 同上 |

接口已留：`channel.json` 的 `auth: "uid"`、`join`／`post`／`admins`／`max_level` 的其他值。ok-sec 還沒定「每 agent 一個 uid 還是每子樹一個」；若是每子樹一個，上表「身分是真的」只能真到子樹，頻道的 `uid` 模式要跟著那個粒度走——這點請 opus 寫進給 ok-sec 的對口信。

---

## 五、工具（題 5）

一個庫 `proto8/lib/aos/comm/`（讀寫布告欄、組信、算 3.3 那張表、頻道一輪）四處共用：CLI、MCP 工具、hook、頻道 proc。協議只有一份實作，四個入口。

### 5.1 MCP 工具

**pack `comm`**（基本款）

| 工具 | 參數 | 行為 |
|---|---|---|
| `board_set` | `mode`（必）、`text`、`doing`、`back_in`（如 `"8h"`）或 `back_at`、`back_text`、`expires_in` 或 `expires_at`、`accept`、`allow_from`、`wake_on_urgent`、`deputy`、`clear_on_start` | **整張換掉**（沒給的欄位清空，`waiting_on` 例外、保留）。`dnd` 沒給到期預設 2 小時、`away` 預設 12 小時。回傳寫好的整張 |
| `board_clear` | 無 | 撕掉：`mode: here`、清文字與等待 |
| `board_wait` | `who`、`what`、`done`（布林） | 在 `waiting_on` 加一筆；`done: true` 拿掉 `who` 那筆 |
| `board_read` | `who`：名字、`"user"`、`"me"` | 回傳布告欄＋`live`（phase、busy）＋`stale`／`overdue`／`clock_odd` 標記；沒貼回 `{"board": null}`，不是錯誤 |
| `board_ls` | `scope`：`team`（預設）／`deep`；`only`：`dnd`／`away`／`waiting`／`waiting_user` | 一隻一行：名字、mode、doing、等誰、幾點回；最後一行是計數 |
| `comm_send` | `to`（名字、名單、或 `#頻道`）、`status`、`title`、`what`、`level`（預設 `normal`）、`why`、`expires_in`、`wait`、`outputs`、`not_done`、`decide`、`in_reply_to` | 寄信（3.4）；回傳信名＋對方現況（不是 `here` 才帶） |
| `comm_read` | `all`（布林） | 照級別先後讀信（3.4）；輸出格式跟 `mailbox_read` 一樣，多 `level`、`expired` 兩欄 |

整張換掉而不是局部修改的理由：便宜模型最容易在「上次留了什麼」上出錯；整張換，寫的就是看到的。

**pack `channel`**（選配）

| 工具 | 參數 | 行為 |
|---|---|---|
| `channel_ls` | `mine`（布林） | 列這張表上的頻道：名字、說明、人數、我在不在 |
| `channel_join` | `channel`、`deliver`（`copy`／`pull`） | 寄 join、等結果 |
| `channel_leave` | `channel` | 寄 leave、等結果 |
| `channel_post` | `channel`、`title`、`what`、`status`（預設 `PROGRESS`） | 發言（等同 `comm_send to=#頻道`） |
| `channel_read` | `channel`、`since`（序號；不給＝我上次讀到的）、`limit`（預設 20） | 讀歷史檔、推進自己的游標 |
| `channel_info` | `channel` | 設定與成員名單 |
| `channel_create` | `name`、`title`、`broadcast`（布林） | 用頻道定義起一隻 proc（照常走 kernel） |

### 5.2 CLI：一支 `aos-comm`

放 `proto8/cmd/aos-comm`（Python），輸出英文，預設一行一項、`--json` 給程式。

| 指令 | 對應 |
|---|---|
| `aos-comm board set MODE [TEXT] [--doing S] [--back 8h] [--for 2h] [--accept L] [--wake] [--deputy N]` | `board_set` |
| `aos-comm board clear` | `board_clear` |
| `aos-comm board wait WHO WHAT` ／ `aos-comm board wait --done WHO` | `board_wait` |
| `aos-comm board show [NAME\|user]` | `board_read`（不給＝自己） |
| `aos-comm board ls [--deep] [--only dnd\|away\|waiting\|waiting-user]` | `board_ls` |
| `aos-comm send --to N[,N…\|#CH] --status S --title T [--level L] [--why S] [--wait] WHAT` | `comm_send`（旗標名字跟 `aos-mailbox send` 對齊） |
| `aos-comm read [--all] [-j]` | `comm_read` |
| `aos-comm chan ls\|join\|leave\|post\|read\|info\|create …` | 頻道七支 |
| `aos-comm check FILE\|LETTER_DIR` | 拿 schema 驗一個檔或一封信，給寫協議實作的人用 |
| `aos-comm level LETTER_DIR` | 印這封信算數的級別（一個字），給 shell hook 用 |

例：`aos-comm board set away "sleeping" --back 8h --deputy repo-aos`、`aos-comm send --to ok-view --status REQUEST --level urgent --why "blocks today's ship" --title "board schema ready" see section 7`。

### 5.3 不用我們的工具也行（普通 proc 幾行）

```sh
# 讀別人的布告欄
jq -r '.mode, .text' "$(aos-agent ctl where ok-view)/board.json"
# 寫自己的
now=$(date -u +%Y-%m-%dT%H:%M:%S.000+00:00)
printf '{"format":"board/1","updated_at":"%s","mode":"busy","doing":"nightly build"}\n' "$now" \
  > "$AOS_STACK/board.json.tmp" && mv "$AOS_STACK/board.json.tmp" "$AOS_STACK/board.json"
# 看一封信幾級
aos-post see "$BOX" "$NAME" | jq -r '.body.comm.level // "normal"'
```

```python
import json, os
b = json.load(open(os.path.join(stack, "board.json")))      # 讀
level = (letter["body"].get("comm") or {}).get("level", "normal")   # 信的級別
```

C++ 同理：用現成的 JSON 庫讀一個檔、取一個鍵；寫檔照「暫存檔再 rename」。指令的確切寫法（`ctl where` 掛在哪支指令下）請 opus 對現碼。

### 5.4 預設給誰、跟 ok-onboard 怎麼對

| 對象 | `comm` pack | `channel` pack | hook | 理由 |
|---|---|---|---|---|
| fsm 範本 | 給 | 不給（要用再疊） | `comm_tick`、改過的 `mail_notify` | 布告欄與分級是人人要的基本禮貌；頻道不是 |
| eca 範本 | 給 | 不給 | 同上 | 同上 |
| tools_sub（CLI 子 agent） | 不給 | 不給 | 無 | 它們本來就沒有 mailbox、self，壽命短 |
| 頻道 proc | — | — | — | 不用模型，直接用庫 |

備料說「沒有新工具自動給所有 agent」，所以「預設給」的意思是改範本的 `tools.json`（`$override` 加一包）。

給 ok-onboard 的對口建議（最後由它定）：

| 角色 | 建議 |
|---|---|
| 隊長 | `comm` 全部＋`channel` 全部；可寄急件 |
| 施工員、審稿員 | `comm` 全部；急件照預設額度 |
| 蒐集員 | `comm` 裡只留 `board_read`、`comm_send`（不開 `level` 參數）、`comm_read` |
| 小助手（xiaosi 類） | `comm` 全部＋`channel` 的 ls／read；它最需要看級別與布告欄 |

「不開 `level` 參數」怎麼做（包一層還是 pack 設定），請 opus 跟 ok-onboard 對。

---

## 六、相容性驗證法（題 6）

### 6.1 新信給舊程式（逐一對備料第三節）

| 舊程式 | 遇到 `body.comm` 會怎樣（依備料） | 要驗什麼 |
|---|---|---|
| aos-post `take`／`see`／`done` | body 是任意 JSON，不驗 | 寄、認領、讀、收，結束碼都跟沒有 `comm` 的同一封一樣 |
| `aos-mailbox read`／MCP `mailbox_read` | `setdefault` 把 `comm` 多印一欄，不蓋既有欄 | 輸出除了多一行 `comm` 外逐字相同；`--json` 那行解析得回來；十三個既有鍵的值沒變 |
| `aos-mailbox peek`／MCP `mailbox_peek` | 不印未知欄位 | 輸出只差標題的 `[URGENT] `／`[#ch] ` 前綴 |
| kernel 框架站轉寄 | 只轉 body → `comm` 會留；信封欄位會掉 | 轉寄後 `body.comm` 逐字還在。我們沒有放任何東西在信封，所以掉了也不少東西 |
| JSONL 留底（`--keep-to`） | 排除 sender、reply_to、絕對路徑 to | 留底那行寫得進去、讀得回來，`comm` 在不在都不壞 |
| `mail_notify`（改之前的版本） | 只數封數與寄件人 | 行數、內容不受 `comm` 影響 |
| xiaosi | 模型讀 `read` 的輸出 | 拿三封樣本信（急件、平信、頻道信）實跑一次：急件有被立刻轉、頻道信進彙整、沒有因為多一欄而誤判 |
| gate 自動處理 | 處理的是起／改 proc 的請求 | 一封帶 `comm` 的請求信過 gate，hold／pass／refuse 的結果跟不帶的一樣 |
| quiet（wf/tools） | 只攔通知、不看信 | 安靜期照攔、結束照補 |
| autoreply（wf/tools） | 對新信回 PROGRESS，跳過 `[auto] ` 標題 | 重點驗頻道：成員裝著 autoreply 時，一則頻道發言不會造成第二則（4.5 第 3 條擋住） |
| llm kernel | 它的信箱不會收到我們的信 | 只驗一件：`comm_send` 不能把 `comm` 塞進寄給 llm kernel 的信（收件人是 kernel 站時不加） |
| 使用者專區 | schema 沒有禁止多餘欄位 | 帶 `comm` 的信過 `aos-user` 的 schema 檢查與 `verify` |

### 6.2 舊信給新程式

| 舊信的樣子 | 新程式要怎樣 |
|---|---|
| 沒有 `comm` | 當 `normal`、不過期；`comm_read` 的順序跟 `mailbox_read` 一樣 |
| body 不是物件（純字串） | 當 `normal`；跟 `flat()` 一樣包成 `{"what": …}` |
| `comm` 不是物件、`v` 是 2、`level` 是 `"URGENT"` 或亂字 | 當 `normal`，照常讀，不丟信、不報錯 |
| 沒有布告欄的舊 agent | `board_read` 回 `null`；寄給它的行為跟現在完全一樣 |

### 6.3 怎麼驗（做法）

| 步驟 | 內容 |
|---|---|
| 樣本信一組 | 固定檔：六種 status 的舊信各一、三種級別的新信各一、頻道複本一、壞 `comm` 四種、純字串 body 一 |
| 一支對照測試 `test_comm_compat.py` | 在暫存樹裡把每封樣本信餵給 6.1 每個程式，跟「同一封拿掉 `comm`」的輸出比，只允許表中寫明的差異 |
| 「沒改到」的硬檢查 | 測試裡斷言 `git diff --stat` 對 `proto8/impls/aos-post` 與 `proto8/cmd/aos-mailbox` 是空的；既有的 aos-post、aos-mailbox、mail_notify 測試原封不動要全綠 |
| body 欄位沒走樣 | `aos-comm send` 與 `aos-mailbox send` 用同樣參數各寄一封，拿掉 `comm` 後 body 逐欄相同 |
| 混用 | 同一個信箱交替跑 `aos-mailbox read` 與 `aos-comm read`：每封信恰好被讀一次 |
| schema | 四份 schema 各配「該過」「該不過」的樣本檔，`aos-comm check` 跑過 |
| xiaosi 與 autoreply | 不是純程式，各實跑一輪留紀錄 |

---

## 七、給 ok-view 的布告欄 schema（可單獨抽出，先交）

> 這一節自成一份，可以整節複製給 ok-view。狀態：**草案 `board/1`**，等使用者看過才算定；欄位只會加、不會改名。

### 7.1 檔在哪

| 誰的 | 路徑 |
|---|---|
| 任一隻 proc | `<它的 stack>/board.json`（跟 `state.json` 同一層） |
| 使用者 | `~/.aos/user/board.json`（定案前仍在 `~/.aos/view/board/user.json`，見待裁 U4） |

沒有這個檔＝沒貼，是常態，不是錯。全景頁只讀、不替 agent 寫；使用者那張由網頁的「貼上布告／清空」寫。

### 7.2 欄位

| 欄位 | 型別 | 必有 | 顯示建議 |
|---|---|---|---|
| `format` | `"board/1"` | 是 | 不是這個值就當沒貼 |
| `updated_at` | ISO 8601 UTC 毫秒 | 是 | 「幾分鐘前貼的」 |
| `mode` | `here`／`busy`／`dnd`／`away` | 是 | 卡片上的小標：在／在忙／請勿打擾／不在 |
| `text` | 字串 ≤1000 | 否 | 員工卡最上方主文 |
| `doing` | 字串 ≤200 | 否 | 一句「在忙什麼」 |
| `waiting_on` | `[{who, what, since_at, ref?}]` ≤20 | 否 | 「在等 X：什麼事（多久了）」；`who` 是 proc 名字或 `"user"` |
| `back_at` | 時間 | 否 | 「預計幾點回來」 |
| `back_text` | 字串 ≤100 | 否 | 有就優先顯示這句白話 |
| `expires_at` | 時間 | 否 | 過了就標灰 |
| `accept` | `low`／`normal`／`urgent`／`none` | 否 | 可不顯示 |
| `deputy` | 名字 | 否 | 「急事找 X」 |
| `by` | `self`／`auto`／`user` | 否 | 可不顯示 |
| `seq` | 整數 | 否 | 拿來判斷要不要重畫 |
| 其他 | — | — | **不認得的鍵一律忽略** |

### 7.3 讀進來之後照這四步算

1. 讀不了或 `format` 不對 → 沒貼。
2. 過期：現在超過 `expires_at`；或沒有 `expires_at`、`mode` 不是 `here`、且超過 `updated_at` 加 24 小時 → **文字照顯示但標灰，`mode` 當 `here`**。
3. `updated_at` 比現在晚超過 5 分鐘 → 當成剛貼的來算（時鐘不準）。
4. 這隻 proc 的 phase 是 sleeping／stopped → 不管布告欄寫什麼，都算「不在」（頁面本來就有灰燈，這裡只是讓計數一致）。

`back_at` 已過而貼文沒過期 → 加註「已超過預計時間」。

### 7.4 三個彙總數字怎麼算（都用第 7.3 算完的結果）

| 全景頁要的 | 算法 |
|---|---|
| 部門卡「幾隻請勿打擾」 | 沒過期且 `mode` 是 `dnd` 的隻數 |
| 部門卡「幾隻在等人」 | 沒過期且 `waiting_on` 不空的隻數 |
| 左欄待辦「在等使用者的」 | 沒過期且 `waiting_on` 有 `who == "user"` 的每一筆，顯示 proc 名字、`what`、`since_at` |

### 7.5 JSON Schema 草案骨架

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "comm/1/board",
  "title": "aos board (comm/1)",
  "type": "object",
  "required": ["format", "updated_at", "mode"],
  "additionalProperties": true,
  "properties": {
    "format": { "const": "board/1" },
    "updated_at": { "$ref": "#/$defs/time" },
    "mode": { "enum": ["here", "busy", "dnd", "away"] },
    "seq": { "type": "integer", "minimum": 0 },
    "by": { "enum": ["self", "auto", "user"] },
    "text": { "type": "string", "maxLength": 1000 },
    "doing": { "type": "string", "maxLength": 200 },
    "waiting_on": {
      "type": "array", "maxItems": 20,
      "items": {
        "type": "object", "required": ["who"], "additionalProperties": true,
        "properties": {
          "who": { "type": "string", "minLength": 1 },
          "what": { "type": "string", "maxLength": 200 },
          "since_at": { "$ref": "#/$defs/time" },
          "ref": { "type": "string" }
        }
      }
    },
    "back_at": { "$ref": "#/$defs/time" },
    "back_text": { "type": "string", "maxLength": 100 },
    "expires_at": { "$ref": "#/$defs/time" },
    "accept": { "enum": ["low", "normal", "urgent", "none"] },
    "allow_from": { "type": "array", "items": { "type": "string" } },
    "wake_on_urgent": { "type": "boolean" },
    "clear_on_start": { "type": "boolean" },
    "deputy": { "type": "string" },
    "ext": { "type": "object" }
  },
  "$defs": {
    "time": { "type": "string", "format": "date-time",
              "description": "ISO 8601 UTC with milliseconds, same as letter.json sent_at" }
  }
}
```

### 7.6 假資料（照這個先做版面）

```json
{"format":"board/1","seq":7,"updated_at":"2026-11-14T06:30:00.000+00:00","by":"self",
 "mode":"dnd","text":"跑全量測試中，結果出來前別丟新工作給我",
 "doing":"ok-board 規劃第 2 稿",
 "waiting_on":[{"who":"user","what":"布告欄協議 6 題待裁","since_at":"2026-11-14T05:10:00.000+00:00"},
               {"who":"ok-sec","what":"uid 粒度","since_at":"2026-11-14T04:00:00.000+00:00"}],
 "back_text":"測試跑完（約一小時）","expires_at":"2026-11-14T08:30:00.000+00:00","deputy":"repo-aos"}
```

```json
{"format":"board/1","updated_at":"2026-11-14T15:00:00.000+00:00","by":"user",
 "mode":"away","text":"去睡了","back_text":"明早","back_at":"2026-11-15T00:00:00.000+00:00",
 "expires_at":"2026-11-15T03:00:00.000+00:00"}
```

---

## 八、其餘三份 schema 骨架

**信件的 `comm` 物件**（`comm/1/letter-comm`；只描述 `body.comm`，body 其餘欄位不歸這份管）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "comm/1/letter-comm",
  "type": "object",
  "required": ["v"],
  "additionalProperties": true,
  "properties": {
    "v": { "const": 1 },
    "level": { "enum": ["urgent", "normal", "low"], "default": "normal" },
    "why": { "type": "string", "maxLength": 200 },
    "expires_at": { "type": "string", "format": "date-time" },
    "auto": { "type": "boolean" },
    "wait": { "type": "boolean" },
    "channel": { "type": "string" },
    "seq": { "type": "integer", "minimum": 1 },
    "via": { "type": "array", "maxItems": 3, "items": { "type": "string" } },
    "origin": { "type": "object",
      "properties": { "from": {"type":"string"}, "sender": {"type":"string"}, "sent_at": {"type":"string"} } },
    "op": { "enum": ["post", "join", "leave", "info", "invite", "kick", "set", "close"] },
    "args": { "type": "object" },
    "result": { "type": "object", "required": ["ok"],
      "properties": { "ok": {"type":"boolean"}, "code": {"type":"string"}, "reason": {"type":"string"} } }
  },
  "if": { "properties": { "level": { "const": "urgent" } }, "required": ["level"] },
  "then": { "required": ["why"] }
}
```

**頻道設定**（`comm/1/channel`）

```json
{
  "$id": "comm/1/channel", "type": "object",
  "required": ["format", "name", "created_at"],
  "additionalProperties": true,
  "properties": {
    "format": { "const": "channel/1" },
    "name": { "type": "string" }, "title": { "type": "string" },
    "created_at": { "type": "string", "format": "date-time" },
    "owner": { "type": "string" },
    "admins": { "type": "array", "items": { "type": "string" }, "default": [] },
    "join": { "enum": ["open", "invite", "closed"], "default": "open" },
    "post": { "enum": ["members", "anyone", "admins"], "default": "members" },
    "members_from": { "enum": ["list", "daemon"], "default": "list" },
    "max_level": { "enum": ["normal", "urgent"], "default": "normal" },
    "deliver_default": { "enum": ["copy", "pull"], "default": "copy" },
    "keep_days": { "type": "integer", "minimum": 1, "default": 30 },
    "auth": { "enum": ["claimed", "uid"], "default": "claimed" },
    "limits": { "type": "object", "properties": {
      "post_per_min": {"type":"integer","default":30}, "members_max": {"type":"integer","default":500},
      "what_max": {"type":"integer","default":20000}, "batch": {"type":"integer","default":50} } }
  }
}
```

**成員表**（`comm/1/channel-members`）

```json
{
  "$id": "comm/1/channel-members", "type": "object",
  "required": ["format", "members"],
  "properties": {
    "format": { "const": "channel-members/1" },
    "seq": { "type": "integer" },
    "members": { "type": "object", "description": "key = member stack absolute path",
      "additionalProperties": { "type": "object", "required": ["name", "box", "joined_at"],
        "properties": {
          "name": {"type":"string"}, "box": {"type":"string"},
          "joined_at": {"type":"string","format":"date-time"},
          "deliver": {"enum":["copy","pull"]}, "role": {"enum":["member","admin"]},
          "sent_seq": {"type":"integer"}, "fails": {"type":"integer"},
          "gone_at": {"type":["string","null"]} } } }
  }
}
```

---

## 九、邊緣狀況

| 狀況 | 怎麼處理 | 理由 |
|---|---|---|
| 「請勿打擾」忘了撕 | 沒寫到期的 24 小時自動失效；工具寫的時候就給預設到期（`dnd` 2 小時、`away` 12 小時） | 壞的預設不能是「永遠擋」 |
| 說八點回來，九點還沒回 | 標 `overdue`，只顯示；貼文到 `expires_at` 才失效 | 晚回來是常態，不該自動當他回來了 |
| 機器時鐘跳動（WSL 休眠後） | 時間比較給 5 分鐘容忍；`updated_at` 在未來就當成現在；要判斷「有沒有變」用 `seq` 不用時間 | 單機為主，不做對時 |
| 睡著但沒貼布告欄 | 讀的時候併入 phase → 算「不在」，沒有回來時間 | 自述缺了，用事實補 |
| 貼了「在」但其實睡了 | 同上，事實優先 | 同上 |
| 睡著的收急件 | 預設不叫醒：寄件人當場被告知，由寄件人決定要不要 `ctl wake`（本來就可以）。對方睡前貼了 `wake_on_urgent` 才自動發叫醒請求，請求照走 kernel、可被拒 | 叫醒要花錢；決定權留給「被叫醒的人事先同意」與 kernel |
| 急件過期才被看到 | 當 `low`、標「已過期」 | 過時的急件不該再插隊 |
| 寄件人造假（冒名、亂標急件） | aos 層擋不住，後果靠收件端額度、頻道封頂、留帳限制；真擋等 uid 層（4.7） | 備料五：aos 不驗寄件人。這點要在規格文件寫白，別讓人以為 `from` 可信 |
| 別人替我寫布告欄 | 規則禁止；第一版查不出；uid 層後可查檔案擁有者 | 同上 |
| 布告欄檔寫到一半被讀 | 寫用 rename，讀失敗重試一次 | 讀的人不必加鎖 |
| proc 被移除、名字被重用 | 一律認 stack 路徑；頻道成員表用路徑當鍵，同名新 proc 不會自動繼承成員身分 | 名字不是身分 |
| 頻道成員已不存在 | 寄複本失敗累計 3 次或 stack 不見 → 標 `gone_at`、停寄；7 天後從成員表移除 | 不因一隻不見卡住整輪；留 7 天是給暫時搬動的緩衝 |
| 頻道 proc 沒在跑 | 發言與 join 都堆在它信箱，起來後照信名順序補處理；工具寄之前看一眼 phase，沒在跑就在回傳加警告 `channel is not running` | 信箱本來就是佇列，不必另做重試 |
| 迴圈轉寄 | 4.5 五條：不轉給自己、`via` 上限 3、機器信不轉、限速、不認得的 `op` 不猜 | 每條各擋一種來源 |
| 大量成員 | 4.6：分批、續寄、超過 50 人預設自己讀、上限 500 | 把「一則發言的成本」封頂 |
| 頻道轉到一半被殺 | 每個成員記 `sent_seq`，重起接著寄；最多重複一封，靠 `channel`＋`seq` 去重 | 寧可重複一封也不漏 |
| 成員睡了三天 | 不寄複本，醒來補一封摘要 | 4.1 |
| 兩套通知同時裝（wf/tools quiet＋布告欄 dnd） | 兩邊各壓各的，結果是壓更久，不會漏信、不會壞 | 配給包避免同裝即可 |
| 舊 `aos-mailbox read` 與新 `comm_read` 混用 | 新的把信認領到 `cur/` 後挑著讀，舊的先讀 `cur/`；不漏不重，只是舊的不照級別 | 已對原碼 |
| 很長的內文寄進頻道 | 超過 `what_max` 拒收並回信 | 一封長信乘以人數 |
| 自己寄給自己、頻道寄給頻道自己 | 寄信工具擋前者（`SendToSelf`），`via` 規則擋後者 | — |
| 跨機器 | 不支援：布告欄是本機檔，頻道是本機 proc | 使用者 11-13「就先只考慮家裏這臺」 |

---

## 十、哪些是 aos 本體、哪些不是（題 7）

| 東西 | 歸屬 | 進 NORMS | 進公開版文件（ok-release） |
|---|---|---|---|
| `comm/1` 規格文件、四份 schema | **aos 本體** | 是（N-70～72，待裁 U1） | 是 |
| `<stack>/board.json` 的位置與欄位 | **aos 本體** | 是；附錄4 加一行 | 是 |
| `body.comm` 欄位與三級 | **aos 本體** | 是 | 是 |
| 頻道 proc 定義、`channel.json`、`members.json`、`log/` | **aos 本體** | 是；附錄4 加三行 | 是 |
| 庫 `lib/aos/comm`、指令 `aos-comm` | **aos 本體**（新增） | 否（實作） | 是（用法） |
| pack `comm`、`channel` | **aos 本體**（新增） | 否 | 是 |
| hook `comm_tick` | **aos 本體**（新增） | 否 | 是 |
| `mail_notify` 加級別與布告欄判斷 | **aos 本體**（改既有；沒新欄位時輸出不變） | 否 | 是（通知行格式） |
| 範本 `tools.json` 加 `comm` 包 | **aos 本體**（改既有範本） | 否 | 是 |
| 知識庫 `aos/comm.json`、錯誤碼進 `errors` | **aos 本體**（新增） | 否 | 是 |
| `aos-user tick` 讀布告欄當安靜來源、`comm_send` 寄 user 的欄位對應 | **aos 本體**（改使用者專區） | 否 | 是 |
| aos-post、aos-mailbox | **不動** | — | — |
| 使用者布告欄網頁、員工卡、部門卡摘要、待辦 | aos-view（ok-view 做） | 否 | 否 |
| xiaosi system.txt 加一句看 `comm.level` | wf | 否 | 否 |
| autoreply 補「頻道信與機器信不回」、quiet 的汰換 | wf/tools | 否 | 否 |
| 哪個角色拿哪些工具、誰能寄急件 | ok-onboard 配給包 | 否 | 否 |
| uid 層的頻道與布告欄權限 | ok-sec | 之後 | 之後 |

新錯誤碼（工具的 `error: Code reason`）：`BoardBad`、`UrgentWhyMissing`、`SendToSelf`、`ChannelMissing`、`ChannelNotMember`、`ChannelJoinRefused`、`ChannelFull`、`ChannelRateLimited`、`ChannelOpUnsupported`。

---

## 十一、建議的上線順序（給 opus 深化，不是施工計劃）

| 批 | 內容 | 為什麼這個順序 |
|---|---|---|
| 0 | 第七節交給 ok-view | 它要照著做版面，欄位只加不改，可以先交 |
| 1 | 布告欄：schema、庫的讀寫、`aos-comm board`、`board_*` 工具 | 自成一塊、不碰信件，最快讓使用者看到東西 |
| 2 | 分級：`comm_send`、`comm_read`、`mail_notify`、`comm_tick`、相容測試 | 要先有布告欄才有 3.3 那張表 |
| 3 | 頻道：proc 定義、`aos-comm chan`、`channel_*` 工具 | 依賴第 2 批的組信與 `comm` 欄位 |
| 4 | NORMS 三條、公開版文件、使用者布告欄搬家 | 用過一輪再把條文寫定 |

請 opus 深化時核對的事實（我只讀了備料，另為相容性對過 aos-mailbox 的 `flat()`、`cmd_read`、`cmd_send` 與 aos-post 的時間寫法四處）：
- `aos_mailbox` 的 `STATUSES`、`SECTIONS`、`target_box` 能不能不改它就 import 來用。
- `ctl where`、`ctl wake` 的確切指令寫法，以及 `ctl wake` 是否如預期經 kernel。
- `mail_notify` 的既有測試涵蓋到什麼程度，夠不夠當「輸出不變」的保證。
- `aos-comm` 這個指令名與 `comm` 這個 pack 名有沒有撞到現有的。
- 頻道定義該放 `proto8/templates/` 還是 `proto8/kernel/` 旁邊。

---

## 十二、待使用者裁（6 條）

每條都有預設；不裁就照預設走，之後可改。

| # | 題目 | 選項與後果 | 預設建議 |
|---|---|---|---|
| U1 | 這套協議要不要進 NORMS | **甲**：試用一輪後收成三條新號（N-70～72），放第 05 章 N-16 旁；之前先放「08-待定」。**乙**：現在就收。後果：條文可能跟著實作改好幾次。**丙**：不進，只當一份規格文件。後果：別的實作不會把它當 aos 的一部分 | 甲 |
| U2 | 信分幾級 | **甲**：三級（急件／平信／知會）。**乙**：兩級（急件／平信）。後果：頻道閒聊與自動通知沒有「可以晚點看」的位置。**丙**：四級，多一個「特急＝一定叫醒」。後果：多一級就多一種濫用，叫醒改由寄件人決定 | 甲 |
| U3 | 急件能不能叫醒睡著的 agent | **甲**：預設不叫醒；寄件人當場被告知對方睡了，自己決定要不要叫；對方睡前在布告欄寫「急件叫我」才自動叫。**乙**：急件一律叫醒。後果：急件變成能花別人額度的按鈕，濫用代價高。**丙**：永不自動叫醒。後果：隊長睡前無法表示「有結果就叫我」 | 甲 |
| U4 | 你的布告欄要不要搬進同一套 | **甲**：搬。改存 `~/.aos/user/board.json`，網頁照樣貼、照樣清，agent 用同一招讀你和讀別的 agent；出門／安靜時段（door）照留，布告欄寫「不在」時專區也當安靜。舊檔不搬資料。**乙**：不搬，兩套並存。後果：agent 要記兩種讀法，你的布告欄沒有到期判斷 | 甲 |
| U5 | 頻道的信怎麼到成員手上 | **甲**：預設每人信箱收一份，另可選「不要複本、自己去頻道讀」；超過 50 人的頻道新成員預設自己讀。**乙**：一律自己去讀。後果：沒有通知，agent 得記得去看。**丙**：一律每人一份。後果：人多、話多的頻道會灌爆信箱 | 甲 |
| U6 | 要不要有「全員廣播」，自動建嗎 | **甲**：有這種頻道（成員＝那張表上所有人、不必加入、最高只到平信），但不自動建，要用時由頂層或隊長建一個 `all`。**乙**：每隊自動建一個。後果：每張表多一隻常駐 proc，多數時候沒人用。**丙**：第一版不做廣播，只做要加入的頻道 | 甲 |

不列為待裁、我直接定了的（都寫在各節，翻案位置在括號）：急件額度每人每小時 3 封（3.6）、到期預設 2／12／24 小時（2.1、5.1）、頻道信最高平信（4.1）、歷史留 30 天（4.1）、等回信 30 分鐘提醒（3.5）、協議與指令叫 `comm`／`aos-comm`（一）。
