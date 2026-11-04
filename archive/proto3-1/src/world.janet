# 世界＝一個 list（form）＋一個環境（folder）。
# 跑一格＝在那個環境裡 eval 那個 list；下一格要跑什麼，用 (next 新form) 寫回去。
# 環境就是資料夾：form 裡 (def x …) 存進去的東西，下一格還看得到——binding 就是檔案。

(def all @{})   # 檔案系統：path → 世界（環境）。path 就是身分（父 path + "/" + 名字）

(defn at "用 path 找世界，找不到回 nil。" [path] (get all path))

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

(defn say "世界自己說一句話，記進 outbox。" [w body]
  (array/push (w :outbox) @{:at (w :now) :body body}))

(defn set-next
  "換掉下一格要跑的 form。用 @[form] 裝箱，這樣 (next nil) 也分得出「有叫過」。"
  [w form] (put w :next @[form]))

# 前向參考：make 要把 spawn／kill 綁進世界的環境，可是它們得等 make 定義完才寫得出來。
(var- spawn-fn nil)
(var- kill-fn nil)

(defn- bind [env sym f] (put env sym @{:value f}))

(defn- install
  "把原語綁進世界自己的環境。eval 出來的碼拿不到外面的 env，只能像這樣用閉包綁進去。"
  [env]
  (bind env 'me env)                                         # 自己的環境
  (bind env 'now (fn [] (env :now)))
  (bind env 'next (fn [form] (set-next env form) nil))       # 蓋掉核心的 next，這裡它是「改寫自己」
  (bind env 'say (fn [body] (say env body)))
  (bind env 'send (fn [to-path body] (when-let [to (at to-path)] (send env to body))))
  (bind env 'mail (fn [&opt pred] (take-mail env pred)))
  (bind env 'kill (fn [path] (when-let [w (at path)] (kill-fn w))))
  (bind env 'kid
        (fn [name & rest]     # (kid "名" form) 借鐘；(kid "名" :own form) 自己一個鐘
          (def own? (= (first rest) :own))
          (or (get (env :kids) name)
              (spawn-fn env name (if own? (get rest 1) (first rest))
                        :clock (if own? :own :shared))))))

(defn make
  "建一個世界：form 是它現在要跑的 list，其餘 kvs 直接塞進環境（keyword 當鍵）。"
  [name form & kvs]
  (def env (make-env root-env))
  (put env :name name) (put env :path name) (put env :form form)
  (put env :now 0) (put env :inbox @[]) (put env :outbox @[]) (put env :kids @{})
  (put env :ticks @{:busy 0 :wait 0 :idle 0 :frozen 0})   # 格的會計：這格在幹嘛
  (each [k v] (partition 2 kvs) (put env k v))
  (install env)
  (put all (env :path) env)
  env)

(defn spawn
  "在 parent 底下生一個小孩。:clock :shared（預設，借父的鐘）或 :own（自己一個鐘，要另外登記）。"
  [parent name form & kvs]
  (def kid (make name form ;kvs))
  (put all (kid :path) nil)                       # make 用名字登記過了，換成 父/名字
  (put kid :path (string (parent :path) "/" name))
  (put kid :parent (parent :path))
  (when (nil? (kid :clock)) (put kid :clock :shared))
  (put (parent :kids) name kid)
  (put all (kid :path) kid)
  kid)

(defn kill
  "把小孩從父的 :kids 與檔案系統拿掉（它的子孫也一起消失）。"
  [kid]
  (when-let [parent (at (kid :parent))] (put (parent :kids) (kid :name) nil))
  (each [path _] (pairs all)
    (when (string/has-prefix? (string (kid :path) "/") path) (put all path nil)))
  (put all (kid :path) nil))

(defn dotick
  "對一個世界求值一格：eval 它的 form。回傳這格做了什麼：:busy／:wait／:idle／:frozen。"
  [w]
  (if (w :frozen)
    (do (update (w :ticks) :frozen inc) :frozen)
    (do
      (update w :now inc)
      (each kid (values (w :kids))            # 借鐘的小孩先跟著走一格
        (when (= (kid :clock) :shared) (dotick kid)))   # （這格才生的小孩，下一格才開始動）
      (def r (if (nil? (w :form)) :idle (eval (w :form) w)))
      (when-let [box (w :next)]               # 求值期間叫過 (next f) 就換 form
        (put w :form (box 0))
        (put w :next nil))
      (def kind (if (index-of r [:busy :wait :idle]) r :busy))   # 別的回傳值一律算 busy
      (update (w :ticks) kind inc)
      kind)))

(set spawn-fn spawn)
(set kill-fn kill)
