# 一隻普通的 agent（先想 eca）怎麼讓自己成為 kernel（11-13；上午線申設計＋暫存樹原型，下午線酉照使用者「1乙，總之先做」做成正式版＝框架站多一個「先留著等表態」的口＋工具包 `kernel_gate`，見第十節）：原型那時的結論——最輕的做法是「一個信箱＋一支通知 hook＋一支表態工具」，原型用真 haiku 跑通（收通知、自己判、自己轉送、回信都回到寄件人）；`desc` 現在就帶得過去；留三題機制缺口給使用者

← [11-13 日索引](README.md)｜相關：[kernel-framework-開工](kernel-framework-開工.md)（框架站、hook 分流）、[手與門](../12/kernel-as-bridge/06-細聊-手與門.md)、[CONCEPTS kernel C-47](../../../docs/CONCEPTS/04-kernel.md)、[NORMS N-42](../../../docs/NORMS/09-kernel.md)（(2)「以 agent 作判斷」那半還沒做，這題就是它）｜分檔：[01-原型實跑](eca-as-kernel/01-原型實跑.md)（線申的原型：重跑指令、通知原文、工具呼叫、回信原文、邊緣狀況的實跑輸出）、[02-正式版實跑](eca-as-kernel/02-正式版實跑.md)（線酉的正式版：同一套景象的原文）

> 路徑一律寫 `~/…`；貼出來的實際輸出裡，家目錄也換成 `~`。原型在 repo 外 `~/code/shen-try-1113/`，不進 main。第一～九節是線申上午寫的（原型＝候選一「agent 自己轉送」）；進 main 的是第十節（候選二「agent 只表態、機器轉送」）。

## 使用者原文（11-13，逐字，依序）

1. 「kernel那塊幫我想個：如果一個普通的aos agent(就先想eca好了)，他想要讓自己成為kernel，那他該怎麼做？有方便快捷的方式嗎」
2. 「讓agent成為kernel，我期望看到的景象是：一個普通的agent隨便弄些hook、json設定啥的，就可以收請求了。請求進來後agent收到通知，他自己判斷要不要過，然後再去轉送」
3. 「然後請求內可能會夾帶一些額外訊息，比如"desc":"我想要做XXX，拜託讓我執行這個"」
4. 「提示注入這塊就是風險自己承擔」
5. 「所以kernel那邊，大家可以自己選擇是否允許這種」
6. 「各種的...都可以大家自己設定」

（第 2～6 句經調度者轉述，逐字。第 5 句的「這種」有兩種讀法：甲＝請求裡夾帶 `desc` 之類的額外訊息，每一站自己決定收不收；乙＝要不要讓 agent 當門、要不要承擔提示注入的風險，各站自己選。兩種讀法在設計上是同一件事：做成每站各自的選擇，預設照現況。）

看完上面的設計與三題之後，對調度者重排的四題的回覆（逐字）：

7. 「1乙，總之先做。 2甲 3乙，我那個只是舉例，實際上大家就隨便加，反正json，不認得的key，只要沒設限制，就能過。 4可以。」

四題與對應（題目是調度者問的）：1 乙＝重用框架站骨架，加一個「先留著等表態」的口，agent 只表態、機器轉送，「總之先做」＝現在就做（原型那支自己轉送的 `gate` 不做）；2 甲＝門自己在忙時通知發不出來，先不補；3 乙＝寄件人那側不加 `--desc` 入口，`desc` 只是舉例，請求信是 json，寄的人想加什麼鍵就加，不認得的鍵、站沒設限制就能過；4＝另一條線的事（agent 的 hooks 改用共用引擎）。

同一天下午對 kernel 第二輪第 1 題（分流後數量上限怎麼算）的回覆，前半句是對框架的定位（逐字；全句與其餘各題在 [kernel-framework-開工 第十四節](kernel-framework-開工.md)）：

8. 「就是說我們做的是框架，最底層就是最簡單的hook+判斷。你說的上限這塊，是在框架之上的通用基礎包，所以可以隨意，可以簡單並通用一些。」

同一天稍早對 `AOS_KERNEL` 的定位（逐字，出處 [kernel-framework-開工](kernel-framework-開工.md)）：「我會覺得AOS_KERNEL他就是在有需要掛一個aos proc的時候，就使用的一個目標，一個通用的，基礎的目標。好比所有C語言程式使用syscall的時候，只要沒有特別指定，不然就是走linux kernel那個記憶體位置。啊如果有需要其他目標...那就自己找方法指定」

## 結論

**收斂的原則（第 6 句）：「各種的...都可以大家自己設定」。** 體系只提供機制，政策留給每一站自己寫。第 8 句給了它結構上的說法：「我們做的是框架，最底層就是最簡單的hook+判斷」——框架本身只有收信、叫 hook、照判決走；數量上限這類是蓋在框架之上的通用基礎包的事。兩句合起來：凡是「體系該不該規定 X」一律不規定，留給各站的 hook 與設定。套在這題上：

