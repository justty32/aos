# daemon（常駐 kernel）測試。跑法：jpm test 或 janet test/daemon.janet
# 這支是**真的開一個 daemon 背景進程**來測，家開在 /tmp，格間 0.2 秒。
# 不管過不過，最後一定把 daemon 收掉、把 /tmp 的家和 count.txt 刪乾淨（不留背景進程）。
(import ../src/daemon :as d)

(var n 0)
(defmacro check [what form]
  ~(do (++ n) (assert ,form (string "第 " n " 條：" ,what))))

# 測試檔在哪跑都一樣：先把 test/ 的絕對路徑算出來
(def cf (or (dyn :current-file) "test/daemon.janet"))
(def testdir (os/realpath (string/slice cf 0 (last (string/find-all "/" cf)))))
(def counter-dir (string testdir "/fx/k/counter"))     # 每格把 count.txt 加一的資料夾
(def count-file (string counter-dir "/count.txt"))
(def home (string "/tmp/aos-proto4-daemon-test-" (d/self-pid)))
(def iv 0.2)                                           # 一格 0.2 秒，測起來快

(defn count-val
  "count.txt 現在是多少（還沒有就 0）。"
  []
  (if (os/stat count-file :mode) (scan-number (string/trim (slurp count-file))) 0))

(defn cleanup
  "收乾淨：daemon 砍掉、count.txt 刪掉、/tmp 的家整個刪掉。"
  []
  (protect (d/stop home))
  # 保險：stop 萬一沒收到，直接照 pid 砍
  (when-let [pid (d/read-pid home)]
    (protect (os/execute ["kill" "-KILL" (string pid)] :p)))
  (protect (when (os/stat count-file :mode) (os/rm count-file)))
  (protect (os/execute ["rm" "-rf" home] :p)))

