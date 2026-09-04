# fuse-host：aos 寄生在一個 FUSE 行程裡

← [top-to-bottom/01-top](top-to-bottom/01-top.md)｜[ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

2026-09-03 使用者提出「daemon 可以是一個支援 FUSE 的行程，整棵 aos 資料夾樹寄生在裡面」。
**本檔無裁決**，全部是 AI 觀察，使用者可以否決；**不排進 OS 第一塊**——那件事已裁
「先停下設計、去用現有的東西玩」（[os-metrics-and-resources §九](os-metrics-and-resources.md#九停下腳步先去用現有的東西玩使用者裁決2026-09-03)），本檔只是先記下這個念頭。

## 使用者原話（2026-09-03）

> 我突然想到，目前我們都是對資料夾做處理，那假如說，我們實現了呃，我記得那叫做檔案協議？
> 反正就是對某個行程可以做檔案操作

> 你提的想法也都不錯，但我其實想的是，寫一個支援FUSE的程式，可能用lua，然後讓這個程式跑
> 起來，他的這個跑起來的行程，就是我們的aos可以寄生的地方

## AI 觀察（非裁決，可否決）

### a. 名字對照

使用者想的那條「對某個行程做檔案操作」的協議，最準的名字是 **Plan 9**（貝爾實驗室做的
一個作業系統）的「**什麼都是檔案**」哲學，它靠的協議叫 **9P**——一個行程把自己整個攤成
一棵檔案樹給別人讀寫，讀寫的其實不是磁碟，是在跟那支程式對話。

Linux 上留下的殘影是兩個東西：**`/proc`**（用檔案的樣子看行程內部狀態，例如
`/proc/1/status`）與 **FUSE**（Filesystem in Userspace，白話：一支普通的使用者程式，跟
核心講好之後就能把自己**裝成**一個資料夾，你 `ls`、`cat`、寫檔案，動作全部轉成呼叫這支
程式，它自己決定怎麼回應）。

### b. 使用者的版本比「外面有個行程裝成資料夾給 aos 開」更進一步

不是 aos 之外另外有個裝成資料夾的行程供它讀；而是**整棵 aos 的樹**（`.aos/`、inbox、
`out/`……）**本身就住在一個 FUSE 行程裡**，是這個宿主行程「演」出來的。aos 寄生其中：
宿主負責把樹端出來，aos 的邏輯變成「有人讀寫這棵樹的時候該做什麼」。

### c. 這改的不是概念、是兩個格子的底座

- **daemon 那格**——先前「daemon 盯著桌子」與「daemon 也可看成一個資料夾」
  （[top-to-bottom/01-top](top-to-bottom/01-top.md#daemon-自己也可以看成一個資料夾所以頂層不用開特例)）
  變成字面事實：**daemon 就是桌子本身**。`deliver` 往 inbox 寫檔的那個動作，直接落在
  宿主手上處理，不必再輪詢磁碟去發現它。
- **資料夾那格**——資料夾從「磁碟上真的有一個目錄」變成「宿主演出來的目錄」。上層的
  結論全部不動：`.aos` 還是 car（[02-folders](top-to-bottom/02-folders.md)）、父層點名
  才開子資料夾、兩層互不相關（inst 鏈 vs 資料夾樹，
  [nested-eval-sugar](nested-eval-sugar.md)）。

### d. 三個提醒（對應既定的三個目標指標）

指標見 [os-metrics-and-resources §三](os-metrics-and-resources.md)：金錢（token）／
可預測性／人類可理解性，**可預測性最優先**。

1. **時間粒度會打架。** aos 的時間本來就粗、而且允許不規則，一回合一回合走
   （[os-metrics-and-resources §五](os-metrics-and-resources.md#五使用者口述為什麼可以理想地抽象)）；
   FUSE 卻是每一次系統呼叫就敲一下，極細。宿主收到讀寫應該**只負責記下來**，回合仍照
   原本的節奏推進——否則每一次 `ls` 都會把可預測性打碎成細沙。
2. **宿主死了，樹還在不在？** 如果整棵樹只活在宿主的記憶體裡，宿主一掛全部消失，人也
   沒辦法隨時打開資料夾接手。宿主底下應該仍然是**真正的目錄**，宿主只是蓋在上面的一層
   （攔截與加值），這樣宿主不在的時候，人仍然看得到穩態。
3. **Lua 不該變成第二種腳本語言。** 已經裁定 `.aos` 裡面是 POSIX 呼叫 ＋ aos 子命令
   （[nested-eval-sugar](nested-eval-sugar.md)），不是別的腳本語言。Lua 是宿主本身用來
   實作 FUSE 的語言，**不進 `.aos`**，否則機器層與行程層又纏在一起。

### e. 現實面（實作時再看，現在不動）

WSL2 與 Manjaro 都有 FUSE，Windows 原生沒有；Lua 的 FUSE 綁定偏老舊，實作時可能要換
別的語言寫宿主。

### f. 與現有程式的關係

今天的 `core/loop` 是**輪詢磁碟**去發現變化。FUSE 宿主有兩種當法：**只做「攔截＋記錄」**、
讓 loop 照舊跑（宿主只是省掉輪詢的那一刻），或者**整個取代 loop**、自己就是引擎。哪一種
未定。

> **2026-09-03 使用者追問「不懂所謂的攔截紀錄、馬上回應是啥意思」**——續篇
> [fuse-host-doorman](fuse-host-doorman.md) 用「門房還是廚師」的比喻展開這兩種當法，
> **仍無裁決**；使用者回應「daemon 可以更漂亮」，方向認同、未選邊。**同日使用者說「都
> 順便記下來吧」**，接著問實作面兩題（會不會麻煩、有沒有開源庫；跟 tmpfs 差在哪）——
> 另存 [fuse-host-impl](fuse-host-impl.md)（**仍無裁決**）。

## 相關

- [top-to-bottom/01-top](top-to-bottom/01-top.md)——daemon＝REPL、daemon 也可看成一個
  資料夾，本檔就是接著這條往下想
- [top-to-bottom/02-folders](top-to-bottom/02-folders.md)——`.aos`＝car、資料夾＝operative，
  本檔確認這些結論不因宿主而變
- [nested-eval-sugar](nested-eval-sugar.md)——inst 層＝POSIX＋aos 子命令、兩層互不相關
  （Lua 該留在哪一層的依據）
- [os-metrics-and-resources](os-metrics-and-resources.md)——三個指標與「先去玩」的裁決
- [play-watchlist](play-watchlist.md)——玩的時候順手核對的觀察清單，本檔性質與它相近
- [fuse-host-doorman](fuse-host-doorman.md)——續篇：門房還是廚師，攔截＋記錄 vs 整個取代
  loop 的具體展開
- [fuse-host-impl](fuse-host-impl.md)——續篇：實作面備忘，會不會麻煩、有沒有開源庫、跟
  tmpfs 差在哪
- [cpu-to-os-gaps](cpu-to-os-gaps.json)——`G06`（行程抽象）／`G14`（載入器）：宿主把 daemon 從「盯著桌子」
  變成「桌子本身」，是這格的一種新形狀