| 體系給的機制 | 每一站自己定的政策（體系不規定） |
|---|---|
| 請求信的最小形狀（aos-post 信封＋body，body 不認得的鍵不管） | 收不收帶 `desc` 的請求、`desc` 怎麼用、要不要剝掉 |
| 能掛 hook 的時機（agent 的 `on_clock`、框架站的三個時機） | 誰來判（機器規則、腦、兩者混合）、判的標準 |
| 一個信箱、通知、表態與轉送的工具 | 等多久算逾時、忙的時候怎麼辦、要不要承擔注入風險 |
| 下一站三段（設定的 `next` → `AOS_KERNEL` → `AOS_DAEMON`） | 放行後寄去哪、回信要不要經過自己 |

其餘結論（第 1、5 點講的是上午的原型；正式版照第 7 句改走候選二，現況在第十節）：

1. **他要的景象今天就做得出來，而且很輕。** 一隻 eca 成為門只要三樣：自己 stack 裡一個信箱、一支 `on_clock` 通知 hook、一支表態工具。原型把三樣包成一支工具 `gate`，agent 叫一次 `{"op": "on"}` 就全掛好、回報「把請求寄到這個路徑」。真 haiku 實跑：收到通知 → 自己判 → 過的那封自己轉送到 daemon 掛起來、不過的回拒信，兩封回信都回到寄件人（[01](eca-as-kernel/01-原型實跑.md)）。
2. **`desc` 現在就帶得過去，什麼都不用改。** 框架站對 body 裡不認得的鍵原樣轉寄、daemon 收到多的鍵照掛（都實測過）。缺的只有兩頭：寄件人那側沒有入口可以寫它（只能手寄信），門這側沒有人把它拿給腦看（原型的通知已經把它跟「實際要掛什麼」並列）。
3. **提示注入**：請求信與 `desc` 的內容會進門那隻 agent 的對話。使用者 11-13 裁：風險自己承擔。原型不做任何包裝、過濾或長度上限。
4. **最大的邊緣狀況是「門在忙」**：agent 自己的一輪進行中，它身上的 `on_clock` hook 不跑，所以通知發不出來、機器也沒辦法替它回逾時。寄件人等到自己的期限就撤信走人（實測）。這是機制缺口，留成題 1。
5. **不新增工具也做得到**，但每封信要腦自己打兩三行 `aos-post`，而且撞 [rules.json](../../../knowledge/aos/rules.json) 第 5 條「不手寄信」。

## 一、「成為 kernel」的幾種意思

照「你把請求寄到哪，哪裡就是你的 kernel」，差別只在信箱後面是誰在判。**他要的是 A。**

**A. agent 自己（腦）判——他要的景象**

```text
寄件的 proc ──請求信──▶ agent stack 裡的信箱
                              │ on_clock hook 看到新信
                              ▼
                        agent 的 queue：「[aos] kernel_request: …」
                              │ 腦判
              ┌───────────────┴───────────────┐
           過：agent 叫工具把信送去下一站      不過：agent 叫工具回拒信
              ▼                               ▼
        下一站（最後是 daemon）──回信──▶ 寄件人 ◀──拒信──
```

其他幾種，各一兩句當對照：

- **B. 身上掛框架站（機器判）**：agent 用 `self_hook` 把 [`lib/aos/kernel`](../../../lib/aos/kernel/README.md) 掛成自己的 `on_clock` hook，規則寫在 `kernel.json`，腦不參與每一封。今天零新程式就做得到（三步，實測過：一封 `applied`、一封 `NameUnknown`）。agent 是規則的作者，不是判的人。
- **C. 另起一個 proc 當站**：把 `kernel/procs-kernel` 抄一份、改 `kernel.json`、掛到 daemon 上，agent 當它的管理者。站不會因為 agent 在忙而停。eca 沒有 `subagent`／`agents_ctl` 工具，只能用 Bash 打 `aos-agent ctl add`。
- **D. 只對自己帶起來的 proc 當門**：信箱跟 A／B 同一個，差在「誰把 `AOS_KERNEL` 指過來」——agent 加別的 proc 時給 `--envs AOS_KERNEL=<我的信箱>`，只有它帶起來的那些會寄過來。
- **E. 混合**：框架站先用機器規則篩，篩不出來的才問 agent。需要框架站多一個「先留著、等人表態」的口（見第三節），今天沒有。

## 二、查到的現況（事實）

請求信：

- 掛 proc 的請求是一封 aos-post 信。信封有 `sender`（寄件人的 cwd 路徑，不是名字，aos 不驗）、`sent_at`、`reply_to`；body 是 `{"procs_added": {名字: {exec, def, ws, as_written}}, "queue_wait_ms": N}`。
- `aos-agent ctl add`／`start`／`wake` 預設帶 `queue_wait_ms`＝自己的等待秒數（預設 30 秒）。等不到回信就**把還沒被認領的信撤回**，印 `DaemonFailed … letter withdrawn, it will not be applied`。信一旦被認領就撤不回。
- 一般 proc 發掛 proc 請求的入口（`subagent`、`agents_ctl`、`fork`、人打的指令）最後都走 `aos-agent ctl add`，body 在 `cmd/aos-agent/aos_agent/ctl/shared.py` 的 `ctl_wait` 組出來。

body 裡多帶一個鍵（實測，在暫存樹）：

- 直接寄給 daemon：body 頂層多一個 `desc`，或 `procs_added` 那一列裡多一個 `desc`，都回 `{"applied": true}`、照掛；`desc` 不會寫進 daemon 的表。
- 經過框架站：沒有 hook 時 body 原樣轉寄，下一站收到的 body 裡 `desc` 還在。

