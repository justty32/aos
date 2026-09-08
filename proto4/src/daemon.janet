# daemon＝一個常駐進程裡跑著一個 kernel（時鐘），外面的人用「丟檔案」跟它講話。
#
# 跟 proto2 的 daemon 不一樣：proto2 一個世界一個 aos-loop 進程、暫停用 SIGSTOP；
# proto4 只有一個進程、一個 kernel，所有資料夾都在它裡面用 kernel/step 推，暫停就是 kernel/pause。
#
# daemon 的家（home）是一個資料夾，第一次 start 自己建，裡面：
#   kernel.pid    daemon 進程的 pid（進程死了檔案可能還在，所以 alive? 要看 /proc/<pid>/stat）
#   state.jdn     每格結束後寫一次的快照（Janet 資料）：
#                 {:pid :steps :interval :updated <epoch 秒> :procs [{:name :dir :interval :paused :runs :error :last} …]}
#                 ls 就是讀這個檔，所以 daemon 沒在跑也看得到上次的樣子
#   kernel.log    daemon 的 stdout／stderr（只印請求結果和 proc 炸掉的那行，不是每格一行）
#   requests/     請求檔 <毫秒時間戳>-<丟的人 pid>-<流水號>.req（副檔名不是 .janet，免得被當模組）
#   requests/done/  處理完的搬來這裡（同檔名），內容換成 {:req 原文 :ok true/false :result …}
#
# 請求檔的內容是**一個 Janet 表達式**（延續「資料夾模擬 lisp」的味道）。daemon 在一個
# 綁好 kernel 操作的環境裡 eval 它，回傳值就是 result。環境裡有（都已經把 kernel 帶進去）：
#   (register dir &opt name interval)  (unregister name)  (pause name)  (resume name)
#   (ls)  (steps)  (stop)  (set-interval sec)
# dir 一律要絕對路徑——daemon 的 cwd 跟客戶端不一樣，客戶端送之前自己 os/realpath。

(import ./kernel)

(var- req-seq 0)   # 同一個進程裡連丟兩個請求，檔名靠這個序號分開

(def this-file
  "本檔的絕對路徑。start 要拿它去開背景進程（janet <本檔> run <home>）。
   :current-file 是相對於載入當下的 cwd，所以在這裡（載入時）就先轉絕對。"
  (os/realpath (or (dyn :current-file) "src/daemon.janet")))

# ── 小工具 ────────────────────────────────────────────

(defn self-pid
  "自己的 pid。Janet 沒有 os/pid，讀 /proc/self/stat 的第一欄（pid 在 comm 前面，不會被空白坑到）。"
  []
  (scan-number (first (string/split " " (slurp "/proc/self/stat")))))

(defn- mkdir-p [path]
  (var cur (if (string/has-prefix? "/" path) "" "."))
  (each seg (string/split "/" path)
    (unless (empty? seg)
      (set cur (string cur "/" seg))
      (unless (os/stat cur :mode) (os/mkdir cur)))))

(defn pid-file   [home] (string home "/kernel.pid"))
(defn state-file [home] (string home "/state.jdn"))
(defn log-file   [home] (string home "/kernel.log"))
(defn req-dir    [home] (string home "/requests"))
(defn done-dir   [home] (string home "/requests/done"))

(defn ensure-home
  "把家建出來（含 requests/、requests/done/），回傳絕對路徑。"
  [home]
  (mkdir-p home)
  (mkdir-p (done-dir home))     # 順便把 requests/ 一起建出來
  (os/realpath home))

(defn- spit-atomic
  "先寫 .tmp 再 rename，免得別人讀到寫到一半的檔。"
  [path content]
  (def tmp (string path ".tmp"))
  (spit tmp content)
  (os/rename tmp path))

(defn- truncate
  "太長就砍掉尾巴、補一個刪節號（state.jdn 不要被一個超長回傳值撐爆）。"
  [s n]
  (if (> (length s) n) (string (string/slice s 0 n) "…") s))

(defn- jdn
  "轉成 Janet 資料字面字串；轉不動（例如裡面有函式）就退成人看得懂的字串。"
  [v]
  (def [ok s] (protect (string/format "%j" v)))
  (if ok s (string/format "%j" (truncate (string/format "%q" v) 200))))

