# linux 使用者是一個可以互動的對象：初步調查——linux 的事實、對到 aos 現況、五個念頭各自的讀法與後果（11-12 晚家機，只調查、沒施工、沒出設計）

← [2026-11-12](README.md)｜前情 [wf-to-aos](wf-to-aos.md)（D4：把人這個 linux user 當 agent、寄信給他）、[no-pid](../05/no-pid/README.md)（11-05 的遠期「一個 agent 一個帳號」，本檔已改成一個帳號一整棵樹）｜鄰居題 `kernel-as-bridge/`（同晚另一位隊長；kernel 是上面與硬體之間的橋）

## 使用者原話（11-12 晚，逐字）

> 「再派一個：關於linux使用者，不管背後是人還是agent，他都是一個可以互動的對象。這個很特別，我第一次跨足這塊。首先是root daemon本身掛在一個使用者底下。然後是一個linux user，他對於linux這個硬體來說，他就是一個proc(不管這個proc背後是誰，反正從linux這邊看過去，他就是一個proc)，他其實跟root daemon是平級的。Hmmm，假如是root user的root daemon呢？或者說，一個linux user他搞不好會說某個root daemon那個proc，就代表他？總之先做初步調查。」

## 一句話

這幾個念頭跟 aos 現況大致合、而且大半是他以前講過的話的延伸；跟 linux 的事實只有一處出入——linux 眼中使用者不是一個行程。

## 最該知道的一個出入

linux 裡「使用者」只是一個號碼（uid），貼在每個行程身上；使用者本身不是一個在跑的東西，linux 不會把它當成一個可以起、停、寄東西過去的單位。一個行程都沒有的使用者照樣存在。

最接近「代表這個使用者的那個行程」的現成東西是 `systemd --user`：linux 的總管替每個使用者起的一隻小總管，一個使用者只有一隻，這個使用者的其他行程都是它的子孫。家機上它是 pid 770，而且設成人不登入它也在。

