# 2026-11-05 無痛遷移的使用者旅程：裝好→複製 agents→起 daemon→掛 agent→sleep→整份搬走續跑（fable 規劃，沒改程式）

← [thinking README](../../../README.md)｜日 [2026-11-05](../README.md)｜前情：[11-04 aos-agent](../../04/aos-agent/README.md)、[11-04 four-elements](../../04/four-elements/README.md)、[11-04 think-as-function](../../04/think-as-function/README.md)、[11-03 procs](../../03/procs/README.md)（sleep／wake）、[11-03 stack-where](../../03/stack-where.md)、[11-02 daemon-env](../../02/daemon-env/README.md)｜程式（只翻、WSL `/tmp` 拷貝實測、沒改）：[aos-daemon](../../../../impls/aos-daemon/README.md)、[aos-daemon-ctl](../../../../bin/docs/03-aos-daemon-ctl.md)、[aos-agent](../../../../extras/agent/README.md)、[aos-exec](../../../../impls/aos-exec/README.md)｜條文：[N-57～N-64](../../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[N-28](../../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[C-56、C-65、C-69](../../../../docs/CONCEPTS/01-設計理念.md)、[P-42](../../../../docs/CONVENTION/02-題目stack停錯腦.md)

狀態：**11-05 使用者裁完八題、已實作**（見下「決定（使用者，11-05 裁八題）」與 [實作結果](#實作結果11-05-隊長)）；以下原規劃段照留。原狀態：**規劃、沒改程式、沒改條文**。使用者 11-05 早一路補了七段話（下），把大半的題都裁了；剩 [05](05-衝突與方向題.md) 五題。實作步驟草稿在 [06](06-實作步驟草稿.md)。本檔只記使用者原文（逐字）、決定、fable 照原則定的結論（可翻案）、要使用者看的題（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-05 早，逐字，依先後）

> 對了，我這邊有個想法，你讓fable去想想：就是說，我會希望整套系統是方便的，首先是我把一些基本的aos工具安裝好，可以在PATH中找到，接著我複製一個agents資料夾(其中附帶一個daemon資料夾)到一個好找的地方，我cd到想要做事的資料夾(ws)，然後aos-exec把daemon叫起來，再開另一個視窗aos-exec呼叫agent做事。在agent做事途中，我可以aos-daemon-ctl

> aos-daemon-ctl sleep bob，把agent停掉。然後用ctrl-c把daemon停掉。接著把daemon的stack、我做事的資料夾(ws)，一起直接複製到另一個地方。實現無痛遷移。

> sleep/wake就開放吧。裝到PATH跟使用env.sh我覺得應該是差不多的。搬家這塊，我預期可能會搬到另一個電腦，乃至於透過git管理，我到另一台電腦做git pull

> 我知道很多都是走絕對路徑，但我發現，為了這種可搬移性，相對路徑比較好。這可能會導致很多問題，所以我這邊給個patch：可以用daemon作為相對路徑的一個基準點。當然，因為daemon底下可以跑另一個daemon，那這個基準點就是以自己頭上最近的那個daemon為準，因為上不知下

> 想想看，lisp可以做image，直接在程式執行中把狀態保存起來。在我們這邊，daemon就像是硬體，各stack就是各程序所佔據的記憶體空間。ws則是外置記憶體。各種定義資料夾則是類似source code，跑起來之後就是看其實例了(daemon下的stack)

> 不在任何daemon下的，我們不管，我們這套體系的基礎就是daemon/loop/exec三者合一。指到daemon外面就是自行承擔風險。子daemon知道自己被父daemon管，兩者間的關係就是daemon/proc，就這樣，要怎麼運用就隨便使用者，但我們在設計的時候不要考慮這些，就盡量解耦合。最近的上層daemon這件事沒啥好說的，在這套系統下，我們不管不在daemon下的proc，所以所有proc都有daemon管...那就是那個daemon。

> stack存定義副本...建議是不要，使用者想弄可以自己弄，但我們自己在做的時候盡量不要

> 主要就：啟動盡量快，就是複製過去、起daemon、(設好環境變數)(盡量少)、aos-exec開跑。

> 起daemon...對啦，也可以不起，那就是沿用

### 使用者原文（11-05，裁八題與補充，逐字）

> 衝突1 →「嚴格分 (Recommended)」
> 衝突2 →「我是希望只存差異，但等一下我要稍微看一下這塊，我怕有問題」
> （後補）「tools只存差異那塊可以先做，我直覺上這是好方法。等實作出來後我再看看」
> 衝突3 →「留成stopped，並寫原因」
> 題1 →「daemon 的 stack (Recommended)」　題2 →「留 ws/.stack (Recommended)」　題3 →「沒設就找 ./.stack」
> 題4 →「aos-agent add。當然，你也可以把_entry寫成aos agent add，這樣我們也可以aos-exec了。」
> 題5 →「用人設吧，你得自己指定。AOS_KERNEL這個命名我感覺他是通用於所有proc的，像是llm請求這塊，感覺要用AOS_LLM_KERNEL，代表llm這個子領域下的，管理呼叫的kernel。」
> 「更新好之後，playground也幫我更新，桌面那份文件也更新」

## 決定（使用者，11-05 裁八題；原文見上）

1. **sleep／wake 與 stop／start 嚴格分**：sleep＝現在就睡、daemon 開門（或 wake）時醒；stop＝等這輪做完、要手動 start；用錯回 `PhaseBad`。
2. **tools 只存差異**（覆蓋層），使用者要看實作 → [WAIT_USER](../../../../../wf/WAIT_USER.md)；說明在 [aos-agent docs/03](../../../../extras/agent/docs/03-tools覆蓋層.md)。
3. **定義沒搬、醒不來的留 `stopped` 並寫原因**（表上 `reason` 欄）。
4. 基準點＝**daemon 的 stack**；daemon 的 stack **留在 `ws/.stack`**。
5. **`AOS_DAEMON` 沒設就找 `./.stack`**（不是推薦項）。
6. 介面維持 **`aos-agent add`**；定義的 `_entry` 可以寫成呼叫 `aos-agent add`，`aos-exec 那個資料夾`＝掛上 daemon；不加 `aos-exec --daemon`。
7. **`AOS_KERNEL` 改名 `AOS_LLM_KERNEL`、由人設**；`AOS_KERNEL` 這名字留給通用 kernel（[kernel-daemon](../kernel-daemon/README.md) 在想）；舊名不認、給提示。值的語意照現狀（llm kernel 的信箱），之後 kernel-daemon 若改成「那台 daemon 的 stack」另做。

<a id="實作結果11-05-隊長"></a>
## 實作結果（11-05 隊長；06 步 0～7 全做，含步 4）

- **daemon**（[aos-daemon 11-05 搬家相關](../../../../impls/aos-daemon/docs/03-起-停-暫停.md#11-05-搬家相關)）：表的 `stack`／`ws`／`exec`／`def` 存相對 daemon stack、adopt 從新位置拼回；小格 `loop.json` 的 `exec` 寫 `{"$env": "AOS_DAEMON", "$path": …}`、內嵌單子 `cwd` 同、`$ref` 相對小格；`procs_slept`／`procs_woken`；wake／start 3 秒內退＝`stopped`＋`reason`；`DaemonRunning`。
- **信封**：aos-post `reply_to` 存相對信箱根（kernel、aos-llm 同）。
- **ctl／aos-agent**：讀相對表、`sleep`／`wake`、`PhaseBad` 照表擋、`./.stack`；tools 覆蓋層（aos-tools `--overlay`，aos-mcp／cli_session 跟著疊）；demo/agent-fsm `_entry` 呼叫 `aos-agent add`（身體 `body.json`）。
- **安裝與搬家說明**：[`proto8/install.sh`](../../../../install.sh)（symlink 進 `~/.local/bin`）、[aos-agent 搬家](../../../../extras/agent/docs/04-搬家.md)與 `stack.gitignore`／`stack.gitattributes` 範本；試驗場與桌面教學更新、真腦（LM Studio qwen3-1.7b）跑通一題。
- **實測**（WSL /tmp）：起 daemon、add、問答 → Ctrl-C → `cp -a` 到別處起，表不改就在新位置醒、子行程 `AOS_STACK`／`AOS_WS` 全是新位置、續答，舊位置沒被碰；git init＋clone 到第三處照樣醒、續答；只搬 daemon／kernel／ws 不搬定義 → 那隻留 `stopped`、`reason` 帶 stderr 最後一行，定義放回 `start` 就回來；sleep／wake、第二個 daemon `DaemonRunning` 都過。
- **代定（可翻案）**：REVIVE 視窗 3 秒；內嵌單子的 `$ref` 相對小格（不是相對 daemon stack；`$ref` 本來就從所在檔算）；daemon 對錯的組合不報錯、只 ctl 擋；add＋sleep 同時＝一列 sleeping；`DaemonRunning` 看 state.json 的 pid＋ticks＋boot_id；tools 覆蓋層的 path 相對覆蓋層檔、舊整份副本當整份取代且 add／rm 要先 reset；`_entry`／`body.json`／interfaces `entry` 的拆法；試驗場 lib 用副本不用 symlink；`.gitignore` 範本放 `ws/.stack/`；`KernelMissing` 代號沒改名；install.sh 只裝有 CMakeLists 的 impls。

## 決定（使用者，11-05 早；原文見上）

1. **`aos-daemon-ctl sleep／wake` 開放成指令**（翻 11-03「先不開放」）。
2. **裝到 PATH ＝ `source env.sh`**，不當大題；剩的差異一句：env.sh 還順手設 `AOS_DAEMON`／`AOS_KERNEL`，PATH 不會（[01 步 0](01-旅程對照.md)、[05 題 4](05-衝突與方向題.md)）。
3. **搬家＝跨電腦、甚至 stack 與 ws 進 git、到另一台 `git pull` 接著跑**（[04](04-跨電腦與git.md)）。
4. **存起來的路徑改相對，基準點＝管我的那個 daemon**；巢狀以頭上最近的那層為準（上不知下）。不在任何 daemon 下的不管；指到 daemon 外面自擔風險；子 daemon 與父的關係就是 daemon／proc，設計時不多考慮、盡量解耦；「最近的上層 daemon」不用找——每個 proc 都有一個 daemon 管，就是它（[03](03-絕對路徑盤點.md)）。
5. **心智模型**：daemon＝硬體、stack＝各程序的記憶體、ws＝外置記憶體、定義資料夾＝source code、daemon 下的 stack＝實例；搬家／git pull＝把 image 存起來、到別台載回來繼續跑（[02](02-image-模型.md)）。
6. **實例（stack）不存定義的副本**，只指向定義；使用者自己要放隨他，我們的工具、demo、試驗場不主動做（[05 衝突 2](05-衝突與方向題.md)）。
7. **總原則（判準，全篇用它量）**：啟動盡量快＝①複製過去 ②起 daemon——**沒有才起、有就沿用** ③設環境變數（盡量少、最好零）④aos-exec 開跑。每個實作步驟都要說它讓這四步變短還是變長，會多出第五步的標出來（[01](01-旅程對照.md) 每步末尾與「沿用」一節、[06](06-實作步驟草稿.md) 每步末欄）。

## 一句話

**旅程八步裡六步今天就能走，卡在第七步「整份搬走續跑」**：image（`ws/.stack/`）裡存的全是絕對路徑（daemon 表的 `stack`／`ws`／`exec`／`def`、小格 `loop.json` 的 `exec`、kernel 信裡的 `reply_to`、tools 副本的 `path`），複製到別處起 daemon，它會回去舊位置醒來、把舊的那份踩壞（[02 實測](02-image-模型.md#實測11-05wsl-tmp-拷貝)）；把路徑手改成新位置就能續跑，git 來回一趟掉的只有空資料夾、全部自癒。所以要改的只有一件事：**存的時候相對 daemon、讀的時候從 `AOS_DAEMON` 拼回來**（使用者 11-05 patch）；外加 sleep／wake 開成指令、工具副本不做、說明頁寫清楚哪些不屬於 image。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-旅程對照](01-旅程對照.md) | 旅程八步：現在能不能做到、差在哪、要改什麼 |
| [02-image-模型](02-image-模型.md) | 硬體／記憶體／外置記憶體／source／實例怎麼對到現況；image 裡有什麼、不屬於 image 的；WSL `/tmp` 拷貝實測五件 |
| [03-絕對路徑盤點](03-絕對路徑盤點.md) | 現在每一處存絕對路徑的地方：改相對 daemon 後怎麼存、怎麼解析；基準點、巢狀、不在 daemon 下、指到外面 |
| [04-跨電腦與git](04-跨電腦與git.md) | 跨電腦與 git pull：要改設計的 vs 自擔風險／寫進說明的；`.gitignore` 該擋什麼 |
| [05-衝突與方向題](05-衝突與方向題.md) | **要使用者看的**：衝突 3、方向題 5（推薦放第一） |
| [06-實作步驟草稿](06-實作步驟草稿.md) | 步 0～7（給隊長，不實作） |
| [07-listen-paused-bug](07-listen-paused-bug.md) | 11-05 晚 listen paused bug：pause→resume→stop→start 後 listen 仍報 paused 的成因、修法、驗證 |

## 使用者看過 tools 覆蓋層（11-05）

「tool差異我看了，我覺得OK。然後其實不用管舊版本遷移這件事，我們在proto8內，就是一律當成沒有舊版。畢竟是prototype-8」——覆蓋層照現狀定案；「舊的整份副本當整份取代」這類舊版處理不需要，規矩記在 [user.md 舊版遷移](../../../../../wf/workflows/common/user.md)。
