← [入口](README.md)｜涵蓋：`AOS_DAEMON` 現況（查清的，不是規劃）；規劃（fable，照原則定的細節，可翻案） › 共同的底：這些工具真正要碰的是什麼、方案 A：三個名字（使用者第一句）｜上一份 [01-使用者原文-11-02-逐字](01-使用者原文-11-02-逐字.md)｜下一份 [03-方案-B-一個名字-使用者第二句-只要投](03-方案-B-一個名字-使用者第二句-只要投.md)

## `AOS_DAEMON` 現況（查清的，不是規劃）

- **來歷**：10-30 使用者看 aos-daemon-ctl 的規劃時說「關於那個aos-daemon-ctl，他應該是要吃環境變數+argv來確定daemon home在哪裡的(要用哪個daemon)。」（[map-review 第 10 點](../../../2026-10/30/map-review/01-使用者原文.md#決定10-30)）。變數名 `AOS_DAEMON`、`--daemon` 蓋過它、**值＝那個 daemon 的 `$AOS_STACK` 資料夾**，三件都是實作隊長照 N-63 代定、條文明寫「可翻案」。使用者原話說的是「daemon home」，沒說是 stack——隊長把 home 落成 stack，因為 aos-daemon-ctl 要碰的三樣東西（信箱 `loops_mailbox/`、名單窗 `loops_state.json`、小格 `<名字>/`）全在 stack 裡。
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