eca 這邊：

- eca 身上的 `on_clock` hook 是在它的 loop 每一圈開頭檢查（約每 0.3 秒一圈），**等 CLI 回答的那段時間不檢查**；睡著、停著、沒時鐘時也不跑。冷卻中照跑（檢查在看冷卻之前）。
- hook 的 handler 拿到 agent 的 stack（事件的 `stack` 欄），自己的小格是 `<stack>/hooks/<名>/`。
- eca 有的工具：`self_*`、`agent_def`、`tools_def`、`mailbox_*`、時鐘、json 幾包，加 CLI 自己的 Bash／Write／Edit。沒有 `subagent`、`agents_ctl`、`fork`。
- 畫面開著的 claude 身，queue 的信會當場進對話（署名 `aos通知中心`）。但通知是 `on_clock` hook 產生的，一輪中間 hook 不跑，所以這條路幫不到「門在忙」。

誰能讓別人的請求寄過來：

- 寄件人自己（每次下指令前設 `AOS_KERNEL`），或帶起寄件人的那一方（`aos-agent ctl add --envs AOS_KERNEL=…`），或人改整棵樹的環境，或上游某一站把 `next`／hook 的 `next` 指過來。
- 當門的 agent 沒辦法強迫任何人：它只能公布路徑（例如寄 mailbox 信）。同一個 Linux 帳號下，寄件人照樣可以直寄 daemon 繞過它；保底是 Linux 權限（C-47）。

## 三、設計：agent 當門的最輕做法

### 四個零件

| 零件 | 做法（原型照這樣做） | 為什麼 |
|---|---|---|
| 信箱 | agent stack 裡新的一格：`<stack>/gate/requests`。別人的 `AOS_KERNEL`（或上游站的 `next`）指到這個路徑 | 不能用 `queue`（進去的東西直接變成對話、形狀不對的信會被丟掉）；不能用 `mailbox`（那是 agent 之間的公文格式，請求信不是）。所以要新的一格 |
| 設定 | `<stack>/gate/gate.json`，兩個選填鍵：`next`（放行的信寄去哪）、`max_wait_s`（一封最多等我幾秒，預設 600） | 都不寫也能跑 |
| 通知 | 一支 `on_clock` hook（每個時鐘週期看一次）。有沒通知過的請求，就往自己 queue 寄一則 `[aos] kernel_request: …`，多封合成一則；沒新信什麼都不做。比照 `mail_notify` | 用 agent 平常就有的手段 |
| 表態 | 一支工具，兩個動作：`pass`（把那封信送去下一站）、`refuse`（附一句原因回拒信） | 見下面「誰轉送」 |

通知裡帶的東西：每封一段，機器從信裡讀出來的事實（信名、寄件人、要掛／停／收哪個名字、定義路徑、工作區、寄件人還等幾秒），下一行是寄件人自己寫的 `desc` 原樣。最後一行寫怎麼表態。只通知一次；機器不看也不轉述 `desc` 以外的自由欄位。

### 誰轉送：主案與對照案

| | 主案：agent 自己轉送（照他的話字面） | 對照案：agent 只表態，機器轉送 |
|---|---|---|
| 怎麼做 | `pass` 那一下，工具就把同一份 body 用原信名寄到下一站，帶著寄件人原本的 `reply_to` | agent 的表態寫成一個檔；框架站下一輪看到檔才轉寄 |
| 回信 | 下一站直接回給寄件人，不經過門 | 可以開 `reply_via_me` 由站代回 |
| 門知道結果嗎 | 不知道（daemon 若回 `InstanceExists`，門不會曉得） | 知道（代回時看得到） |
| 現成的好處 | 沒有 | 數量上限、排隊、hook 分流、防重、轉寄對照表都現成 |
| 要動什麼 | 不動框架，另寫約 300 行（原型已有） | 框架站要多一個口（下一段） |

下一站照今天的三段：`gate.json` 的 `next` → 環境的 `AOS_KERNEL`（指到自己的信箱就跳過）→ `AOS_DAEMON` 的 ctl 信箱。原型照這樣做。

### 能不能重用框架站的骨架

可以重用大半，但缺一個口：**「先留著、等人表態」**。現在一封信每一輪一定要有結果（過、拒、或因為沒格而排隊）；hook 能改的判決只有 `pass`／`refuse`，「排隊」是掛 proc 那一包在沒格時自己決定的，hook 叫不出來。要讓 hook 說「這封先留著」，現有做法只有讓 hook 故意失敗，那會讓整輪退 1、後面的信全卡住。

最小的口：`after_verdict` hook 的 stdout 多收一個值 `{"verdict": "hold"}`——這封留在 `cur/`、不回信、下一輪再問一次。放在 `after_verdict` 的好處是內建的期限檢查先跑，過期的自動拒，不用另外寫。

| 路 | 工作量（估） | 得到什麼 |
|---|---|---|
| 另寫小東西（主案，原型這條） | 原型已有約 300 行。收成正式工具包（測試、說明、知識庫一條、掛進範本的選項）約一天 | 最貼他的話；不碰框架 |
| 框架加 `hold` 口＋「問主人」的 hook 與表態工具（對照案） | 骨架與 hook 約 20 行＋測試與說明，半天；hook handler 與工具各約 60 行，半天 | 機器轉送、代回、上限、分流都現成；E（混合）也順便有了 |

