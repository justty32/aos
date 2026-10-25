# emit - 把 (dir …) 寫到磁碟：資料夾照建、JSON 的值寫成 JSON 檔、文字檔照權限寫
#
# 長大成資料夾：JSON 的值裡面碰到檔案節點，就把它寫成同一層的子資料夾（或檔），原地換成它的名字。
# 名字取它所在的 key；key 是 "exec" 時取上一層的 key（fsm 的 states/idle/exec → idle/）。

(import ./aos)
(import ./json_write :as jw)

(defn- hoist-name [path]
  (def k (if (and (= (last path) "exec") (> (length path) 1)) (path (- (length path) 2)) (last path)))
  (unless (bytes? k) (aos/fail "HoistBad" (string "陣列裡的檔案節點不知道該叫什麼名字（位置 /" (string/join (map string path) "/") "）")))
  k)

(defn- rebuild [x f]
  "物件照原本的 key 順序重建，每個值交給 f。"
  (def ks (jw/ordered-keys x))
  (aos/obj ;(mapcat |[$ (f $ (jw/obj-get x $))] ks)))

(defn- write-file [path s mode]
  (when (= :directory (os/stat path :mode)) (aos/fail "OutBad" (string path " 是資料夾，不能寫成檔")))
  (spit path s)
  (os/chmod path mode))

(defn- make-dir [path]
  (case (os/stat path :mode)
    nil (os/mkdir path)
    :directory nil
    (aos/fail "OutBad" (string path " 已經是檔，不能建成資料夾"))))

(var- emit-node nil)

(defn- emit-dir [d out]
  (make-dir out)
  (def taken (tabseq [[n _] :in (d :items)] n true))
  (def grown @[])
  (defn grow [x path]
    (cond
      (aos/node? x)
      (let [n (hoist-name path)]
        (when (taken n) (aos/fail "NameTaken" (string out "/" n " 已經有東西，長不出這個子資料夾")))
        (put taken n true)
        (array/push grown [n x])
        n)
      (indexed? x) (map |(grow $1 [;path $0]) (range (length x)) x)
      (or (struct? x) (table? x)) (if (= x aos/null) x (rebuild x |(grow $1 [;path $0])))
      x))
  (each [n x] (d :items)
    (def p (string out "/" n))
    (if (aos/node? x)
      (emit-node x p)
      (write-file p (string (jw/write (grow x @[])) "\n") 8r644)))
  (each [n x] grown (emit-node x (string out "/" n))))

(set emit-node
  (fn [x out]
    (case (x :kind)
      :dir (emit-dir x out)
      :text (write-file out (x :text) (x :mode)))))

(defn emit
  "把程式（一個 (dir …)）寫到 out。out 已經有東西＝OutExists，除非 force（只蓋這次要寫的檔，其他不刪）。"
  [prog out &opt force]
  (unless (and (aos/node? prog) (= (prog :kind) :dir)) (aos/fail "ProgramBad" "program 要是一個 (dir …)"))
  (case (os/stat out :mode)
    nil nil
    :directory (when (and (not force) (not (empty? (os/dir out))))
                 (aos/fail "OutExists" (string out " 裡面已經有東西（要蓋過去加 --force）")))
    (aos/fail "OutBad" (string out " 不是資料夾")))
  (emit-node prog out))