(defn- safe-val
  "確定這個值寫得進 %j 也讀得回來；不行就換成 %q 的字串。"
  [v]
  (def [ok _] (protect (parse (string/format "%j" v))))
  (if ok v (truncate (string/format "%q" v) 200)))

(defn- human
  "把一個結果印成人看得懂的一行：字串就是字串本身，別的走 %q。"
  [v] (truncate (if (string? v) v (string/format "%q" v)) 200))

(defn- stamp []
  (def d (os/date (os/time) true))
  (string/format "%02d:%02d:%02d" (d :hours) (d :minutes) (d :seconds)))

(defn- log
  "daemon 自己的一行紀錄，走 stderr（會被導進 kernel.log）。"
  [& xs]
  (eprint (stamp) " " (string ;(map string xs)))
  (protect (file/flush stderr)))

# ── 狀態檔 ────────────────────────────────────────────

(defn proc-summary
  "一個 proc 縮成寫得進檔案的樣子（:last 轉成字串、太長截到 200 字）。"
  [p]
  {:name (p :name)
   :dir (p :dir)
   :interval (p :interval)
   :paused (truthy? (p :paused))
   :runs (p :runs)
   :error (if (p :error) (truncate (string (p :error)) 200) nil)
   :last (if (nil? (p :last)) nil (truncate (string/format "%q" (p :last)) 200))})

(defn write-state [home k ctl]
  (spit-atomic (state-file home)
               (jdn {:pid (self-pid)
                     :steps (k :steps)
                     :interval (ctl :interval)
                     :updated (os/time)
                     :procs (map proc-summary (kernel/ls k))})))

(defn read-state
  "讀 state.jdn；沒有或讀壞了就回 nil。"
  [home]
  (def f (state-file home))
  (if (os/stat f :mode)
    (let [[ok v] (protect (parse (slurp f)))] (if ok v nil))
    nil))

(defn read-pid
  "讀 kernel.pid；沒有就 nil。（有這個檔不代表活著，要再看 /proc。）"
  [home]
  (def f (pid-file home))
  (if (os/stat f :mode)
    (let [[ok v] (protect (scan-number (string/trim (slurp f))))]
      (if (and ok (number? v)) v nil))
    nil))

(defn- proc-state
  "/proc/<pid>/stat 的第三欄——進程狀態（R 跑／S 睡／Z 殭屍…）；沒這個進程就 nil。
   第二欄 comm 是用括號包起來的、裡面可能有空白，所以從最後一個 ) 之後才開始拆。"
  [pid]
  (def f (string "/proc/" pid "/stat"))
  (unless (os/stat f :mode) (break nil))
  (def [ok raw] (protect (slurp f)))
  (unless ok (break nil))
  (def s (string raw))
  (if-let [i (last (string/find-all ")" s))]
    (first (string/split " " (string/trim (string/slice s (+ i 1)))))
    nil))

(defn alive?
  "daemon 還在嗎：pid 檔在、/proc/<pid> 也在，而且不是殭屍。
   （被 kill -9 砍掉但爸爸還沒收屍的話，/proc/<pid> 這個資料夾還在，只看資料夾會誤判成活著。）"
  [home]
  (if-let [pid (read-pid home)
           st (proc-state pid)]
    (not= st "Z")
    false))

# ── 請求 ──────────────────────────────────────────────

