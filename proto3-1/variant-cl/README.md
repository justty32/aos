# variant-cl — 世界是 list、求值走 eval 的 Common Lisp 版（SBCL）

← [proto3-1/README](../README.md)｜規格 [notes/2026-09-08-design](../notes/2026-09-08-design.md)｜上一版 [proto3/variant-cl](../../proto3/variant-cl/README.md)

一個世界＝**一個 list（form）＋一個資料夾**。跑一格＝在那個資料夾裡 `eval` 那個 list。
下一格要跑什麼，由 form 自己用 `(next 新form)` 寫回去——所以 agent 的狀態機不是 `case`，
是 **form 改寫**：`(agent-idle)` → `(agent-think)` → `(agent-wait …)` → `(agent-act)` → `(agent-idle)`。
只用 SBCL 標準庫加 `sb-thread`，不裝任何套件（這台是 SBCL 2.2.9）。

## 怎麼跑

```sh
cd proto3-1/variant-cl
sbcl --script test/basic.lisp          # 44 條測試
sbcl --script src/main.lisp 8          # 同步走 8 格
sbcl --script src/main.lisp async 5    # 非同步跑 5 秒（一鐘一 thread）
```

## 檔案

```
src/package.lisp   套件 :aos
src/load.lisp      照順序載入 src/*.lisp（main／test 都 load 這支）
src/world.lisp     世界（list＋資料夾）、dotick＝eval、form 裡的原語、信箱、kid
src/kernel.lisp    時鐘：同步 step-all／run、非同步 start（thread）
src/llm.lisp       LLM 世界（它的 form 就是 (llm-step)）＋兩個假 engine
src/agent.lisp     agent：四個 form 互相改寫，加 wait-for
src/main.lisp      範例（跟 proto3 同一個劇情）
test/basic.lisp    proto3 的 36 條 ＋ eval 特有的 8 條
```

## 跟 proto3/variant-cl 差在哪

| 概念 | proto3/variant-cl | proto3-1/variant-cl（這版） |
|------|-------------------|------------------------------|
| 世界怎麼跑一格 | 走一遍 key，看到 `:func-tick` 就 `funcall` | `(eval (w-get w :form))` |
| 下一格跑什麼 | 改 `:state` 欄位，`func-tick` 裡 `case` 分岔 | `(next '(新form))`，form 改寫自己 |
| 現在是什麼狀態 | `(w-get a :state)` | `(state-of a)`＝form 的第一個符號 |
| 跨格的狀態 | closure 抓變數／欄位 | `(var 'x)`／`(setvar 'x v)`，寫進自己的資料夾 |
| 原語怎麼拿到「自己」 | 每個都吃 `w`：`(say w x)`、`(send-mail from to x)` | 全看動態變數 `*me*`：`(say x)`、`(send path x)`、`(mail)` |
| 在 form 外面用原語 | 直接傳 `w` | `(with-world w (send "b" "hi"))` |
| 生小孩 | `(spawn parent name :func-tick …)`，事先建 | `(kid "name" form)` 寫在 form 裡，第一次求值時建 |
| 等待 | `wait-for` 把 until／then 兩個 closure 存進 `:waiting` | `wait-for` 把它們變成資料，塞進 `(agent-wait '(:llm-result 3) 'agent-got-llm 30 2)` 這個 form |
| 鐘怎麼存 | hash table（走格順序看 hash） | list，照登記順序（走格順序才是確定的） |
| 測試 | 36 條 | 44 條（36 條照搬＋8 條 eval 特有） |

名字沿用上一版：`make-world`／`dotick`／`world-at`／`kill`、
`register`／`unregister`／`pause`／`resume`／`ls`／`step-all`／`run`／`start`／`stop-all`、
`make-llm`／`ask`／`echo-engine`／`script-engine`、`make-agent`／`wait-for`。
`make-world` 多吃一個參數（form），`spawn`／`take-mail`／`send-mail` 換成 form 裡的 `kid`／`mail`／`send`。

## CL 沒有一等環境，這件事怎麼處理、代價是什麼

Janet 那邊一格是 `(eval form env)`：env 是一等的資料夾，form 裡 `(def x 1)` 就是在資料夾裡放一個檔案，
下一格還在。**CL 的 `eval` 只吃一個參數，沒有地方塞環境**（`*package*` 不是環境，`(let ((x …)) (eval …))`
的 lexical binding 也進不了 eval）。所以這版照規格用動態變數：

