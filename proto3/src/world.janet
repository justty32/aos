# 世界＝一份 Janet 資料（table）。「跑世界」＝對它求值：走一遍元素，
# :func-tick 就叫它、:kids 裡借父時鐘的小孩跟著走一格。
# 這就是「list 當資料夾、執行資料夾＝對 list 求值」。

(def all @{})   # 檔案系統：path → 世界。path 就是身分（父 path + "/" + 名字）

(defn make
  "建一個世界。name 是名字，其餘 kvs 直接塞進去（例如 :func-tick）。"
  [name & kvs]
  (def w @{:name name :path name
           :kids @{} :inbox @[] :outbox @[]
           :ticks @{:busy 0 :wait 0 :idle 0 :frozen 0}   # 格的會計：這格在幹嘛
           :now 0})                                       # 自己走了幾格
  (each [k v] (partition 2 kvs) (put w k v))
  (put all (w :path) w)
  w)

(defn at "用 path 找世界，找不到回 nil。" [path] (get all path))

(defn- count-tick [w kind]
  (update (w :ticks) kind (fn [n] (inc (or n 0)))))

(defn dotick
  "對一個世界求值一格。回傳這格做了什麼：:busy／:wait／:idle／:frozen。"
  [w]
  (if (w :frozen)
    (do (count-tick w :frozen) :frozen)
    (do
      (update w :now inc)
      (var result :idle)
      (each key (keys w)               # 先拍快照：元素求值時可以改世界自己
        (case key
          :func-tick (set result (or ((w :func-tick) w) :busy))
          :kids (each kid (values (w :kids))
                  (when (= (kid :clock) :shared) (dotick kid)))))
      (count-tick w result)
      result)))

# ── 信箱：任何世界都能收信、說話 ────────────────────────────
(defn send
  "from 寄一封信到 to 的 inbox。信＝{:from 寄件人 path :body 內容 :at 收件人當時的格}。"
  [from to body]
  (def m @{:from (from :path) :body body :at (to :now)})
  (array/push (to :inbox) m)
  m)

(defn take-mail
  "把 inbox 全部拿走（拿走就算讀過）。給 pred 就只拿符合的那些。"
  [w &opt pred]
  (if (nil? pred)
    (do (def got (array/slice (w :inbox))) (array/clear (w :inbox)) got)
    (do
      (def got (filter pred (w :inbox)))
      (put w :inbox (filter (complement pred) (w :inbox)))
      got)))

(defn say
  "世界自己說一句話，記進 outbox。"
  [w body]
  (array/push (w :outbox) @{:at (w :now) :body body}))

# ── 小孩：資料夾裡的資料夾 ─────────────────────────────────
(defn spawn
  "在 parent 底下生一個小孩。:clock :shared（預設，借父的鐘、父走一格它走一格）
   或 :own（自己一個鐘，要另外向 kernel 登記）。"
  [parent name & kvs]
  (def kid (make name ;kvs))
  (put all (kid :path) nil)
  (put kid :path (string (parent :path) "/" name))
  (put kid :parent (parent :path))
  (when (nil? (kid :clock)) (put kid :clock :shared))
  (put (parent :kids) name kid)
  (put all (kid :path) kid)
  kid)

(defn kill
  "把小孩從父的 :kids 與檔案系統拿掉（它的小孩也一起消失）。"
  [kid]
  (def parent (at (kid :parent)))
  (when parent (put (parent :kids) (kid :name) nil))
  (each [path w] (pairs all)
    (when (string/has-prefix? (string (kid :path) "/") path) (put all path nil)))
  (put all (kid :path) nil))
