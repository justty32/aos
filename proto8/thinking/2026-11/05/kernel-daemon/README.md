# 2026-11-05 早 kernel 與 daemon：daemon 是最基礎的 kernel、兩種模式、問腦改成 daemon 下的 proc（fable 規劃，沒改程式）

← [thinking README](../../../README.md)｜日 [2026-11-05](../README.md)｜同天另一份：[portable-flow](../portable-flow/README.md)（可搬移；基準點＝daemon 的 stack、sleep／wake 與 stop／start 嚴格分；交集只指過去、不改它）｜前情：[11-04 think-as-function](../../04/think-as-function/README.md)、[11-03 procs](../../03/procs/README.md)、[10-15 general-kernel](../../../2026-10/15/general-kernel.md)、[10-13 kernel-agent](../../../2026-10/13/kernel-agent/README.md)｜程式（只翻、沒改）：[aos-daemon](../../../../impls/aos-daemon/README.md)、[aos-daemon-ctl](../../../../bin/docs/03-aos-daemon-ctl.md)、[aos-llm-kernel](../../../../impls/aos-llm-kernel/README.md)、[aos-llm](../../../../impls/aos-llm/README.md)｜條文：[C-47](../../../../docs/CONCEPTS/04-kernel.md)、[N-42](../../../../docs/NORMS/09-kernel.md)、[N-28、N-54](../../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-63、N-64](../../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[C-52、C-56、C-64](../../../../docs/CONCEPTS/01-設計理念.md)

狀態：**11-05 隊長已實作（06 步 0～6 全做）**，見下「[實作結果](#實作結果11-05-隊長)」與 [08](08-實作結果.md)；以下原規劃段照留。原狀態：**規劃、沒改程式、沒改條文**。本檔只記使用者原文（逐字）、決定、fable 照原則定的結論（可翻案）、要使用者看的題（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。[05](05-衝突與方向題.md) 的衝突 2 題使用者 11-05 已裁（都選推薦）；其餘代定、標可翻案。實作步驟草稿在 [06](06-實作步驟草稿.md)。

## 使用者原文（11-05 早，逐字，依先後）

> daemon是硬體，他是比較特殊的存在，他的stack就是自己本身，所以才說AOS_DAEMON，而非AOS_DAEMON_STACK。然後kernel和daemon，兩者其實可以合一，就是說，daemon他收請求，按照請求去掛proc到自己身上，而kernel按照定義，他是管理proc是否要執行的傢伙，這樣子會有兩種模式，一種是兩者合一，變成說收到信後跑一個函數，決定是否要掛(從這個來看，其實daemon也算是一種kernel，只是他就是來者不拒，可以說是一種最基礎的kernel實作)，有點類似繼承，把函數覆蓋掉，並在新建的函數末尾呼叫base class函數。第二種是kernel作為一個唯一有權限對daemon下daemon-ctl指令的proc，其他人要掛proc，就是要改將請求丟給這個kernel proc，這就比較類似linux，有一個0號proc

（頂層說現在的 llm kernel 代為問腦跟這個 kernel 是兩回事）

> 同一回事，因為問腦，他本身也可以包裝成一個aos函數，掛成proc去跑。我也建議這樣。kernel的定義是管理某proc是否可以執行，硬要說的話，現在的代為問腦也可以算，只是他的問腦proc，是直接打endpoint，也就是他的proc是掛在linux底下，而非daemon底下。不太...好，但demo可以這樣啦，畢竟aos函數有好處，但是也有開銷。

> 啊不過老實說，我們的核心思想就是開銷不算啥，因為LLM本身就是最消耗時間的。所以...還是都包成aos函數吧

> 能包盡量包啦

> 不過我又想到了另一個：kernel管理proc要不要跑，那，假如有一個loop，他同樣是收信，做判斷，但他判斷要跑這個請求的時候，所做的動作是把請求轉交給另一個真正有權限的kernel，那他也算kernel嗎？我覺得是算的，他的命名中也可以帶有kernel，只是說，建議不要濫用...。除此之外，假如他判斷要跑這個請求後，所做的動作是直接執行linux原生proc，或是一些函數，那他算kernel嗎？我覺得是不算的...

> hmmm，這一套搞不好可以再開一個fable去思考。然後兩個fable思考出來有想法，能做的就先做吧

同天稍後在 portable-flow 題 5 順帶裁的命名（逐字，頂層轉達）：

> 用人設吧，你得自己指定。AOS_KERNEL這個命名我感覺他是通用於所有proc的，像是llm請求這塊，感覺要用AOS_LLM_KERNEL，代表llm這個子領域下的，管理呼叫的kernel。

再稍後（逐字，頂層轉達；本檔 [07](07-llm-daemon佈局.md) 回答）：

> llm這塊，我預期他是這樣的用法：我先在把定義複製到~/llm_kernel/def，然後cd ~/llm_kernel && aos-exec def，把llm的daemon+kernel叫起來。然後開另一個視窗，把另一個daemon叫起來，這是用來跑agent的...叫起來之前要先設AOS_LLM_KERNEL=~/llm_kernel/.stack。這樣的好處是之後可以起另一個agent用的daemon，然後共用一個llm kernel，並統一管理從這台電腦出去的endpoint呼叫。hmmm，感覺設置daemon的時候，都是指其stack...有好辦法嗎

> 啊不對，應該說aos-exec --stack . def，直接讓他把~/llm_kernel作為stack就好

> def/那個只是方便，實際上放哪都可以。原始碼就隨意，真的。

## 決定（使用者，11-05 早；原文見上）

1. **kernel＝管理某 proc 是否可以執行的東西**（C-47 原生定義不變、aos 實作定義收緊，見 [01](01-現況對照.md)）。
2. **daemon 是最基礎的 kernel**：來者不拒（收到掛的請求就掛）。daemon 的 stack 就是它本身，所以叫 `AOS_DAEMON`、不叫 `AOS_DAEMON_STACK`（跟 11-04 晚改名同一句話）。
3. **兩種模式**：① **繼承式**——daemon 收到信先跑一個函數決定要不要掛，函數末尾呼叫 base（daemon 原本的「掛」）；② **0 號 proc 式**——唯一能對 daemon 下 ctl 指令的 kernel proc，其他人把請求丟給它。
4. **問腦包成 aos 函數、掛成 daemon 底下的 proc**；現在 aos-llm-kernel 自己 fork 打端點「不太好，demo 可以」→ 改成請 daemon 掛（[03](03-問腦改掛daemon.md)）。
5. **能包成 aos 函數的盡量包**：開銷不算啥，LLM 本身才是最慢的。
6. **轉交型也算 kernel**：收信、判斷、判斷要跑時轉交給真正有權的 kernel——算，命名可以帶 kernel、別濫用。**判斷後直接跑 Linux 原生程序或函數的不算 kernel**。
7. **命名**：`AOS_KERNEL` 保留給「通用、管所有 proc 的 kernel」；llm 子領域管呼叫的 kernel 叫 **`AOS_LLM_KERNEL`**，由人設、不自動傳（改名實作另有隊在做；本檔的設計一律用新名字，`AOS_KERNEL` 在兩種模式下指什麼見 [02/01 § 4](02-兩種模式/01-唯一-AOS_KERNEL-命名.md)）。
8. **llm kernel 是自己一台 daemon**（daemon＋kernel 合一）：`cd ~/llm_kernel && aos-exec --stack . def`，那個資料夾本身就是那台 llm daemon；跑 agent 的 daemon 另起、可以好幾台，起之前設 `AOS_LLM_KERNEL=~/llm_kernel`，共用一個 llm kernel、統一管理這台電腦出去的 endpoint 呼叫。定義（原始碼）放哪都行，`def/` 只是方便。「設 daemon 都是指其 stack，有好辦法嗎」是使用者的問題，答在 [07](07-llm-daemon佈局.md)。

## 一句話

**「kernel」是角色不是程式：誰決定「這個 proc 掛不掛到 daemon 上」誰就是 kernel，daemon 自己是最底下那個（來者不拒）。** 掛 proc 只有一條路——往 daemon 的 ctl 信箱寄一封 `procs_added` 信；繼承式＝daemon.json 的 `exec` 身體當判官、判完轉寄進自己的 ctl 信箱（「呼叫 base」就是這一寄，零改 aos-daemon）；0 號式＝同一支判官掛成 loop 型 proc、daemon 信箱靠 Linux 權限只讓它寫。**llm kernel 就是繼承式的第一個實例**（`~/llm_kernel/def/daemon.json` 的身體＝`aos-llm-kernel`），它改一件事：不再自己 fork 跑 endpoint 函數，而是把那次問腦寫成 `procs_added` 信請自己這台 daemon 掛成 `max: 1` 的 loop（stack＝信資料夾），下一拍從 `state.json`＋`reply.json` 收、回信、刪信——「不補位」「RunFailed」兩個已知限制順帶消失。`AOS_LLM_KERNEL`＝那台 llm daemon 的 stack，信箱固定 `<stack>/mailbox/`；信的形狀、`aos-llm` 不變。

<a id="實作結果11-05-隊長"></a>
## 實作結果（11-05 隊長）

06 步 0～6 全做，另照同輪使用者兩句做了「aos-agent 管理類收進 `ctl`」與「proto8 一律當沒有舊版」（舊版相容碼刪掉）。llm kernel 現在是自己一台 daemon（`demo/llm-kernel`；`cd ~/llm_kernel && aos-exec --stack . def`），每次問腦是那台 daemon 表上的一列 `llm_<信件名稱>`；`AOS_LLM_KERNEL`＝那台的 stack；判官範本 `lib/base/judge`（模式 1 `demo/daemon-judge`、模式 2 `demo/procs-kernel`）；aos-daemon-ctl 認 `AOS_KERNEL`。代定 12 條（例：在飛判定看表＋`state.json`、不用 `applied` 回信；`KernelMissing` 改名 `LlmKernelMissing`）、刪掉的相容碼、實測、已知限制都在 **[08 實作結果](08-實作結果.md)**。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-現況對照](01-現況對照.md) | 現有東西哪些算／不算 kernel；跟哪些條文、裁定衝突或要改 |
| [02-兩種模式](02-兩種模式.md) | 模式 0／1／2 各自怎麼落到 daemon、daemon-ctl、ctl 信箱：介面、「唯一能下 ctl」怎麼保證、base 呼叫與判官怎麼表達成 aos 函數；`AOS_KERNEL` 指什麼 |
| [03-問腦改掛daemon](03-問腦改掛daemon.md) | llm kernel 收信→請 daemon 掛問腦 proc→收結果→回信：掛信形狀、一拍流程、完成判定、slots、逾時、失敗、kernel 睡醒 |
| [04-邊緣狀況](04-邊緣狀況.md) | daemon 不在／暫停／拒信、名字、睡醒、kill -9、兩個 kernel、搬家、權限、表上多出來的列 |
| [05-衝突與方向題](05-衝突與方向題.md) | **要使用者看的**：衝突 2（推薦放第一）；fable 代定清單 |
| [06-實作步驟草稿](06-實作步驟草稿.md) | 步 0～6（小步、每步 build 得過），標哪幾步跟 portable-flow 無衝突可以先做 |
| [08-實作結果](08-實作結果.md) | 11-05 隊長實作結果：做了什麼、實作時代定（可翻案）、刪的舊版相容、實測、已知限制 |
| [07-llm-daemon佈局](07-llm-daemon佈局.md) | llm kernel 自己一台 daemon（合一）：`~/llm_kernel` 長什麼樣、`AOS_LLM_KERNEL` 的值＝stack、信箱固定 `mailbox/`、多台 agent daemon 共用；「設 daemon 都是指其 stack」三個選項（推薦放第一）；要轉給改名隊的語意改動 |
