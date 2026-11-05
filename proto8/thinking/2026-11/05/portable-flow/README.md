# 2026-11-05 無痛遷移的使用者旅程：裝好→複製 agents→起 daemon→掛 agent→sleep→整份搬走續跑（fable 規劃，沒改程式）

← [thinking README](../../../README.md)｜日 [2026-11-05](../README.md)｜前情：[11-04 aos-agent](../../04/aos-agent/README.md)、[11-04 four-elements](../../04/four-elements/README.md)、[11-04 think-as-function](../../04/think-as-function/README.md)、[11-03 procs](../../03/procs/README.md)（sleep／wake）、[11-03 stack-where](../../03/stack-where.md)、[11-02 daemon-env](../../02/daemon-env/README.md)｜程式（只翻、WSL `/tmp` 拷貝實測、沒改）：[aos-daemon](../../../../impls/aos-daemon/README.md)、[aos-daemon-ctl](../../../../bin/docs/03-aos-daemon-ctl.md)、[aos-agent](../../../../extras/agent/README.md)、[aos-exec](../../../../impls/aos-exec/README.md)｜條文：[N-57～N-64](../../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[N-28](../../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[C-56、C-65、C-69](../../../../docs/CONCEPTS/01-設計理念.md)、[P-42](../../../../docs/CONVENTION/02-題目stack停錯腦.md)

狀態：**規劃、沒改程式、沒改條文**。使用者 11-05 早一路補了七段話（下），把大半的題都裁了；剩 [05](05-衝突與方向題.md) 五題。實作步驟草稿在 [06](06-實作步驟草稿.md)。本檔只記使用者原文（逐字）、決定、fable 照原則定的結論（可翻案）、要使用者看的題（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

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
