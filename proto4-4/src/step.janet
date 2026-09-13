# 一次只跑一個 Janet 頂層 form，把環境存進 PROG 旁的 .aos-step/。

(defn- dirname [path]
  (def cuts (string/find-all "/" path))
  (if (= 0 (last cuts)) "/" (string/slice path 0 (last cuts))))

(def- source-file
  (or (os/realpath (dyn :current-file))
      (error "aos-step: 無法定位 src/step.janet")))
(def- aos-file (string (dirname source-file) "/aos.janet"))

(defn- path [state name] (string state "/" name))
(defn- exists? [p] (not (nil? (os/stat p :mode))))

(defn- rm-tree [p]
  (case (os/stat p :mode)
    :directory (do (each name (os/dir p)
                     (rm-tree (string p "/" name)))
                   (os/rmdir p))
    nil nil
    (os/rm p)))

(defn- atomic-spit [p contents]
  (def tmp (string p ".tmp." (os/getpid)))
  (spit tmp contents)
  (os/rename tmp p))

(defn- parse-forms [prog]
  (def parser (parser/new))
  (parser/consume parser (slurp prog))
  (parser/eof parser)
  (when-let [message (parser/error parser)]
    (error message))
  (def forms @[])
  (var wrapped (parser/produce parser true))
  (while wrapped
    (array/push forms (wrapped 0))
    (set wrapped (parser/produce parser true)))
  forms)

(defn- source-checksum [source]
  # Janet 的 hash 每個行程會換 seed；這裡要的是可跨行程比對的內容指紋。
  (var a 1)
  (var b 0)
  (each byte source
    (set a (mod (+ a byte) 65521))
    (set b (mod (+ b a) 65521)))
  (string b "-" a))

(defn- source-id [prog forms]
  # Janet 沒有內建 sha256；照 fallback 存 bytes 與 mtime，再加內容 checksum。
  (def info (os/stat prog))
  (def source (slurp prog))
  {:n (length forms) :bytes (info :size) :mtime (info :modified)
   :checksum (source-checksum source)})

(defn- read-src [state]
  (def p (path state "src"))
  (if (exists? p) (parse (slurp p)) nil))

(defn- read-state [state]
  (def p (path state "state"))
  (if (exists? p)
    (let [value (parse (slurp p))]
      (unless (table? value) (error "state 壞了：必須是 table")) value)
    @{}))

(defn- write-state [state value]
  (atomic-spit (path state "state") (string/format "%q\n" value)))

(defn- now [] (string (os/strftime "%Y-%m-%dT%H:%M:%S" (os/time) false) "+00:00"))

(defn- absolute-path [given here]
  (unless (string? given) (error "aos/wait-for: path 必須是字串"))
  (def raw (if (string/has-prefix? "/" given) given (string here "/" given)))
  (def parts @[])
  (each part (string/split "/" raw)
    (cond (or (= "" part) (= "." part)) nil
          (= ".." part) (array/pop parts)
          (array/push parts part)))
  (string "/" (string/join parts "/")))

(defn- trim-history [history]
  (while (> (length history) 50) (array/remove history 0)) history)

(defn- waiting-line [waiting]
  (unless (and (dictionary? waiting)
               (string? (waiting :for)) (string/has-prefix? "/" (waiting :for))
               (string? (waiting :since))
               (number? (waiting :after_pc)) (>= (waiting :after_pc) 0)
               (number? (waiting :checks)) (>= (waiting :checks) 0))
    (error "state 壞了：waiting 欄位不合法"))
  (string "在等 " (waiting :for) "（已看 " (waiting :checks) " 次，從 " (waiting :since) " 起）"))

(defn- check-waiting [state saved]
  (if-let [waiting (saved :waiting)]
    (do
      (waiting-line waiting)
      (if (not (exists? (waiting :for)))
        (do (put waiting :checks (inc (waiting :checks)))
            (put saved :waiting waiting) (write-state state saved) true)
        (do
          (var history (or (saved :history) @[]))
          (unless (array? history) (set history @[]))
          (array/push history @{:pc (waiting :after_pc) :step "(wait)" :exit 0
                                :waited_checks (waiting :checks) :at (now) :ms 0})
          (put saved :history (trim-history history))
          (put saved :waiting nil)
          (write-state state saved)
          false)))
    false))