(defn- make-req-env
  "請求跑起來的環境：一個完整的 Janet 環境，外加幾個已經把 kernel／ctl 綁好的函式。"
  [k ctl]
  (def env (make-env root-env))
  (defn bind [name f] (put env name @{:value f}))
  (bind 'register    (fn [dir &opt name interval]
                       (proc-summary (kernel/register k dir name interval))))
  (bind 'unregister  (fn [name] (if-let [p (kernel/unregister k name)] (proc-summary p) nil)))
  (bind 'pause       (fn [name] (if-let [p (kernel/pause k name)] (proc-summary p) nil)))
  (bind 'resume      (fn [name] (if-let [p (kernel/resume k name)] (proc-summary p) nil)))
  (bind 'ls          (fn [] (map proc-summary (kernel/ls k))))
  (bind 'steps       (fn [] (k :steps)))
  (bind 'stop        (fn [] (put ctl :stop true) :stopping))
  (bind 'set-interval (fn [sec] (put ctl :interval sec) sec))
  env)

(defn- handle-one
  "跑一個請求檔：eval 內容 → 寫 done/<同名> → 刪原檔。"
  [home name env]
  (def src-path (string (req-dir home) "/" name))
  (def [got raw] (protect (slurp src-path)))
  (def src (if got (string raw) ""))          # slurp 給的是 buffer，轉成字串才寫得回 %j 也比得起來
  (def [ok res] (if got (protect (eval-string src env)) [false (string "讀不到請求檔：" raw)]))
  (def rec {:req src :ok (truthy? ok) :result (if ok (safe-val res) (string res))})
  (spit-atomic (string (done-dir home) "/" name) (jdn rec))
  (when (os/stat src-path :mode) (os/rm src-path))
  (log "請求 " name (if ok " ok " " 失敗 ") (human (rec :result)))
  rec)

(defn- handle-requests
  "把 requests/ 裡所有 .req 照檔名排序處理掉（檔名開頭是毫秒時間戳，排序＝先來先做）。
   單一個請求炸了只記一行，繼續做下一個；但整個 requests/ 不見了（家被刪了）就讓它往外炸——
   家都沒了，daemon 就該死，不要在那邊空轉。"
  [home env]
  (def names (sorted (filter |(string/has-suffix? ".req" $) (os/dir (req-dir home)))))
  (each nm names
    (def [ok err] (protect (handle-one home nm env)))
    (unless ok (log "請求 " nm " 處理時自己炸了：" err))))

# ── 常駐迴圈 ──────────────────────────────────────────

(defn serve
  "前景常駐：每格＝處理完 requests/ → kernel/step → 寫 state.jdn → 睡 interval 秒。
   收到 (stop) 請求或 SIGTERM，就把這格跑完才結束；結束時刪掉 kernel.pid。"
  [home0 &opt interval]
  (def home (ensure-home home0))
  (def ctl @{:stop false :interval (or interval 1)})
  (def k (kernel/new))
  (def env (make-req-env k ctl))
  (spit (pid-file home) (string (self-pid)))
  # SIGTERM：把旗子插起來，這格跑完就走（第三個參數 true＝可以打斷 os/sleep）
  (protect (os/sigaction :term (fn [& _] (put ctl :stop true)) true))
  (log "daemon 起來了 pid=" (self-pid) " home=" home " interval=" (ctl :interval))
  (defer (when (os/stat (pid-file home) :mode) (os/rm (pid-file home)))
    (forever
      (handle-requests home env)
      (protect (kernel/step k))
      (protect (write-state home k ctl))
      (when (ctl :stop) (break))
      (protect (os/sleep (ctl :interval)))))
  (log "daemon 收工，走了 " (k :steps) " 格")
  (k :steps))

(defn start
  "背景開一個 daemon。已經活著就說一聲回 false；
   否則 os/spawn 一個 detach 的 janet 進程（:pd＝走 PATH ＋ detach，關掉母進程也活著），
   stdout／stderr 都導進 kernel.log，等到 pid 檔活著、state.jdn 也寫出第一格才回 true（最多 5 秒）。"
  [home0 &opt interval]
  (def home (ensure-home home0))
  (def iv (or interval 1))
  (if (alive? home)
    (do (print "已經在跑（pid " (read-pid home) "）") false)
    (do
      # 上次沒收乾淨留下的 pid 檔（進程早死了），清掉
      (when (os/stat (pid-file home) :mode) (os/rm (pid-file home)))
      (def logf (file/open (log-file home) :a))
      (def pr (os/spawn ["janet" this-file "run" home "--interval" (string iv)]
                        :pd {:out logf :err logf}))
      (:close logf)
      (def child (pr :pid))
      (var up false)
      (var waited 0)
      (while (and (not up) (< waited 5))
        (os/sleep 0.05)
        (+= waited 0.05)
        (def st (read-state home))
        # 認新的那個：state.jdn 裡的 pid 要是剛開的這隻，而且第一格已經跑完
        (when (and (alive? home) st (= (st :pid) child) (>= (or (st :steps) 0) 1))
          (set up true)))
      (if up
        (do (print "起來了（pid " child "，每 " iv " 秒一格）") true)
        (do (print "起不來，看 " (log-file home)) false)))))

(defn request
  "丟一個請求檔（先寫 .tmp 再 rename，免得 daemon 讀到半個）。
   wait（預設 true）＝等 done/ 冒出同名檔（最多 5 秒），回讀成 Janet 資料；
   daemon 沒活著就不等，請求先放著。"
  [home0 form-string &opt wait]
  (default wait true)
  (def home (ensure-home home0))
  # 檔名＝毫秒時間戳（13 位，字串排序就是時間排序）＋ 丟的人的 pid ＋ 流水號，撞不到
  (++ req-seq)
  (def nm (string (string/format "%013d" (math/floor (* 1000 (os/clock :realtime))))
                  "-" (self-pid) "-" (string/format "%04d" (% req-seq 10000))
                  ".req"))
  (def path (string (req-dir home) "/" nm))
  (spit (string path ".tmp") form-string)     # .tmp 結尾，daemon 只挑 .req，不會讀到半個
  (os/rename (string path ".tmp") path)
  (cond
    (not (alive? home))
    (do (print "daemon 沒在跑，請求先放著：" nm) nil)

    (not wait)
    (do (print "送出：" nm) nil)

    (do
      (def done (string (done-dir home) "/" nm))
      (var waited 0)
      (while (and (not (os/stat done :mode)) (< waited 5))
        (os/sleep 0.05)
        (+= waited 0.05))
      (if (os/stat done :mode)
        (let [[ok v] (protect (parse (slurp done)))]
          (if ok v (do (print "done 檔讀不動：" v) nil)))
        (do (print "等了 5 秒沒回音：" nm) nil)))))

(defn stop
  "先丟 (stop) 請求讓它跑完這格自己走（等 3 秒），還活著就 kill：先 TERM 再 KILL。"
  [home0]
  (def home (ensure-home home0))
  (unless (alive? home)
    (when (os/stat (pid-file home) :mode) (os/rm (pid-file home)))
    (print "沒在跑")
    (break false))
  (def pid (read-pid home))
  (request home "(stop)" false)
  (var waited 0)
  (while (and (alive? home) (< waited 3)) (os/sleep 0.1) (+= waited 0.1))
  (when (alive? home)
    (os/execute ["kill" "-TERM" (string pid)] :p)
    (set waited 0)
    (while (and (alive? home) (< waited 2)) (os/sleep 0.1) (+= waited 0.1)))
  (when (alive? home)
    (os/execute ["kill" "-KILL" (string pid)] :p)
    (os/sleep 0.2)
    (when (os/stat (pid-file home) :mode) (os/rm (pid-file home))))   # 被 KILL 的來不及自己清
  (print "收工了（pid " pid "）")
  true)

(defn ls
  "讀 state.jdn 印出來：第一行是 kernel 自己，後面一行一個 proc。daemon 沒在跑也看得到。"
  [home0]
  (def home (ensure-home home0))
  (def st (read-state home))
  (def on (alive? home))
  (print "kernel  " (if on "alive" "dead")
         "  pid=" (or (read-pid home) "-")
         "  steps=" (if st (st :steps) "-")
         "  interval=" (if st (st :interval) "-")
         "  home=" home)
  (if (or (nil? st) (empty? (or (st :procs) [])))
    (print "  （沒有登記任何資料夾）")
    (each p (st :procs)
      (print "  " (p :name)
             "  " (p :dir)
             "  每 " (p :interval) " 格"
             (if (p :paused) "  [暫停]" "")
             "  runs=" (p :runs)
             (if (p :error) (string "  error=" (p :error)) "")))))

# 背景進程是這樣被叫起來的：janet src/daemon.janet run <home> --interval N
(defn main [& argv]
  (def args (drop 1 argv))
  (unless (= (first args) "run")
    (eprint "這個檔平常給 aos-daemon.janet 用；直接跑只認：janet src/daemon.janet run <home> [--interval N]")
    (os/exit 2))
  (var home nil)
  (var interval 1)
  (var i 1)
  (while (< i (length args))
    (def a (args i))
    (cond
      (= a "--interval") (do (++ i) (set interval (scan-number (args i))))
      (set home a))
    (++ i))
  (unless home (eprint "run 要給 home") (os/exit 2))
  (serve home interval))