所以「user 就是一個 proc」得先說是哪一個 proc。四種讀法（[03 § c](linux-user/03-各念頭的讀法與後果.md)）：那隻小總管；純粹一個身分；aos 眼中一個能收信的對象；人自己開的那些沒被任何 daemon 管的行程（殼、Claude Code）。**使用者定了第三種**：aos 眼中一個能收信的對象（見 [§ 使用者細聊](#使用者細聊11-12-晚稍後)）。

## 分檔

| 分檔 | 涵蓋 |
|---|---|
| [01-linux這邊的事實](linux-user/01-linux這邊的事實.md) | 使用者是號碼不是行程；最接近「代表行程」的三樣；行程樹（家機實看）；權限、訊號、上限各照什麼算；root 特別在哪；使用者之間現成的管道 |
| [02-對到aos現況](linux-user/02-對到aos現況.md) | 逐項：aos 怎麼認誰、哪裡已經用到 linux user、哪裡沒有；「帳號」有三種；使用者以前講過的相關原話 |
| [03-各念頭的讀法與後果](linux-user/03-各念頭的讀法與後果.md) | a～e 各自的讀法、走法、後果；人與 agent 同等對待之後；Argon 補的；跨機 |

## 五個念頭：現況與走法

| 念頭 | 現況 | 看得到的走法 |
|---|---|---|
| a. user 是可以互動的對象 | 對人已經成立：人的信箱 `~/.aos/stack/mailbox` 在家目錄，天然一個 user 一個；環境變數就叫 `AOS_LINUX_USER_STACK`；信的 `from` 預設是 `$USER`。對 agent 不成立：agent 不是 linux 帳號 | 地址用家目錄固定路徑（現在；家目錄 700，別的帳號寄不進來）／公共位置按帳號名（像傳統 unix 信）／查表 |
| b. root daemon 掛在一個 user 底下 | 成立：誰起它它就是誰；它能做的事上限就是這個 user 能做的事 | 維持；或登記成 `systemd --user` 的服務，讓它真的掛在「代表這個 user 的行程」底下（不需要 root） |
| c. user 是一個 proc、跟 root daemon 平級 | 跟 linux 事實有出入（見上） | **定**：user＝aos 眼中一個能收信的對象（[§ 使用者細聊](#使用者細聊11-12-晚稍後)） |
| d. root user 的 root daemon | 沒有；但 daemon 替底下的 proc 換帳號的機制已寫好（`limits.user`，daemon 不是 root 就報錯） | **有方向、先不做**：一個帳號一整棵樹；root 的事仍由使用者親手做（自己 `sudo -u 帳號 …` 起那個帳號的 root daemon）。常駐拿著 root 的小 daemon（早期那支小輔助程式、它本身也可以當 agent）先不做，等哪天要讓 agent 自己開別的帳號的樹再說（[§ 續：念頭 d](#續念頭-droot-user-的-root-daemon)、[§ 續：root 小 daemon 先不做](#續root-小-daemon-先不做)） |
| e. 某個 root daemon 代表這個 user | 沒有；一個 user 現在可以有很多棵樹，寄給 user 的信跟任何 daemon 無關 | **不需要**（使用者定，[§ 使用者細聊](#使用者細聊11-12-晚稍後)） |

## 初步結論

**現在就已經成立、只是沒這樣說過的**：

- 人這個 linux user 是一個能收信的對象（信箱在家目錄、名字用 `$USER`）。
- root daemon 屬於某一個 linux user。
- 「linux 那邊的身分、權限全歸 daemon 那層」（名詞表）；daemon 表上已經有換帳號那一格。

**差一小步的**（不需要 root、不動身分）：

- 讓 root daemon 真的掛在 linux 替這個 user 起的小總管底下（`systemd --user` 的服務），順便拿到開機自動起、死了重起、整棵樹的總量上限。
- 人收信的兩個洞（讀了就從清單消失、不會被通知）。
- 主 session 的身分（它現在是以人的 uid 做事的樹外行程）。

**要動到身分與權限這層才成立的**（要 root，至少一次）：

- agent 也是 linux user（使用者定一個帳號一整棵樹）——這之後「不管背後是人還是 agent」才是 linux 也認的事實。
- 跨帳號寄信（現成的只有問腦信箱那一套，agent 之間的信箱沒有）。
- 冒用身分擋得住（現在同一個 uid，任何 agent 都能往人的信箱放信、替人回信）。
- root user 的 root daemon。

## 最要緊的邊緣狀況

1. **現在整套是同一個 uid**：agent 之間、agent 與人之間在 linux 眼中沒有界線。分帳號之後，現在靠「大家都讀寫得到」在跑的每一樣（共用的 lib、工作區、daemon 的表、彼此的信箱）都要重新決定歸誰。
2. **一個 user 很多棵樹**：試驗場、測試臨時起的、以後正式的。不指定哪一棵代表 user（念頭 e 不需要）；寄給 user 的信跟任何 daemon 無關，哪棵樹掛了都不影響寄到 user。
3. **人會多開**：好幾個終端機、好幾個 Claude Code 讀同一個信箱，誰先讀誰拿走。
4. **root daemon 是 root 時**，任何寫得進它信箱或表的人就等於拿到整台機器；這跟現在「root 的事由使用者親手做」的做法方向相反。
5. **uid 與帳號名只在一台機器裡有意義**：兩台機器的同名帳號對 linux 是兩個人；反過來一台機器上兩個帳號可以是同一個人。

## 跟 kernel-as-bridge 怎麼接

那一題說「root daemon 的硬體是 linux」，它的邊緣狀況寫了「嚴不嚴格 aos 自己說了不算，linux 說了才算……真要擋住靠 linux 帳號」「起 proc 的那一層負責套帳號與沙箱」。本題是它的「linux 那一側長什麼樣」：

- linux 這個硬體給的東西裡，那一題列了行程、訊號、檔案、上限；**身分（uid）是同一張清單上還沒展開的一項**，本題把它展開。
- 照那一題的層次，人自己開的行程與 root daemon 都是「硬體是 linux」的東西（讀法四的「平級」）；使用者定的是讀法三，那個讀法下的「平級」見 [§ 使用者細聊](#使用者細聊11-12-晚稍後)的頂層推論。
- 「root user 的 root daemon」照那一題的說法就是在現在的根上面再加一層：linux → root 帳號的那台 → 各帳號的 root daemon → agent；每往下一層，上一層替下一層套好帳號與上限。
- 那一題說比喻在最上面（agent 對 subagent）開始不貼；本題發現**最下面也有一處不貼**：linux 與 root daemon 之間其實還夾著 `systemd --user` 與 user slice，那是 linux 自己「一個使用者一棵樹」的做法。

兩題各寫各的檔；本題沒改它的檔。它的入口檔寫本題時還沒出現，所以上面只寫夾名、沒連結。

## 可以先想的問題（只列問題）

（「本體是資料夾還是行程」「代表要哪幾樣」「一個帳號對一隻 agent 還是一整棵樹」三題已由 [§ 使用者細聊](#使用者細聊11-12-晚稍後) 收掉：最後一題是一整棵樹。）

（「人開著 Claude Code 做事時算樹外還是樹內」也已收掉：不是問題，見 [§ 續：C-64 以今晚為準](#續c-64-以今晚為準)。目前沒有待想的問題。）

**root 權限放哪一格**：目前由使用者親手拿著——一個帳號一整棵樹，要起某帳號的樹就自己 `sudo -u 帳號 …` 起那個帳號的 root daemon；常駐拿著 root 的小 daemon 先不做（[§ 續：root 小 daemon 先不做](#續root-小-daemon-先不做)）。帳號誰建、跨帳號寄信的資料夾權限未定。

## 想親手玩的話（不需要 root）

先看「代表你的那個行程」與你底下現在有什麼（純看）：

```sh
loginctl user-status          # 你這個使用者：那隻小總管、它底下一格一格的行程
ps -o user,pid,ppid,cmd -u "$USER" --forest | less    # 行程樹；找 aos-daemon 看它的上一層是誰
```

再試「在自己這一格底下圈一小格、設上限」——這就是以後 root daemon 掛在你底下時能拿到的東西（家機實測過，結束碼 137＝超過 64MB 被 linux 殺掉；它只開一個臨時的小格，跑完就沒了）：

```sh
systemd-run --user --scope -q -p MemoryMax=64M -p MemorySwapMax=0 \
  python3 -c 'x=bytearray(300*1024*1024); print("survived")'; echo "exit $?"
```

## Argon

已照 [aos-teams/05](../../../../wf/workflows/dispatch/aos-teams/05-同機session與Argon.md) 的指令送出原話＋初步整理，有回。它的看法與隊長同不同意，逐條在 [03 § Argon 補的](linux-user/03-各念頭的讀法與後果.md)；併進來的有：c 的讀法四、d 的「root 帳號那台是各帳號 daemon 的上一層」、人會多開、問題 1、3、4。它有一處事實說錯（說信讀完會留在 `cur/`；現在預設是讀完就刪）。提示與回覆全文只在當晚 session 的 scratchpad，沒進 repo。

（11-12 收工補）提示與回覆原文已存進 repo：[linux-user/Argon回覆](linux-user/Argon回覆.md)。

## 沒查的、未定的

- 公司 WSL 有沒有 `systemd --user`、linger、能不能建帳號與用 root。
- `limits.user` 有沒有在真 root 下跑過（這次沒找到紀錄）。
- aos-mailbox 的 `read`／`send` 在跨帳號的資料夾權限下能不能用。
- 家機有沒有在送傳統 unix 信的程式。
- 念頭 c、e 已定、d 有方向（root 小 daemon 先不做）（[§ 使用者細聊](#使用者細聊11-12-晚稍後)）；a、b 沒有決定，本檔沒有代定。

使用者：「linux user要等等。」（11-12 晚）——同晚稍後回來細聊，見下節。

## 使用者細聊（11-12 晚稍後）

頂層先問「user 是一個 proc」是哪一個 proc（四種讀法：小總管 `systemd --user`／純身分／aos 眼中一個能收信的對象／人自己開的、沒被 daemon 管的行程），本體是資料夾還是一隻活著的行程。使用者（逐字）：

> 「user是哪個proc...對，就是aos眼中一個能收信的對象。」

頂層接著問：照這讀法，「某個 root daemon 那個 proc 就代表他」還需不需要（頂層偏不需要：信箱就是代表，一個 user 可有很多棵樹、不必指定哪棵）。使用者（逐字）：

> 「就是說，aos-post是一種IPC手段，而只要這個手段能聯絡上的，那自然是proc。　然後那個讀法不需要了」

（前半「aos-post……能聯絡上的，那自然是proc」同晚收回，見 [§ 續：aos-post 那句收回](#續aos-post-那句收回)；後半「那個讀法不需要了」照留。）

**決定**：

- linux user＝aos 眼中一個能收信的對象（讀法三）。
- 「某個 root daemon 代表這個 user」不需要了（念頭 e 結案）。

**頂層當場講的推論**（使用者沒逐條確認）：

- 本體是信箱那個資料夾，人不在線也存在。
- 「不管背後是人還是 agent」因此現在就成立，agent 不必先變成 linux 帳號。
- 跟 root daemon「平級」＝兩邊都是可以寄過去的對象。

### 續：念頭 d（root user 的 root daemon）

頂層問念頭 d 現在聊還是等等。使用者（逐字）：

> 「emmm，我這邊簡單說一下，我記得在早期，那時候有想過，讓某個proc可以切換uid，這樣可以最大程度利用linux權限體系。那時候的方案是弄一支小的輔助程式，必須使用root權限跑他，他就持續跑着，接收請求，把某個proc用指定的uid跑起來。一些細節我忘了。現在看來，或許可以作爲daemon?kernel？」

頂層回（頂層的話）：照同晚「手／門」（[kernel-as-bridge 06](kernel-as-bridge/06-細聊-手與門.md)），兩個都是、主要是 daemon——起 proc 是 daemon 的活，daemon 表上已有換帳號那格（`limits.user`，daemon 不是 root 會報錯），所以那支小輔助程式就是一台用 root 跑的很小的 daemon；「接收請求時判斷誰可以要哪個 uid」是門。層次：linux → root 帳號的小 daemon → 各帳號的 root daemon → agent。由使用者親手用 sudo 起，agent 只能寄信請它起東西。接著問：它底下起的是一個帳號一整棵樹，還是一個帳號一隻 agent？使用者（逐字）：

> 「一個帳號一整棵樹。然後這個root daemon本身也可以作爲agent，畢竟他有body」

頂層問「作為 agent」是只照表做事、還是有腦（LLM）自己決定（後者＝一顆有 root 的腦，被信騙到就等於交出整台機器）。使用者（逐字）：

> 「不，這個不用細究，反正就是root daemon也可以有不同版本，可能某個版本他就是合並了loop fsm agent。」

**決定**：

- 早期那支「用 root 跑、持續跑著、接請求、把某個 proc 用指定 uid 跑起來」的小輔助程式，要做的話可以做成 daemon：使用者以問句「或許可以作爲daemon?kernel？」提出，頂層答「手是 daemon、門是 kernel，主要是 daemon」，使用者沒反對、接著往下答（不是他明確裁定）。同晚定先不做，見 [§ 續：root 小 daemon 先不做](#續root-小-daemon-先不做)。
- 一個帳號一整棵樹。
- 這台 root daemon 本身也可以當 agent（它有 body）；root daemon 可以有不同版本，某個版本可以是合併了 loop fsm agent 的；有沒有腦、腦能做到哪「不用細究」。

**頂層講過、使用者沒逐條確認的**：誰寄得進它的信箱就等於拿到整台機器，所以門要嚴、表要小；它不是熱路徑（只起各帳號的 root daemon）。

**仍未定**（不代定、只列）：帳號誰建；跨帳號寄信的資料夾權限。root 小 daemon 先不做（下面「續」），門怎麼守等要做時再說。

### 續：aos-post 那句收回

頂層問：「aos-post 聯絡得上的就是 proc」跟 C-80（所有 proc 都有 daemon 管）衝突，聽誰的？擺了甲（C-80 補人是例外）、乙（以新句為準）、丙（以 C-80 為準、人不叫 proc）。使用者（逐字）：

> 「今晚的說法拿掉。這是aos-post的特性，就這樣」

**決定**：

- 「aos-post 聯絡得上的自然是 proc」這個說法拿掉；aos-post 寄得到有箱子的東西，是 aos-post 自己的特性，不拿來定義 proc。
- C-80 照舊，沒有衝突了。
- 「linux user＝aos 眼中一個能收信的對象」「某個 root daemon 代表他不需要」沒被收回，照留。

### 續：root 小 daemon 先不做

頂層解釋：aos-sandbox 本來就會換 uid（設定的 `user` 那格，叫它的人要是 root），所以「root 權限由誰拿著」分兩種——使用者親手起（一個帳號一整棵樹、很少起，自己 `sudo -u 帳號 …` 起那個帳號的 root daemon 即可，不需要常駐的 root 小 daemon；這條路頂層沒實測、照 linux 常理講的）；agent 自己要求起（才需要常駐拿著 root 的小 daemon）。頂層建議先不做。使用者（逐字；「這個程式」＝aos-sandbox）：

> 「我對這個程式沒有印象。既然有了這個程式，那還需要我們先前提的換uid那個嗎？既然環境做不到，那這個程式就該報錯」

> 「可以，root小daemon先不做」

（前一句後半「既然環境做不到，那這個程式就該報錯」是在答沙箱那題，見 [metainfo-views § 使用者裁定](metainfo-views.md#使用者裁定11-12-晚)。）

**決定**：

- root 小 daemon 先不做；等哪天要讓 agent 自己開別的帳號的樹再說。
- root 的事仍由使用者親手做（一個帳號一整棵樹，使用者自己用 sudo 起那個帳號的 root daemon）。

### 續：C-64 以今晚為準

頂層問：C-64 以前寫遠期「一個 agent 一個帳號」，今晚定的是「一個帳號一整棵樹」，以今晚為準還是兩個都留？使用者（逐字）：

> 「以今晚爲準。」

**決定**：C-64 的遠期改成「一個帳號一整棵樹」（已改：[C-64](../../../docs/CONCEPTS/01-設計理念/05-布局成長與檔案權限.md)、[條號表](../../../docs/CONCEPTS/附錄3-條號表/01-條號-檔.md)）。

頂層說剩一小題「你開著 Claude Code 做事時，你的行程算樹外還是樹內」，建議留到明天跟主 session 接 aos 一起談。使用者（逐字）：

> 「這個問題...不是問題，我開claude code做事，如果這個是claude code eca，那一切都被收在claude code eca中，對於其他proc來說，他們面對的就是這個eca proc。」

**決定**：「人的行程算樹外還是樹內」不是問題、結案——人開的 Claude Code 若是 claude code eca，一切都收在那隻 eca 裡，其他 proc 面對的就是這隻 eca proc。

### 跟現況的出入

**事實（讀程式＋暫存目錄實跑確認）**：

- `aos-post` 寄得到人的信箱。人的信箱 `<stack>/mailbox/`（stack＝`-s`＞`$AOS_LINUX_USER_STACK`＞`~/.aos/stack`）就是一個 aos-post 箱子（`tmp/ new/ cur/`）；`aos-mailbox` 不是另一條路，它的 send／read 都是去叫 `aos-post` 命令列（`proto8/cmd/aos-mailbox/aos_mailbox/__init__.py` 的 `_post`）。實跑：空目錄當人的 stack，`aos-mailbox where` 建出箱子，直接 `aos-post send <箱子>` 退 0，`aos-mailbox peek`／`read` 讀得到；body 不照 inbox 格式（例如只寄一個字串）也收得進，peek 那幾欄印 `?`。
- 寄給人只能用路徑：`aos-mailbox send --to 名字` 只查 daemon 表，人不在任何表上；要寄給人得 `--box <人的信箱路徑>`（給腦的 `mailbox_send` 的 `box` 同理）。用路徑寄不替人建箱（`MailboxMissing`），人的箱子要他自己跑過 `aos-mailbox where` 或 `send`（寄信時替寄件人建自己的箱子，好讓對方回信）才有。
- `aos-post send` 要求 `tmp/`、`new/` 對寄件人可寫（N-16）；現在整套同一個 uid 所以都寄得進，分帳號後別的帳號寄不進家目錄裡的信箱（上面「邊緣狀況 1」）。

**條文（只列、沒改）**：

- **C-80、C-75：說法收回後已無衝突**。C-80（[03-基礎設施/02](../../../docs/CONCEPTS/03-基礎設施/02-資料夾程式-工作區與-stack.md)）「所有proc都有daemon管」、C-75（[03-基礎設施/01-續-C-75](../../../docs/CONCEPTS/03-基礎設施/01-續-C-75.md)）與[名詞表](../../../docs/CONCEPTS/附錄1-名詞.md) proc 列「會跑、跟 Linux 同字同義」照舊；aos-post 寄得到人的信箱只是 aos-post 的特性，不讓人的信箱變成 proc（[§ 續：aos-post 那句收回](#續aos-post-那句收回)）。
- **念頭 d 那段帶出的出入**：C-64（[01-設計理念/05](../../../docs/CONCEPTS/01-設計理念/05-布局成長與檔案權限.md)）遠期的說法已照今晚改成「一個帳號一整棵樹」（[§ 續：C-64 以今晚為準](#續c-64-以今晚為準)），無出入；[名詞表](../../../docs/CONCEPTS/附錄1-名詞.md) daemon 列「根 daemon……由使用者顧……aos 不做根的根」，root 帳號的小 daemon 正是各帳號根 daemon 的上一層——既然先不做（[§ 續：root 小 daemon 先不做](#續root-小-daemon-先不做)），目前無出入；同列「最基礎的 kernel（來者不拒）」跟頂層說的「門要嚴」——照手／門分開看可以不衝突，列著。
- **對得上的**：N-16（[05-N-16](../../../docs/NORMS/05-基礎設施-窗/05-N-16.md)）「aos-post＝IPC 的語法糖、基底工具，跟 aos proc 的關聯不深」、C-75 的「不要去與aos-post耦合太深」（跟「這是aos-post的特性」同向）；P-48「agent 跟 agent（含把自己當一隻 agent 的人）互相寄信」；N-16「位置由擁有者定、不強制在 `$AOS_STACK`」；N-28「沒掛 daemon＝Linux 管」（講的是直接 `aos-exec` 跑的東西，沒說它不是 proc）。
