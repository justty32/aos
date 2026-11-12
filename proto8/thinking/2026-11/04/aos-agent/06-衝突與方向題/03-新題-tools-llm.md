← [回入口 06-衝突與方向題.md](../06-衝突與方向題.md)｜段落：11-04 晚追加 `aos-agent tools`／`llm` 後的題與裁定；`AOS_BRAIN_URL` 與「思考也是 aos 函數」的原文｜上一份：[02-新題-11-04-晚](02-新題-11-04-晚.md)｜下一份：—

### 衝突 3：`tools add`／`llm set` 改定義資料夾，對上 P-15【已答：「改副本。改定義那塊用aos-tools」】

P-15「執行中的一切只寫 `$AOS_STACK`，定義資料夾不被寫」。使用者答「改副本。改定義那塊用aos-tools」：aos-agent 改 stack 裡的副本，「stack 有就用 stack 的」寫成子介面的承諾；落在 [03/01](../03-種類與契約/01-tools-llm-與兩個範本要改什麼.md#副本怎麼運作fable-照原則定的可翻案)。

### 方向題 3：`llm` 走入口（各自一支小程式）還是統一 `.env`？【已答：「一個入口小程式。並且要是aos資料夾函數。可以設計宣告介面。」】

`llm` 的做法同晚照下面「思考也是 aos 函數」的方向改成設定檔宣告（[think-as-function 03 § 4](../../think-as-function/03-呼叫端.md)）；`screen` 是資料夾程式、自己宣告遵守 `aos-agent/screen`。

### 方向題 4：副本要不要跟著定義變？

bob 已有副本之後，人又改了定義，bob 要不要看到。

## 使用者裁定（11-04 晚，選項原文）

方向題 4（副本跟不跟定義）：

> 不跟。風險自行處理。但我們可以給reset。

決定：副本建了就不跟定義變（風險使用者自行處理）；給 `aos-agent tools／llm --target 名字 reset` 刪副本、回去用定義的。

## 使用者原文（11-04 下班後，逐字）：AOS_BRAIN_URL

> AOS_BRAIN_URL，我不喜歡這個環境變數

方向在下一段。

## 使用者原文（11-04 晚，逐字）：方向——思考也是 aos 函數、寄給 llm kernel

> brain url那塊我不喜歡，我希望llm呼叫，或者說思考，這本身也是用aos函數

> 並且可以的話，考慮非同步呼叫，也就是正在跑的loop不停。

> 然後aos llm,tool這兩個，我希望他們的定位是跟aos post一樣，作為基礎工具

> llm呼叫這塊，我希望是把請求丟到llm kernel(一個loop)，處理好後收回信

> 也可以是一個daemon，實際endpoint呼叫就是aos exec

> 包起來的

> 我是希望走2（「包起來的」兩個讀法選 ②：daemon 包在 kernel 的信箱介面後面）

> 除此之外，各種llm設定也可以包裝，這樣寄信的時候只要寫簡單的代號就可以

決定：`AOS_BRAIN_*` 不要；問腦＝寄請求信給 llm kernel、收回信（非同步）；端點／模型／金鑰在 kernel 的定義、包成代號；`aos-llm`／`aos-tools` 是基礎工具。設計在 [think-as-function](../../think-as-function/README.md)；本檔的 `llm` 子介面照那份 [03 § 4](../../think-as-function/03-呼叫端.md) 縮成設定檔宣告＋aos-json 語法糖（可翻案）。
