# kernel：管時鐘。一個世界一個鐘；鐘＝「每 interval 秒對那個世界求值一格」。
# 兩種走法：step-all（同步走一格，測試與手動用）、start（每個鐘一條 fiber 自己走）。

(import ./world :as world)

(def clocks @{})        # path → 鐘 @{:world :interval :status :ticks :fiber}
(var started false)     # start 過了沒；過了以後新登記的鐘要自己開 fiber
(var steps 0)           # 同步模式走了幾格（interval 在同步模式＝每幾格動一次）

(defn- run-clock [c]
  (while (not= (c :status) :stopped)
    (when (= (c :status) :running)
      (update c :ticks inc)
      (world/dotick (c :world)))
    (ev/sleep (c :interval))))

(defn register
  "替世界登記一個鐘。interval 秒走一格（預設 1）。同一個世界重複登記＝換掉舊鐘。"
  [w &opt interval]
  (def c @{:world w :interval (or interval 1) :status :running :ticks 0})
  (put clocks (w :path) c)
  (when started (put c :fiber (ev/spawn (run-clock c))))
  c)

(defn unregister [path]
  (when-let [c (clocks path)] (put c :status :stopped))
  (put clocks path nil))

(defn pause "鐘停著不走，但登記還在。" [path] (put (clocks path) :status :paused))
(defn continue "暫停的鐘再走。" [path] (put (clocks path) :status :running))
(defn stop-all [] (each path (keys clocks) (unregister path)))

(defn ls
  "列所有鐘：[path 狀態 走了幾格]。"
  []
  (seq [[path c] :pairs clocks] [path (c :status) (c :ticks)]))

(defn step-all
  "同步：每個在走的鐘各走一格（不睡；interval N 的鐘每 N 格才動）。回傳 {path → :busy/...}。"
  []
  (def did @{})
  (++ steps)
  (each [path c] (pairs clocks)
    (when (and (= (c :status) :running) (zero? (% steps (c :interval))))
      (update c :ticks inc)
      (put did path (world/dotick (c :world)))))
  did)

(defn run
  "同步走 steps 格，每格睡 interval 秒（steps 給 nil 就一直走）。"
  [&opt steps interval]
  (var n 0)
  (while (or (nil? steps) (< n steps))
    (step-all)
    (++ n)
    (when (and interval (> interval 0)) (ev/sleep interval))))

(defn start
  "非同步：每個鐘一條 fiber，各照自己的 interval 走。"
  []
  (set started true)
  (each c (values clocks)
    (when (nil? (c :fiber)) (put c :fiber (ev/spawn (run-clock c))))))
