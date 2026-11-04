# kernel：時鐘。登記一群資料夾，每走一格，該輪到的資料夾就 run-dir 一次。
# 資料夾自己的狀態存在它自己的檔案裡（inst 想留東西就自己 spit），kernel 不管。
# 先做同步版：step 走一格、run 連走 N 格。不做 fiber／async。

(import ./runf)

(defn new
  "開一個新的 kernel：@{:procs @{…} :steps 走了幾格}。procs 以 name 當 key。"
  []
  @{:procs @{} :steps 0})

(defn- iv-of
  "拿 proc 的間隔，保證至少 1（免得 % 除以 0）。"
  [p] (max 1 (or (p :interval) 1)))

(defn register
  "登記一個資料夾。name 預設＝dir 最後一段，interval 預設 1（每幾格跑一次）。
   同名重登記＝整個換掉舊的。回傳這個 proc。"
  [k dir &opt name interval]
  (def nm (or name (last (string/split "/" dir))))
  (def p @{:dir dir
           :name nm
           :interval (max 1 (or interval 1))   # 0 或負數當 1，顯示跟實際一致
           :paused false
           :runs 0        # 成功跑了幾次
           :last nil      # 上次的回傳值
           :error nil})   # 上次的錯誤訊息（成功一次就清掉）
  (put (k :procs) nm p)
  p)

(defn unregister
  "把一個 proc 從登記表拿掉。回傳被拿掉的那個（沒有就 nil）。"
  [k name]
  (def p (get (k :procs) name))
  (put (k :procs) name nil)
  p)

(defn pause
  "暫停：登記還在，但不跑。"
  [k name]
  (when-let [p (get (k :procs) name)] (put p :paused true) p))

(defn resume
  "解除暫停，繼續跑（跟 proto3 的 CL 版一樣叫 resume，不叫 continue）。"
  [k name]
  (when-let [p (get (k :procs) name)] (put p :paused false) p))

(defn ls
  "列所有 proc，照 name 排序（table 的順序不固定，一定要排過才穩）。"
  [k]
  (sorted-by |($ :name) (values (k :procs))))

(defn step
  "走一格：steps +1，然後照 name 排序，把沒暫停、又剛好輪到的資料夾各跑一次。
   跑法是 (run-dir dir steps)——inst 裡 (first args) 就是現在第幾格。
   inst 炸了只記在那個 proc 的 :error、印一行到 stderr，kernel 不停、別人照跑。
   回傳這格有跑到的 name 陣列（炸掉的也算跑到）。"
  [k]
  (update k :steps inc)
  (def now (k :steps))
  (def did @[])
  (each p (ls k)
    (when (and (not (p :paused)) (zero? (% now (iv-of p))))
      (array/push did (p :name))
      (def [ok res] (protect (runf/run-dir (p :dir) now)))
      (if ok
        (do (put p :last res)
            (put p :error nil)
            (update p :runs inc))
        (do (put p :error (string res))
            (eprint "kernel：第 " now " 格 " (p :name) " 炸了：" res)))))
  did)

(defn stop
  "叫 run 的迴圈下一格停下來（無限跑的時候用得到）。"
  [k]
  (put k :running false)
  k)

(defn run
  "同步連走 steps 格（nil＝一直走到有人 stop），每格之間睡 interval 秒（預設 0＝不睡）。
   回傳這次實際走了幾格。"
  [k &opt steps interval]
  (def nap (or interval 0))
  (put k :running true)
  (var n 0)
  (while (and (k :running) (or (nil? steps) (< n steps)))
    (step k)
    (++ n)
    (when (> nap 0) (os/sleep nap)))
  (put k :running false)
  n)