### 「隨便弄些 hook、json」最少幾樣

**一支工具叫一下（原型的 `gate`）**：

```text
gate {"op": "on"}                      建信箱、寫 gate.json、掛通知 hook，印出「請求寄到這個路徑」與放行後會寄去哪
gate {"op": "on", "next": "/abs/box", "max_wait_s": 120}
gate {"op": "ls"}                      還在等的請求（跟通知同一個排版）
gate {"op": "pass", "letter": "<信名>"}
gate {"op": "refuse", "letter": "<信名>", "reason": "給寄件人看的一句"}
gate {"op": "off"}                     拿掉通知 hook，回報還有幾封沒答
```

錯誤代號：`LetterMissing`（信不在了：被撤回、逾時、或已判過）、`LetterLate`（超過寄件人的期限，已替你回 `GateTimeout`、沒有轉送）、`ForwardFailed`（下一站寄不進去，信還留著）、`NextMissing`。拒信的形狀跟框架站一樣：`{"applied": false, "error": {"code": "GateRefused", "msg": 原因}}`。

**完全不新增工具**（只用現有的 `self_hook`、Write、Bash）：做得到，開張三步、之後每封兩三行。

1. Bash：`aos-post init <自己 stack>/gate/requests`。
2. Write：自己寫一支通知程式（約 40 行，抄 `lib/agent/mail_notify` 改成看這個信箱）。
3. `self_hook {"op": "add", "event": "on_clock", "every_cycles": 1, "name": "gate_notify", "path": "…", "on_error": "continue"}`。
4. 每封信，Bash：`aos-post take-all BOX`、`aos-post see BOX 信名`；過＝`aos-post send --reply-to <原回信箱> <下一站> 信名 < body` 再 `aos-post done BOX 信名`；不過＝`echo '{"applied": false, …}' | aos-post done --reply BOX 信名`。

這條路沒有另外叫腦跑過，但每一行指令就是原型工具底下跑的那幾行。它會撞到的界線：rules.json 第 5 條（「to send letters by hand」明列為不該用 shell 做的事）；知識庫 `kernel.json` 的「write your own」卻正是教這幾行。兩處對 agent 來說互相打架，要嘛出工具、要嘛改第 5 條的說法（題 2）。

## 四、請求裡的額外訊息（`desc`）

| 問題 | 結論 |
|---|---|
| 現況多帶一個 `desc` 會怎樣 | 沒事。框架站原樣轉、daemon 照掛（實測）。沒有任何一站會看它 |
| 要讓它「可以帶」最小改什麼 | 傳輸上不用改。缺的是寄件人的入口與門這側的顯示 |
| 放哪一層 | body 頂層（代定）。信封的欄位是 aos-post 固定的；C-47 寫明請求放在 body、body 各類自理 |
| 叫什麼、是不是任意鍵 | 任意鍵都能帶（不認得的鍵不管）；`desc` 是照他舉的例子約定的名字，門的通知預設拿它給腦看（代定）。要看別的鍵是各站自己的事 |
| 寄件人怎麼填 | 現在沒有入口，只能手寄信。最小的加法：`aos-agent ctl add`／`start`／`wake` 多一個選填 `--desc TEXT`，寫進 body 頂層；`subagent`、`agents_ctl` 的 add 多一個選填鍵 `desc` 傳下去。約 30～50 行加說明（題 3） |
| 門這側 | 通知裡 `desc` 原樣給 agent，跟機器讀到的「實際要掛什麼」並列。實測：自述說「看時間的小工具」、實際要掛完整的 eca-claude，haiku 看得出對不上並拒絕 |
| 轉送時留不留 | 原樣帶著。下一站照自己的選擇處理；到 daemon 也不用剝（它不看、不存） |

**各站自己選擇收不收**（第 5 句）：不需要新的設定鍵，用現有的機制就做到（都實測過）。

- 框架站：`before_verdict` hook。什麼都不掛＝收下、原樣轉；hook 把 `desc` 從 body 拿掉再回 `{"body": …}`＝剝掉再轉；hook 看到 `desc` 就退 10＝拒（寄件人收到 `HookRejected` 與 hook 說的原因）。
- agent 當門：就是它的判斷標準的一部分，一句話交代即可。實測交代「沒寫自述就拒」，它照做。

## 五、邊緣狀況

標「實測」的在暫存樹跑過，輸出在 [01](eca-as-kernel/01-原型實跑.md)；其餘是讀程式推出來的。

**門沒空判**

1. **門正在自己的一輪裡（忙）**：通知 hook 不跑，請求躺在信箱裡沒人知道。用 `aos-agent ctl` 寄的（預設等 30 秒）到期自己撤信，看到的是 `DaemonFailed no result from the daemon …`——訊息說的是 daemon，其實是門沒回。手寄、沒帶期限的信就一直等到門閒下來。
2. **門睡著／停著**（實測）：同上。帶 5 秒期限的寄件人 5 秒後撤信、失敗；沒帶期限的信留著，門醒來第一個週期就通知、照判（實測放行成功）。
3. **冷卻中**：hook 照跑、通知進 queue，但 queue 的信要等冷卻過了才會交給腦；機器的逾時回覆照常。
4. **畫面有人**：claude 身畫面開著時通知會當場進對話；但若它正在答上一題，見第 1 條。
5. **寄件人的期限到了**：信還沒被認領＝寄件人自己撤走，門之後才表態會得到 `LetterMissing`。信已被認領（門判過同一批的別封）＝撤不回；原型在 `pass` 當下再比一次期限，過期就回 `GateTimeout`、不轉送（實測）。沒有這一比，會出現「寄件人以為失敗、proc 卻被掛起來」。
6. **它忘了表態**：只通知一次、不再提醒。超過 `max_wait_s` 由通知 hook 替它回 `GateTimeout`——前提是 hook 有在跑（門不忙、沒睡）。

