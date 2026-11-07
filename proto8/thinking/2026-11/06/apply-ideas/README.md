# 2026-11-06 昨晚與今天聊出來的東西怎麼用到現況、要不要插進大重構（apply-ideas，fable 規劃，沒改程式）

← [2026-11-06](../README.md)｜[thinking](../../../README.md)｜源頭：[fs-image](../../05/fs-image/README.md)（信封與 body、暫停時間、[非同步呼叫原文](../../05/fs-image/02-非同步呼叫原文.md)）、[tick-time](../../05/tick-time/README.md)、[json-argv](../../05/json-argv/README.md)（含 [07 使用者回覆](../../05/json-argv/07-使用者回覆-11-05晚.md)）、[no-pid](../../05/no-pid/README.md)（[08 P1 結果](../../05/no-pid/08-P1實作結果.md)）、[knowledge-write](../../05/knowledge-write/README.md)、[small-thought](../../05/small-thought/README.md)、[portable-flow 07](../../05/portable-flow/07-listen-paused-bug.md)｜同日另一位 fable：[body-protocol](../body-protocol/README.md)（非同步呼叫協議的形狀，本夾只排它什麼時候做）｜現況：[arch-refactor 06 § 明天剩什麼](../../05/arch-refactor/06-工作量與排程.md#明天剩什麼11-05-收尾改成實際)、[SESSION-LOG](../../../../../wf/SESSION-LOG.md)｜規矩：[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)、[refactor](../../../../../wf/workflows/refactor/README.md)（重構＝行為不變）

狀態：**只規劃、沒改程式、沒改條文**。**11-06 下午使用者已裁**：D1 先只有硬凍、排程照推薦（J1 已開）、tick 五題（Q1／Q2 改，新設計在 [tick-time 03](../../05/tick-time/03-11-06-裁定與新設計.md)）、body-protocol 四題照推薦。寫到 11-06 中午：S0～S5、P1、P2 已進 main（路徑以搬夾後的 `cmd/`、`py/`、`kernel/`、`templates/` 為準），P3＝S6 正在做，S7 分支在家機。本檔記使用者原文（逐字）、一句話結論、六樣東西各一行、要不要插進大重構的裁法、方向題與代定；細節在分檔。

## 使用者原文（11-06，逐字）

> 我也希望你能派fable去把昨晚我們聊出來的東西，還有我們今天聊的東西，拿去思考說如何應用在我們現在的狀況上，包括是否要將其插入大重構排程中。

## 一句話結論（白話）

**昨晚聊的六樣東西，沒有一樣要「插進」大重構的某一步——大重構是搬家不改行為，這些全是新行為，疊在搬完、拆完的程式上最省事；只有一處要「緊接著」做：tick 時間改 llm kernel 的 deadline，跟 S9 改 `DeadlineMissed` 名字是同幾行程式，同一人一口氣做。** 信封／body 跟暫停時間，程式現在就已經是那個樣子（aos-post 不看 body；daemon sleep 就是凍住），只差寫進條文，再加 no-pid 的 P6 讓整棵樹一次睡醒。非同步呼叫協議的形狀另一位 fable 今早在 body-protocol 想好了（一箱一函數、body＝函數的 stdin JSON、回信＝stdout），五題等你裁，我只排它：通用 runner（暫名 aos-serve）排在大重構後、P6 之後。今天在公司能動而且互不撞檔的只有 P3＝S6（進行中）跟 J1 旗標映射（可開）；其他全部回家排在 S7 併進之後。

## 六樣東西各一行（細節 [01](01-逐項落點.md)）

| 想法 | 現況對照 | 落到哪 | 大約多大 |
|---|---|---|---|
| A 信封＝IPC、body 歸收信程式 | aos-post `letter.json` 四欄＋`body`，壞信判定不看 body——**已如此** | 條文一句（N-16 旁）；信封加 `sent_tick`（tick-time #13） | 0.5 h 條文＋0.5 h C++ |
| B 非同步呼叫協議 | 形狀見 [body-protocol](../body-protocol/README.md)：一箱一函數、body＝stdin JSON、回信＝stdout／頂層 `error`；現成三個收信者（daemon ctl、llm kernel、判官）已是這樣 | 條文等它的五題；通用 runner aos-serve 排大重構後、P6 後 | 條文 1 h；runner 半天 |
| C 暫停時間＝fs image | daemon 收工把 loop 型留 `sleeping`、整包 `cp -a`／git 來回實測過——**已成立八成**；缺「整棵樹一次睡」（子 daemon 是 exec 型，父 sleep 帶不動它） | **＝no-pid P6**；條文 C-16／C-17／N-03 加註；一份「凍住→git→醒來」食譜 | 程式 0（P6 已排）；條文與食譜 1 h |
| D 時鐘回到 tick | 15 處用秒已盤點（tick-time 01），lib 補掃完（本夾 01 § D）；11-06 改成「daemon `tick` key 自帶時鐘、沒 tick 退牆鐘」 | T1～T8（util `now_tick`＋兩鐘 `deadline()`、aos-lock 一次改完、post、llm-kernel、inst、lib、daemon `tick` key、條文） | 9～11 h；T7 等 P6 |
| E json-argv | 使用者 07 已回；J1～J8 已排 | J1 今天可開（只動 `lib/tool_io.py`，S5 沒搬它）；巢狀 `--a.b` 翻了「不做點路徑」的代定 | 約 8 h |
| F no-pid 監管樹 | P1、P2 做完、P3＝S6 進行中 | 照原排；P6＝fs-image 的實作、P7 的 N 秒改 ticks（排在 T 之後）、P2 的 `responded_at` 留牆鐘 | 不變（約 12 h） |
| G 已裁三樣（knowledge-write、small-thought 餘項、五題） | 都「排在大重構後」 | W 的鎖那行照 T2 新旗標；`tools add --env-file／--envs` 跟 J3／P4 同檔同人；寄件人額度相對 kernel 跟 T4 同專案 | 不變 |

## 要不要插進大重構（細節與新排程表在 [02](02-排程.md)）

- **原則**：大重構＝行為不變（refactor 工作流）；上面全是新行為，**不混進 S 步**（唯一例外是使用者已裁的 S6＝P3）。
- **撞檔**：家機 S7 分支動到 aos-util／post／llm／llm-kernel／loop／fsm／lock／daemon——幾乎所有 impls，而且回家還要先疊到 S5＋P1＋P2 之上；S8 拆 daemon.cpp／serve.cpp／aos-agent／ctl／aos-tools。所以 **所有 C++ 新行為（T、P6～P7、aos-serve）一律排 S7 併進之後**；T4 跟 S9 同人緊接；S10 的「aos-lock `acquire --pid` 死碼」移給 T2 一起做。
- **先後依賴**：fs-image 整樹凍住 ← P6；P7 ← T（stuck 用 ticks）；W1 的鎖那行 ← T2；J3／J6 ← P4；T ← tick-time Q1～Q5；aos-serve ← body-protocol 五題、P6。
- **今天公司**：P3＝S6（進行中）、J1 兩線；使用者聊出來的裁定由頂層收、條文草稿先寫進 thinking（不進 docs）。**今晚家機**：S7 疊到 main 併 → S8 ‖ P4／P5／P5b → S9（＋T4）→ S10 → S11 → 有力就 P6。**之後**：T → P6～P9 → J2～J8 → W → 五題餘項 → aos-serve（五題裁了才做）。

## 方向題（細節 [03](03-方向題.md)；11-06 下午 D1、Q1～Q5 已裁）

1. ~~凍住的方式~~ 已裁：先只有硬凍。
2. ~~tick-time Q1～Q5~~ 已裁：Q3～Q5 照推薦；Q1 改「daemon 設定自帶 `tick` key」、Q2 改「沒 tick 退牆鐘當逃生口」。新題 N1（`_tick` 死了自動重起？）、N2（時鐘檔過舊退牆鐘？）使用者同日「那兩題都按照推薦」已裁（[tick-time 03 § 五](../../05/tick-time/03-11-06-裁定與新設計.md)）：自帶的 `_tick` 照 daemon 型規則重起、人停的不重起；過舊不退牆鐘、靠表看。**方向題全部清空。**
3. **非同步呼叫的五題**在 [body-protocol § 方向題](../body-protocol/README.md#方向題11-06-已裁題-14-照推薦題-5-照-apply-ideas-排程)，不重問；它的題 5（aos-serve 什麼時候做）我代答：大重構後、P6 之後，見 [02](02-排程.md)。

## 邊緣狀況

挖出來的在 [04](04-邊緣狀況.md)（已在 fs-image／tick-time／no-pid／body-protocol 列過的只標出處、不重講）。

## fable 代定（可翻案）

1. 新行為不混進 S 步；「T4 緊接 S9」是同人同批、兩個 commit，不是併進 S9。
2. 凍住＝現在的硬凍；軟凍等 tick 落地才做。
3. P2 加的 `responded_at` 留牆鐘（給人看，第①類）；P7 判 stuck 時另加 `responded_tick`，有 `AOS_TICK` 才寫。
4. aos-serve（body-protocol 暫名）排大重構後、P6 之後，掛在 daemon 下；形狀照 body-protocol，本夾不另定。
5. ~~「`AOS_TICK` 沒設」印 warning~~ 11-06 作廢：沒 tick 是正常狀態（退牆鐘），不印。
6. J1 的巢狀旗標 `--a.b x` 只換 stdin 裡那一葉；鍵本身含 `.` 的只能從 stdin 給。
7. aos-lock 的「改檔案鎖」（使用者已裁）跟租約改 tick 一次做（T2）；S10 的 `acquire --pid N` 死碼項併入。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-逐項落點](01-逐項落點.md) | A～G 每樣：已定／暫定、現況對照、要改哪些檔與條文（搬夾後路徑）、大約多大、跟哪些條文或實作衝突 |
| [02-排程](02-排程.md) | 插不插的裁法（逐項）、今天公司／今晚家機／大重構後三張表、牆鐘估時 |
| [03-方向題](03-方向題.md) | D1 硬凍／軟凍；tick-time Q1～Q5 一行一題；body-protocol 五題只指過去 |
| [04-邊緣狀況](04-邊緣狀況.md) | 凍住、時鐘、非同步呼叫（只補 body-protocol 沒列的）、json-argv 四組 |

## 使用者裁定（11-07，sol 審查；以下取代同題舊代定）

11-07 使用者裁定 sol 審查 #15-2：「15-2B*」——起來後第一拍就照做 ctl.json 裡已有的指令。代定（11-07 落實時，可翻案）：凍住時寫的新 ctl 醒來首拍照做，只有上一份 state 已回音的同 seq 略過。（原話全文見 [wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md](../../../../../wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）
