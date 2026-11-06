# 2026-11-06 早 信件 body 與「可選的非同步呼叫協議」（body-protocol，fable 規劃，沒改程式）

← [2026-11-06](../README.md)｜[thinking](../../../README.md)｜源頭：[11-05 fs-image](../../05/fs-image/README.md)（信封＝IPC、body 不多限制）、[fs-image 02 非同步呼叫原文](../../05/fs-image/02-非同步呼叫原文.md)（對照 JSON-RPC、暫定）｜相關：[json-argv](../../05/json-argv/README.md)（argv＝method、stdin JSON＝input、`_tooldef.json`）、[no-pid](../../05/no-pid/README.md)（寄信不回＝呼叫失敗、共用回信信箱）、[kernel-daemon 08](../../05/kernel-daemon/08-實作結果.md)（llm kernel＝現成的「收信→跑→回信」）、[think-as-function 02](../../04/think-as-function/02-設計-信與kernel.md)（11-04 把 inst 從信裡拿掉）、[stdio-unify](../../05/stdio-unify/README.md)（三扇門）、[tick-time](../../05/tick-time/README.md)

使用者 11-06 早：「body這塊，我一時之間也想不出來……你先再派個fable去幫我想想吧。」本夾只記使用者原文、fable 照原則推出的結論與選項、未決。另一位 fable 同日在 `apply-ideas/` 想「怎麼落到現況」，會參考本夾；本夾不排程、不碰那邊。

## 使用者裁定（11-06，原話）

> 四題都按照推薦。然後我這邊要提點一句，就是說，好比ISO網路七層架構，封包是被一層層包起來。我們這邊也是，我們的非同步呼叫，就是透過aos-post這東西包起來去做。但aos-post本身他就只是普通的收發信協議，body內有啥他不管。非同步呼叫則是藉助aos-post去實現它的功能。所以不要去與aos-post耦合太深。當然，如果aos-post有需要改的地方也可以改，畢竟現在是demo階段，而aos-post目前最重要的用途就是這個非同步呼叫。

**已裁**：題 1～4 照推薦（一箱一函數、body＝函數 stdin JSON；看不懂 body 有 `reply_to` 就回錯誤信、信封壞照舊不回；回信＝stdout 原樣／頂層 `error`；進度先讀信資料夾的窗）。題 5（通用 runner 何時做）apply-ideas 代答「大重構後、P6 之後」，使用者照排程同意。

**分層（照他的提點）**：三層、各管各的——
1. **aos-post**＝收發信協議：信封（`sender`、`sent_at`、`reply_to`、`in_reply_to`）＋送達（四格、認領、撤回、回信照 `reply_to` 投）；**body 內有啥它不管**。
2. **非同步呼叫層**（收信→跑→回信的 runner；kernel、判官、daemon ctl 現在各自做的那段）：body＝函數 stdin、stdout＝回信、看不懂回 `{"error"}`、`ping`、進度怎麼看——**本夾所有規則都在這一層**，aos-post 一條都不認。
3. **函數**：只看 stdin、只寫 stdout／stderr／結束碼（三扇門），不知道自己是被信叫的。

本夾原稿有三處字眼容易讀成「塞進 aos-post」，已改：② 的「N-16 決定 27 要加註分層」→ N-16 不改、錯誤回信是第 2 層自己的規則；`ping` 的「信箱層保留字」→ 第 2 層 runner 的保留字，aos-post 不認；衝突 2、4 同步改字。aos-post 真的可以順手改的列在最後一節，都是選用、沒有一條是推薦方案的前提。

## 一句話結論

**信封照舊只管送達；「非同步呼叫」不必在 body 裡放協議欄位——一個信箱就是一個 aos 函數，body 就是那個函數的 stdin JSON，回信就是它的 stdout（出錯＝`{"error": {"code", "msg"}}`，代號照三扇門錯誤行）。** 現在三個會回信的收信者（daemon ctl 信箱、llm kernel、判官）早就是這個形狀；「body 直接就是 inst」留成一種特例信箱（專門跑別人單子的沙箱 worker 才開），不當通則。支不支援不用看 PATH：收信者把什麼函數接在信箱後面，就支援什麼；要分權就多開信箱，一箱一函數。

