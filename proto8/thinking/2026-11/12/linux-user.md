# linux 使用者是一個可以互動的對象：初步調查——linux 的事實、對到 aos 現況、五個念頭各自的讀法與後果（11-12 晚家機，只調查、沒施工、沒出設計）

← [2026-11-12](README.md)｜前情 [wf-to-aos](wf-to-aos.md)（D4：把人這個 linux user 當 agent、寄信給他）、[no-pid](../05/no-pid/README.md)（遠期一個 agent 一個帳號）｜鄰居題 `kernel-as-bridge/`（同晚另一位隊長；kernel 是上面與硬體之間的橋）

## 使用者原話（11-12 晚，逐字）

> 「再派一個：關於linux使用者，不管背後是人還是agent，他都是一個可以互動的對象。這個很特別，我第一次跨足這塊。首先是root daemon本身掛在一個使用者底下。然後是一個linux user，他對於linux這個硬體來說，他就是一個proc(不管這個proc背後是誰，反正從linux這邊看過去，他就是一個proc)，他其實跟root daemon是平級的。Hmmm，假如是root user的root daemon呢？或者說，一個linux user他搞不好會說某個root daemon那個proc，就代表他？總之先做初步調查。」

## 一句話

這幾個念頭跟 aos 現況大致合、而且大半是他以前講過的話的延伸；跟 linux 的事實只有一處出入——linux 眼中使用者不是一個行程。

## 最該知道的一個出入

linux 裡「使用者」只是一個號碼（uid），貼在每個行程身上；使用者本身不是一個在跑的東西，linux 不會把它當成一個可以起、停、寄東西過去的單位。一個行程都沒有的使用者照樣存在。

最接近「代表這個使用者的那個行程」的現成東西是 `systemd --user`：linux 的總管替每個使用者起的一隻小總管，一個使用者只有一隻，這個使用者的其他行程都是它的子孫。家機上它是 pid 770，而且設成人不登入它也在。

所以「user 就是一個 proc」要成立，得先說是哪一個 proc。看得到四種讀法（[03 § c](linux-user/03-各念頭的讀法與後果.md)）：那隻小總管；純粹一個身分；aos 眼中一個能收信的對象；或人自己開的那些沒被任何 daemon 管的行程（殼、Claude Code）。

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
| c. user 是一個 proc、跟 root daemon 平級 | 跟 linux 事實有出入（見上） | 四種讀法；其中兩種能讓 b 與 c 同時對：「行程樹上在底下、角色上同型（都是一棵監管樹的根）」，或「人開的行程與 root daemon 都直接踩在 linux 上、都沒有 aos 的上一層」 |
| d. root user 的 root daemon | 沒有；但 daemon 替底下的 proc 換帳號的機制已寫好（`limits.user`，daemon 不是 root 就報錯） | 不放 root（帳號由使用者親手建）／root 只放一支小程式（11-05 說過的、沙箱線現成的形）／一台很小的 root daemon 只管換帳號起下一層／整棵樹的根就是 root |
| e. 某個 root daemon 代表這個 user | 沒有；一個 user 現在可以有很多棵樹，寄給 user 的信跟任何 daemon 無關 | 「代表」分收信、額度、身分三種意思，可以只要一兩種；代表可以是一台指定的 daemon，也可以就是 `~/.aos/stack` 這個資料夾（現況） |

## 初步結論

**現在就已經成立、只是沒這樣說過的**：

- 人這個 linux user 是一個能收信的對象（信箱在家目錄、名字用 `$USER`）。
- root daemon 屬於某一個 linux user。
- 「linux 那邊的身分、權限全歸 daemon 那層」（名詞表）；daemon 表上已經有換帳號那一格。

**差一小步的**（不需要 root、不動身分）：

- 讓 root daemon 真的掛在代表這個 user 的行程底下（`systemd --user` 的服務），順便拿到開機自動起、死了重起、整棵樹的總量上限。
- 人收信的兩個洞（讀了就從清單消失、不會被通知）。
- 指定「這個 user 的那一棵樹／那一個本家」（現在沒有這個概念）。
- 主 session 的身分（它現在是以人的 uid 做事的樹外行程）。