(defn- source-changed? [state pc current]
  (def old (read-src state))
  (and (> pc 0) old (not (= old current))))

(defn- write-src [state src]
  (atomic-spit (path state "src") (string/format "%q\n" src)))

(defn- read-pc [state]
  (def p (path state "pc"))
  (if (not (exists? p))
    0
    (let [text (string/trim (slurp p))
          value (scan-number text)]
      (unless (and value (number? value) (= value (math/floor value)) (>= value 0))
        (error (string "pc 壞了：" text)))
      value)))

(defn- error-text [state]
  (def p (path state "error"))
  (if (exists? p) (string (slurp p)) nil))

(defn- trace-text [fib err]
  (def out @"")
  (with-dyns [*err* out]
    (debug/stacktrace fib err ""))
  (string/trim out))

(defn- write-error [state pc err trace]
  (os/mkdir state)
  (atomic-spit (path state "error")
               (string "form " pc "\n"
                       (describe err) "\n"
                       trace "\n")))

(defn- fail [state pc err &opt fib]
  (def trace (if fib (trace-text fib err) (describe err)))
  (write-error state pc err trace)
  (def first-line ((string/split "\n" (describe err)) 0))
  (eprintf "aos-step: 第 %d 個 form（0 起算）失敗：%s（全文：.aos-step/error 或 --status）"
           pc first-line)
  1)

(defn- bind-runtime [env here pc]
  # 絕對路徑用 require 載入，再把公開名字每次重綁進持久 env。
  (def module (require aos-file))
  # 函式庫每個公開名字都綁（不寫死清單：新加的 aos/llm 之類才不會漏）。
  (eachp [name entry] module
    (when (and (symbol? name) (table? entry) (not (entry :private)) (has-key? entry :value))
      (eval ~(def ,(symbol (string "aos/" name)) (quote ,(entry :value))) env)))
  # env 裡的綁定有編譯器用的描述層，不能只用 put 塞裸值。
  (eval ~(def here ,here) env)
  (eval ~(def pc ,pc) env)
  env)

(defn- load-env [state]
  (def p (path state "env.img"))
  (if (exists? p) (load-image (slurp p)) (make-env)))

(defn- step [prog here state]
  (label finish
  (var pc 0)
  (def got-pc (fiber/new (fn [] (read-pc state)) :e))
  (set pc (resume got-pc))
  (when (= :error (fiber/status got-pc))
    (return finish (fail state 0 (fiber/last-value got-pc) got-pc)))
  (def state-read (protect (read-state state)))
  (unless (state-read 0)
    (return finish (fail state pc (state-read 1))))
  (def saved (state-read 1))
  (def checked (protect (check-waiting state saved)))
  (unless (checked 0)
    (return finish (fail state pc (checked 1))))
  (when (checked 1) (return finish 0))
  (def parsed (fiber/new (fn [] (parse-forms prog)) :e))
  (def forms (resume parsed))
  (when (= :error (fiber/status parsed))
    (return finish (fail state pc (fiber/last-value parsed) parsed)))
  (def src (source-id prog forms))
  (def old-src (read-src state))
  (when (and (> pc 0) old-src (not (= old-src src)))
    (eprintf "aos-step: prog.janet 改過了（上次 %d 個 form、現在 %d 個），pc=%d 可能已經錯位；確定要重來就 --reset"
             (old-src :n) (src :n) pc))
  (when (>= pc (length forms))
    (os/mkdir state)
    (spit (path state "done") "")
    (write-src state src)
    (return finish 100))
  (when (exists? (path state "done"))
    (os/rm (path state "done")))
  (def prepared (fiber/new
                  (fn []
                    (def env (bind-runtime (load-env state) here pc))
                    (def value (eval (forms pc) env))
                    # image 存不下也算這一步失敗，pc 和舊 image 都不動。
                    [value (make-image env)])
                  :e))
  (def result (resume prepared))
  (when (= :error (fiber/status prepared))
    (return finish (fail state pc (fiber/last-value prepared) prepared)))
  (def [value image] result)
  (def item @{:pc pc :step (string/format "%q" (forms pc)) :exit 0
              :at (now) :ms 0})
  (var history (or (saved :history) @[]))
  (unless (array? history) (set history @[]))
  (array/push history item)
  (put saved :last item)
  (put saved :history (trim-history history))
  (when (and (dictionary? value) (has-key? value :aos/wait-for))
    (put saved :waiting @{:for (absolute-path (value :aos/wait-for) here)
                          :since (now) :after_pc pc :checks 0}))
  (os/mkdir state)
  (atomic-spit (path state "env.img") image)
  (atomic-spit (path state "pc") (string (inc pc) "\n"))
  (write-src state src)
  (write-state state saved)
  (when (exists? (path state "error"))
    (os/rm (path state "error")))
  (if (and (= (inc pc) (length forms)) (nil? (saved :waiting)))
    (spit (path state "done") "")
    (when (exists? (path state "done")) (os/rm (path state "done"))))
  (printf "%q" value)
  0))