## 使用者已定的（11-05 夜，字句照原話；整理版全文見 [fs-image](../../05/fs-image/README.md)、[fs-image 02](../../05/fs-image/02-非同步呼叫原文.md)）

- 「信件是IPC手段，然後我們的"非同步呼叫aos函數"又是基於這個手段的。body內部的json格式我們不多做限制，因爲不管是寄信收信，body的處理都是依靠當初規定這份json格式的人去處理的」
- 「想想看json-rpc，他有的，我們的aos-exec/inst格式也有了……基於aos-post這塊(在json外包着的)」「主要在body內」
- 暫定（他自言「可能思慮不周，明天再說」）：「body應該自由設定。只是說有需要的話，可以遵從非同步呼叫這套協議，如果遵從的話，那body就是inst，是否支援，就看接收者那邊的PATH有沒有相關東西(這好像不太好)，至於權限這塊...能寫檔就有權限，頂多多弄幾個mailbox分權。直接就是inst吧。長時間呼叫回報進度，這套就自己做，我們之後有需要的話再往上疊。」
- 另兩條已定、本夾直接沿用：「寄信不回，等同於呼叫失敗」（11-05 晚，[no-pid](../../05/no-pid/README.md)）；「寄信收信是我們aos的非同步呼叫的底層機制」（同）。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-對照表](01-對照表.md) | JSON-RPC 的 method／params／id／result／error／notification／batch ↔ aos 現有的東西；哪些有、哪些缺；現成三個收信者的 body 形狀 |
| [02-三個口子](02-三個口子.md) | ① 「看 PATH」不好在哪、三個替代（信箱即能力／直接寄 inst／清單檔）——每個選項一句白話＋一封信長什麼樣＋後果，推薦放第一 |
| [02-三個口子-續](02-三個口子-續.md) | ② 看不懂 body 回不回（錯誤回信／只靠不回／JSON-RPC 式包一層）；③ 長時間呼叫的進度（讀窗／進度信／掛 proc） |
| [03-邊緣與衝突](03-邊緣與衝突.md) | 邊緣狀況（寄到一半、收信方睡著／凍住、重複投遞、回信寄不回、body 是 inst 的注入與沙箱、大 body、回信寄給自己、`ping`…） |
| [03-邊緣與衝突-續](03-邊緣與衝突-續.md) | 跟現行實作／條文的衝突表 10 條 |
| [04-方向題與aos-post可改](04-方向題與aos-post可改.md) | 五題方向題全文（11-06 已裁）；aos-post 可以改的地方（全部選用）與明寫不改的 |

## 方向題（11-06 已裁：題 1～4 照推薦；題 5 照 apply-ideas 排程）

五題的選項、後果與推薦全文在 [04](04-方向題與aos-post可改.md)。一行版：① body＝一箱一函數的 stdin JSON；② 看不懂 body 有 `reply_to` 就回錯誤信、信封壞不回；③ 回信＝stdout 原樣／頂層 `error`；④ 進度先讀信資料夾的窗；⑤ 通用 runner（暫名 aos-serve）大重構後、P6 之後。

## 衝突一覽（細節在 [03-續](03-邊緣與衝突-續.md)）

11-04 決定「kernel 不替人跑單子、信裡不帶 inst／env」↔ 暫定「body 直接就是 inst」；N-16 決定 27「壞信不通知寄信人」↔ ② 錯誤回信（第 1 層不回、第 2 層回，N-16 不改）；C-52 准讀下層 stderr 的例外表只有三處 ↔ 通用 runner 把函數的錯誤行變成錯誤回信（要加第 ④ 處）；no-pid 代定的 `{"ping": true}` 是 body 裡唯一的保留字 ↔ 一箱一函數時 body 全是函數的輸入（第 2 層接掉、aos-post 不認）。

## aos-post 可以改的地方

全部選用、推薦方案不靠任何一條，列在 [04](04-方向題與aos-post可改.md)：`send` 附檔口、`take`／`see --in-reply-to`、`sent_tick`（tick-time 的題）；明寫**不改**的：不加協議標記、不認 `ping`、不驗 body、不管回信形狀、不做去重與進度。
