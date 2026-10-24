# json_write - 把 Janet 的值寫成好讀的 JSON 字串（key 有固定順序、中文不跳脫、短的擠一行）
#
# 物件的 key 順序：用 (obj ...) 建的照寫的順序；一般 struct／table 照 key-order 再照字母。
# keyword、symbol 寫成字串（照字面，不換 - 與 _）。

(def key-order
  "一般 struct／table 的 key 先照這張表排（aos 常見的 key），表上沒有的照字母排在後面。"
  ["_entry" "$env" "$ref" "$path" "$prefix"
   "argv" "cwd" "envs" "stdin" "stdout" "stderr" "stdout_append" "stderr_append" "timeout_ms" "grace_ms"
   "exec" "max" "interval_ms" "ctl" "state" "start" "states" "next"
   "description" "type" "properties" "required" "parameters"])

(def width "一行塞得下就擠一行的寬度（以位元組算，中文一字三位元組）" 100)

(def- order-rank (tabseq [[i k] :pairs key-order] k i))

(defn key-str [k]
  (case (type k)
    :string k :buffer (string k) :keyword (string k) :symbol (string k)
    (error (string "KeyBad JSON 物件的 key 只能是字串、keyword 或 symbol：" (describe k)))))

(defn ordered-keys
  "物件的 key（字串）照順序：有 :aos/keys 原型就照它，否則照 key-order 再照字母。"
  [x]
  (def proto (when (table? x) (table/getproto x)))
  (if (and proto (proto :aos/keys))
    (map key-str (proto :aos/keys))
    (sort (map key-str (keys x))
          (fn [a b]
            (def ra (get order-rank a 1e9))
            (def rb (get order-rank b 1e9))
            (if (= ra rb) (< a b) (< ra rb))))))

(defn obj-get [x k]
  "照字串 key 取值（建的時候可能用 keyword）。"
  (def v (get x k))
  (if (nil? v) (get x (keyword k)) v))

(defn esc [s]
  (def b @"\"")
  (each c s
    (case c
      34 (buffer/push b "\\\"") 92 (buffer/push b "\\\\")
      10 (buffer/push b "\\n") 13 (buffer/push b "\\r") 9 (buffer/push b "\\t")
      (if (< c 32) (buffer/push b (string/format "\\u%04x" c)) (buffer/push-byte b c))))
  (buffer/push b "\"")
  (string b))

(defn num [x]
  (cond
    (or (nan? x) (= x math/inf) (= x (- math/inf))) (error "NumberBad JSON 不收 NaN／無限大")
    (and (= x (math/floor x)) (< (math/abs x) 9007199254740992)) (string/format "%d" x)
    (string/format "%.17g" x)))

(defn json-object? [x] (or (struct? x) (table? x)))

(defn one-line [x]
  (cond
    (nil? x) "null"
    (= x :json/null) "null"
    (= x true) "true"
    (= x false) "false"
    (number? x) (num x)
    (bytes? x) (esc x)
    (indexed? x) (string "[" (string/join (map one-line x) ", ") "]")
    (json-object? x)
    (string "{" (string/join (map |(string (esc $) ": " (one-line (obj-get x $))) (ordered-keys x)) ", ") "}")
    (error (string "ValueBad 寫不成 JSON 的值：" (describe x)))))

(defn pretty
  "indent＝這個值所在那行的縮排；col＝這個值開頭的欄位（判斷擠不擠得下一行用）。"
  [x indent col]
  (def flat (one-line x))
  (if (or (<= (+ col (length flat)) width) (not (or (indexed? x) (json-object? x))) (empty? x))
    flat
    (let [in (+ indent 2)
          pad (string/repeat " " in)
          end (string "\n" (string/repeat " " indent))]
      (if (indexed? x)
        (string "[\n" (string/join (map |(string pad (pretty $ in in)) x) ",\n") end "]")
        (string "{\n"
                (string/join (map |(let [k (esc $)] (string pad k ": " (pretty (obj-get x $) in (+ in (length k) 2))))
                                  (ordered-keys x)) ",\n")
                end "}")))))

(defn write
  "Janet 的值 → JSON 字串（結尾不帶換行）。"
  [x]
  (pretty x 0 0))
