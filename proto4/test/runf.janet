# 資料夾模擬 lisp。跑法：jpm test 或 janet test/runf.janet
(import ../src/runf :as r)
(use ../src/runf)   # 拿到 runf 巨集

(var n 0)
(defmacro check [what form]
  ~(do (++ n) (assert ,form (string "第 " n " 條：" ,what))))

# 測試檔在哪跑都一樣：先切到 test/fx
(def cf (or (dyn :current-file) "test/runf.janet"))
(def fx (os/realpath (string (string/slice cf 0 (last (string/find-all "/" cf))) "/fx")))
(os/cd fx)
(def start (os/cwd))

# ── 基本：跑一個資料夾 ──
(def h (runf (./hello 1 2)))
(check "inst 最後一個值就是回傳值" (= (h :said) "hi from hello"))
(check "跑的時候工作目錄在那個資料夾裡" (= (h :cwd) (string start "/hello")))
(check "參數傳進去了" (deep= (h :args) [1 2]))
(check "跑完工作目錄切回來" (= (os/cwd) start))
(check "路徑用字串也行" (= ((runf "./hello") :said) "hi from hello"))
(check "沒參數 args 是空 tuple" (deep= ((runf (./hello)) :args) []))

# ── 一層叫一層 ──
(check "資料夾裡可以再 runf 子資料夾，路徑相對於自己"
       (deep= (runf (./outer)) [:outer 30 40]))
(check "巢狀跑完工作目錄也切回來" (= (os/cwd) start))

# ── inst 路徑可以設定 ──
(check "預設是 .aos/inst" (= (r/inst-path) ".aos/inst"))
(check "with-dyns 改一段，子孫沿用"
       (deep= (with-dyns [:inst-path "my-inst"] (runf (./alt))) [:alt "my-inst" :sub-ok]))
(check "with-dyns 結束就恢復預設" (= (r/inst-path) ".aos/inst"))
(setdyn :inst-path "my-inst")
(check "setdyn 全域改" (deep= (runf (./alt)) [:alt "my-inst" :sub-ok]))
(setdyn :inst-path nil)
(check "設回 nil 就回預設" (= ((runf (./hello)) :said) "hi from hello"))

# ── 出錯 ──
(defn fails? [f] (not (first (protect (f)))))   # protect 回 [true 值] 或 [false 錯誤]
(check "資料夾不存在 → error" (fails? |(runf (./nope))))
(check "資料夾有但沒 inst → error" (fails? |(runf (./alt))))     # alt 沒有 .aos/inst
(check "inst 自己炸 → error 往外丟" (fails? |(runf (./boom))))
(check "炸了工作目錄還是切回來" (= (os/cwd) start))
(check "資料夾不在：訊息帶路徑" (string/find "./nope" (get (protect (runf (./nope))) 1)))
(check "inst 不在：訊息帶 inst 檔名" (string/find "alt/.aos/inst" (get (protect (runf (./alt))) 1)))

(print "runf：" n " 條全過")
