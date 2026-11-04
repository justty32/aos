← [回入口 10-基礎設施-定義與工作區.md](../10-基礎設施-定義與工作區.md)｜段落：hub 型環境變數（10-28）、父子交代（10-29）｜上一份：[06-N-50～N-53](06-N-50～N-53.md)｜下一份：—

## hub 型環境變數（10-28）

- **N-63**（10-28 定，草稿；使用者 10-28「hub 照你的建議定薄標準。」，[thinking 10-28 medium](../../../thinking/2026-10/28/medium/README.md) 決定 17）**hub（類 singleton、全樹共用的那一個東西）用環境變數指，只定三件事，其他不管**：
  ① **命名 `AOS_<名字>`，值是一個資料夾的路徑**；
  ② **沒設定＝報錯、說缺什麼**：代號 `<名字>Missing`（C-54，例 `StackMissing`、`DaemonMissing`），不自己猜一個位置；
  ③ **子 process 預設繼承**（照 Linux 環境變數本來的樣子往下傳）。
  資料夾裡放什麼、誰建、怎麼跟它講話，各 hub 自己定。現有的實例：`AOS_STACK`（執行中狀態放哪，N-57）、`AOS_KERNEL`（kernel 的信箱資料夾，N-16、[aos-llm-send](../../../impls/aos-llm-send/README.md)）、`AOS_DAEMON`（見下）。
  - **跟實作對不上的**（只列、程式沒改）：
    - `AOS_STACK` 沒設時 **aos-exec 自己退回預設** `$AOS_WS/.stack/`（N-57、C-69，impls aos-exec `setup_ws_stack`），跟 ② 不合；aos-loop（開了窗才要）、aos-fsm、aos-daemon、aos-llm-kernel 沒設就報 `StackMissing`，合。
    - `AOS_KERNEL` 沒設時 aos-llm-send 報錯、不猜位置，合 ②；但代號是 `MailboxMissing`、不是 `KernelMissing`（impls aos-llm-send `send.cpp`）。kernel 那一邊（aos-llm-kernel）不讀 `AOS_KERNEL`，信箱位置讀 kernel.json 的 `mailbox`（封存在 proto8/archive/llm-kernel-demo/ 的 demo，`_entry` 再把同一個路徑設給 `AOS_KERNEL`）。
    - ③ 跟 [CONVENTION P-39](../../CONVENTION/06-巢狀/03-P-37～P-40.md) 的寫法不同：P-39 把 `AOS_STACK` 歸「叫別人時明給」（每層開小格、重設），不是一路繼承；繼承是預設，P-39 是 agent 範本在叫別人時的做法。
  - **實例 `AOS_DAEMON`**（使用者 10-30「關於那個aos-daemon-ctl，他應該是要吃環境變數+argv來確定daemon home在哪裡的(要用哪個daemon)。」，[thinking 10-30 map-review](../../../thinking/2026-10/30/map-review/01-使用者原文.md#決定10-30) 第 10 點；名字：使用者 11-02「就AOS_DAEMON_STACK吧」「最好明講，也就是--daemon-stack」，[thinking 11-02 daemon-env](../../../thinking/2026-11/02/daemon-env/01-使用者原文-11-02-逐字.md#決定11-02使用者)；**11-04 註**：改回 `AOS_DAEMON`、旗標 `--daemon`，使用者 11-04 晚「AOS_DAEMON_STACK實在太醜，還是直接簡化成AOS_DAEMON就好了」，[thinking 11-04 aos-agent](../../../thinking/2026-11/04/aos-agent/02-找-agent.md#哪個-daemon)；優先順序是實作代定、可翻案；照實作寫，[aos-daemon-ctl](../../../bin/README.md)、aos-eca〔11-04 併進 [aos-agent](../../../extras/agent/README.md)，照同一條〕）：aos-daemon-ctl、aos-eca〔＝aos-agent〕找「掛到哪個 daemon」用 `--daemon` ＞ `$AOS_DAEMON`，值＝那個 daemon 的 `$AOS_STACK` 資料夾；都沒有或不是資料夾＝`DaemonMissing`；子 process 照常繼承——三件都合。
    - **舊名退場**（11-04 晚反向重寫：11-02 定的是 `AOS_DAEMON`→`AOS_DAEMON_STACK`、不留別名〔頂層代定〕；現在倒回來、一樣不留別名，[11-04 四元素審查](../../../thinking/2026-11/04/four-elements/README.md)點名）：`AOS_DAEMON_STACK`、`--daemon-stack` 不留別名——給 `--daemon-stack`＝`FlagUnknown`；只設了 `AOS_DAEMON_STACK`、沒設 `AOS_DAEMON`＝`DaemonMissing`，訊息提示改設 `AOS_DAEMON`（或 `--daemon`）。
    - **不定三名**（使用者 11-02「那就不用定這三個名字了」）：不另設「daemon 的定義所在」「daemon 的工作區」的變數。
    - **daemon 起子項時把 `AOS_DAEMON` 設給它**（11-04 晚改名）（兄弟要共用位置時用；只設這一個。使用者 11-02 對常駐 bob 的衝突與方向題回「照建議走」，[thinking 11-02 resident-bob](../../../thinking/2026-11/02/resident-bob/02-衝突與方向題的裁定-11-02-晚-使用.md#衝突與方向題的裁定11-02-晚使用者) 衝突 2；照實作寫，[aos-daemon](../../../impls/aos-daemon/README.md)）：loop 型、exec 型子項的環境一律多 `AOS_DAEMON`＝daemon 自己的 `$AOS_STACK`，轉成絕對路徑、結尾 `/`（跟 aos-exec 給的 `AOS_STACK` 同形；頂層代定、可翻案）；daemon 自己的環境裡原本有沒有這個變數都蓋過去。子項裡的 `aos-daemon-ctl` 因此不用另給 `--daemon` 就找得到它的 daemon。
    - **例外 `AOS_AGENT`**（11-04 註；使用者 11-04 晚裁「N-63 加一句例外」，[thinking 11-04 aos-agent 06/02](../../../thinking/2026-11/04/aos-agent/06-衝突與方向題/02-新題-11-04-晚.md#使用者裁定11-04-晚選項原文)）：`AOS_` 開頭但**不是 hub**（值是名字、不是資料夾，不照 ①）：是 aos-agent 給人殼用的預設對象（`--target` 沒給就看它，[02-找-agent](../../../thinking/2026-11/04/aos-agent/02-找-agent.md#找-agent只有一條路)）。
  - **沒有 `AOS_HUB`**（使用者 10-30「都照建議」，[thinking 10-30 eca](../../../thinking/2026-10/30/eca/09-方向題.md#決定10-30) 衝突 2、4；[10-30 map-review](../../../thinking/2026-10/30/map-review/01-使用者原文.md#決定10-30) 第 5 點）：aos-eca〔11-04 併進 [aos-agent](../../../extras/agent/README.md)，同樣建在 aos-daemon 上〕 建在 aos-daemon 上、不設自己的常駐 kernel，用哪個 daemon 照 `AOS_DAEMON`（上面），不另設變數（一個 hub 一個變數，這裡的 hub 就是 daemon；另設＝同一個資料夾兩個名字，C-54 一詞一義）。`aos-hub` 這個名字保留，以後真有通用的 hub 再用（使用者 10-30）。

## 父子交代（10-29）

- **N-64**（10-29 定；使用者 10-29「父子交代...可以算基本概念，用不用都可以，用了的話我們也提供一些aos標準供人遵守」，看完衝突與方向題回「都照建議」，[thinking 10-29 medium-plan](../../../thinking/2026-10/29/medium-plan/README.md) § 六、條文草稿；[10-28 medium](../../../thinking/2026-10/28/medium/README.md) 決定 22、23、28；概念 [C-75](../../CONCEPTS/03-基礎設施/01-inst至fsm.md#proc-之間的交流10-29)）**父子交代（選用）**：上一代生下一代時給的、下一代結束時留下的，只在上下兩代之間。
  ① **上一代給下一代的**＝args、stdin、aos-exec 保證的六個環境變數（N-57）與 hub 型變數（N-63）；參數怎麼進由下一代自己說（[N-27](../03-基礎設施-inst.md)）。
  ② **下一代留給上一代的**＝結束碼（[N-43](../01-總則/02-N-43.md)）、stdout、stack 裡的檔（[N-13](../05-基礎設施-窗/03-N-13～N-14.md)）。
  ③ 下一代要自報身分就報 `$AOS_WS`：上一代給的工作區就是它的名字。
  ④ 上一代要讓下一代找到自己的信箱或窗，用 hub 型變數（N-63）或 args 明給，不另加新的環境變數（C-69 aos 只訂那幾個）。例：daemon 起子項時設 `AOS_DAEMON`＝自己的 stack（N-63「daemon 起子項時把 `AOS_DAEMON` 設給它」），子項（與它的兄弟）照它找到 daemon 的信箱 `procs_ctl_mailbox/`、名單窗 `procs_state.json`、彼此的小格 `procs/<名字>/` 或列上的 `stack`（[N-28](../04-基礎設施-loop與daemon/02-N-28.md)「每項選填 `stack`」、[thinking 11-03 procs](../../../thinking/2026-11/03/procs/README.md)）。
  這一條只是把散在 N-27、N-43、N-13、N-57、N-63 的東西集中點名；用不用都可以。daemon 起子 loop 就是一個實例（寫小格 `loop.json`、`AOS_STACK`＝小格、起 `aos-exec 小格/loop.json#/_entry`，N-28）。
