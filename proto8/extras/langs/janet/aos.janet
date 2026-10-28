# aos - 用 Janet 描述一支 aos 程式（資料夾＝程式），(emit 程式 輸出資料夾) 把它寫成資料夾＋JSON＋腳本
#
# 兩種東西：
#   JSON 的值：Janet 的 struct／table／tuple／array／字串／數字…，寫成 JSON 檔（obj 建的物件照寫的順序）
#   檔案節點：(dir …)、(text …)、(script …)、(sh …)、(copy …)，寫成資料夾或一般檔
# JSON 的值裡面放了檔案節點（例：fsm 某格的 exec 寫成 (dir …)）＝那格長成旁邊的子資料夾，exec 換成它的名字。

(import ./json_write :as jw)
(import ./code_write :as cw)

(defn fail [code reason] (error (string code " " reason)))

(def null "JSON 的 null（Janet 的 table 存不了 nil；obj 裡寫 nil＝那個 key 不寫）" :json/null)

# ---- JSON 的值 ----

(defn obj
  "照寫的順序建一個 JSON 物件：(obj \"argv\" [...] \"cwd\" \"x\")；值是 nil＝不寫那個 key。"
  [& kvs]
  (when (odd? (length kvs)) (fail "ArgumentsBad" "obj 要一對一對寫 key 與值"))
  (def t @{})
  (def ks @[])
  (each [k v] (partition 2 kvs)
    (def s (jw/key-str k))
    (when (has-key? t s) (fail "KeyTwice" (string "同一個物件寫了兩次 " s)))
    (unless (nil? v) (array/push ks s) (put t s v)))
  (table/setproto t @{:aos/keys ks}))

(defn env "指示詞 {\"$env\": 名, \"$path\": 接在後面的字串}" [name &opt path] (obj "$env" name "$path" path))
(defn ref "指示詞 {\"$ref\": \"檔#/指標\"}（也可以給陣列）" [target] (obj "$ref" target))
(defn inst "單子 {\"argv\": [...], 其他 key...}" [argv & kvs] (obj "argv" argv ;kvs))
(defn self-entry "JSON 自己的入口：[程式, {\"$env\": \"AOS_CF\"}]（aos-exec 這份檔＝用程式跑它）" [prog] [prog (env "AOS_CF")])
(defn aos-loop "loop.json：{\"exec\": 目標或單子, \"max\": …}" [exec & kvs] (obj "exec" exec ;kvs))

(defn fsm-table
  "fsm.json：states 是 [[名 exec 下一個] …]，start 沒給＝第一格；entry 給了就放 _entry。"
  [states &named start entry]
  (when (empty? states) (fail "ArgumentsBad" "fsm 至少要一格"))
  (obj "_entry" entry
       "start" (or start ((first states) 0))
       "states" (obj ;(mapcat (fn [[n e nx]] [n (obj "exec" e "next" nx)]) states))))

(defmacro aos-fsm
  "(aos-fsm [:start 名] [:entry 值] (名 exec -> 下一個) …)；名字寫 symbol，-> 可省。"
  [& forms]
  (var i 0)
  (def opts @[])
  (while (keyword? (get forms i))
    (def k (forms i))
    (def v (get forms (+ i 1)))
    (array/push opts k (if (= k :start) (string v) v))
    (+= i 2))
  (def states
    (map (fn [f]
           (def f (filter |(not= $ '->) f))
           (unless (= 3 (length f)) (error (string "ArgumentsBad fsm 的一格要寫 (名 exec -> 下一個)：" (describe f))))
           ~[,(string (f 0)) ,(f 1) ,(string (f 2))])
         (slice forms i)))
  ~(,fsm-table [,;states] ,;opts))

# ---- 檔案節點 ----

(def- Node @{})
(defn- node [& kvs] (table/setproto (table ;kvs) Node))
(defn node? [x] (and (table? x) (= (table/getproto x) Node)))

(defn- name-ok [name]
  (unless (and (bytes? name) (not (empty? name)) (not (string/find "/" name)) (not= name ".") (not= name ".."))
    (fail "NameBad" (string "檔名不能是空的、. 、.. 或帶 /：" (describe name))))
  (string name))

(defn dir
  "資料夾：(dir 名 內容 名 內容 …)；內容是檔案節點或 JSON 的值（寫成 JSON 檔）。"
  [& kvs]
  (when (odd? (length kvs)) (fail "ArgumentsBad" "dir 要一對一對寫名字與內容"))
  (def items (map (fn [[n x]] [(name-ok n) x]) (partition 2 kvs)))
  (def seen @{})
  (each [n _] items (when (seen n) (fail "NameTaken" (string "同一層有兩個 " n))) (put seen n true))
  (node :kind :dir :items items))

(defn text "一般文字檔" [s] (node :kind :text :text s :mode 8r644))
(defn script "可執行檔（內容自己帶 #!）" [s] (node :kind :text :text s :mode 8r755))
(defn sh "shell 腳本：#!/bin/sh 加上每一行" [& lines] (script (string "#!/bin/sh\n" (string/join lines "\n") "\n")))

(defn- here []
  (def f (or (dyn :current-file) "."))
  (def d (if-let [i (last (string/find-all "/" f))] (slice f 0 i) "."))
  (if (string/has-prefix? "/" d) d (string (os/cwd) "/" d)))

(defn copy
  "照抄一個檔（相對路徑從寫這行的 .janet 檔所在的資料夾算），權限照原檔。"
  [path]
  (def src (if (string/has-prefix? "/" path) path (string (here) "/" path)))
  (unless (= :file (os/stat src :mode)) (fail "SourceMissing" (string "找不到要抄的檔 " src)))
  (node :kind :text :text (slurp src) :mode (band (os/stat src :int-permissions) 8r777)))

(defn dotenv
  "`.env` 檔：每個參數是一行；字串照抄（註解），[名 值] 寫成 名=值（值不能有空白、# 、引號、$）。"
  [& lines]
  (text (string
          (string/join
           (map (fn [l]
                 (if (bytes? l) l
                   (let [[k v] l]
                     (when (peg/find '(set " \t\n#'\"$\\") v) (fail "ValueBad" (string ".env 的值要加引號，這裡不支援：" k)))
                     (string k "=" v))))
                lines)
           "\n")
          "\n")))

(defn tool
  "agent 的工具：資料夾裡 _tooldef.json（給模型看）＋ _entry。"
  [&named description parameters entry]
  (dir "_tooldef.json" (obj "description" description "parameters" (or parameters {:type "object" :properties {}}))
       "_entry" entry))

(defmacro janet-main
  "用 Janet 寫的葉子程式：(janet-main [_ & args] 程式…) → #!/usr/bin/env janet 的可執行檔，內容是 (defn main …)。"
  [params & body]
  ~(,script ,(string "#!/usr/bin/env janet\n" (cw/top (tuple 'defn 'main params ;body)) "\n")))
