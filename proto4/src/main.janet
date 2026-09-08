# aos-kernel 命令列：把幾個資料夾登記進時鐘，然後一格一格跑。
#
#   janet src/main.janet DIR... [--steps N] [--interval SEC]
#
# DIR 的寫法（三段，中間兩段可省）：  [名字=]資料夾[:間隔]
#   ./work                 名字＝work、每格都跑
#   ./work:3               每 3 格才跑一次
#   w=./some/long/path     自己取名叫 w
#   w=./work:2             都指定
# --steps N     跑幾格（不給就一直跑到 Ctrl-C）
# --interval S  每格之間睡幾秒（預設 0＝能跑多快跑多快）
# 跑完印每個 proc 的 name／runs／error。

(import ./kernel)

(defn- digits? [s]
  (and (not (empty? s)) (all |(and (>= $ (chr "0")) (<= $ (chr "9"))) s)))

(defn parse-spec
  "把 [名字=]資料夾[:間隔] 拆成 [dir name interval]（沒寫的就是 nil）。
   間隔只認最後面那段純數字，所以 C:\\ 這種怪路徑不會被誤拆。"
  [s]
  (var name nil)
  (var dir s)
  (var interval nil)
  (when-let [i (string/find "=" dir)]
    (set name (string/slice dir 0 i))
    (set dir (string/slice dir (+ i 1))))
  (when-let [i (last (string/find-all ":" dir))]
    (def tail (string/slice dir (+ i 1)))
    (when (digits? tail)
      (set interval (scan-number tail))
      (set dir (string/slice dir 0 i))))
  [dir name interval])

(defn main [& argv]
  (def args (drop 1 argv))          # 第一個是程式名字
  (def specs @[])
  (var steps nil)
  (var interval 0)
  (var i 0)
  (while (< i (length args))
    (def a (args i))
    (cond
      (= a "--steps")    (do (++ i) (set steps (scan-number (args i))))
      (= a "--interval") (do (++ i) (set interval (scan-number (args i))))
      (array/push specs a))
    (++ i))
  (when (empty? specs)
    (eprint "用法：janet src/main.janet [名字=]資料夾[:間隔] ... [--steps N] [--interval SEC]")
    (os/exit 1))

  (def K (kernel/new))
  (each s specs
    (def [dir name interval] (parse-spec s))
    (def p (kernel/register K dir name interval))
    (print "登記 " (p :name) " → " (p :dir) "（每 " (p :interval) " 格）"))

  (kernel/run K steps interval)

  (print "\n跑了 " (K :steps) " 格：")
  (each p (kernel/ls K)
    (print "  " (p :name) "  runs=" (p :runs)
           (if (p :error) (string "  error=" (p :error)) ""))))
