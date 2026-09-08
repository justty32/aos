# kernel（時鐘）測試。跑法：jpm test 或 janet test/kernel.janet
(import ../src/kernel :as k)

(var n 0)
(defmacro check [what form]
  ~(do (++ n) (assert ,form (string "第 " n " 條：" ,what))))

# 測試檔在哪跑都一樣：先切到 test/fx
(def cf (or (dyn :current-file) "test/kernel.janet"))
(def fx (os/realpath (string (string/slice cf 0 (last (string/find-all "/" cf))) "/fx")))
(os/cd fx)
(def start (os/cwd))

# 計數器那格會留檔案，先清掉，不然上次跑的數字會接著加
(when (os/stat "k/counter/count.txt" :mode) (os/rm "k/counter/count.txt"))

# ── 登記 ──────────────────────────────────────────────
(def K (k/new))
(check "新 kernel 沒東西、格數 0" (and (empty? (k/ls K)) (= (K :steps) 0)))
(def pa (k/register K "./k/a"))
(check "name 預設＝路徑最後一段" (= (pa :name) "a"))
(check "interval 預設 1" (= (pa :interval) 1))
(check "剛登記：沒暫停、跑了 0 次、沒錯誤" (and (not (pa :paused)) (= (pa :runs) 0) (nil? (pa :error))))
(check "register 回傳那個 proc，也放進 procs" (= (get (K :procs) "a") pa))
(def pb (k/register K "./k/b" "zz"))
(check "name 可以自己取" (= (pb :name) "zz"))
(def pb2 (k/register K "./k/b" "zz" 5))
(check "同名重登記＝覆蓋，不會變兩個" (and (= (length (k/ls K)) 2) (= (get (K :procs) "zz") pb2)))
(check "覆蓋後拿到新的設定" (= (pb2 :interval) 5))
(k/register K "./k/b" "zz")   # 換回 interval 1，後面比較好算

# ── ls 排序 ───────────────────────────────────────────
(k/register K "./k/a" "m")
(check "ls 照 name 排序（table 順序不固定，要排過）"
       (deep= (map |($ :name) (k/ls K)) @["a" "m" "zz"]))
(k/unregister K "m")

# ── 走一格 ────────────────────────────────────────────
(def did (k/step K))
(check "step 回傳這格跑了誰（照 name 排序）" (deep= did @["a" "zz"]))
(check "步數前進" (= (K :steps) 1))
(check "跑成功：runs 加一、:last 存回傳值" (and (= (pa :runs) 1) (deep= (pa :last) [:a 1])))
(check "inst 裡 (first args) 就是現在第幾格" (= (last (pa :last)) 1))
(k/step K)
(check "第二格 args 就變 2" (= (last (pa :last)) 2))
(check "跑完工作目錄切回來" (= (os/cwd) start))

# ── interval：每 N 格才跑一次 ─────────────────────────
(def K2 (k/new))
(k/register K2 "./k/a")            # 每格
(k/register K2 "./k/b" "b2" 2)     # 每兩格
(check "第 1 格只有 interval 1 的跑" (deep= (k/step K2) @["a"]))
(check "第 2 格兩個都跑" (deep= (k/step K2) @["a" "b2"]))
(check "第 3 格又只剩一個" (deep= (k/step K2) @["a"]))
(check "四格下來：interval 1 跑 4 次、interval 2 跑 2 次"
       (do (k/step K2)
           (and (= ((get (K2 :procs) "a") :runs) 4)
                (= ((get (K2 :procs) "b2") :runs) 2))))

# ── pause／resume／unregister ─────────────────────────
(k/pause K2 "a")
(check "暫停的不跑，也不出現在回傳裡" (deep= (k/step K2) @[]))
(check "暫停期間 runs 不動" (= ((get (K2 :procs) "a") :runs) 4))
(k/resume K2 "a")
(check "resume 就再跑" (deep= (k/step K2) @["a" "b2"]))
(k/unregister K2 "a")
(check "unregister 後登記表裡沒它了" (nil? (get (K2 :procs) "a")))
(check "unregister 後那格就不跑它" (not (find |(= $ "a") (k/step K2))))
(check "動不存在的名字不會炸" (and (nil? (k/pause K2 "沒這個")) (nil? (k/unregister K2 "沒這個"))))

# ── 出錯：記著、別人照跑、下一格成功就清掉 ────────────
(def K3 (k/new))
(k/register K3 "./k/flaky")
(k/register K3 "./k/a")
(k/step K3)                        # 第 1 格：奇數 → flaky 炸
(def pf (get (K3 :procs) "flaky"))
(check "inst 炸了：:error 記著訊息" (and (string? (pf :error)) (string/find "奇數格炸" (pf :error))))
(check "炸掉的 runs 不加、:last 還是 nil" (and (= (pf :runs) 0) (nil? (pf :last))))
(check "有人炸，kernel 不停、別人照跑" (= ((get (K3 :procs) "a") :runs) 1))
(check "炸掉的也算「這格有跑到」" (deep= (k/step K3) @["a" "flaky"]))   # 第 2 格：偶數 → 好
(check "下一格成功：error 清掉、runs 加、:last 有值"
       (and (nil? (pf :error)) (= (pf :runs) 1) (deep= (pf :last) [:flaky 2])))
(check "炸完工作目錄還是切回來" (= (os/cwd) start))

# ── run：連走 N 格 ────────────────────────────────────
(def K4 (k/new))
(k/register K4 "./k/a")
(check "run 回傳走了幾格" (= (k/run K4 5) 5))
(check "run 之後步數對" (= (K4 :steps) 5))
(check "run 之後 runs 對" (= ((get (K4 :procs) "a") :runs) 5))
(check "run 可以接著再跑" (do (k/run K4 2 0) (= (K4 :steps) 7)))
(check "run 跑完 :running 是 false" (not (K4 :running)))
(def t0 (os/clock))
(k/run K4 2 1)   # 兩格、格間睡 1 秒 → 至少 2 秒
(check "run 的 interval 真的有睡（2 格 × 1 秒 ≥ 2 秒）" (>= (- (os/clock) t0) 2))
(k/stop K4)
(check "stop 把 :running 關掉（無限跑時下一格就停）" (false? (K4 :running)))

# ── 資料夾自己存狀態：計數器 ──────────────────────────
(def K5 (k/new))
(k/register K5 "./k/counter")
(k/run K5 3)
(check "inst 自己 spit 檔案留狀態：跑 3 格後 count.txt 是 3"
       (= (string/trim (slurp "k/counter/count.txt")) "3"))
(check "kernel 拿到的 :last 也是 3" (= ((get (K5 :procs) "counter") :last) 3))
(os/rm "k/counter/count.txt")

(print "kernel：" n " 條全過")