**判與轉送**

7. **表態後轉送失敗**（實測）：下一站信箱不在，工具回 `ForwardFailed`、信留在原地，腦可以再試或改拒。
8. **放行不等於掛得起來**：主案的回信直接回寄件人，daemon 若拒絕（名字撞了、滿了），門不會知道。
9. **數量上限沒人數**：門不數格子。要數得腦自己看表，或把下一站指到一個有 `max_running` 的框架站。
10. **一輪進來很多封**（實測 5 封）：合成一則通知、一輪判完。放行的先後是腦叫工具的先後，不保證照寄來的順序。
11. **只能整批認領**：`aos-post` 沒有「只認領指定那一封」的口，判第一封時整批都被認領，其餘幾封的寄件人從此撤不回（題外的小缺口，見第七節）。
12. **判一封要花一輪腦的錢**：每一批請求一輪。沒有請求時不花腦，但通知 hook 每個時鐘週期起一次小程式。

**繞回自己、被收掉**

13. **它判自己發的請求**（實測）：門自己用 `AOS_KERNEL` 指到自己的信箱去掛 proc，一定失敗——它在等指令回來，等的那段正是它沒辦法判的時候；8 秒後 `DaemonFailed`、信撤回。門自己要掛東西得直接寄下一站。
14. **整棵樹的 `AOS_KERNEL` 都指到這隻**：三段裡第二段指到自己會跳過，放行的信直接進 daemon，不會繞圈。
15. **兩隻互相當對方的下一站**：信會來回傳，每一跳各花一輪腦。轉寄出去的是新信、`sent_at` 重算，所以期限每一跳重新起算，不會自己停。框架站也不偵測成環。
16. **被 stop／sleep**：stack 留著，信留在信箱；見第 2 條。
17. **被 rm**：不帶 `--purge` 同上。帶 `--purge` 信箱整個沒了，沒答的信一起消失、沒人回；之後寄過來的人當場收到 `MailboxMissing`。
18. **改名**：等於 rm 再 add，預設的 stack 路徑跟著名字變，舊的 `AOS_KERNEL` 指到空路徑。
19. **換定義（`set-def`）**：stack 不動，信箱、hook、工具登記都在 stack 裡，門照常。
20. **它死了誰知道**：沒有人。寄件人只看得到逾時。

**其他**

21. **一隻 agent 宣稱自己是 kernel，別人憑什麼聽**：不憑什麼。kernel 是寄件人主觀的選擇；門只能公布路徑。
22. **跟框架站串成鏈**：門放在哪一站都行，站與站之間只認信箱路徑。門在前、框架站在後＝腦先判、機器再數格；反過來則是機器先篩、剩下的才花腦。
23. **提示注入**：請求信與 `desc` 的內容會進門那隻 agent 的對話。使用者 11-13 裁：風險自己承擔。

## 六、原型

做的是 A 的主案：`~/code/shen-try-1113/gate/`（工具 `_entry` 106 行、通知 hook `notify` 47 行、共用 `gate_common.py` 131 行）。暫存樹一台根 daemon（帶時鐘）加一隻 eca-claude 的 `kay`（haiku，claude 2.1.323）。`aos-daemon` 執行檔是 11-13 08:23 那一版（15:30 換新版之前）；proto8 的 Python 部分是 12:20 左右從工作樹抄的複本。

重跑（從無到有，跑完自己停樹；會花兩輪 haiku）：

```sh
bash ~/code/shen-try-1113/demo.sh
```

實際結果（完整輸出在 [01](eca-as-kernel/01-原型實跑.md)）：

- 對 `kay` 說一句話，它叫 `gate {"op": "on"}`，回報信箱路徑。
- 另一個 proc 寄三封帶 `desc` 的請求。`kay` 收到一則通知，叫了三次工具：
  - `logwatch`（自述跟實際對得上）→ `pass` → 寄件人收到 `{"applied": true}`，daemon 表上多一列 `logwatch running`。
  - `quiet`（沒寫 `desc`）→ `refuse` → 寄件人收到 `GateRefused`「沒有寫 desc（自述），無法判斷要掛什麼用途，請補上用途說明後重送。」
  - `clockpeek`（自述說是看時間的小工具，實際要掛完整的 eca-claude、工作區是家目錄）→ `refuse` → `GateRefused`，原因寫出兩邊哪裡對不上。
- 另外用 `aos-agent ctl add` 走同一道門也通：放行的印出新 proc 的 stack、退 0；被拒的印 `AddRejected the add letter was refused: GateRefused …`、退 1。

## 七、建議與留給使用者的題

**建議**：先把主案收成一個選掛的工具包（一支 `gate`＋它的通知 hook），因為它已經能跑、不碰框架、最貼他說的景象；知識庫寫明「底下就是一個信箱、一支 hook、一份 json」，想自己搭的 agent 照著搭。框架的 `hold` 口另外排，等真的要「機器先篩、剩下問腦」時再做。