(defn- status [prog state]
  (var n 0)
  (var parse-error nil)
  (def parsed (fiber/new (fn [] (parse-forms prog)) :e))
  (def forms (resume parsed))
  (if (= :error (fiber/status parsed))
    (set parse-error (describe (fiber/last-value parsed)))
    (set n (length forms)))
  (var pc 0)
  (def read (protect (read-pc state)))
  (if (read 0) (set pc (read 1)) (set parse-error (describe (read 1))))
  (def state-read (protect (read-state state)))
  (def saved (if (state-read 0) (state-read 1) @{}))
  (unless (state-read 0) (set parse-error (describe (state-read 1))))
  (when-let [waiting (saved :waiting)]
    (def line (protect (waiting-line waiting)))
    (if (line 0)
      (eprint (line 1))
      (set parse-error (describe (line 1)))))
  (def err (or parse-error (error-text state)))
  (def changed
    (if parse-error
      false
      (source-changed? state pc (source-id prog forms))))
  # table/struct 不會保留 nil value，所以手寫最外層，確保 :error nil 也真的印出來。
  (printf "{:pc %d :n %d :done %s :changed %s :error %s :last %q :history %q :waiting %q}"
          pc n
          (if (exists? (path state "done")) "true" "false")
          (if changed "true" "false")
          (if err (string/format "%q" err) "nil")
          (saved :last) (or (saved :history) @[]) (saved :waiting))
  0)

(defn- usage []
  (eprint "用法：aos-step PROG.janet [--status|--reset]")
  2)

(defn main [& argv]
  (def args (drop 1 argv))
  (when (< (length args) 1)
    (os/exit (usage)))
  (def given (args 0))
  (var flag nil)
  (var i 1)
  (while (< i (length args))
    (def arg (args i))
    (case arg
      "--status"
        (if flag
          (os/exit (usage))
          (set flag arg))
      "--reset"
        (if flag
          (os/exit (usage))
          (set flag arg))
      "--done-exit"
        (do
          (eprint "aos-step: --done-exit 已拿掉；這個號碼由 kernel 的 config.json 說了算")
          (os/exit 2))
      (os/exit (usage)))
    (++ i))
  (def tried (protect (os/realpath given)))
  (def prog (if (tried 0) (tried 1) nil))
  (unless (and prog (= :file (os/stat prog :mode)))
    (eprintf "aos-step: 找不到程式：%s" given)
    (os/exit 2))
  (def here (dirname prog))
  (def state (string here "/.aos-step"))
  (def code
    (case flag
      "--reset" (do (rm-tree state) 0)
      "--status" (status prog state)
      (step prog here state)))
  (os/exit code))
