# proto3-1（Janet）— 世界是 list，求值走 eval

← [設計](notes/2026-09-08-design.md)｜上一版 [proto3](../proto3/README.md)｜Janet 參考 `~/projs/langlab-janet`
｜同一份規格的 Common Lisp 版在 [variant-cl](variant-cl/)

**一個世界＝一個 list（form）＋一個環境（folder）。跑一格＝在那個環境裡 eval 那個 list。**

proto2 的 `.aos/inst` 是「一句 shell，跑完可以把下一句寫回去」；這裡 inst 就是 list，
寫回去就是 `(next 新form)`。所以狀態機不是 `case`，是**form 改寫**：
`(agent-idle)` 求值完把自己換成 `(agent-think)`，再換成 `(agent-wait …)`……
「現在什麼狀態」＝現在的 form 第一個符號，不用另外存 `:state`。

環境就是資料夾：form 裡 `(upscope (def x …))` 定義的東西，下一格還在——**binding 就是檔案**。

## 怎麼跑

```sh
cd proto3-1
janet src/main.janet 8          # 同步走 8 格就停（interval N 的鐘每 N 格才動）
janet src/main.janet async 5    # 非同步：每個鐘一條 fiber 各走各的，5 秒後收
jpm test                        # 55 條測試
```

同步跑出來長這樣（節錄）：

```
  2 observer：agent-1 的 form → agent-think
  3 observer：agent-1 的 form → agent-wait
  4 observer：agent-1 的 form → agent-act
  5 observer：agent-1 的 form → agent-idle

agent-1 的 form 走過：agent-idle → agent-think → agent-wait → agent-act → agent-idle
user 收到：收到：你好，agent-1
```

## 檔案

```
src/world.janet   世界＝環境＋form：make／dotick／at／spawn／kill；信箱；原語綁進環境
src/kernel.janet  時鐘：register／unregister／pause／continue／ls／step-all／run／start／stop-all（跟 proto3 一模一樣）
src/llm.janet     LLM 世界，它的 form 是 (llm-step)；echo-engine、script-engine
src/agent.janet   agent 狀態機＝四段 form 互相改寫；wait-for 把等待條件（純資料）寫進 form，跟 variant-cl 一致
src/main.janet    範例：報時世界、echo LLM、agent-1（兩個小孩）、user、旁觀者
test/basic.janet  55 條：沿用 proto3 的 36 條精神，加上 eval／form 改寫特有的
```

## 跟 proto3 差在哪

| | proto3 | proto3-1 |
|---|---|---|
| 世界是什麼 | table `@{}` | **環境** `(make-env root-env)` |
| 世界的「程式」 | `:func-tick` 一個 Janet 函式 | `:form` 一段 list |
| 跑一格 | 走一遍 table 的元素，叫 `:func-tick` | **`(eval (w :form) w)`** |
| 下一格跑什麼 | 都一樣，函式自己看 `:state` 分支 | `(next 新form)` 把 `:form` 換掉 |
| agent 狀態機 | `(case (a :state) :idle … :think …)` | 四段 form 互相改寫，狀態＝form 的頭 |
| 「等待」帶在哪 | `:waiting` 一張表 | 帶在 `(agent-wait until then timeout since)` 這個 list 裡：until 是純資料（`[:llm-result id]`／`[:mail]`），then 是原語符號（如 `agent-got-llm`），逾時一律回 `(agent-idle)`（沒有 else，跟 variant-cl 的 `agent-wait` 一致） |
| 跨格的狀態 | `(put w :k v)` | 一樣可以，另外多了 `(upscope (def x …))` 寫進環境 |
| 生小孩 | `world/spawn` | form 裡 `(kid "名" '(…))`／`(kid "名" :own '(…))`；spawn 也還在 |
| 小孩第一格 | spawn 完那格就跟著走 | `kid` 生出來的那格還不動，下一格才開始（先走小孩再 eval form） |
| kernel／llm／信箱／會計 | — | 沒動，一模一樣 |

## 寫的時候踩到的坑

1. **`(do (def x 1) …)` 的 x 不會留在環境裡**，它只是那個區塊的區域變數；`eval` 是把整個 form 編成一支函式，
   只有**最上層**的 `def` 才寫得進 env。要跨格留著就用 `(upscope (def x 1) …)`——`upscope` 跟 `do` 一樣按順序跑，
   但不開新 scope。測試「form 裡 (def x …) 存進世界自己的環境」那條就是被這個絆倒的，旁邊留了一條反面的把它記著。
2. **eval 出來的碼看不到你這邊的 env**：`(fiber/getenv (fiber/current))` 拿不到傳給 `eval` 的那張表。
   所以原語只能用閉包綁進去：`(put env 'next @{:value (fn [f] …)})`。world.janet 的 `install` 做的就是這件事。
3. **原語 `next` 蓋掉核心的 `next`**（序列迭代那個）。這是規格指定的名字，就接受了；form 裡想迭代請用別的。
   順帶查過 `root-env` 只有 5 個 keyword 鍵（`:syspath :args :pretty-format :executable :peg-grammar`），
   我們拿 `:path :form :now :inbox …` 當世界的欄位不會撞到。
4. **模組內的前後順序**：`make` 要把 `spawn`／`kill` 綁進世界的環境，可是這兩個得等 `make` 定義完才寫得出來。
   用 `(var- spawn-fn nil)` 前向參考、檔案最後 `(set spawn-fn spawn)` 收尾。
5. **同步模式鐘的先後順序不保證**（`clocks` 是 hash table）。proto3 跑起來旁觀者剛好排在 agent 前面，
   這一版剛好排在後面，於是開場的 `agent-idle` 就被漏看了。解法：旁觀者一開始先把當下的 form 記進 chain，
   之後只記「變了」的。main 和測試都這樣做，兩邊就都穩了。
6. `=` 比 array 是比身分不是內容（tuple 才是比內容），測試一律用 `deep=`——proto3 的老教訓，這版照樣受用。
7. **`agent-wait` 的等待條件本來是塞兩個 closure 進 form**（`until`／`then` 都是 `(fn [a] …)`），
   跟 variant-cl 的 `agent-wait` 對不起來——CL 那邊 `until` 是純資料（`(:llm-result id)`），靠 `wait-check`
   照 `(first until)` 分派；`then` 是函式名符號，`funcall` 叫。改成一樣的做法之後才發現一個小雷：
   `[:llm-result id]` 這種字面值求值完是 **parens 型**tuple（不是想像中的 brackets 型），
   照樣塞回 form 裡、下一格再 eval 一次，會被誤當成呼叫（`(:llm-result 3)` 變成「拿 3 的 :llm-result 欄位」）。
   解法：`wait-for` 存進 form 前用 `(tuple/brackets ;until)` 轉成 brackets 型，再 eval 才會被當純資料字面值。
   `then` 那格因為是裸符號，eval 時 Janet 自己就會把它解析成綁在 agent 環境裡的原語函式，等於 CL 版的 `funcall`，
   不用另外處理。

## 還沒做（刻意，同 proto3）

存磁碟、接 proto2 的 Python 工具包、team／預算、agent 之間交流、真的 LLM 引擎、
agent 狀態機的完整版（重送／卡住／每題上限）。