照「機制給體系、政策給各站」，政策題都不問；下面三題都是「機制缺一個口，要不要加」。

**題 1：門在忙的時候，通知發不出來。要不要補機制？**

- 甲（建議）：先不補。門忙＝寄件人等到自己的期限就撤信，行為乾淨、已實測。零工作量。後果：一隻常常在長時間工作的 agent 當不好門。
- 乙：通知那支改成 agent 以外的一個小 proc 來跑。門忙的時候通知照發、逾時照回；畫面開著的 claude 身還能在一輪中間收到通知。後果：多佔 daemon 一格，agent 要有辦法掛 proc（eca 現在只能靠 Bash）。
- 丙：改 eca 的 loop，等 CLI 回答時也照跑 `on_clock`。後果：所有 hook 的行為一起變，要另外想清楚。

**題 2：agent 自己搭門時會撞「不手寄信」那條界線。怎麼處理？**

- 甲（建議）：出工具包，agent 不必手寄信；rules.json 第 5 條不動。知識庫「write your own」那段補一句「agent 請用工具」。
- 乙：不出工具，改第 5 條，明講「當 kernel 轉寄請求信」不算手寄信。後果：每封信腦要自己打兩三行指令，容易打錯。

**題 3：寄件人那側要不要加一個寫 `desc` 的入口？**

- 甲（建議）：加。`aos-agent ctl add`／`start`／`wake` 多一個選填 `--desc`，`subagent`、`agents_ctl` 的 add 多一個選填鍵。小改動。
- 乙：不加，要帶的自己手寄信。後果：一般 agent 實際上帶不了 `desc`，門看不到自述。

另外兩個小缺口，不用他裁，記著給施工時用：`aos-post` 沒有「只認領指定那一封」；門沒回時 `aos-agent ctl` 的錯誤訊息說的是 daemon、還叫人去看一個不存在的 `queue.json`。

## 八、供參考：體系替各站做了政策決定的地方

只列這題附近看到的，不重審框架。

1. 框架站：寄件人的期限過了一律拒，就算當下有格；排隊只有先來先掛。站自己選不了。
2. 框架站：停、收、睡、ping 的信內建規則一律不判；要判得自己寫 hook（這條改得了，只是預設偏一邊）。
3. `aos-agent ctl`：add／start／wake 一律帶期限、逾時一律撤信；要不帶得加 `--on-queued ok`。這是替寄件人定的。
4. rules.json 第 5 條對所有 agent 一體適用，不分它是不是在當門。

## 九、過程中的一次失誤與收尾

- **失誤（12:22）**：有兩行指令我直接在 zsh 裡 `source` 了暫存樹的環境檔，檔裡清 `AOS_*` 的那行用的是 bash 才有的寫法，在 zsh 裡沒生效。結果那兩次 `aos-agent ctl add` 帶著調度者 session 的 `AOS_STACK`，把回信箱開在 `~/aos-home` 樹裡調度者那一格的 `daemon_reply/`：兩封回信短暫進出、被我自己的指令收走，沒有留下檔案；請求本身寄的是我的暫存樹。同時掛起來的測試 proc 工作區被設成 repo 根，它只閒置、沒寫任何東西，隨後已收掉。之後環境檔改成「不是 bash 就拒絕、清完還有殘留就拒絕」，所有指令都經 bash 腳本。
- 暫存樹已停（`aos-daemon-ctl -d ~/code/shen-try-1113/tree/stacks/root shutdown`）。repo 裡只新增這份與同名夾一份分檔。

## 十、正式版（線酉，11-13 下午）：框架站的「先留著等表態」＋工具包 `kernel_gate`

照第 7 句「1乙，總之先做」做成進 main 的東西。實跑原文在 [02-正式版實跑](eca-as-kernel/02-正式版實跑.md)。

### 做了什麼

| 層 | 東西 | 在哪 |
|---|---|---|
| 骨架的口 | `after_verdict` hook 回 `{"verdict": "hold"}`＝這封留在站裡；別人把 `{"verdict": "pass"}` 或 `{"verdict": "refuse", "error": …}` 寫進 `<站的 stack>/decisions/<信名>.json`，站下一輪照做。轉寄走平常那條路（下一站三段、hook 分流、代回、防重、臨轉寄再驗期限） | [`lib/aos/kernel`](../../../lib/aos/kernel/README.md)（`hold.py`、`round.py`、`hooks.py`），commit `6f83a431a` |
| 包的口 | 掛 proc 那一包的 `held`：留著的信每輪只驗寄件人的期限，過了拒 `SlotMissing` | `procs_rules.py`，同一個 commit |
| 工具包 | `kernel_gate`：`on`／`off`／`ls`／`pass`／`refuse`；附兩支 hook 程式 `tick`（agent 身上的 `on_clock`：叫站跑一輪＋發通知）與 `hold`（站的 `after_verdict`：回 hold） | [`lib/agent/kernel_gate`](../../../lib/agent/kernel_gate/)、[`lib/packs/kernel_gate.json`](../../../lib/packs/kernel_gate.json)，commit `306078925` |
| 說明 | 框架 README「先留著等表態」、[kernel/docs/02「agent 當門」](../../../kernel/docs/02-kernel-modes.md)、知識庫 `aos/kernel.json` 的 `gate` 與 `write_your_own`、`aos/packs.json` | |

