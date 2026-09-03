# inst 鏈是語法糖：薄的 `.aos` 與厚的 `.aos`

← [nested-eval-car](nested-eval-car.md)｜[nested-eval](nested-eval.md)｜[program-form](program-form.md)｜[ideas](README.md)

**本檔是 [nested-eval-car](nested-eval-car.md) 的續節**（2026-09-03）——「資料夾＝operative」
裁定之後，使用者接著看出 `.aos` 內那條 inst 鏈的地位變了。**裁決見文末
[「裁決（2026-09-03）」節](#裁決2026-09-03)，其餘為使用者觀察與 AI 觀察**（可否決）。

## 使用者觀察（2026-09-03）

> inst 攤平 接力棒 out/這些，在這種情況下，它就變成一種語法糖。因為複雜的邏輯可以直接託付給子資料夾

## AI 觀察（非裁決，可否決）

### a. 意思上同意：`.aos` 不能省的只剩兩樣

1. **原子 inst**——工具呼叫、LLM 呼叫。它們**不是資料夾**，無法再往下託付，是**底**。
2. **開／讀／選**——開一個子資料夾、讀它的 `out/`、決定下一個開誰。

其餘全部可以改寫成「**每步一個子資料夾**」：inst 鏈、攤平、接力棒、`out/` 的中間值。
對應 lisp：**special form 只有幾個，其餘都是 macro 疊出來的糖。**

### b. 成本上不是糖

開一個子資料夾＝**生一個行程**：至少多一輪、多 token、多一分不確定；而 `.aos` 內一串 inst
是**內聯**。跟 C 的「函數呼叫 vs 內聯」一樣——**意思相同，成本不同**。這正落在
[os-metrics-and-resources](os-metrics-and-resources.md) 的三指標（金錢、可預測性）與
[nested-eval §e](nested-eval.md)「深度＝幾輪回不來」那條邊界上。**兩種寫法都要留，依情況選。**

### c. 接力棒沒消失，只是搬家

父層仍然得記「**開過誰、下一個開誰**」——接力棒變成**資料夾層級的短接力棒**，不是不見了。
誘人的省法是「看檔案系統就好」（子資料夾有 `out/` ＝做完）；但再走一步變成「**材料齊了就
跑**」，那就是 **Make 的模型**，等於回到 **applicative**（先算引數），與剛裁的「父層點名才開」
**相反**。所以**父層那條短的要留**，能省的只是 `.aos` 內那條細的。

### d. `.aos` 會有兩種長相

**薄的**（只做開／讀／選，邏輯全在子資料夾）與**厚的**（一整串 inst）。**今天的 aos 只有厚
的，薄的不存在**——這大概就是 `G14`（載入器）那格真正缺的東西。先記著，不動手
（使用者已裁「先停下設計、去用現有的東西玩」）。

## 裁決（2026-09-03）

> 喔天啊，這套模型太棒了！你說的對，inst語法糖就是為了省成本而做的

**inst 鏈（攤平、接力棒、`out/` 中間值）是為了省成本而存在的語法糖，不是本體。**
本體是「原子 inst ＋ 開／讀／選」那兩樣。

## AI 觀察續（非裁決，可否決）

### e. 攤平＝內聯

C 語言線的 **源碼 json → flatten → inst 鏈**（[assembly-and-chains/compile-pipeline](assembly-and-chains/compile-pipeline.md)），
用本節的話講就是：**把「本來要開子資料夾才做的事」壓進 `.aos` 直接走**，省掉生行程的那幾輪。

### f. 編譯器在這套模型裡只做一件事

**判斷哪些子資料夾可以安全地壓成 inst 鏈。** 壓得越多越便宜，但越看不見——
**金錢與人類可理解性在這裡拉鋸**，編譯器就是**調那個旋鈕的人**
（接 [os-metrics-and-resources](os-metrics-and-resources.md) 的三指標）。

### g. 兩種 `.aos` 於是有名字

**薄的＝未編譯，厚的＝編譯過。** 今天的 aos 只有編譯過的那種，所以攤平**看起來**像繞不開的
本體——其實它是**最佳化**。

## 相關

- [nested-eval-car](nested-eval-car.md)——本檔的上游：`.aos` 是 car、資料夾＝operative、
  子資料夾跑不跑由父 `.aos` 決定、頂層由使用者或 daemon 開
- [nested-eval](nested-eval.md)、[program-form](program-form.md)——更上游的兩篇
- [assembly-and-chains/compile-pipeline](assembly-and-chains/compile-pipeline.md)——寫→編譯→
  執行三段式生產線，本節給了「編譯」一個新職責
- [os-metrics-and-resources](os-metrics-and-resources.md)——金錢／可預測性／人類可理解性
- [cpu-to-os-gaps](cpu-to-os-gaps.json)——`G14`（載入器：薄的 `.aos` 還不存在）
