# 2026-11-02 daemon 的環境變數：`AOS_DAEMON` 指 stack 不對勁——三個名字（定義／stack／ws）還是一個名字（溝通入口）

← [thinking README](README.md)｜月份表 [2026-11](months/2026-11.md)｜出發點：[11-02 試驗場 daemon](2026-11-02-playground-daemon.md)（指令要 `export AOS_DAEMON=$PWD/.stack`）｜前情：[11-01 環境變數盤點](2026-11-01-playground-bob/01-環境變數盤點.md)、[要使用者裁的問題](2026-11-01-playground-bob/02-環境變數要使用者裁的問題.md)（第 1 題「hub 型不用改」）、[10-30 map-review 第 10 點](2026-10-30-map-review/01-使用者原文.md#決定10-30)（`AOS_DAEMON` 的來歷）｜條文：[N-63 hub 型變數、N-64 父子交代、N-57 六個變數、N-55](../docs/NORMS/10-基礎設施-定義與工作區.md)、[N-28 daemon、N-54](../docs/NORMS/04-基礎設施-loop與daemon.md)、[C-54 命名、C-69](../docs/CONCEPTS/01-設計理念.md)、[C-65／C-67 stack 與工作區](../docs/CONCEPTS/03-基礎設施.md)、[P-39](../docs/CONVENTION/06-巢狀.md)｜程式：[aos-daemon-ctl](../bin/README.md)、[aos-eca-hub](../extras/eca_hub/README.md)、[aos-daemon](../impls/aos-daemon/README.md)

本檔只記使用者原文（逐字）、決定、fable 照原則定的規劃（可翻案）、要使用者看的衝突與方向題（[user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。**只規劃，程式與條文都還沒動**；步驟表在最後。

## 使用者原文（11-02，逐字）

> AOS_DAEMON=$PWD/.stack，原來要指向stack...感覺不太對。最初AOS_DAEMON的作用是啥，我記得就是方便大家透過aos-daemon-ctl進行投遞之類的操作。那大家就應該約定說，AOS_DAEMON_STACK，指向的就是一個正在跑的daemon他的stack，AOS_DAEMON則是一個正在跑的daemon它的定義所在，而AOS_DAEMON_WS就是daemon正在處理的ws的位置。

補一個替代方案（11-02，逐字）：

> 或者說，如果只是要投遞請求或查看東西的話，那這三個都不用，只需要AOS_DAEMON_CTLBOX？幫我想個好名字

再補（11-02，逐字）：

> 投遞、查看、停止...那改叫AOS_DAEMON_WINDOW？

再補（11-02，逐字；**命名先不定**，下面規劃一律用暫名「控制口」指那個變數，候選名只列、不定案）：

> 命名這塊還得再想想。然後aos-exec啟動一個daemon後，daemon是把它運行時候的各種東西都放在stack。我覺得OK。搞不好daemon啟動後也可以吃這個AOS_DAEMON_CTL變數，把相關的東西切開來放在那邊？這樣方便管理權限也說不定。

同一天另一句，只當參考、不延伸成條文（[11-02 cathy](2026-11-02-playground-cathy.md#使用者原文11-02逐字)）：「AOS_CF/CD/CO就像是現在執行到哪個指令，而STACK/WS就是最重要的兩個暫存器。」

## 決定（11-02，使用者）

使用者原文（逐字）：

> 可以明寫，沒寫就默認跟STACK攪在一起

- 衝突 4 定案：daemon 要把對外的東西（信箱、窗）切到控制口，**由 daemon.json 作者明寫**（用 `$env` 指示詞），aos-daemon 程式不內建讀固定變數名。
- **沒寫＝照舊跟 stack 放在一起**。
- 命名仍未定（使用者「命名這塊還得再想想」）；其餘衝突 1～3、方向題 1～2 待使用者。

再一輪（11-02，逐字；頂層重新編號問三題：第 1 題＝控制口變數叫什麼；第 2 題 a／b／c＝下面衝突 1／2／3；第 3 題＝[工人提的三點](#工人提的三點11-02使用者)）：

> 1. 先看看具體會切啥出去。3.a.那就是後續使用者要自己小心。b.自己小心。c.不用測試。2.a.那就不用定這三個名字了...喔我們先等第一題搞定。b.hub以後再說。c.不，最好明講，也就是--daemon-stack，但具體還是等第一題搞定。

- **控制口命名**：先看具體會切出哪些東西再定（頂層另外列給使用者）。
- **衝突 1**：傾向不定三個名字（定義／stack／ws），但等控制口那題定了再說。
- **衝突 2**：hub（N-63「一個 hub 一個變數」）以後再說。
- **衝突 3**：旗標名要明講，傾向 `--daemon-stack`；具體等控制口那題定案。
- 方向題 1～2 仍待使用者。

再一輪（11-02，逐字；頂層先把方案 C 會切出去的列給使用者：信箱 `loops_ctl_mailbox/`、`loops_state.json`、`daemon_state.json`、`daemon_ctl.json`、`loops_ctl.json` 切出，`loops/<名>/` 小格與 `eca_archive` 留 stack，另加 `loops_state` 多一欄 `stack` 補洞）：

> 先不要討論eca-hub。然後就算把STACK整個開出去，或許我們也可以利用檔案權限來阻擋？但那樣比較麻煩就是。不過這還是麻煩，在我們目前來說，因為還在初期，沒有權限問題，所以直接把整個STACK公開出去反而是最方便的。就AOS_DAEMON_STACK吧

> 或者說，反正大家都是走包裝後的aos-daemon-ctl

- **命名定案**：變數叫 `AOS_DAEMON_STACK`，值＝daemon 的 stack（方案 B）。現階段**不切控制口**，整個 stack 公開給外人（理由：還在初期沒有權限問題、大家都走包裝後的 aos-daemon-ctl）；權限以後要時可用檔案權限擋（使用者說較麻煩，先不做）。daemon.json 用 `$env` 明寫切出的能力照舊在（上面已定），只是現在不用。
- **衝突 1 定**：不定三個名字（使用者前一則「那就不用定這三個名字了」）。
- **衝突 3 定**：旗標 `--daemon-stack`（使用者前一則「最好明講，也就是--daemon-stack」）。
- **方向題 1 頂層代定（可翻案）**：舊名 `AOS_DAEMON` 退場——不定三名，就沒有「定義資料夾」那個意思要留。
- **方向題 2**：照 fable 建議先不做，等常駐 bob 用到再說。
- eca-hub 先不討論（它也讀這個變數，實作時跟著改名即可）。

## `AOS_DAEMON` 現況（查清的，不是規劃）

- **來歷**：10-30 使用者看 aos-daemon-ctl 的規劃時說「關於那個aos-daemon-ctl，他應該是要吃環境變數+argv來確定daemon home在哪裡的(要用哪個daemon)。」（[map-review 第 10 點](2026-10-30-map-review/01-使用者原文.md#決定10-30)）。變數名 `AOS_DAEMON`、`--daemon` 蓋過它、**值＝那個 daemon 的 `$AOS_STACK` 資料夾**，三件都是實作隊長照 N-63 代定、條文明寫「可翻案」。使用者原話說的是「daemon home」，沒說是 stack——隊長把 home 落成 stack，因為 aos-daemon-ctl 要碰的三樣東西（信箱 `loops_mailbox/`、名單窗 `loops_state.json`、小格 `<名字>/`）全在 stack 裡。
- **誰讀**：只有兩支——`bin/aos-daemon-ctl`（`daemon_dir()`：`--daemon` ＞ `$AOS_DAEMON`，不是資料夾＝`DaemonMissing`；投信進 `<D>/loops_mailbox/`、`ls` 讀 `<D>/loops_state.json`、`--ws` 的捷徑指到 `<D>/loops/<名字>/`）、`extras/eca_hub/bin/aos-eca-hub`（同一套，多驗 `loops_state.json` 的心跳行程活著；小格 `$AOS_DAEMON/<名字>/`、歸檔 `$AOS_DAEMON/eca_archive/`）。aos-daemon 本體**不讀也不設**它；aos-ai、demo 的程式、lib 都不碰。
- **誰設**：沒有任何程式設；只有使用者自己 `export`（demo/daemon-3 README、eca_hub README、11-02 試驗場指令都是 `export AOS_DAEMON=…/.stack`），或測試（`test_aos_daemon_ctl.py`、`test_eca_hub.py`）。
- **條文**：N-63 10-30 補（實例 `AOS_DAEMON`，「值＝那個 daemon 的 `$AOS_STACK` 資料夾」）、10-30 夜改（拿掉 `AOS_HUB`、「一個 hub 一個變數，這裡的 hub 就是 daemon」）；N-28 10-30 補末句；NORMS.md 總表、附錄 1 條號表、附錄 2 各批出處；bin/README、impls/aos-daemon README、demo/daemon-3 README、eca_hub README；code map 三處。
- **11-01 盤點**歸它「邊界」（hub 型），第 1 題「hub 型算不算必要」使用者答「不用」＝不用改、N-63 不動。所以今天這題**不是**「要不要用環境變數指 daemon」（已裁：hub 型留），是「這個變數的**名字跟它指的東西對不上**」。
- 更早的影子：proto2 的 `AOS_DAEMON_DIR`、舊 playground 的 `AOS_DAEMON_HOME`，都是「daemon 的家」一個資料夾，定義與狀態同住。proto8 把定義（資料夾程式）跟執行中狀態（stack）分開了（C-65），「家」就拆成兩個位置，名字沒跟著拆——這就是今天覺得不對勁的根。

## 規劃（fable，照原則定的細節，可翻案）

兩個方案並列。先講共同的底，再比。

### 共同的底：這些工具真正要碰的是什麼

aos-daemon-ctl 與 aos-eca-hub 要做的三件事，碰的檔全在 **daemon 的 stack** 裡（N-13 窗在 stack、N-28 daemon 的窗接在 `$AOS_STACK` 後面）：投遞＝寫 `loops_mailbox/new/`；查看＝讀 `loops_state.json`（名單）、`state.json`（loop 面）；停＝寫 `ctl.json`。小格也在那（`loops/<名字>/`，11-02 隊長那輪起）。**沒有任何一件要碰 daemon 的定義資料夾或工作區。** 所以不管哪個方案，**工具只需要「那個 daemon 的 stack 在哪」這一個事實**；而這個事實從定義推不出來（stack 放哪是呼叫方的自由，C-67），從工作區也只能猜（`$WS/.stack/` 只是 aos-exec 的預設，N-63 ② 說不猜）。

### 方案 A：三個名字（使用者第一句）

| 名字 | 指什麼 | 怎麼算 | 依據 |
|---|---|---|---|
| `AOS_DAEMON` | 正在跑的 daemon 的**定義**＝它的資料夾（例 `daemons/main/`） | 定義一律是資料夾（C-54 用詞「定義＝一個資料夾（程式）」、N-63 ① 值是資料夾）。daemon 自己算＝設定檔的所在資料夾（`dirname(abs(daemon.json))`；經 aos-exec 起時就等於它拿到的 `AOS_CD`）；`daemon.json#/sub` 一樣取檔所在資料夾 | C-54、N-57（`AOS_CD` 的定義） |
| `AOS_DAEMON_STACK` | 它的 stack（`loops_mailbox/`、`loops_state.json`、`ctl.json`、`loops/<名字>/` 都在這） | ＝daemon 自己的 `$AOS_STACK` | N-28、N-13 |
| `AOS_DAEMON_WS` | 它正在處理的工作區 | ＝daemon 自己的 `$AOS_WS`；daemon 沒有 `AOS_WS`（直接 `aos-daemon daemon.json` 跑、沒經 aos-exec）就不設 | N-55 |

對照使用者的暫存器比喻：對 daemon 這一層，`AOS_DAEMON` ≈ 它的 `AOS_CD`、`AOS_DAEMON_STACK` ≈ 它的 `AOS_STACK`、`AOS_DAEMON_WS` ≈ 它的 `AOS_WS`——三個都是「正在跑的那個 daemon 的事實」，不是旋鈕。

誰設、誰讀：

1. **daemon 自己設給子項**（三個都設，起每個子 loop／exec 子項時跟 `AOS_STACK=小格` 一起 `setenv`）。依據 N-64 ④「上一代要讓下一代找到自己的信箱或窗，用 hub 型變數（N-63）」、N-63 ③ 子 process 預設繼承——daemon 底下的 bob 要再掛一個兄弟、或 eca 實例要知道 daemon 的工作區，就靠這三個，不用另發明機制。巢狀 daemon：內層 daemon 對自己的子項覆寫三個（最近的那個 daemon 贏，跟 `AOS_STACK` 每層自己訂一樣，C-70）。
2. **外面的人（使用者的 shell、demo README、試驗場指令）手動 `export`**，至少設 `AOS_DAEMON_STACK`；另外兩個要用才設。依據 N-63 ②（沒設就報缺什麼、不猜）。
3. **aos-daemon-ctl、aos-eca-hub 只讀 `AOS_DAEMON_STACK`**（旗標 `--stack D` ＞ `$AOS_DAEMON_STACK`；旗標從 `--daemon` 改名，因為「`--daemon` 的值是 stack」正是這次要去掉的混淆；`--stack` 跟 aos-say／aos-mcp 的 `--stack`「要接上哪個 stack」同一個意思）。**只給 `AOS_DAEMON` 或 `AOS_DAEMON_WS`、沒給 stack＝`DaemonMissing`**，錯誤訊息補一句「`AOS_DAEMON` 現在指定義資料夾，要投遞請設 `AOS_DAEMON_STACK`（或 `--stack`）」。不從定義或工作區推 stack（上面「共同的底」）。
4. **錯誤代號維持 `DaemonMissing`**：缺的東西是「那個 daemon」，三個變數描述同一個 hub。N-63 ② 的「`<名字>Missing`」要補半句：一個 hub 可以有幾個面向的變數 `AOS_<名字>_<面向>`，代號仍照 hub 的名字。
5. **不另加「stack 反查定義／工作區」**：`loops_state.json` 要不要多記 daemon 的 `def`／`ws` 讓 `ls` 印出來——現在沒人要，KISS（C-56）不加；要時再加一行。
6. **遷移**：舊的 `AOS_DAEMON`（＝stack）**意義改變**。讀者只有兩支程式、三個測試、十來處文檔與試驗場指令，沒有外部依賴，**直接改、不留相容期**（KISS「寫什麼就做什麼」——不偷偷把「`AOS_DAEMON` 指到一個有 `loops_mailbox/` 的資料夾」當成 stack；10-23 `_exec`→`_entry` 改名也是一次改完）。唯一的緩衝就是第 3 點那句錯誤訊息。

### 方案 B：一個名字（使用者第二句「只要投遞或查看，那三個都不用」）

一個變數指「跟正在跑的 daemon 溝通的入口」。**它要指哪裡才能同時投遞、查看、停？答案：就是 daemon 的 stack 資料夾**——三件事碰的檔已經全在那一個資料夾裡（上面「共同的底」），一個變數指它就全做得到，**佈局一處都不用改**。所以方案 B 的實質是：把今天的 `AOS_DAEMON` **改一個誠實的名字**，意義不變（＝stack），別的什麼都不加。

要不要改佈局、把窗收進 stack 底下一個子資料夾（例 `$AOS_STACK/ctlbox/`）再讓變數指那裡？**不建議**：`ctl.json`／`state.json` 是 aos-loop 那層的窗、位置「接在 `$AOS_STACK` 後面」是 loop 與 daemon 共用的規則（daemon.json 是 loop.json 的超集，N-28），只為 daemon 搬就破壞超集；要搬就牽 aos-loop／aos-daemon C++、所有讀窗的工具（aos-say、aos-listen、aos-eca-hub、aos-mcp）與測試、條文 N-13／N-28；而搬完變數指的還是 stack 底下一個資料夾，比直接指 stack 沒多做到任何事。使用者 11-01「明明現有的機制組合一下就能搞定」——這裡現有機制就夠。

名字候選（C-54：全大寫底線、主題放前面、沿用現有名詞——stack、mailbox／信箱、ctl／手把、state／窗；新縮寫要先進縮寫表）：

| 候選 | 一句理由 | 問題 |
|---|---|---|
| **`AOS_DAEMON_STACK`**（推薦） | 它指的**就是** daemon 的 stack，一字不騙；跟方案 A 的第二個名字同一個，今天選 B、以後要 A 不用再改名；`stack` 是現有名詞、不用進縮寫表 | 字面沒說「拿來溝通」——但 aos 裡「窗都在 stack」（N-13）本來就是常識，aos-say 的 `--stack` 也是這個意思 |
| `AOS_DAEMON_MAILBOX` | 投遞那半很貼（N-16 信箱、`loops_mailbox`） | 查看讀的是 `loops_state.json`、停寫的是 `ctl.json`，都不是信箱；而且 daemon 的信箱資料夾是 `loops_mailbox/`，變數叫 mailbox 卻指它的上一層，會讀錯 |
| `AOS_DAEMON_CTL` | 「控制 daemon 的入口」好懂，aos-daemon-ctl 也叫 ctl | `ctl` 在 aos 裡已經是一個具體的檔（`ctl.json`、`loops_ctl.json`＝手把），變數叫 CTL 卻指整個資料夾，一詞兩義（C-54） |
| `AOS_DAEMON_CTLBOX`（使用者提的） | 「控制箱」把投遞、查看、停三件事包起來，意圖最直白 | 新造詞：`ctlbox` 不在縮寫表、跟 `loops_mailbox`／`ctl.json` 都不是同一個東西；指的位置還是 stack，等於替 stack 取個別名——C-54 一詞一義（10-30 拿掉 `AOS_HUB` 就是這個理由） |
| `AOS_DAEMON_HOME`／`AOS_DAEMON_DIR` | proto2、舊 playground 用過，「家」好記 | 「家」聽起來像定義所在（使用者今天就是要把定義跟 stack 分開），會回到今天的混淆 |
| `AOS_DAEMON_WINDOW`（使用者提的） | 「窗」是 aos 現有名詞（N-13、N-14）：daemon 對外的 `ctl.json`（停）、`state.json`、`loops_state.json`（查看）都真的是窗，三件事裡兩件貼 | **投遞那件不是窗**：N-14 10-29 改口「窗＝只看最新那份的固定檔，鎖、信箱不算窗；信箱歸投遞（N-16）」，而 aos-daemon-ctl 最主要的動作 add／rm 就是往 `loops_mailbox/` 投信。叫 WINDOW 卻拿來投遞，正撞 10-29 使用者自己拍板的分界（「窗可以跟投遞並列」）。細評見下 |

**`AOS_DAEMON_WINDOW` 細評**（使用者問「投遞、查看、停止…那改叫 WINDOW？」）：

- **跟既有「窗」吻合的部分**：查看＝讀 state 窗（`state.json`、`loops_state.json`）、停＝寫 ctl 窗（`ctl.json`）——這兩件正是 N-13「程式內部狀態的外顯」，一個變數說「daemon 的那組窗」在這裡完全對。
- **混淆的部分**：① 投遞不是窗（上面）。10-29 把「窗」收窄成「只有最新那份算數的固定檔」，信箱是「一封一封、每封都算」的投遞，刻意分成兩個詞；變數叫 WINDOW 卻主要拿來投信，等於把 10-29 分開的又黏回去。② aos 裡「窗」是**一個檔**（N-13 每扇窗一個固定檔、名字程式自訂），不是一個資料夾；「`AOS_DAEMON_WINDOW` 指一個資料夾」會讓人以為那是某一扇窗的檔。③ aos-eca-hub 除了窗與信箱還要碰**小格**（`loops/<名字>/`，接 aos-say／aos-listen）跟**歸檔**（`eca_archive/`）——這兩個更不是窗。
- **若硬要「一個變數指 daemon 的那組窗」，佈局怎麼落**：其實今天不改程式就能把窗收在一起——N-28 的窗路徑都是「接在 `$AOS_STACK` 後面」、名字自訂，daemon.json 寫 `"ctl": "win/ctl.json", "state": "win/state.json", "loops_state": "win/loops_state.json", "loops_mailbox": "win/loops_mailbox"` 就全進 `$AOS_STACK/win/`。但接著有三個代價：(1) aos-daemon-ctl／aos-eca-hub 現在認的是「stack 底下的**預設檔名**」，改成「某個資料夾底下的預設檔名」要兩支都改，而且 daemon.json 寫了別的檔名它們就找不到（今天也一樣，只是多一層變數）；(2) 小格與歸檔在 `$AOS_STACK/loops/`、`$AOS_STACK/eca_archive/`，不在窗資料夾裡——eca-hub 仍得知道 stack 在哪，一個變數不夠，又回到要兩個；要把小格也搬進窗資料夾，就是把 11-02 隊長剛搬到 `loops/` 的小格再搬一次、且「小格在窗底下」說不通。(3) 信箱放進叫 window 的資料夾，撞 10-29。**結論：不吻合（三件事裡投遞那件剛好是最常用的、又剛好不是窗），不建議。** 使用者要的「一個名字包住投遞、查看、停止」，aos 裡本來就有一個現成的詞把這三樣（加小格、歸檔）全裝在一起——就是 **stack**。

fable 的推薦（只是推薦，使用者 11-02 第四句說命名還要再想，**沒定**）：變數指 stack 就叫 `AOS_DAEMON_STACK`；若走下面方案 C（切出去）、指的不再是 stack，候選要重列，見方案 C 末段。

### 方案 C：daemon 自己也讀「控制口」，把對外的那部分切出 stack（使用者第四句）

使用者接受「daemon 執行時的東西都放 stack」；新想法是：daemon 起來時讀同一個變數（暫名「控制口」），**給外人碰的那幾樣**放到它指的資料夾，stack 只留內部的，權限好切（外人只能寫信箱、讀 state，碰不到 stack 裡面）。

**1. 哪些算「對外」、哪些留 stack**（判準：這個檔是不是**設計上就要讓 daemon 以外的人讀或寫**；依據 N-13「窗＝程式願意分享給大家的」、N-16 信箱＝給人投的、C-64 權限歸 Linux 檔案層）：

| 放控制口（對外） | 誰碰、怎麼碰 | 留 stack（內部） | 理由 |
|---|---|---|---|
| `loops_mailbox/`（`tmp/`、`new/`、`cur/`） | 外人**寫**（aos-post send 先寫 `tmp/` 再 rename 進 `new/`），daemon 讀、搬 `cur/` | `loops/<名字>/`（子項小格：`loop.json`、`stderr.txt`、子項自己的窗與小格） | 小格是**子項的 stack**（C-70 子程式的 stack 由父訂），不是 daemon 對外的東西；外人要跟某個子項講話走子項自己的窗（aos-say 的 `--stack`） |
| `loops_state.json`（＋分頁 `loops_state_loops/`） | 外人**讀**（ls、eca-hub 的心跳檢查） | `eca_archive/`（eca-hub 的歸檔） | eca-hub 自己的東西，放 daemon 的 stack 是 10-30 的決定，跟對外無關 |
| `state.json`（loop 面的窗） | 外人讀 | daemon 自己的 `trace`、暫存、以後的鎖 | 內部 |
| `ctl.json`（停）；非信箱模式時的 `loops_ctl.json` | 外人**寫**——但只有「管理者」該寫得了 | | 權限上把 ctl 跟信箱分開：信箱群組可寫、ctl 只有擁有者可寫，正好是「誰能投、誰能停」兩種人 |

**2. 沒給變數時放哪**：**照舊全在 stack**（N-28 現行；使用者說「我覺得 OK」）。不猜別的位置（N-63 ②）。

**3. 怎麼落地——先看現有機制夠不夠**（11-01 使用者「明明現有的機制組合一下就能搞定」）：**今天不改 aos-daemon 一行就能切**。daemon.json 的 `ctl`、`state`、`loops_ctl`、`loops_state`、`loops_mailbox` 五個 key 都吃指示詞（`config.cpp resolve_keys`、`daemon.cpp` 對 `loops_*` 的 `aos::resolve`），絕對路徑照寫（impls README `loops_mailbox` 那列）。所以 `daemons/main/daemon.json` 寫

```json
"loops_mailbox": {"$env": "控制口", "$path": "loops_mailbox"},
"loops_state":   {"$env": "控制口", "$path": "loops_state.json"},
"ctl":           {"$env": "控制口", "$path": "ctl.json"},
"state":         {"$env": "控制口", "$path": "state.json"}
```

就是「daemon 吃這個變數、把對外的切到那邊」；不寫＝照舊在 stack。這有三個好處：(a) **不是 aos-daemon 偷讀一個固定名字的環境變數**——是 daemon 定義的作者在 daemon.json 裡明寫要讀哪個變數、放哪幾個檔，跟 `{"$env": "AOS_WS"}` 一樣的寫法（N-45、P-39「要往下傳就拿它的值明給」）；(b) 不給變數時 `$env` 解不開＝指示詞錯、退 1，不會默默退回 stack（N-63 ②、KISS「寫什麼就做什麼」）；(c) 控制口資料夾誰建、權限怎麼設，全在 daemon 外面由起它的人決定（C-67 放哪是呼叫方的自由、C-64 權限歸 Linux）。**要補的只有**：impls README 一段「把對外的窗切出 stack」的範例、demo 一份 daemon.json 示範——條文不用加新機制。

要不要再進一步讓 aos-daemon **內建**讀這個變數（沒寫路徑就自動放控制口）？不建議：那是把一個環境變數當 aos-daemon 的設定旋鈕（11-01 第 3 題裁「這就是濫用」——旋鈕走 argv 或設定檔）；而且 daemon.json 本來就是它的設定檔，再多一條「環境變數也能定位置」就是兩個地方管同一件事。

**4. 外部工具怎麼找到它**：aos-daemon-ctl、aos-eca-hub 讀同一個變數（控制口）→ 在那個資料夾裡用**預設檔名**找 `loops_mailbox/`、`loops_state.json`（跟今天找 `$AOS_DAEMON` 底下一樣，只是資料夾從 stack 換成控制口）。沒切的 daemon，使用者就把控制口設成 stack——**方案 B 是方案 C 的特例**（控制口＝stack）。所以程式面兩個方案改的是同一行：`daemon_dir()` 讀控制口變數。
   - 一個洞：aos-daemon-ctl `add --ws` 會把 `<WS>/.stack` 捷徑指到小格 `<stack>/loops/<名字>/`、eca-hub 要搬小格去歸檔——這兩件要知道 **stack** 在哪，控制口≠stack 時就找不到。補法（照「別多一個變數」）：daemon 把每個子項的小格路徑寫進 `loops_state.json` 那一列（多一欄 `stack`），工具從狀態窗讀、不用知道 daemon 的 stack。C++ 一行＋ctl／eca-hub 改讀那欄；這也是「stack 反查」唯一真的要加的一欄（上面方案 A 第 5 點說不加的，是 daemon 自己的定義／ws，不是這個）。

**5. 跟沙箱身分層的關係**（[10-24 sandbox](2026-10-24-sandbox.md) S14、S17、`setup.sh --mailbox`）：那套已經是「信箱擁有者＝跑 kernel 的人、群組 `aos-run`、2770＋預設 ACL，沙箱裡只綁信箱、`AOS_KERNEL` 指它」。控制口資料夾就是 daemon 版的同一招：擁有者＝跑 daemon 的人；`loops_mailbox/`（含 `tmp/`、`new/`、`cur/`）2770＋同一組 ACL 讓 `aos-run` 投得進；`loops_state.json`、`state.json` 照 umask 644 誰都讀得到；`ctl.json`、`loops_ctl.json` 600 只有擁有者能停；**stack 整個 700**，沙箱裡不綁它。`setup.sh --mailbox` 現在只處理一個 kernel 信箱，要擴成「`--daemon-ctl 控制口`」把這四種權限一次設好（腳本層，不是 aos 程式）。注意 daemon 寫 `loops_state.json` 走原子 rename（N-05），控制口資料夾本身要讓 daemon 可寫、外人只要 r-x。這是方案 C 真正的收益：**沒切的話，信箱在 stack 裡，要讓外人投信就得把 stack 開給他走**，順手看到小格裡的一切。

**6. 跟 11-01「環境變數只在必要時用」的關係**：方案 C 用的變數仍只有一個（控制口），個數跟 B 一樣；它是 hub 型（一個位置、兩層以上要讀：外面的工具與 daemon.json 都讀，中間的 shell 不必懂）——11-01 第 1 題裁「hub 型不用改」。daemon 那邊靠 daemon.json 的 `$env` 明讀、不是程式偷讀，沒踩「環境變數當設定」那條。

**方案 C 的名字**：變數指的不再是 stack，`AOS_DAEMON_STACK` 就不對了；候選要照「外人跟 daemon 來往的那個資料夾」重想（命名使用者說再想，這裡只列）：`AOS_DAEMON_CTL`（使用者暫用；問題同上表——`ctl` 已是 `ctl.json` 那一個檔的名字，一詞兩義）、`AOS_DAEMON_WINDOW`（問題同上——信箱不是窗，而信箱正是最常碰的）、`AOS_DAEMON_BOX`／`AOS_DAEMON_FRONT`（新詞，要進縮寫表／名詞表）、`AOS_DAEMON_PUBLIC`（意思最準：「daemon 公開給外人的那一夾」，但 aos 沒用過 public 這個詞）。**fable 不在這裡推薦**，等使用者想；只提醒 C-54 一詞一義：別跟 `ctl.json`、`loops_mailbox`、「窗」這三個已有具體意思的詞撞。

### 方案 A、B、C 怎麼選（fable 的建議：程式面先做 B＝C 的特例，daemon.json 的切法當示範；A 的另外兩個名字等有讀者再加）

- **B 是 A 的子集**：兩邊 aos-daemon-ctl／aos-eca-hub 讀的都是 `AOS_DAEMON_STACK`，改程式的那一塊一樣。差別只在 A 多定兩個名字（`AOS_DAEMON`＝定義、`AOS_DAEMON_WS`）、並讓 daemon 把三個設給子項。
- **跟 11-01「環境變數只在必要時用」的關係**：B＝改名、個數不變（一個換一個），完全合；A＝多兩個今天**沒有任何程式讀**的變數——不合「必要時才用」的字面。A 的那兩個什麼時候變必要？當 daemon 底下的子項（bob、eca 實例）要知道「我是哪個 daemon 的、它在替哪個工作區幹活」的那天；今天的 demo 與試驗場都沒有這個需求。
- **C 不跟 B 衝突、也不另加變數**：程式面兩邊改的是同一行（工具讀控制口變數、在那夾裡用預設檔名找）；C 多的只是 daemon.json 用 `$env` 把窗寫到控制口、一份示範、`loops_state.json` 多一欄 `stack`、setup.sh 擴一個選項。使用者「這樣方便管理權限」的收益要等沙箱身分層真的套到 daemon 時才兌現，所以示範寫好、權限腳本等用到再擴。
- 所以建議：**現在做 B**（改名＋旗標改 `--stack`＋條文把 `AOS_DAEMON`「值＝stack」那句翻掉）；**A 的三名制寫進 N-63 當「保留的約定」**（名字與意義照使用者第一句定死，誰要設就照這個設），但程式不設、不讀，等有讀者再補 daemon 的 `setenv`（步驟表第 6 步，標「待需求」）。這樣使用者的兩句話都接住：名字的意義定下來了，變數的個數沒多。
- 如果使用者要**現在就做 A**：步驟表全做，多的是 child.cpp 三行 `setenv`、一個測試案、N-64 ④ 補 daemon 例子。代價小，只是跟 11-01 的字面不合，要他點頭。

## 要使用者看的衝突與方向題

### 衝突 1：方案 A 加兩個沒人讀的變數 vs 11-01「只在必要時用環境變數」

- **哪條**：11-01 使用者「這就是濫用...除非真的有必要的，否則不要用」；第 1 題裁「hub 型不用改」（留的是**現有**的 hub 變數，沒說可以多加）。
- **衝突在哪**：`AOS_DAEMON`（定義）、`AOS_DAEMON_WS` 今天沒有讀者；設了也只是擺著。
- **例子**：bob 掛在 daemon 底下寫詩，從頭到尾用不到 daemon 的定義在哪、工作區在哪（它自己有 `AOS_WS`）。唯一想得到的用法是「bob 想再掛一個兄弟 bob2」——那也只要 `AOS_DAEMON_STACK`。
- **後果**：選 B＝個數不變、合 11-01；選 A＝多兩個「先占名字」的變數，將來 daemon 的子項需要時不用再想名字，代價是跟 11-01 字面不合、盤點表多兩列。**fable 建議 B＋把 A 的名字寫成保留約定**（上面）。

### 衝突 2：N-63 10-30 夜改寫的「一個 hub 一個變數」

- **哪條**：N-63 拿掉 `AOS_HUB` 的理由「一個 hub 一個變數，這裡的 hub 就是 daemon；留著＝同一個資料夾兩個名字，C-54 一詞一義」。
- **衝突在哪**：方案 A 是一個 hub（daemon）三個變數。但三個指**三個不同的資料夾**，不是同一個資料夾兩個名字，C-54 其實沒被踩到；踩到的只是那句話的字面。
- **後果**：選 A 要把那句改讀成「**一個資料夾一個名字**」（真正的 C-54 意思），N-63 ② 補「一個 hub 可有幾個面向 `AOS_<名字>_<面向>`、代號仍 `<名字>Missing`」；選 B 不用動這句。

### 衝突 3：`--daemon` 旗標改 `--stack`——改了 10-30 使用者「環境變數＋argv」裡 argv 的名字

- **哪條**：10-30 第 10 點只定「靠環境變數＋argv」，旗標名是隊長代定、可翻案；但 demo/daemon-3 README、eca_hub README、測試都寫了 `--daemon`。
- **衝突在哪**：留 `--daemon D` 而 D 是 stack，就是今天要去掉的那種「名字跟東西對不上」；改 `--stack` 則 aos-daemon-ctl 跟 aos-eca-hub 都要改，使用者手上的指令也換。
- **後果**：改＝一次把名字對齊（變數 `AOS_DAEMON_STACK`、旗標 `--stack`、aos-say／aos-mcp 的 `--stack` 同義）；不改＝少改幾處，混淆留著。**fable 建議改。**

### 衝突 4：方案 C 若做成「aos-daemon 內建讀控制口變數」，撞 11-01「旋鈕走 argv／設定檔」

- **哪條**：11-01 第 3 題使用者「這就是濫用...除非真的有必要的，否則不要用」——程式自己讀環境變數當設定，就是被改掉的那 42 個旋鈕的樣子；daemon.json 本來就是 daemon 的設定檔。
- **衝突在哪**：使用者第四句「daemon 啟動後也可以吃這個變數」字面上是讓 aos-daemon 讀它。
- **fable 的化解**：不讓 aos-daemon 內建讀；由 daemon.json 作者用現成的 `{"$env": "控制口", "$path": …}` 明寫（五個窗 key 今天就吃指示詞，零程式改動）。效果一樣、沒給變數時是指示詞錯退 1、不會兩個地方管同一件事。**要使用者點頭的是**：他要的「吃變數」是不是這個意思；如果他要的是「不寫 daemon.json 也自動切」，那就是真的衝突，代價是 aos-daemon C++ 多一個固定變數名與一條「有變數就放那、沒有就放 stack」的雙軌規則。
- **連帶一處**：10-30 使用者選「A」的「eca 歸檔放 daemon 小格那邊 `$AOS_DAEMON/eca_archive/`」——控制口≠stack 時，歸檔與小格都在 stack、不在控制口，eca-hub 得從 `loops_state.json` 的新欄 `stack` 反查；10-30 那條的意思不變，只是路徑的來源換了。

### 方向題 1：`AOS_DAEMON` 這個名字本身要不要留

- 方案 B 做完後，`AOS_DAEMON` 沒有任何程式讀。兩條路：**(a) 退場**（像 10-30 的 `AOS_HUB`，條文寫「11-02 拿掉，原本的意思改叫 `AOS_DAEMON_STACK`」）；**(b) 保留、重定義為「定義資料夾」**（使用者第一句），寫在 N-63 當保留約定、程式不碰。
- 原則推不出：(a) 合「沒人讀就別留」（11-01 盤點把 `AOS_HUB` 列「沒人讀」就是這個態度）；(b) 合使用者第一句的意圖（三個名字一組，意義先釘死，免得下次又有人拿 `AOS_DAEMON` 指別的）。
- 後果：(a) 之後要再加就得重開一題；(b) 盤點表留一列「保留、沒讀者」。**fable 傾向 (b)**——一個名字曾經指錯過，把正確意思寫下來比留空好；但這是方向，由使用者定。

### 方向題 2：要不要現在就讓 daemon 把這些變數設給子項

- 上面規劃說「等有讀者」。但使用者 11-02 試驗場正在玩「bob 掛在 daemon 底下」，下一步若是「bob 自己再掛東西」或「eca 實例回報給 daemon」，就是讀者。
- 原則推不出時間點：N-64 ④ 說可以用 hub 型變數讓下一代找到自己，沒說一定要給；11-01 說必要才用。
- 例子：daemon 設了 `AOS_DAEMON_STACK=…/.stack` 給 bob，bob 的題目寫「幫我再掛一個 clock2」，bob 的工具 `aos-daemon-ctl add …` 就直接接得上，不用使用者在信裡塞路徑。
- 後果：現在做＝child.cpp 三行、一個測試、README 一段；不做＝試驗場要玩到那步時再補（半小時的事）。**fable 建議不做、列待需求**（跟衝突 1 同一個方向）。

## 實作步驟表（給隊長；每步都要先 pull）

**前提**：另一位 Opus 隊長**正在改** `aos-daemon-ctl`、aos-daemon C++（子項小格搬 `loops/<名>/`、拿掉擋名字）、aos-mcp。**實作者要等那輪 commit 進 main、`git pull` 之後再開工**，不然 `aos-daemon-ctl` 的 `link_stack`／`unlink_stack`、eca_hub README 的小格路徑會改在舊版上。開工前在 WSL 跑 `python3 -m unittest proto8/tests/test_aos_daemon_ctl.py proto8/tests/test_eca_hub.py proto8/tests/test_daemon.py` 當基線（要先建好 `proto8/impls`）。

| # | 改哪 | 做什麼 | 驗證 |
|---|---|---|---|
| 1 | `proto8/bin/aos-daemon-ctl` | `daemon_dir()`：`--stack` ＞ `$AOS_DAEMON_STACK`；`DaemonMissing` 訊息加一句「`AOS_DAEMON` 現在是定義資料夾（若方向題 1 選 (b)），投遞請設 `AOS_DAEMON_STACK` 或 `--stack`」；docstring、USAGE 同步；`--daemon` 不再認（`FlagUnknown`，不留別名——KISS） | `test_aos_daemon_ctl.py`：`ctl()` 的 env 改 `AOS_DAEMON_STACK`；「`--daemon` 蓋過」那案改 `--stack`；加 1 案「只設 `AOS_DAEMON`＝`DaemonMissing`、訊息含 `AOS_DAEMON_STACK`」 |
| 2 | `proto8/extras/eca_hub/bin/aos-eca-hub` | 同第 1 步（`DAEMON` 從 `--stack`／`$AOS_DAEMON_STACK` 定；叫 aos-daemon-ctl 時改傳 `--stack`） | `test_eca_hub.py`：`CLEAR` 加 `AOS_DAEMON_STACK`（方案 A 再加另外兩個）、`e["AOS_DAEMON"]` 改名；DaemonMissing 那案照跑 |
| 3 | `proto8/bin/README.md`、`proto8/extras/eca_hub/README.md`（9 處）、`proto8/impls/aos-daemon/README.md`、`proto8/demo/daemon-3/README.md`（指令塊） | `$AOS_DAEMON` → `$AOS_DAEMON_STACK`、`--daemon` → `--stack`；eca README 的小格路徑照隊長那輪的 `loops/<名字>/` | 讀一遍；`grep -rn 'AOS_DAEMON\b' proto8 --include=*.md` 只剩 thinking 的歷史與 N-63 的「舊名」說明 |
| 4 | 條文：`NORMS/10-基礎設施-定義與工作區.md` N-63（加 11-02 補：改名、`--stack`、三名制當保留約定或退場〔照方向題 1〕、「一個 hub 一個變數」改讀成「一個資料夾一個名字」）、`NORMS/04` N-28 末句、`NORMS.md` 總表那列、`NORMS/附錄1-條號表.md` N-63 列、`NORMS/附錄2-各批出處.md` 加 11-02 一條、`CONCEPTS/附錄1-名詞.md`（若加三名制：一行「daemon 的三個變數」） | 原文與決定引本檔；不改 10-30 的歷史句，只加「11-02 改」 | `/wf-lint` 無壞連結 |
| 5 | code map：`wf/workflows/common/code-map/proto8.md`（aos-daemon-ctl 那行）、`code-map/proto8/06-周邊工具-3.md`（eca-hub 兩處）、`code-map/proto8/02-tests-2.md`（測試案數） | 同步名字與案數 | 跟程式對一遍 |
| 6 | **（方案 A 或方向題 2 選「做」才做）** `impls/aos-daemon/src/child/child.cpp`（`run_child` 多三個 `setenv`：`AOS_DAEMON`＝設定檔所在資料夾絕對路徑、`AOS_DAEMON_STACK`＝`stack_`、`AOS_DAEMON_WS`＝daemon 的 `AOS_WS`、沒有就不設）、`daemon.cpp`（建構時算定義資料夾、傳給 child）、impls README「給子項的三個變數」一段、N-64 ④ 加 daemon 例子 | `test_daemon.py` 加 1 案：exec 子項把 `env` 寫進檔，驗三個值；巢狀不測 | ctest／unittest 全綠 |
| 7 | `proto8/thinking/2026-11-02-playground-daemon.md`「給使用者的指令」 | `export AOS_DAEMON=$PWD/.stack` → `export AOS_DAEMON_STACK=$PWD/.stack`；本檔「決定」節補使用者的裁定 | — |
| 8 | `wf/WAIT_USER.md` | 一條：使用者在 `~/code/playground/ws` 親手試 `export AOS_DAEMON_STACK=$PWD/.stack && aos-daemon-ctl ls`、投一封信；（做了第 6 步）看 `.stack/loops/bob/stderr.txt` 或讓 bob 印 `env | grep AOS_DAEMON` | 使用者回報 |
| 9（方案 C） | `proto8/impls/aos-daemon/README.md` 加「把對外的窗切出 stack」一段＋`proto8/demo/daemon-3`（或新 demo）一份用 `{"$env": "控制口", "$path": …}` 的 daemon.json；`daemon.cpp`／`state` 寫法：`loops_state.json` 每列多一欄 `stack`＝小格絕對路徑；aos-daemon-ctl `link_stack`／`unlink_stack`、aos-eca-hub 的小格與歸檔改讀那欄；`extras/sandbox/root/setup.sh` 加 `--daemon-ctl 控制口`（信箱 2770＋ACL、state 644、ctl 600、說明 stack 700 不綁）；N-28 補一句「窗可用指示詞放到 stack 外」、N-17 loops_state 補 `stack` 欄 | 變數名等使用者定了才動；`test_daemon.py` 加 1 案（窗寫到另一夾、stack 裡沒有）、`test_aos_daemon_ctl.py` 加 1 案（控制口≠stack 時 `--ws` 捷徑仍指對小格）；setup.sh 乾跑 |
| 10 | 收尾 | `grep -rn 'AOS_DAEMON\b' proto8 wf --include=* \| grep -v thinking \| grep -v digest \| grep -v session_logs` 應只剩 N-63 說明舊名那幾行；session log 一行；一個 commit（程式＋測試＋README＋條文＋code map 同一個） | ctest 全綠（repo 根）、`python3 -m unittest discover -s proto8/tests` 在 WSL 全綠、`/wf-lint` |

不動的：wf/digest 兩處（歷史快照）、`wf/session_logs/archive`、proto2／舊 playground 的 `AOS_DAEMON_DIR`／`AOS_DAEMON_HOME`（凍結的舊 proto）、10-30 以前的 thinking。

## 工人提的三點（11-02，使用者）

小格改 `loops/<名>/` 時（[11-02 stack-tools § 實作結論](2026-11-02-stack-tools.md#實作結論11-02隊長代定可翻案)）工人提的三點；使用者原文在上面[決定](#決定11-02使用者)那段（「3.a.那就是後續使用者要自己小心。b.自己小心。c.不用測試。」）。

- **(a) `loops` 成了 daemon stack 的保留名**（子項小格在 `.stack/loops/<名>/`，窗或信箱路徑取名 `loops` 會撞、程式不檢查）：使用者自己小心，不加檢查。
- **(b) 路徑 `./x/../s.json` 在 x 不存在時 `WriteFailed`**（沒先化簡路徑）：使用者自己小心，不改。
- **(c) 子項與信箱同名缺正向測試**：不補測試。

## aos-daemon-ctl 的定位（11-02，使用者）

使用者原文（逐字）：

> 對的，aos-daemon-ctl目前主要是對daemon底下的procs進行操作，對daemon本身操作這塊目前還是繼承於loop那樣，用ctl/state.json，往後可以給aos-daemon-ctl添加一些相關指令，但那是以後的事情

- aos-daemon-ctl 現在管 daemon **底下的子項**（add／rm／ls）。
- 對 daemon **本身**的操作（停、暫停、節奏）照 loop 的做法，寫它的 ctl 窗、讀它的 state 窗。
- 給 aos-daemon-ctl 加管 daemon 本身的指令：以後再說。