分層照第 8 句：留著與表態是骨架的口（機制）；誰來判、怎麼通知、哪些信要留、留多久，全是各站 hook 與設定的事（政策）。`kernel_gate` 只是其中一種現成的搭法。

### 一隻普通 eca 變成門：兩次工具呼叫

```text
self_tools  {"op": "add", "path": "<AOS_HOME 的實際路徑>/lib/agent/kernel_gate"}
kernel_gate {"op": "on"}
```

`on` 做三件事並回報：建站的 stack（`<agent 的 stack>/hooks/kernel_gate/`，含 `requests/` 收件信箱）；沒有 `kernel.json` 才寫預設那份（一支 `hold` hook、`condition: "pass"`）；在自己身上掛一支 `on_clock` hook `kernel_gate`（每個時鐘週期跑站一輪）。印出的第一行就是「把請求寄到這個路徑」。收掉：`kernel_gate {"op": "off"}`（把還留著的全部回拒 `HoldRefused`、拿掉 hook；`kernel.json` 與信箱留著，再 `on` 就接著用）。

之後：有請求被留下 → 一則 `[aos] kernel_hold: N requests held …` 進它的 queue，每封五行（信名、`from`、`request`＝`procs_*` 與 `ping` 那幾個鍵的原樣 JSON、期限、寄件人多寫的其他鍵原樣 JSON）→ 它叫 `kernel_gate {"op": "pass", "letter": …}` 或 `{"op": "refuse", "letter": …, "reason": …}` → 工具寫表態檔、當場叫站跑一輪、回報結果。

完全不用新工具也行（只靠 `self_hook`、手寫 `kernel.json` 與一支 hook、表態＝用 Write 寫一個檔）：步驟寫在知識庫 `aos/kernel.json#/write_your_own` 第 3 種，`lib/agent/kernel_gate/tests/test_kernel_gate.py` 的 `test_09` 照那份步驟跑過。這條路 agent 不必手寄信（轉寄是站做的），所以跟 [rules.json](../../../knowledge/aos/rules.json) 第 5 條不再打架；知識庫原本教「每輪手打 `aos-post`」的那段改成「這是寫給程式做的，不要自己在殼裡手打」。

混合用法（機器先照規則判、只有規則沒把握的才留給腦）：`kernel.json` 寫 `allowed`／`max_running`，hook 自己決定哪些信回 hold。最小例子（只留帶 `desc` 的）在框架 README 與知識庫 `aos/kernel.json#/gate`；`test_kernel_hold.py` 的 `test_11`、`test_kernel_gate.py` 的 `test_06` 蓋住。

### 代定（線酉；可翻案）

1. **表態 pass 蓋不過規則**：有人說 pass 的那一輪，站把信重判一次（期限、白名單、上限、排隊都照跑，`after_verdict` 也再跑一次、這次 hook 再回 hold 不算數）。所以期限過了才說的 pass 不放行；想讓腦蓋過規則，是那一站自己寫 hook 的事。
2. **名字**：判決值 `hold`；窗 `hold.json`；表態檔 `decisions/<信名>.json`，形狀跟 hook 的 stdout 一樣（`verdict`＋選填 `error`）；拒信代號預設 `HoldRefused`（表態檔自己給了 `error` 就用它的）；工具與包叫 `kernel_gate`；通知種類 `kernel_hold`。
3. **跟 `queue` 的關係**：兩個各自獨立的窗。排隊＝等格子（機器自己放）；留著＝等表態。留著的信不佔格、不擋後面的信；表態 pass 之後沒格就進排隊窗，出隊時不再被留。
4. **留著的信不重跑 `before_verdict`**、改過的 body 存 `bodies/`（跟排隊的信同一套）；留著時 hook 給的 `next` 不記，重判那次給才算。
5. **站沒有自己的「最多留多久」**：只認寄件人的 `queue_wait_ms`。沒帶期限的信一直留到有人表態（原型的 `max_wait_s` 沒做——那是政策）。
6. **通知與 `ls` 不解讀額外的鍵**：`procs_*`、`queue_wait_ms`、`ping` 算「request」，其餘鍵整包原樣 JSON 印一行；不挑 `desc`、不截長、不過濾（第 4 句「提示注入這塊就是風險自己承擔」）。
7. **預設那份 `kernel.json` 的 hook 寫 `condition: "pass"`**：規則拒的直接拒、不吵腦。
8. **`pass`／`refuse` 當場叫站跑一輪**：agent 在自己的一輪裡時 `on_clock` 不跑，不當場跑的話要等這一輪結束才轉寄。
9. **`off` 把留著的回拒**：不留「認領了卻沒人答」的信。
10. **不掛進任何範本**（已不是代定：使用者 11-13「預設不掛」，見下面）。

### 第五節的邊緣狀況，在這個做法下各自變成怎樣

「實跑」＝02 那次真 haiku；「測試」＝單元測試蓋住；沒標的是讀程式推的。