(defn body []
  (when (os/stat count-file :mode) (os/rm count-file))   # 上次留下的數字不要接著加

  # ── start／alive? ─────────────────────────────────────
  (check "start 回 true" (d/start home iv))
  (check "start 之後 alive?" (d/alive? home))
  (check "kernel.pid 是數字" (number? (d/read-pid home)))
  (check "requests/done/ 建出來了" (= (os/stat (d/done-dir home) :mode) :directory))

  # ── state.jdn：ls 讀得到、steps 在長 ──────────────────
  (def st (d/read-state home))
  (check "state.jdn 讀得到，第一格已經跑完" (>= (st :steps) 1))
  (check "state.jdn 裡的 pid 就是 kernel.pid" (= (st :pid) (d/read-pid home)))
  (check "state.jdn 記著格間秒數" (= (st :interval) iv))
  (check "還沒登記任何資料夾" (deep= (st :procs) @[]))
  (def s1 ((d/read-state home) :steps))
  (os/sleep 0.8)
  (check "時鐘自己在走：steps 一直在長" (> ((d/read-state home) :steps) s1))

  # ── register：資料夾真的被跑起來 ─────────────────────
  (def r (d/request home (string "(register " (string/format "%j" counter-dir) " \"cnt\")")))
  (check "register 請求 :ok true" (r :ok))
  (check "register 回傳登記好的那個 proc" (= ((r :result) :name) "cnt"))
  (check "dir 是絕對路徑" (= ((r :result) :dir) counter-dir))
  (os/sleep 0.8)
  (def c1 (count-val))
  (check "登記的資料夾每格被跑一次：count.txt 出現了" (> c1 0))
  (os/sleep 0.6)
  (check "count.txt 還在長" (> (count-val) c1))
  (check "ls 看得到它" (= ((first ((d/read-state home) :procs)) :name) "cnt"))

  # ── pause／resume ────────────────────────────────────
  (check "pause 請求 ok" ((d/request home "(pause \"cnt\")") :ok))
  (os/sleep 0.4)                       # 讓可能正在跑的那格結束
  (def c2 (count-val))
  (os/sleep 0.8)
  (check "pause 之後 count.txt 就不長了" (= c2 (count-val)))
  (check "state.jdn 標著 [暫停]" ((first ((d/read-state home) :procs)) :paused))
  (check "resume 請求 ok" ((d/request home "(resume \"cnt\")") :ok))
  (os/sleep 0.8)
  (check "resume 之後又開始長" (> (count-val) c2))

  # ── unregister ───────────────────────────────────────
  (def ru (d/request home "(unregister \"cnt\")"))
  (check "unregister 回傳被拿掉的那個" (= ((ru :result) :name) "cnt"))
  (def rl (d/request home "(ls)"))
  (check "unregister 之後 ls 空了" (deep= (rl :result) @[]))
  (def c3 (count-val))
  (os/sleep 0.6)
  (check "unregister 之後 count.txt 不再長" (= c3 (count-val)))

  # ── 隨便丟一個表達式 ─────────────────────────────────
  (def re (d/request home "(+ 1 2)"))
  (check "請求檔就是一個 Janet 表達式：(+ 1 2) 回 3" (and (re :ok) (= (re :result) 3)))
  (check "done 檔裡留著原文" (= (re :req) "(+ 1 2)"))
  (def rs (d/request home "(steps)"))
  (check "(steps) 拿得到現在第幾格" (and (rs :ok) (> (rs :result) 0)))

  # ── 壞表達式 ─────────────────────────────────────────
  (def rb (d/request home "(這個東西不存在)"))
  (check "壞表達式：:ok false" (not (rb :ok)))
  (check "壞表達式：result 是錯誤訊息" (and (string? (rb :result)) (not (empty? (rb :result)))))
  (check "炸了一個請求，daemon 還活著" (d/alive? home))

  # ── stop ─────────────────────────────────────────────
  (check "stop 回 true" (d/stop home))
  (check "stop 之後 kernel.pid 不見了" (nil? (os/stat (d/pid-file home) :mode)))
  (check "stop 之後 alive? 是 false" (not (d/alive? home)))
  (check "daemon 沒在跑，state.jdn 照樣讀得到" (number? ((d/read-state home) :steps)))
  (def rq (d/request home "(steps)"))
  (check "daemon 沒在跑就不等，請求先放著" (nil? rq))
  (check "那個請求還躺在 requests/ 裡"
         (not (empty? (filter |(string/has-suffix? ".req" $) (os/dir (d/req-dir home))))))

  # ── start 兩次 ───────────────────────────────────────
  (check "停掉之後再 start 起得來" (d/start home iv))
  (def pid-a (d/read-pid home))
  (check "start 兩次，第二次說已經在跑（回 false）" (not (d/start home iv)))
  (check "第二次 start 沒有再開一個：pid 還是同一個" (= (d/read-pid home) pid-a))
  (os/sleep 0.4)
  (check "重開之後剛才躺著的請求被撿起來處理掉"
         (empty? (filter |(string/has-suffix? ".req" $) (os/dir (d/req-dir home)))))

  # ── 被 kill -9 砍掉 ──────────────────────────────────
  (def pid (d/read-pid home))
  (os/execute ["kill" "-KILL" (string pid)] :p)
  (os/sleep 0.4)
  (check "被 kill -9 之後 pid 檔還在（來不及自己清）" (= (d/read-pid home) pid))
  (check "但 alive? 看 /proc 就知道死了" (not (d/alive? home)))
  (check "死掉之後再 start 起得來" (d/start home iv))
  (check "新的 pid 跟被砍掉的不一樣" (not= (d/read-pid home) pid))
  (check "最後再收一次" (d/stop home)))

# 不管過不過都要收乾淨：先 protect 跑完，再 cleanup，最後才把錯誤丟出去
(def [ok err] (protect (body)))
(cleanup)
(unless ok (error err))
(print "daemon：" n " 條全過")
