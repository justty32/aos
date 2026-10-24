# code_write - 把 Janet 的程式碼（被引用的資料）印回 Janet 原始碼；字串裡的中文照原樣，不像 %j 會變成 \xE5…
#
# 只認讀進來的程式碼會出現的東西：tuple（() 與 []）、array、struct、table、字串、數字、keyword、symbol、nil、true、false。

(defn- esc [s]
  (def b @"\"")
  (each c s
    (case c
      34 (buffer/push b "\\\"") 92 (buffer/push b "\\\\")
      10 (buffer/push b "\\n") 13 (buffer/push b "\\r") 9 (buffer/push b "\\t")
      (if (< c 32) (buffer/push b (string/format "\\x%02X" c)) (buffer/push-byte b c))))
  (buffer/push b "\"")
  (string b))

(defn form
  "一個 form → 一行原始碼。"
  [x]
  (def items |(string/join (map form $) " "))
  (def pairs |(string/join (map (fn [[k v]] (string (form k) " " (form v))) (sort (pairs $))) " "))
  (case (type x)
    :tuple (if (= (tuple/type x) :brackets) (string "[" (items x) "]") (string "(" (items x) ")"))
    :array (string "@[" (items x) "]")
    :struct (string "{" (pairs x) "}")
    :table (string "@{" (pairs x) "}")
    :string (esc x)
    :buffer (string "@" (esc x))
    :keyword (string ":" x)
    :symbol (string x)
    :number (string/format "%j" x)
    :nil "nil"
    :boolean (if x "true" "false")
    (error (string "FormBad 印不回原始碼的東西：" (describe x)))))

(defn top
  "頂層的 (defn …)／(def …)：頭一行放到參數為止，後面每個 form 各一行、縮兩格。"
  [x]
  (if (and (tuple? x) (> (length x) 3) (index-of (x 0) ['defn 'defn-]))
    (string "(" (form (x 0)) " " (form (x 1)) " " (form (x 2))
            (string/join (map |(string "\n  " (form $)) (slice x 3)))
            ")")
    (form x)))