**要動到身分與權限這層才成立的**（要 root，至少一次）：

- agent 也是 linux user（一個 agent 一個帳號）——這之後「不管背後是人還是 agent」才是 linux 也認的事實。
- 跨帳號寄信（現成的只有問腦信箱那一套，agent 之間的信箱沒有）。
- 冒用身分擋得住（現在同一個 uid，任何 agent 都能往人的信箱放信、替人回信）。
- root user 的 root daemon。

## 最要緊的邊緣狀況

1. **現在整套是同一個 uid**：agent 之間、agent 與人之間在 linux 眼中沒有界線。分帳號之後，現在靠「大家都讀寫得到」在跑的每一樣（共用的 lib、工作區、daemon 的表、彼此的信箱）都要重新決定歸誰。
2. **一個 user 很多棵樹**：試驗場、測試臨時起的、以後正式的。「代表這個 user」要嘛指定一棵，要嘛讓資料夾當代表；綁在行程上的話，它掛了人就在 aos 眼中失聯，雖然人還坐在鍵盤前。
3. **人會多開**：好幾個終端機、好幾個 Claude Code 讀同一個信箱，誰先讀誰拿走。
4. **root daemon 是 root 時**，任何寫得進它信箱或表的人就等於拿到整台機器；這跟現在「root 的事由使用者親手做」的做法方向相反。
5. **uid 與帳號名只在一台機器裡有意義**：兩台機器的同名帳號對 linux 是兩個人；反過來一台機器上兩個帳號可以是同一個人。

## 跟 kernel-as-bridge 怎麼接

那一題說「root daemon 的硬體是 linux」，它的邊緣狀況寫了「嚴不嚴格 aos 自己說了不算，linux 說了才算……真要擋住靠 linux 帳號」「起 proc 的那一層負責套帳號與沙箱」。本題是它的「linux 那一側長什麼樣」：

- linux 這個硬體給的東西裡，那一題列了行程、訊號、檔案、上限；**身分（uid）是同一張清單上還沒展開的一項**，本題把它展開。
- 照那一題的層次，人自己開的行程與 root daemon 都是「硬體是 linux」的東西，這給了「平級」一個說得通的位置（讀法四）。
- 「root user 的 root daemon」照那一題的說法就是在現在的根上面再加一層：linux → root 帳號的那台 → 各帳號的 root daemon → agent；每往下一層，上一層替下一層套好帳號與上限。
- 那一題說比喻在最上面（agent 對 subagent）開始不貼；本題發現**最下面也有一處不貼**：linux 與 root daemon 之間其實還夾著 `systemd --user` 與 user slice，那是 linux 自己「一個使用者一棵樹」的做法。

兩題各寫各的檔；本題沒改它的檔。它的入口檔寫本題時還沒出現，所以上面只寫夾名、沒連結。

## 可以先想的問題（只列問題）

1. 「一個 linux user」在 aos 裡的本體是 `~/.aos/stack` 那個資料夾，還是某一隻活著的行程？（Argon 提的問法；資料夾的話現在就有了，行程的話才需要「代表」。）
2. 「代表」要的是哪幾樣：收信的地址、資源額度、還是身分？
3. 人開著 Claude Code 做事時，人的行程算在樹外（跟 root daemon 當鄰居、只靠信箱往來）還是樹內（某台 daemon 表上的一列）？
4. 給 agent 一個 linux 帳號時，那個帳號對應一隻 agent，還是一整棵樹（帳號裡有自己的 root daemon、底下還有子 agent）？

**方向題**（原則推不出、只有他能定）：root 權限放哪一格——完全不放／只放一支小程式／一台 root 身分的 daemon。這題同時決定「一個 agent 一個帳號」什麼時候能成立，也跟現在「root 的事由使用者親手做」的做法有衝突，衝突在 [03 § d](linux-user/03-各念頭的讀法與後果.md)。

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
- 念頭 a～e 都還沒有決定；本檔沒有代定。