| # | 狀況 | 現在 |
|---|---|---|
| 1 | 門正在自己的一輪裡 | **還在**（使用者「2甲」：先不補）。它身上的 hook 不跑＝站不跑，信躺在信箱沒被認領，帶期限的寄件人到期自己撤信 |
| 2 | 門睡著／停著 | 同上；站的狀態都在 stack 裡，醒來接著跑 |
| 3 | 冷卻中 | hook 照跑＝站照跑，期限照驗；通知要等冷卻過了才交給腦 |
| 4 | 畫面有人 | 沒變（沒測） |
| 5 | 寄件人的期限到了 | **由機器管了**：留著的信每輪驗期限，過了回 `SlotMissing`（測試）；期限過了才說 pass＝站重判時拒、工具回 `LetterRefused`（測試）。實跑裡帶 4 秒期限的那封 haiku 在 3.8 秒內放行成功。前提仍是站有在跑（第 1 條） |
| 6 | 它忘了表態 | 只通知一次、不再提醒。帶期限的到期由站拒；沒帶期限的一直留著（代定 5） |
| 7 | 表態後轉送失敗 | **變了**：站照平常回 `ForwardFailed` 拒信給寄件人並收信，工具回 `LetterRefused`；信不會留著等重試 |
| 8 | 放行不等於掛得起來 | 預設回信直接回寄件人，門不知道。可以在 `kernel.json` 開 `reply_via_me` 讓站代回（還能掛 `before_reply` hook）；腦仍不會被通知 |
| 9 | 數量上限沒人數 | **消失**：`kernel.json` 寫 `max_running`（下一站不是自己的 daemon 時加 `count_daemon`），機器數 |
| 10 | 一輪進來很多封 | 留得住（測試 5 封；實跑 3 封合成一則通知）。放行先後是表態先後 |
| 11 | 只能整批認領 | 還在（站每輪整批認領，認領後寄件人撤不回）。差別：認領後到期，站會回拒信，不會懸著 |
| 12 | 判一封要花一輪腦 | 每批一輪。另外每個時鐘週期起一次站（比原型的通知 hook 重）。混合用法可以少問腦 |
| 13 | 它判自己發的請求 | 還在（它等指令回來的時候站不跑）。門自己要掛東西得直寄下一站 |
| 14 | 整棵樹的 `AOS_KERNEL` 都指到這隻 | 站的三段照舊：指到自己就跳過、進 `AOS_DAEMON`（框架的測試） |
| 15 | 兩隻互相當下一站 | 還在，不偵測 |
| 16 | 被 stop／sleep | stack 留著：信、`hold.json`、表態檔都在，回來接著跑 |
| 17 | 被 rm | 不帶 `--purge` 同上；帶了整個沒了 |
| 18 | 改名 | 沒變 |
| 19 | 換定義 | 沒變（站、hook、工具登記都在 stack 裡） |
| 20 | 它死了誰知道 | 沒有人 |
| 21 | 別人憑什麼聽 | 沒變 |
| 22 | 跟框架站串成鏈 | 門本身就是一個框架站，放在鏈上哪一站都行，分流、代回、上限都現成 |
| 23 | 提示注入 | 沒變：額外的鍵原樣進對話，風險自己承擔 |

這個做法多出來的：

- 表態工具那一輪與 `on_clock` 那一輪用同一把鎖（`requests/.flock`）；工具拿不到鎖時回「decision recorded…applied on its next round」。
- `off` 之後信箱還在：之後寄進來的信沒人認領（帶期限的寄件人自己撤）。
- `hold.json` 壞＝當空窗、cur 裡的信當新信重判（腦會再收到一次通知）；表態檔壞＝刪掉、信照留（都有測試）。
- 通知種類 `kernel_hold` 已登記進 `py/aos_flags.py` 的 `NOTE_KINDS` 與 N-43 續的名單（`1c973e47e`，調度者授權）；`tick` 跟 `mail_notify` 一樣自己拼同一個格式。

### 要不要掛進範本：已裁

題目（調度者問的）：`kernel_gate` 要不要預設掛進 eca-claude／agent-fsm 範本（甲＝不掛，要用的 agent 自己 `self_tools add`；乙＝掛進兩個範本）。使用者 11-13（逐字）：

9. 「預設不掛」

維持現況：不進任何範本，要當門的 agent 自己用 `self_tools` 加。照第 6、8 句，政策題都不問；目前沒有等使用者裁的題。

另外沒補、記著的機制缺口（第 1、2 個是線申記的，照舊）：`aos-post` 沒有「只認領指定那一封」；門沒回時 `aos-agent ctl` 的錯誤訊息說的是 daemon；門在忙時通知發不出來（使用者已裁先不補）。

### 生效表

| 改的東西 | 活樹（`~/aos-home`）什麼時候有 |
|---|---|
| `lib/aos/kernel`（hold、轉寄對照的洞、有序＋分流） | 複本，下次重抄才有；今天 15:08 釘住的 commit 不含。樹裡沒人用框架站 |
| `lib/agent/kernel_gate`、`lib/packs/kernel_gate.json` | 新夾，下次重抄才有。沒掛進任何範本，重抄後也要 agent 自己加才會用到 |
| `knowledge/aos/kernel.json`、`packs.json` | 複本，下次重抄才有 |
| `kernel/`、`extras/kernel-chain-check`、條文、thinking | 不在活樹裡用 |

沒有動 `proto8/cmd`、`proto8/py`、被指令直接 import 的 `lib/agent/*.py`：沒有「存檔即生效」的項目。