```lisp
(let ((*me* w) (*next-form* '%none))     ; dotick 裡
  (eval (w-get w :form)))
```

`*me*` 就是「現在誰在跑」，`me`／`now`／`var`／`setvar`／`say`／`send`／`mail`／`kid`／`kill`／`next`
全是普通函式，內部去看 `*me*`。代價老實說有四個：

1. **狀態要用 `(var 'x)`／`(setvar 'x v)`，不能用 `(let …)` 或 `(defvar …)`。**
   form 裡寫 `(setvar 'acc 3)` 而不是 `(def acc 3)`——多一層引號、多一次手寫的查表。
   換句話說：Janet 版是「語言的 binding 就是資料夾裡的檔案」，CL 版是「我自己拿 hash table 演一個」。
2. **同一時間只能有一個世界在求值。** `*me*` 是全域的動態綁定，所以非同步模式下所有鐘的求值都得搶
   同一把 `*tick-lock*`——一鐘一 thread 但實際上是排隊跑。Janet 的 fiber 本來就協作式，這條差別不明顯，
   但 CL 這邊是「本來可以真並行、被環境的做法逼回單線」。
3. **form 裡的符號一定要在 `:aos` 套件裡。** `'(agent-idle)` 在 `:aos` 的檔案裡讀進來才是 `AOS::AGENT-IDLE`；
   從字串讀要自己 `(let ((*package* (find-package :aos))) (read-from-string …))`。
   一等環境本來會順便帶名字解析，這裡得手動顧。
4. **巢狀求值要靠動態綁定自己解決。** 小孩 `dotick` 會再綁一次 `*me*`／`*next-form*`，靠 unwind 還原。
   能動，但「誰是 me」這件事變成隱形的，讀 code 時要記得它在。

換來的好處是真的有：**form 是純資料**，`(agent-wait '(:llm-result 3) 'agent-got-llm 30 2)` 印出來就看得懂
它在等什麼、等到了要叫誰、幾格放棄——`state-of` 只是 `(car form)`，observer 不用問 agent 任何事。
proto3 那版的 `:waiting` 裡放的是兩個 closure，印出來只有 `#<FUNCTION>`。

## 寫的時候踩到的

- **`wait-for` 不能直接把 closure 包進 form。** SBCL 的 `eval` 其實會讓函式物件自我求值（`(funcall #<FN> …)`
  跑得起來），所以「塞得進去」；但塞進去以後 form 就不再是印得出來、讀得回來的資料了，
  form 改寫這招最大的好處就沒了。改成 until 用描述（`'(:llm-result 3)`）、then 用函式名（`'agent-got-llm`），
  由 `wait-check` 去解讀。
- **鐘存在 hash table 裡，同步走格的順序不確定。** 這版狀態機一格只換一個 form，
  如果 observer 的鐘剛好排在 agent 後面，`agent-wait` 那一格就會被跳過看不到。把 `*clocks*` 改成
  照登記順序的 list，observer 登記在第一個，才穩定印得出 IDLE → THINK → WAIT → ACT → IDLE。
- **`stop-all` 一個一個 join，等待會累加。** 五個鐘、interval 1 秒，`async 5` 跑完要花 10 秒才退出
  （每個 thread 最多還要睡完手上那一秒）。改成先把全部狀態設 `:stopped`、再一個一個 join，就變 6 秒。
- **`(next f)` 的「沒叫過」不能用 `nil` 表示。** `nil` 是合法的 form（沒有 form 的世界＝idle），
  所以 `*next-form*` 用 `'%none` 當哨兵。
- **這格才生出來的小孩不該同一格就跟著走。** `dotick` 先把 `:kids` 拍成快照再 eval，
  `(kid "k" '(…))` 第一次求值只建立，下一格才開始跟著父走。
- **`continue` 是 CL 內建符號、SBCL 有 package lock**，不能拿來當函式名 → 沿用上一版的 `resume`。
- **thread 的 lambda 不能共用 loop 變數**（全部會抓到同一個、迴圈結束後是 nil），`start` 裡要 `let` 一份新的。
